from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional, Tuple

import cv2
import numpy as np
import torch
from torch import nn
from ultralytics import YOLO

NUM_KEYPOINTS = 17
DEFAULT_MASK_VALUE = -1.0


@dataclass
class DetectorConfig:
    yolo_model: str
    classifier_ckpt: str
    window: int = 20
    threshold: float = 0.8
    kpt_conf: float = 0.5


class GRUNet(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_layers: int):
        super().__init__()
        self.gru = nn.GRU(input_size=input_size, hidden_size=hidden_size, num_layers=num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        packed = nn.utils.rnn.pack_padded_sequence(x, lengths.cpu(), batch_first=True, enforce_sorted=False)
        _, h_n = self.gru(packed)
        return self.fc(h_n[-1]).squeeze(1)


class TrackState:
    def __init__(self, window: int):
        self.buffer: Deque[np.ndarray] = deque(maxlen=window)
        self.last_prob: float = 0.0
        self.last_label: str = "UNKNOWN"


def _normalize_xy_by_wh(feats: np.ndarray, width: int, height: int, mask_value: float) -> np.ndarray:
    out = feats.copy()
    x_idx = np.arange(0, out.shape[1], 2)
    y_idx = x_idx + 1
    x = out[:, x_idx]
    y = out[:, y_idx]
    x[x != mask_value] /= float(width)
    y[y != mask_value] /= float(height)
    out[:, x_idx] = x
    out[:, y_idx] = y
    return out


def _kpts_to_feat_row(kpts_xy: np.ndarray, kpts_conf: Optional[np.ndarray], conf_thr: float) -> np.ndarray:
    row = np.zeros((NUM_KEYPOINTS * 2,), dtype=np.float32)
    for i in range(NUM_KEYPOINTS):
        if kpts_conf is not None and float(kpts_conf[i]) < conf_thr:
            row[2 * i : 2 * i + 2] = 0.0
        else:
            row[2 * i] = float(kpts_xy[i, 0])
            row[2 * i + 1] = float(kpts_xy[i, 1])
    return row


class FallDetector:
    def __init__(self, cfg: DetectorConfig, device: Optional[str] = None):
        self.cfg = cfg
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        ckpt = torch.load(cfg.classifier_ckpt, map_location="cpu")
        model_cfg = ckpt.get("cfg", {})
        self.mask_value = float(ckpt.get("mask_value", DEFAULT_MASK_VALUE))
        self.model = GRUNet(
            input_size=int(model_cfg.get("input_size", NUM_KEYPOINTS * 2)),
            hidden_size=int(model_cfg.get("hidden_size", 64)),
            num_layers=int(model_cfg.get("num_layers", 1)),
        )
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.to(self.device)
        self.model.eval()
        self.yolo = YOLO(cfg.yolo_model)
        self.tracks: Dict[int, TrackState] = {}

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, list[dict]]:
        height, width = frame.shape[:2]
        results = self.yolo.track(frame, persist=True, verbose=False)
        detections: list[dict] = []
        if not results:
            return frame, detections
        r = results[0]
        if r.boxes is None or r.keypoints is None or r.boxes.xyxy is None:
            return frame, detections

        ids = r.boxes.id.detach().cpu().numpy().astype(np.int64) if r.boxes.id is not None else np.arange(int(r.boxes.xyxy.shape[0]))
        b_xyxy = r.boxes.xyxy.detach().cpu().numpy()
        k_xy = r.keypoints.xy.detach().cpu().numpy()
        k_conf = r.keypoints.conf.detach().cpu().numpy() if r.keypoints.conf is not None else None

        for i, tid in enumerate(ids):
            tid = int(tid)
            if tid not in self.tracks:
                self.tracks[tid] = TrackState(self.cfg.window)
            st = self.tracks[tid]
            kxy = k_xy[i][:NUM_KEYPOINTS].astype(np.float32, copy=False)
            kcf = k_conf[i][:NUM_KEYPOINTS].astype(np.float32, copy=False) if k_conf is not None else None
            row = _kpts_to_feat_row(kxy, kcf, self.cfg.kpt_conf).reshape(1, -1)
            st.buffer.append(_normalize_xy_by_wh(row, width, height, self.mask_value)[0])
            seq = np.stack(list(st.buffer), axis=0).astype(np.float32, copy=False)
            if seq.shape[0] < self.cfg.window:
                pad = np.full((self.cfg.window - seq.shape[0], seq.shape[1]), self.mask_value, dtype=np.float32)
                seq = np.concatenate([pad, seq], axis=0)

            x = torch.from_numpy(seq).unsqueeze(0).to(self.device)
            valid_row = ~(x == self.mask_value).all(dim=-1)
            lengths = torch.clamp(valid_row.sum(dim=1).to(torch.int64), min=1)
            x_filled = x.masked_fill(x == self.mask_value, 0.0)
            with torch.no_grad():
                prob = float(torch.sigmoid(self.model(x_filled, lengths)).item())
            label = "FALL" if prob >= self.cfg.threshold else "NORMAL"
            st.last_prob = prob
            st.last_label = label
            detections.append({"track_id": tid, "bbox": [float(v) for v in b_xyxy[i]], "label": label, "probability": prob})
            x1, y1, x2, y2 = [int(v) for v in b_xyxy[i]]
            color = (0, 0, 255) if label == "FALL" else (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"id={tid} {label} {prob:.2f}", (x1, max(0, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        return frame, detections
