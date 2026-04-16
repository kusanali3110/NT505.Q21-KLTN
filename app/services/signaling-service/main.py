import asyncio
import json
import logging
import os
import redis.asyncio as redis
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import jwt
from jwt.exceptions import InvalidTokenError
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

class Settings(BaseSettings):
    service_name: str = "signaling-service"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    mqtt_host: str = Field(default="mqtt-broker", validation_alias="MQTT_HOST")
    mqtt_port: int = Field(default=1883, validation_alias="MQTT_PORT")
    mqtt_username: str = Field(validation_alias="MQTT_USERNAME")
    mqtt_password: str = Field(validation_alias="MQTT_PASSWORD")
    mqtt_topic_prefix: str = Field(default="visionguard", validation_alias="MQTT_TOPIC_PREFIX")
    jwt_secret: str = Field(validation_alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    database_url: str = Field(validation_alias="DATABASE_URL")
    redis_host: str = Field(default="redis", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="REDIS_PORT")


logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(levelname)s [%(name)s] %(message)s",
)
settings = Settings()
logger = logging.getLogger()
app = FastAPI(title="signaling-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)

class EventManager:
    def __init__(self):
        self.connections: dict[WebSocket, dict[str, Any]] = {}

    async def connect(self, ws: WebSocket, user_id: int, role: str) -> None:
        await ws.accept()
        self.connections[ws] = {"user_id": user_id, "role": role}

    def disconnect(self, ws: WebSocket) -> None:
        self.connections.pop(ws, None)

    async def broadcast(self, payload: dict, owner_id: Optional[int]) -> None:
        stale: list[WebSocket] = []
        for ws, info in self.connections.items():
            if info["role"] == "admin" or (owner_id and info["user_id"] == owner_id):
                try:
                    await ws.send_json(payload)
                except Exception:
                    stale.append(ws)
        for ws in stale:
            self.disconnect(ws)

event_manager = EventManager()


async def get_device_owner(device_id: int) -> Optional[int]:
    cache_key = f"device:{device_id}:owner"
    try:
        cached = await redis_client.get(cache_key)
        if cached is not None:
            return int(cached) if cached != "None" else None
    except Exception as e:
        logger.warning(f"Redis get failed: {e}")

    try:
        def fetch_db():
            with SessionLocal() as db:
                row = db.execute(text("SELECT owner_user_id FROM devices WHERE id = :id"), {"id": device_id}).fetchone()
                return row[0] if row else None
        owner_id = await asyncio.to_thread(fetch_db)
        
        try:
            await redis_client.setex(cache_key, 300, str(owner_id))
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")
            
        return owner_id
    except Exception as e:
        logger.error(f"DB access failed: {e}")
        return None

def _mqtt_event_type_from_topic(topic: str, topic_prefix: str) -> Optional[dict]:
    prefix = topic_prefix.rstrip("/")
    if topic.startswith(f"{prefix}/devices/") and topic.endswith("/status"):
        return {"type": "device_status"}
    if topic.startswith(f"{prefix}/alerts/") or topic.startswith(f"{prefix}/ingest/alert/"):
        return {"type": "alert"}
    return None


async def mqtt_subscriber():
    queue: asyncio.Queue[dict] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    client_id = settings.service_name
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=settings.service_name)
    client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

    def on_connect(c: mqtt.Client, _userdata, _flags, _reason_code, _properties) -> None:
        prefix = settings.mqtt_topic_prefix.rstrip("/")
        c.subscribe(f"{prefix}/devices/+/status", qos=1)
        c.subscribe(f"{prefix}/alerts/+", qos=1)
        c.subscribe(f"{prefix}/alerts/+/update", qos=1)

    def on_message(_c: mqtt.Client, _userdata, msg: mqtt.MQTTMessage) -> None:
        info = _mqtt_event_type_from_topic(msg.topic, settings.mqtt_topic_prefix)
        if not info:
            return
        try:
            raw = msg.payload.decode("utf-8")
            data = json.loads(raw)
            event_type = info["type"]
            payload = {"type": event_type, "data": data}
            loop.call_soon_threadsafe(queue.put_nowait, payload)
        except Exception:
            logger.exception("Failed to parse MQTT message topic=%s", msg.topic)
            return

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
    client.loop_start()
    app.state.mqtt_client = client

    while True:
        payload = await queue.get()
        data = payload.get("data", {})
        device_id = data.get("device_id")
        
        if device_id is not None:
            owner_id = await get_device_owner(int(device_id))
            await event_manager.broadcast(payload, owner_id)
        else:
            # Broadcast to all admins if no specific device
            await event_manager.broadcast(payload, owner_id=None)

@app.on_event("startup")
async def startup():
    app.state.subscriber_task = asyncio.create_task(mqtt_subscriber())

@app.on_event("shutdown")
async def shutdown():
    if getattr(app.state, "subscriber_task", None):
        app.state.subscriber_task.cancel()
    if getattr(app.state, "mqtt_client", None):
        app.state.mqtt_client.loop_stop()
        app.state.mqtt_client.disconnect()
    try:
        await redis_client.close()
    except:
        pass

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "signaling-service"}


@app.websocket("/ws/")
async def event_stream(ws: WebSocket, token: str = Query(...)) -> None:
    try:
        user = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError:
        await ws.close(code=4001, reason="Invalid token")
        return

    user_id = int(user.get("sub", 0))
    role = user.get("role", "user")

    await event_manager.connect(ws, user_id, role)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        event_manager.disconnect(ws)
