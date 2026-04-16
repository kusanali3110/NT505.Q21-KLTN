import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Annotated, Any, Dict
import asyncio
import boto3
from botocore.config import Config

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
    aws_access_key_id: str | None = Field(default=None, validation_alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, validation_alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="ap-southeast-1", validation_alias="AWS_REGION")
    s3_bucket: str | None = Field(default=None, validation_alias="S3_BUCKET")

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
        fall_id = payload.get("fall_id")
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
        alert = Alert(fall_id=fall_id, device_id=device_id, confidence=confidence, label=label)
        db.add(alert)
        db.commit()
        db.refresh(alert)
        out = {
            "id": alert.id,
            "fall_id": alert.fall_id,
            "device_id": alert.device_id,
            "confidence": alert.confidence,
            "label": alert.label,
            "occurred_at": alert.occurred_at.isoformat() if alert.occurred_at else datetime.utcnow().isoformat(),
            "video_url": alert.video_url,
        }
    finally:
        db.close()

    publisher = getattr(app.state, "mqtt_publisher", None)
    if publisher:
        # Precompute the redirect link for realtime socket subscribers
        if out.get("video_url") and not out["video_url"].startswith("http"):
            out["video_url"] = f"/api/alerts/{out['id']}/video"
            
        publisher.publish_json(f"alerts/{device_id}", out)
    return out


from fastapi.responses import RedirectResponse

@app.get("/{alert_id}/video")
def get_alert_video(alert_id: int):
    db = SessionLocal()
    try:
        alert = db.execute(select(Alert).where(Alert.id == alert_id)).scalar_one_or_none()
        if not alert or not alert.video_url:
            raise HTTPException(status_code=404, detail="Video not found")
            
        if alert.video_url.startswith("http"):
            return RedirectResponse(url=alert.video_url)
            
        s3_client = boto3.client('s3', region_name=settings.aws_region, 
                                 aws_access_key_id=settings.aws_access_key_id, 
                                 aws_secret_access_key=settings.aws_secret_access_key,
                                 config=Config(signature_version='s3v4'))
        url = s3_client.generate_presigned_url('get_object', 
                                               Params={'Bucket': settings.s3_bucket, 'Key': alert.video_url}, 
                                               ExpiresIn=3600)
        return RedirectResponse(url=url)
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
        c.subscribe(f"{topic_prefix}/ingest/alert/fall", qos=1)
        c.subscribe(f"{topic_prefix}/ingest/upload/request", qos=1)
        c.subscribe(f"{topic_prefix}/ingest/alert/update", qos=1)

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
            
        elif item["topic"] == f"{topic_prefix}/ingest/upload/request":
            data = item["data"]
            try:
                device_id = int(data["device_id"])
                fall_id = data["fall_id"]
                object_key = f"raw_videos/{fall_id}.mp4"
                
                if settings.s3_bucket and settings.aws_access_key_id:
                    s3_client = boto3.client('s3', region_name=settings.aws_region, 
                        aws_access_key_id=settings.aws_access_key_id, 
                        aws_secret_access_key=settings.aws_secret_access_key,
                        config=Config(signature_version='s3v4'))
                        
                    url = s3_client.generate_presigned_url('put_object', 
                                                           Params={'Bucket': settings.s3_bucket, 'Key': object_key, 'ContentType': 'video/mp4'}, 
                                                           ExpiresIn=300)
                    
                    publisher = getattr(app.state, "mqtt_publisher", None)
                    if publisher:
                        publisher.publish_json(f"devices/{device_id}/upload_url", {
                            "fall_id": fall_id,
                            "url": url,
                            "key": object_key
                        })
            except Exception as e:
                pass

        elif item["topic"] == f"{topic_prefix}/ingest/alert/update":
            data = item["data"]
            try:
                fall_id = data["fall_id"]
                video_key = data["video_key"]
                
                db = SessionLocal()
                try:
                    alert = db.execute(select(Alert).where(Alert.fall_id == fall_id)).scalar_one_or_none()
                    if alert:
                        # Store raw key, we will dynamically generate presigned urls
                        alert.video_url = video_key
                        db.commit()
                        
                        publisher = getattr(app.state, "mqtt_publisher", None)
                        if publisher:
                            update_payload = {
                                "id": alert.id,
                                "fall_id": alert.fall_id,
                                "device_id": alert.device_id,
                                "video_url": f"/api/alerts/{alert.id}/video"
                            }
                            publisher.publish_json(f"alerts/{alert.device_id}/update", update_payload)
                finally:
                    db.close()
            except Exception as e:
                pass


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    fall_id = Column(String(36), index=True, nullable=True) # Edge generates UUID
    device_id = Column(Integer, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    confidence = Column(Float, nullable=False)
    label = Column(String(20), nullable=False, default="FALL")
    video_url = Column(String(500), nullable=True)
    acknowledged = Column(Boolean, default=False)

class AlertBody(BaseModel):
    device_id: int
    confidence: float
    label: str = "FALL"

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
                "fall_id": row.fall_id,
                "device_id": row.device_id,
                "confidence": row.confidence,
                "label": row.label,
                "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
                "video_url": f"/api/alerts/{row.id}/video" if row.video_url and not row.video_url.startswith('http') else row.video_url,
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
