import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("edge-agent.identity")

class IdentityManager:
    def __init__(self, identity_file: Path):
        self.identity_file = identity_file
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self):
        if self.identity_file.exists():
            try:
                with open(self.identity_file, "r") as f:
                    self._data = json.load(f)
                logger.info("Loaded identity from %s", self.identity_file)
            except Exception as e:
                logger.error("Failed to load identity: %s", e)
                self._data = {}
        else:
            self._data = {}

    def save(self, device_id: int, token: str):
        self._data = {
            "device_id": device_id,
            "token": token
        }
        try:
            with open(self.identity_file, "w") as f:
                json.dump(self._data, f, indent=4)
            logger.info("Saved identity to %s", self.identity_file)
        except Exception as e:
            logger.error("Failed to save identity: %s", e)

    @property
    def device_id(self) -> Optional[int]:
        return self._data.get("device_id")

    @property
    def token(self) -> Optional[str]:
        return self._data.get("token")

    def exists(self) -> bool:
        return bool(self.device_id and self.token)
