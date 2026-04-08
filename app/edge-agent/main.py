import asyncio
import collections
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from detector import DetectorConfig, FallDetector
from identity import IdentityManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("edge-agent")

EDGE_DIR = Path(__file__).resolve().parent
load_dotenv(EDGE_DIR / ".env")


@dataclass
class AgentConfig:
    device_id: Optional[int]
    device_token: str
    camera_index: int
    fall_clip_dir: str
    mqtt_ws_host: str
    mqtt_ws_port: int
    mqtt_ws_path: str
    mqtt_username: str
    mqtt_password: str
    mqtt_topic_prefix: str


def _resolve_model_path(path_str: str) -> str:
    p = Path(path_str)
    if p.is_absolute():
        return str(p)
    return str((EDGE_DIR / p).resolve())


def _open_video_capture(cfg: AgentConfig) -> cv2.VideoCapture:
    camera_url = (os.getenv("CAMERA_URL") or "").strip()
    backend_key = (os.getenv("CAMERA_BACKEND") or "").strip().lower()
    backends = {
        "dshow": cv2.CAP_DSHOW,
        "msmf": cv2.CAP_MSMF,
        "ffmpeg": cv2.CAP_FFMPEG,
    }
    if hasattr(cv2, "CAP_V4L2"):
        backends["v4l2"] = int(cv2.CAP_V4L2)
    backend = backends.get(backend_key)

    def _open(source: str | int) -> cv2.VideoCapture:
        if backend is not None:
            return cv2.VideoCapture(source, backend)
        return cv2.VideoCapture(source)

    if camera_url:
        return _open(camera_url)
    return _open(cfg.camera_index)


def _capture_read(cap: cv2.VideoCapture):
    return cap.read()


def load_agent_config(identity: IdentityManager) -> AgentConfig:
    env_token = os.getenv("DEVICE_TOKEN")
    
    device_id = identity.device_id
    device_token = identity.token or env_token
    
    if not device_token:
        raise RuntimeError("DEVICE_TOKEN is required in .env for initial onboarding")
        
    return AgentConfig(
        device_id=device_id,
        device_token=device_token,
        camera_index=int(os.getenv("CAMERA_INDEX", "0")),
        fall_clip_dir=os.getenv("FALL_CLIP_DIR", "./fall_clips"),
        mqtt_ws_host=os.getenv("MQTT_WS_HOST", "localhost"),
        mqtt_ws_port=int(os.getenv("MQTT_PORT_WS", "9002")),
        mqtt_ws_path=os.getenv("MQTT_WS_PATH", "/mqtt"),
        mqtt_username=os.getenv("MQTT_USERNAME", ""),
        mqtt_password=os.getenv("MQTT_PASSWORD", ""),
        mqtt_topic_prefix=os.getenv("MQTT_TOPIC_PREFIX", "visionguard"),
    )


class MQTTAgentPublisher:
    def __init__(self, cfg: AgentConfig, identity: IdentityManager):
        self.topic_prefix = cfg.mqtt_topic_prefix.rstrip("/")
        self.identity = identity
        self.device_id = cfg.device_id
        self.device_token = cfg.device_token
        
        client_id = (os.getenv("MQTT_CLIENT_ID") or "").strip() or f"edge-{time.time()}"
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, transport="websockets")
        self.client.username_pw_set(cfg.mqtt_username, cfg.mqtt_password)
        self.client.ws_set_options(path=cfg.mqtt_ws_path)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.handlers: dict[str, list] = {}
        self.loop = asyncio.get_running_loop()
        
        logger.info("Connecting to MQTT (Pending Auth)")
        self.client.reconnect_delay_set(min_delay=1, max_delay=60)
        self.client.connect(cfg.mqtt_ws_host, cfg.mqtt_ws_port, keepalive=60)
        self.client.loop_start()

    def _on_disconnect(self, c, userdata, disconnect_flags, reason_code, properties=None) -> None:
        logger.warning("MQTT disconnected reason_code=%s", reason_code)

    def _on_connect(self, c: mqtt.Client, _userdata, _flags, _reason_code, _properties) -> None:
        if self.device_id:
            c.subscribe(f"{self.topic_prefix}/provisioning/{self.device_id}/active-token", qos=1)
            c.subscribe(f"{self.topic_prefix}/devices/{self.device_id}/command", qos=1)
        else:
            token_hash = hashlib.sha256(self.device_token.encode("utf-8")).hexdigest()
            logger.info(f"Subscribing to {self.topic_prefix}/provisioning/token/{token_hash}/active-token")
            c.subscribe(f"{self.topic_prefix}/provisioning/token/{token_hash}/active-token", qos=1)
            c.subscribe(f"{self.topic_prefix}/provisioning/token/{token_hash}/invalid", qos=1)

    def add_handler(self, topic: str, callback):
        if topic not in self.handlers:
            self.handlers[topic] = []
            self.client.subscribe(topic, qos=1)
        self.handlers[topic].append(callback)

    def _on_message(self, _c: mqtt.Client, _userdata, msg: mqtt.MQTTMessage) -> None:
        for topic, callbacks in self.handlers.items():
            if mqtt.topic_matches_sub(topic, msg.topic):
                for cb in callbacks:
                    try:
                        cb(msg)
                    except Exception:
                        pass

        # Handle commands
        if msg.topic.endswith("/command") or msg.topic.endswith("/invalid"):
            try:
                data = json.loads(msg.payload.decode("utf-8"))
                if data.get("command") == "shutdown":
                    logger.warning("Backend requested shutdown (token rejected or deleted). Exiting process...")
                    identity_file = EDGE_DIR / "identity.json"
                    if identity_file.exists():
                        os.unlink(identity_file)
                    os._exit(1)
            except Exception:
                pass

        # Check for provisioning tokens
        try:
            if msg.topic.endswith("/active-token"):
                data = json.loads(msg.payload.decode("utf-8"))
                new_token = str(data.get("active_token", "")).strip()
                new_id = data.get("device_id")
                
                if new_token and new_id:
                    logger.info("Provisioning successful! ID=%s", new_id)
                    self.device_token = new_token
                    self.device_id = int(new_id)
                    self.identity.save(self.device_id, self.device_token)
                    self.client.subscribe(f"{self.topic_prefix}/provisioning/{self.device_id}/active-token", qos=1)
                    self.client.subscribe(f"{self.topic_prefix}/devices/{self.device_id}/command", qos=1)
        except Exception as e:
            logger.error("Failed to parse MQTT message: %s", e)

    def publish(self, topic_suffix: str, payload: dict) -> None:
        topic = f"{self.topic_prefix}/{topic_suffix.lstrip('/')}"
        self.client.publish(topic, json.dumps(payload), qos=1)

    def close(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()


import threading

class NativeVideoManager:
    def __init__(self, cfg: AgentConfig, out_dir: Path):
        self.cfg = cfg
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.cap = None
        
        self.ready_event = threading.Event()
        self.native_fps = 30
        self.width = 640
        self.height = 480
        self.buffer = collections.deque(maxlen=90)
        
        self.is_recording = False
        self.is_falling = False
        self.writer = None
        self.current_filename = None
        
        self.latest_frame = None
        self.lock = threading.Lock()
        
        self.running = True
        self.thread = threading.Thread(target=self._run_capture, daemon=True)
        self.thread.start()

    def _run_capture(self):
        self.cap = _open_video_capture(self.cfg)
        if not self.cap.isOpened():
            logger.error("Cannot open camera — on Windows try CAMERA_BACKEND=dshow or a different CAMERA_INDEX")
            self.ready_event.set()
            return
            
        self.native_fps = int(self.cap.get(cv2.CAP_PROP_FPS) or 30)
        if self.native_fps <= 0:
            self.native_fps = 30
            
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
        self.buffer = collections.deque(maxlen=int(self.native_fps * 3.0))
        
        logger.info(f"Native Video capture thread started at {self.native_fps} FPS, {self.width}x{self.height}")
        self.ready_event.set()
        
        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.01)
                continue
                
            native_frame = frame.copy()
            
            with self.lock:
                self.latest_frame = native_frame
                falling_now = self.is_falling
                
            if falling_now:
                if not self.is_recording:
                    self.is_recording = True
                    now = datetime.now()
                    self.current_filename = self.out_dir / f"fall_{now.strftime('%Y%m%d_%H%M%S')}.mp4"
                    self.writer = cv2.VideoWriter(
                        str(self.current_filename), 
                        cv2.VideoWriter_fourcc(*"mp4v"), 
                        self.native_fps, 
                        (self.width, self.height)
                    )
                    # flush pre-fall buffer to disk
                    for b_frame in self.buffer:
                        self.writer.write(b_frame)
                    self.buffer.clear()
                
                if self.writer:
                    self.writer.write(native_frame)
            else:
                if self.is_recording:
                    # Cut immediately!
                    self.is_recording = False
                    if self.writer:
                        self.writer.release()
                        self.writer = None
                        logger.info(f"Saved native quality fall clip locally at: {self.current_filename}")
                self.buffer.append(native_frame)

    def get_latest_frame(self):
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
        return None
        
    def set_falling_status(self, is_falling: bool):
        with self.lock:
            self.is_falling = is_falling

    def stop(self):
        self.running = False
        self.thread.join(timeout=2.0)
        if self.cap:
            self.cap.release()
        if self.writer:
            self.writer.release()


async def heartbeat_loop(mqtt_publisher: MQTTAgentPublisher) -> None:
    last_log_ts = 0.0
    while True:
        try:
            mqtt_publisher.publish(
                "ingest/device/heartbeat",
                {
                    "device_id": mqtt_publisher.device_id,
                    "token": mqtt_publisher.device_token,
                    "status": "online",
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            now = time.time()
            if now - last_log_ts > 60:
                logger.warning("Heartbeat publish failed: %s", e)
                last_log_ts = now
        await asyncio.sleep(10)


async def run_agent() -> None:
    identity = IdentityManager(EDGE_DIR / "identity.json")
    cfg = load_agent_config(identity)

    yolo_model = _resolve_model_path(os.getenv("YOLO_MODEL", "models/yolo26n-pose.pt"))
    classifier_ckpt = _resolve_model_path(os.getenv("CLASSIFIER_CKPT", "models/gru_pose_masked.pt"))
    detector = FallDetector(DetectorConfig(yolo_model=yolo_model, classifier_ckpt=classifier_ckpt))

    clip_dir = Path(cfg.fall_clip_dir)
    if not clip_dir.is_absolute():
        clip_dir = (EDGE_DIR / clip_dir).resolve()
    
    video_manager = NativeVideoManager(cfg, clip_dir)
    video_manager.ready_event.wait()
    if not video_manager.cap or not video_manager.cap.isOpened():
        raise RuntimeError("Camera failed to open.")
        
    mqtt_publisher = MQTTAgentPublisher(cfg, identity)
    
    logger.info("Agent strictly inferencing at 50ms intervals. Minimum 40 frames to alert.")
    hb_task = asyncio.create_task(heartbeat_loop(mqtt_publisher))
    show_ui = os.getenv("HEADLESS", "0").strip().lower() not in ("1", "true", "yes")
    
    fall_persistence_frames = 0
    REQUIRED_PERSISTENCE = 40  # 40 frames @ 50ms = 2.0s
    INTERVAL_S = 0.05

    try:
        while True:
            t_start = time.time()
            frame = video_manager.get_latest_frame()
            if frame is None:
                await asyncio.sleep(0.01)
                continue
            
            rendered, detections = detector.process_frame(frame)
            fall_detected = False
            confidence = 0.0
            
            for det in detections:
                if det["label"] == "FALL":
                    fall_detected = True
                    confidence = det["probability"]
                    break
            
            elapsed = time.time() - t_start
            intervals = int(elapsed // INTERVAL_S) + 1
            delay = max((intervals * INTERVAL_S) - elapsed, 0.001)

            if fall_detected:
                fall_persistence_frames += intervals
            else:
                fall_persistence_frames = 0
            
            if fall_persistence_frames >= REQUIRED_PERSISTENCE:
                video_manager.set_falling_status(True)
                if (fall_persistence_frames - intervals) < REQUIRED_PERSISTENCE:
                    logger.info("FALL DETECTED constantly for 40 frames (2s)! Triggering alerts...")
                    mqtt_publisher.publish(
                        "ingest/alert/fall",
                        {
                            "device_id": mqtt_publisher.device_id,
                            "token": mqtt_publisher.device_token,
                            "confidence": confidence,
                            "label": "FALL",
                            "ts": datetime.now(timezone.utc).isoformat(),
                        },
                    )
            else:
                video_manager.set_falling_status(False)

            if show_ui:
                cv2.imshow("edge-agent-inference", rendered)
                key = cv2.waitKey(1) & 0xFF
                if key == 27 or key == ord("q"):
                    break
            
            await asyncio.sleep(delay)

    finally:
        hb_task.cancel()
        if mqtt_publisher.device_token:
            mqtt_publisher.publish(
                "ingest/device/heartbeat",
                {
                    "device_id": mqtt_publisher.device_id,
                    "token": mqtt_publisher.device_token,
                    "status": "offline",
                    "ts": datetime.now(timezone.utc).isoformat()
                },
            )
        mqtt_publisher.close()
        video_manager.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    asyncio.run(run_agent())
