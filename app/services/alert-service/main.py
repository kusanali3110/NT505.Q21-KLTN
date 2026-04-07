import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Annotated, Any, Dict
import asyncio

import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, create_engine, func, select, update
from sqlalchemy.orm import declarative_base, sessionmaker


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "alert-service"
    database_url: str = Field(validation_alias="DATABASE_URL")
    mqtt_host: str = Field(default="mqtt-broker", validation_alias="MQTT_HOST")
    mqtt_port: int = Field(default=1883, validation_alias="MQTT_PORT")
    mqtt_username: str = Field(validation_alias="MQTT_USERNAME")
    mqtt_password: str = Field(validation_alias="MQTT_PASSWORD")
    mqtt_topic_prefix: str = Field(default="visionguard", validation_alias="MQTT_TOPIC_PREFIX")
    mqtt_client_id: str | None = Field(default=None, validation_alias="MQTT_CLIENT_ID")
    device_service_url: str = Field(default="http://device-service:8000", validation_alias="DEVICE_SERVICE_URL")
    jwt_secret: str = Field(validation_alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")

security = HTTPBearer()

def decode_token(token: str, secret: str, algorithm: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, secret, algorithms=[algorithm])
    except InvalidTokenError as exc:
        raise ValueError("Invalid token") from exc

def get_current_user(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> dict:
    try:
        return decode_token(credentials.credentials, settings.jwt_secret, settings.jwt_algorithm)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


settings = Settings()
app = FastAPI(title="alert-service")
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


def persist_alert_and_publish(payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        device_id = int(payload["device_id"])
        confidence = float(payload["confidence"])
        label = str(payload.get("label", "FALL"))
        snapshot_url = payload.get("snapshot_url")
    except Exception:
        return None

    # Verify device exists
    try:
        req = urllib.request.Request(f"{settings.device_service_url}/{device_id}")
        with urllib.request.urlopen(req, timeout=3) as resp:
            pass
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # Device is permanently gone. Attempt to kill rogue agent if it sends an alert.
            publisher = getattr(app.state, "mqtt_publisher", None)
            if publisher:
                publisher.publish_json(f"devices/{device_id}/command", {"command": "shutdown"})
        return None
    except Exception:
        pass

    db = SessionLocal()
    try:
        alert = Alert(device_id=device_id, confidence=confidence, label=label, snapshot_url=snapshot_url)
        db.add(alert)
        db.commit()
        db.refresh(alert)
        out = {
            "id": alert.id,
            "device_id": alert.device_id,
            "confidence": alert.confidence,
            "label": alert.label,
            "occurred_at": datetime.utcnow().isoformat(),
            "snapshot_url": alert.snapshot_url,
        }
    finally:
        db.close()

    publisher = getattr(app.state, "mqtt_publisher", None)
    if publisher:
        publisher.publish_json(f"alerts/{device_id}", out)
    return out





async def mqtt_ingest_subscriber() -> None:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    topic_prefix = settings.mqtt_topic_prefix.rstrip("/")
    client_id = f"{settings.service_name}-ingest"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

    def on_connect(c: mqtt.Client, _userdata, _flags, _reason_code, _properties) -> None:
        c.subscribe(f"{topic_prefix}/ingest/alert/fall", qos=1)

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
        if item["topic"] == f"{topic_prefix}/ingest/alert/fall":
            data = item["data"]
            try:
                device_id = int(data["device_id"])
            except Exception:
                continue
            persist_alert_and_publish(data)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    confidence = Column(Float, nullable=False)
    label = Column(String(20), nullable=False, default="FALL")
    snapshot_url = Column(String(500), nullable=True)
    acknowledged = Column(Boolean, default=False)


class AlertBody(BaseModel):
    device_id: int
    confidence: float
    label: str = "FALL"
    snapshot_url: str | None = None

class AlertUpdate(BaseModel):
    acknowledged: bool


# manager = WSManager() (Moved to signaling-service)


@app.on_event("startup")
async def startup() -> None:
    Base.metadata.create_all(bind=engine)
    app.state.mqtt_publisher = MQTTPublisher(
        host=settings.mqtt_host,
        port=settings.mqtt_port,
        username=settings.mqtt_username,
        password=settings.mqtt_password,
        topic_prefix=settings.mqtt_topic_prefix,
        client_id=settings.mqtt_client_id or settings.service_name,
    )
    app.state.mqtt_ingest_task = asyncio.create_task(mqtt_ingest_subscriber())


@app.on_event("shutdown")
async def shutdown() -> None:
    if getattr(app.state, "mqtt_ingest_task", None):
        app.state.mqtt_ingest_task.cancel()
    if getattr(app.state, "mqtt_ingest_client", None):
        app.state.mqtt_ingest_client.loop_stop()
        app.state.mqtt_ingest_client.disconnect()
    if getattr(app.state, "mqtt_publisher", None):
        app.state.mqtt_publisher.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.service_name}


@app.post("/")
async def create_alert(body: AlertBody) -> dict:
    payload = {
        "device_id": body.device_id,
        "confidence": body.confidence,
        "label": body.label,
        "snapshot_url": body.snapshot_url,
    }
    out = persist_alert_and_publish(payload)
    if not out:
        raise HTTPException(status_code=400, detail="Invalid payload")
    return out


@app.get("/")
def list_alerts(limit: int = 50) -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.execute(select(Alert).order_by(Alert.id.desc()).limit(limit)).scalars().all()
        return [
            {
                "id": row.id,
                "device_id": row.device_id,
                "confidence": row.confidence,
                "label": row.label,
                "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
                "snapshot_url": row.snapshot_url,
                "acknowledged": row.acknowledged,
            }
            for row in rows
        ]
    finally:
        db.close()


@app.patch("/{alert_id}")
def update_alert(alert_id: int, body: AlertUpdate) -> dict:
    db = SessionLocal()
    try:
        alert = db.execute(select(Alert).where(Alert.id == alert_id)).scalar_one_or_none()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        alert.acknowledged = body.acknowledged
        db.commit()
        return {"id": alert.id, "acknowledged": alert.acknowledged}
    finally:
        db.close()

@app.post("/acknowledge-all")
def acknowledge_all() -> dict:
    db = SessionLocal()
    try:
        db.execute(update(Alert).where(Alert.acknowledged == False).values(acknowledged=True))
        db.commit()
        return {"success": True}
    finally:
        db.close()


@app.delete("/{alert_id}")
def delete_alert(alert_id: int, current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
    db = SessionLocal()
    try:
        alert = db.execute(select(Alert).where(Alert.id == alert_id)).scalar_one_or_none()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
            
        role = current_user.get("role", "user")
        user_id = int(current_user.get("sub", 0))
        
        if role != "admin":
            try:
                req = urllib.request.Request(f"http://device-service:8000/{alert.device_id}")
                with urllib.request.urlopen(req) as resp:
                    device_data = json.loads(resp.read())
                    owner = device_data.get("owner_user_id")
                    if owner != user_id:
                        raise HTTPException(status_code=403, detail="Not authorized to delete this alert")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    pass # Ignore if device 404
                else:
                    raise HTTPException(status_code=500, detail="Error communicating with device service")
            except Exception:
                pass
                
        db.delete(alert)
        db.commit()
        return {"deleted": alert_id}
    finally:
        db.close()

# Consolidated to signaling-service
