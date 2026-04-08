from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import asyncio
import json
import hashlib
import secrets
import logging
import time
import paho.mqtt.client as mqtt

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Boolean, Column, DateTime, Integer, String, create_engine, func, select, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "device-service"
    database_url: str = Field(validation_alias="DATABASE_URL")
    mqtt_host: str = Field(default="mqtt-broker", validation_alias="MQTT_HOST")
    mqtt_port: int = Field(default=1883, validation_alias="MQTT_PORT")
    mqtt_username: str = Field(validation_alias="MQTT_USERNAME")
    mqtt_password: str = Field(validation_alias="MQTT_PASSWORD")
    mqtt_topic_prefix: str = Field(default="visionguard", validation_alias="MQTT_TOPIC_PREFIX")
    mqtt_client_id: str | None = Field(default=None, validation_alias="MQTT_CLIENT_ID")
    jwt_secret: str = Field(validation_alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")

settings = Settings()
security = HTTPBearer()
logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)
app = FastAPI(title="device-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

_INVALID_LOG_INTERVAL_S = 60
_last_invalid_log_ts: dict[str, float] = {}

def _should_log_invalid(key: str) -> bool:
    now = time.time()
    last = _last_invalid_log_ts.get(key, 0.0)
    if now - last >= _INVALID_LOG_INTERVAL_S:
        _last_invalid_log_ts[key] = now
        return True
    return False

class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True)
    owner_user_id = Column(Integer, nullable=True)
    name = Column(String(100), nullable=False)
    location = Column(String(255), nullable=True)
    notes = Column(String(1000), nullable=True)
    token = Column(String(255), unique=True, nullable=False)
    onboarding_token_hash = Column(String(128), nullable=True)
    onboarding_expires_at = Column(DateTime(timezone=True), nullable=True)
    onboarding_used_at = Column(DateTime(timezone=True), nullable=True)
    active_token_hash = Column(String(128), nullable=True)
    provisioning_status = Column(String(20), nullable=False, default="pending")
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class DeviceCreate(BaseModel):
    name: str
    location: str | None = None
    notes: str | None = None

class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    owner_user_id: Optional[int] = None
    is_online: Optional[bool] = None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class MQTTPublisher:
    def __init__(self, host: str, port: int, username: str, password: str, topic_prefix: str, client_id: str):
        self.topic_prefix = topic_prefix.rstrip("/")
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self.client.username_pw_set(username, password)
        self.client.connect(host, port, keepalive=60)
        self.client.loop_start()

    def publish_json(self, topic_suffix: str, payload: dict) -> None:
        topic = f"{self.topic_prefix}/{topic_suffix.lstrip('/')}"
        self.client.publish(topic, json.dumps(payload), qos=1)

    def close(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()


def publish_device_status(device_id: int, status: str, provisioning_status: Optional[str] = None) -> None:
    publisher = getattr(app.state, "mqtt_publisher", None)
    if not publisher:
        return
    payload = {"device_id": device_id, "status": status, "ts": datetime.now(timezone.utc).isoformat()}
    if provisioning_status:
        payload["provisioning_status"] = provisioning_status
    publisher.publish_json(f"devices/{device_id}/status", payload)


def publish_active_token(device_id: int, active_token: str, original_token: Optional[str] = None) -> None:
    publisher = getattr(app.state, "mqtt_publisher", None)
    if not publisher:
        return
    payload = {"device_id": device_id, "active_token": active_token, "ts": datetime.now(timezone.utc).isoformat()}
    publisher.publish_json(f"provisioning/{device_id}/active-token", payload)
    if original_token:
        publisher.publish_json(f"provisioning/token/{hash_token(original_token)}/active-token", payload)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def generate_token() -> str:
    return secrets.token_urlsafe(32)

def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict[str, Any]:
    return decode_access_token(credentials.credentials)

def ensure_schema() -> None:
    stmts = [
        "ALTER TABLE devices ADD COLUMN IF NOT EXISTS location VARCHAR(255)",
        "ALTER TABLE devices ADD COLUMN IF NOT EXISTS notes VARCHAR(1000)",
        "ALTER TABLE devices ADD COLUMN IF NOT EXISTS onboarding_token_hash VARCHAR(128)",
        "ALTER TABLE devices ADD COLUMN IF NOT EXISTS onboarding_expires_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE devices ADD COLUMN IF NOT EXISTS onboarding_used_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE devices ADD COLUMN IF NOT EXISTS active_token_hash VARCHAR(128)",
        "ALTER TABLE devices ADD COLUMN IF NOT EXISTS provisioning_status VARCHAR(20) DEFAULT 'pending'",
    ]
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))

def consume_device_token(db: Session, token: str) -> tuple[bool, Device | None, str | None]:
    token_hash = hash_token(token)
    
    # 1. Check if token is an active token
    device = db.execute(
        select(Device).where(Device.active_token_hash == token_hash)
    ).scalar_one_or_none()
    
    if device:
        return True, device, None
        
    # 2. Check if token is an onboarding token
    device = db.execute(
        select(Device)
        .where(Device.onboarding_token_hash == token_hash)
    ).scalar_one_or_none()

    if not device:
        if _should_log_invalid(f"invalid_token:{token_hash[:8]}"):
            logger.warning("device_token_invalid reason=device_not_found_or_invalid_token hash=%s", token_hash[:8])
        return False, None, None

    now = datetime.now(timezone.utc)
    
    # If already active, this is likely a retry heartbeat before the agent received its active token
    if device.provisioning_status == "active":
        return True, device, device.token
        
    if device.provisioning_status != "pending":
        return False, device, None
    if device.onboarding_expires_at and device.onboarding_expires_at <= now:
        device.provisioning_status = "expired"
        db.commit()
        if _should_log_invalid(f"expired:{device.id}"):
            logger.warning("device_onboarding_expired reason=onboarding_expired device_id=%s", device.id)
        return False, device, None

    new_active = generate_token()
    device.active_token_hash = hash_token(new_active)
    device.token = new_active
    device.onboarding_used_at = now
    device.provisioning_status = "active"
    db.commit()
    return True, device, new_active

def process_ingest_heartbeat(payload: dict[str, Any]) -> None:
    token = payload.get("token")
    if not token:
        return

    db = SessionLocal()
    try:
        valid, device, rotated = consume_device_token(db, str(token))
        if not valid or not device:
            publisher = getattr(app.state, "mqtt_publisher", None)
            if publisher:
                device_id = payload.get("device_id")
                if device_id:
                    publisher.publish_json(f"devices/{device_id}/command", {"command": "shutdown"})
                else:
                    token_hash = hash_token(str(token))
                    publisher.publish_json(f"provisioning/token/{token_hash}/invalid", {"command": "shutdown"})
            return
        if rotated:
            publish_active_token(device.id, rotated, original_token=str(token))
        # Get the status sent from the edge agent
        status = payload.get("status", "online")
        was_offline = not device.is_online
        device.is_online = (status == "online")
        device.last_seen = datetime.now(timezone.utc)
        db.commit()

        # If transitioning to online or just rotated tokens => broadcast online
        if device.is_online and (was_offline or rotated): 
            publish_device_status(device.id, "online", provisioning_status=device.provisioning_status)
        
        # If transitioning to offline (e.g. graceful shutdown) => broadcast offline
        elif not device.is_online and not was_offline:
            publish_device_status(device.id, "offline", provisioning_status=device.provisioning_status)
    finally:
        db.close()

async def mqtt_ingest_subscriber() -> None:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    topic_prefix = settings.mqtt_topic_prefix.rstrip("/")
    client_id = f"{settings.service_name}-ingest"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

    def on_connect(c: mqtt.Client, _userdata, _flags, _reason_code, _properties) -> None:
        c.subscribe(f"{topic_prefix}/ingest/device/heartbeat", qos=1)

    def on_message(_c: mqtt.Client, _userdata, msg: mqtt.MQTTMessage) -> None:
        try:
            data = json.loads(msg.payload.decode("utf-8"))
            loop.call_soon_threadsafe(queue.put_nowait, {"topic": msg.topic, "data": data})
        except Exception:
            return

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
    client.loop_start()
    app.state.mqtt_ingest_client = client

    while True:
        item = await queue.get()
        topic = item["topic"]
        data = item["data"]
        if topic == f"{topic_prefix}/ingest/device/heartbeat":
            process_ingest_heartbeat(data)

async def check_device_timeouts():
    while True:
        try:
            db = SessionLocal()
            now = datetime.now(timezone.utc)
            timeout_threshold = timedelta(minutes=2)
            expired_devices = db.execute(
                select(Device)
                .where(Device.is_online == True)
                .where(Device.last_seen < now - timeout_threshold)
            ).scalars().all()
            for d in expired_devices:
                d.is_online = False
                publish_device_status(d.id, "offline", provisioning_status=d.provisioning_status)
            db.commit()
            db.close()
        except Exception as e:
            print(f"Checkout timeout error: {e}")
        await asyncio.sleep(30)

@app.on_event("startup")
async def startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    app.state.mqtt_publisher = MQTTPublisher(
        host=settings.mqtt_host,
        port=settings.mqtt_port,
        username=settings.mqtt_username,
        password=settings.mqtt_password,
        topic_prefix=settings.mqtt_topic_prefix,
        client_id=settings.mqtt_client_id or settings.service_name,
    )
    app.state.mqtt_ingest_task = asyncio.create_task(mqtt_ingest_subscriber())
    app.state.timeout_task = asyncio.create_task(check_device_timeouts())

@app.on_event("shutdown")
async def shutdown() -> None:
    if getattr(app.state, "mqtt_ingest_task", None):
        app.state.mqtt_ingest_task.cancel()
    if getattr(app.state, "mqtt_ingest_client", None):
        app.state.mqtt_ingest_client.loop_stop()
        app.state.mqtt_ingest_client.disconnect()
    if getattr(app.state, "timeout_task", None):
        app.state.timeout_task.cancel()
    if getattr(app.state, "mqtt_publisher", None):
        app.state.mqtt_publisher.close()

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.service_name}

@app.get("/")
def list_devices(db: Session = Depends(get_db)) -> list[dict]:
    devices = db.execute(select(Device)).scalars().all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "location": d.location,
            "notes": d.notes,
            "provisioning_status": d.provisioning_status,
            "onboarding_expires_at": d.onboarding_expires_at.isoformat() if d.onboarding_expires_at else None,
            "owner_user_id": d.owner_user_id,
            "is_online": d.is_online,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
        }
        for d in devices
    ]

@app.post("/")
def create_device(body: DeviceCreate, current_user: dict[str, Any] = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    onboarding_token = generate_token()
    onboarding_expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    placeholder_active = generate_token()
    device = Device(
        name=body.name,
        location=body.location,
        notes=body.notes,
        token=placeholder_active,
        owner_user_id=int(current_user["sub"]),
        onboarding_token_hash=hash_token(onboarding_token),
        onboarding_expires_at=onboarding_expires,
        provisioning_status="pending",
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return {
        "id": device.id,
        "name": device.name,
        "location": device.location,
        "notes": device.notes,
        "owner_user_id": device.owner_user_id,
        "is_online": device.is_online,
        "provisioning_status": device.provisioning_status,
        "onboarding_token": onboarding_token,
        "onboarding_expires_at": onboarding_expires.isoformat(),
    }

@app.get("/{device_id}")
def get_device(device_id: int, db: Session = Depends(get_db)) -> dict:
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return {
        "id": device.id, "name": device.name,
        "location": device.location,
        "notes": device.notes,
        "owner_user_id": device.owner_user_id, "is_online": device.is_online,
        "provisioning_status": device.provisioning_status,
        "onboarding_expires_at": device.onboarding_expires_at.isoformat() if device.onboarding_expires_at else None,
        "last_seen": device.last_seen.isoformat() if device.last_seen else None,
    }

@app.put("/{device_id}")
def update_device(device_id: int, body: DeviceUpdate, db: Session = Depends(get_db)) -> dict:
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if body.name is not None:
        device.name = body.name
    if body.location is not None:
        device.location = body.location
    if body.notes is not None:
        device.notes = body.notes
    if body.owner_user_id is not None:
        device.owner_user_id = body.owner_user_id
    if body.is_online is not None:
        device.is_online = body.is_online
    db.commit()
    db.refresh(device)
    return {
        "id": device.id,
        "name": device.name,
        "location": device.location,
        "notes": device.notes,
        "is_online": device.is_online,
    }

@app.delete("/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db)) -> dict:
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    publisher = getattr(app.state, "mqtt_publisher", None)
    if publisher:
        publisher.publish_json(f"devices/{device_id}/command", {"command": "shutdown"})
        
    db.delete(device)
    db.commit()
    return {"deleted": device_id}
