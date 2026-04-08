# Camera Fall System (Local Dev)

## Prerequisites

- Copy [.env.example](.env.example) to `.env` in this directory (`app/`) and set all required values. Docker Compose reads `app/.env` automatically for `${VAR}` substitution when you run commands from `app/`. Application containers receive secrets only via `environment` in [docker-compose.yml](docker-compose.yml) (no credentials in Python source defaults for DB/JWT/MinIO).

## Services

- `user-service` — `http://localhost:${USER_SERVICE_PORT:-8001}`
- `device-service` — `http://localhost:${DEVICE_SERVICE_PORT:-8002}`
- `alert-service` — `http://localhost:${ALERT_SERVICE_PORT:-8003}`
- `signaling-service` — `http://localhost:${SIGNALING_SERVICE_PORT:-8004}`
- `postgres`, `redis`, `minio`, `mqtt-broker` — ports from `.env` (see `.env.example`)

## Run with Docker Compose

```bash
cd app
copy .env.example .env   # Windows: edit .env and fill secrets
docker compose up --build
```

## Edge agent (on host)

Inference (YOLO + GRU) and agent in [edge-agent](edge-agent/): `main.py`, `detector.py`, `webrtc.py`.

```bash
cd app/edge-agent
pip install -e .
```

Set `.env` in `app/` or current working directory; need at least `DEVICE_TOKEN`, `MQTT_WS_HOST`, `MQTT_WS_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`. If WebRTC is enabled (`ENABLE_WEBRTC=1`), add `SIGNALING_WS_URL`.

```bash
cd app/edge-agent
python main.py
```

## Required environment (summary)

- **Compose / cloud**: `POSTGRES_*`, `DATABASE_URL`, `JWT_SECRET`, `MINIO_ROOT_*`, `MQTT_*` — see `.env.example`.
- **Edge**: `DEVICE_TOKEN` (required), `MQTT_WS_*`, `MQTT_* auth`, optional model paths as documented in `.env.example`.
