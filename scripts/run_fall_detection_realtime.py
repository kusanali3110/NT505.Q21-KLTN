import argparse
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch
from torch import nn
from ultralytics import YOLO


NUM_KEYPOINTS = 17  # COCO17
DEFAULT_MASK_VALUE = -1.0

# COCO-17 skeleton edges (0-indexed). Works for Ultralytics pose models.
COCO17_EDGES = [
    (0, 1),
    (0, 2),
    (1, 3),
    (2, 4),
    (5, 6),
    (5, 7),
    (7, 9),
    (6, 8),
    (8, 10),
    (5, 11),
    (6, 12),
    (11, 12),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Realtime fall detection: YOLO pose + tracking + GRU/LSTM classifier."
    )
    p.add_argument("--video", type=str, required=True, help="Path to input video.")
    p.add_argument(
        "--yolo-model",
        type=str,
        default=None,
        help="Path/name of YOLO pose model (e.g. models/yolo26n-pose.torchscript or yolo26n-pose.pt).",
    )
    p.add_argument(
        "--classifier",
        type=str,
        choices=["gru", "lstm"],
        default="gru",
        help="Sequence classifier type (default: gru).",
    )
    p.add_argument(
        "--ckpt",
        type=str,
        default=None,
        help="Path to classifier checkpoint (.pt). If omitted, will auto-pick from ./models/.",
    )
    p.add_argument("--device", type=str, default=None, help="cpu|cuda (default: auto)")
    p.add_argument("--window", type=int, default=20, help="Sequence length window.")
    p.add_argument("--threshold", type=float, default=0.8, help="Fall threshold on probability.")
    p.add_argument("--budget-ms", type=float, default=50.0, help="YOLO inference budget per frame.")
    p.add_argument("--kpt-conf", type=float, default=0.5, help="Keypoint confidence threshold.")
    p.add_argument(
        "--yolo-conf",
        type=float,
        default=0.25,
        help="YOLO detection confidence threshold (used for tracking).",
    )
    p.add_argument(
        "--yolo-iou",
        type=float,
        default=0.7,
        help="YOLO NMS IoU threshold (used for tracking).",
    )
    p.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="YOLO inference image size (smaller -> faster, larger -> more accurate).",
    )
    p.add_argument(
        "--missing",
        type=str,
        choices=["minus1", "reuse"],
        default="minus1",
        help="When a track is missing on a frame, append -1 row or reuse previous row.",
    )
    p.add_argument(
        "--tracker",
        type=str,
        default="botsort.yaml",
        help="Ultralytics tracker config (e.g., botsort.yaml, bytetrack.yaml).",
    )
    p.add_argument("--show-fps", action="store_true", help="Overlay display FPS + yolo timing.")
    return p.parse_args()


def pick_device(device_arg: Optional[str]) -> torch.device:
    if device_arg is not None:
        return torch.device(device_arg)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def normalize_xy_by_wh(feats: np.ndarray, width: int, height: int, mask_value: float) -> np.ndarray:
    """
    feats: (T, F) where F=34 = [x0,y0,x1,y1,...]
    Keep mask_value as mask_value. Normalize x,y where value != mask_value.
    """
    out = feats.copy()
    if width <= 0 or height <= 0:
        return out
    x_idx = np.arange(0, out.shape[1], 2)
    y_idx = x_idx + 1
    x = out[:, x_idx]
    y = out[:, y_idx]
    x_mask = x != mask_value
    y_mask = y != mask_value
    x[x_mask] = x[x_mask] / float(width)
    y[y_mask] = y[y_mask] / float(height)
    out[:, x_idx] = x
    out[:, y_idx] = y
    return out


def kpts_to_feat_row(
    kpts_xy: np.ndarray,
    kpts_conf: Optional[np.ndarray],
    kpt_conf_thr: float,
) -> np.ndarray:
    """
    Convert (K,2) keypoints to a (F,) row where F=K*2, applying the same
    conventions as training:
    - if keypoint conf < threshold -> store (0,0)
    """
    row = np.zeros((NUM_KEYPOINTS * 2,), dtype=np.float32)
    for i in range(NUM_KEYPOINTS):
        if kpts_conf is not None and float(kpts_conf[i]) < kpt_conf_thr:
            row[2 * i] = 0.0
            row[2 * i + 1] = 0.0
        else:
            row[2 * i] = float(kpts_xy[i, 0])
            row[2 * i + 1] = float(kpts_xy[i, 1])
    return row


@dataclass
class GRUConfig:
    input_size: int
    hidden_size: int
    num_layers: int
    output_size: int = 1
    dropout_prob: float = 0.0


class GRUNet(nn.Module):
    def __init__(self, cfg: GRUConfig):
        super().__init__()
        self.gru = nn.GRU(
            input_size=cfg.input_size,
            hidden_size=cfg.hidden_size,
            num_layers=cfg.num_layers,
            batch_first=True,
            dropout=cfg.dropout_prob if cfg.num_layers > 1 else 0.0,
            bidirectional=False,
        )
        self.fc = nn.Linear(cfg.hidden_size, cfg.output_size)

    def forward(self, x: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        packed = nn.utils.rnn.pack_padded_sequence(
            x, lengths.cpu(), batch_first=True, enforce_sorted=False
        )
        _, h_n = self.gru(packed)
        last = h_n[-1]
        logits = self.fc(last)
        return logits.squeeze(1)


@dataclass
class LSTMConfig:
    input_size: int
    hidden_size: int
    num_layers: int
    output_size: int = 1
    dropout_prob: float = 0.0


class LSTMNet(nn.Module):
    def __init__(self, cfg: LSTMConfig):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=cfg.input_size,
            hidden_size=cfg.hidden_size,
            num_layers=cfg.num_layers,
            batch_first=True,
            dropout=cfg.dropout_prob if cfg.num_layers > 1 else 0.0,
            bidirectional=False,
        )
        self.fc = nn.Linear(cfg.hidden_size, cfg.output_size)

    def forward(self, x: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        packed = nn.utils.rnn.pack_padded_sequence(
            x, lengths.cpu(), batch_first=True, enforce_sorted=False
        )
        _, (h_n, _) = self.lstm(packed)
        last = h_n[-1]
        logits = self.fc(last)
        return logits.squeeze(1)


def load_classifier(
    classifier: str, ckpt_path: Path, device: torch.device
) -> Tuple[nn.Module, float, Dict]:
    ckpt = torch.load(str(ckpt_path), map_location="cpu")
    cfg_dict = ckpt.get("cfg") or ckpt.get("cfg", {})
    mask_value = float(ckpt.get("mask_value", DEFAULT_MASK_VALUE))

    if classifier == "gru":
        cfg = GRUConfig(
            input_size=int(cfg_dict["input_size"]),
            hidden_size=int(cfg_dict["hidden_size"]),
            num_layers=int(cfg_dict["num_layers"]),
            output_size=int(cfg_dict.get("output_size", 1)),
            dropout_prob=float(cfg_dict.get("dropout_prob", 0.0)),
        )
        model = GRUNet(cfg)
    else:
        cfg = LSTMConfig(
            input_size=int(cfg_dict["input_size"]),
            hidden_size=int(cfg_dict["hidden_size"]),
            num_layers=int(cfg_dict["num_layers"]),
            output_size=int(cfg_dict.get("output_size", 1)),
            dropout_prob=float(cfg_dict.get("dropout_prob", 0.0)),
        )
        model = LSTMNet(cfg)

    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device)
    model.eval()
    return model, mask_value, ckpt


def compute_lengths_and_mask(x: torch.Tensor, mask_value: float) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    x: (B,T,F) with mask_value for invalid timesteps.
    Returns:
      x_filled: (B,T,F) where mask_value -> 0
      lengths: (B,) >=1
    """
    valid_row = ~(x == mask_value).all(dim=-1)
    lengths = valid_row.sum(dim=1).to(torch.int64)
    lengths = torch.clamp(lengths, min=1)
    x_filled = x.masked_fill(x == mask_value, 0.0)
    return x_filled, lengths


@dataclass
class TrackState:
    buffer: "Deque[np.ndarray]"
    last_bbox_xyxy: Optional[np.ndarray] = None
    last_kpts_xy: Optional[np.ndarray] = None  # (K,2) pixel coords
    last_kpts_conf: Optional[np.ndarray] = None  # (K,)
    last_prob: float = 0.0
    last_label: str = "UNKNOWN"
    last_seen_frame_idx: int = -1


def draw_skeleton(frame: np.ndarray, kpts_xy: np.ndarray, kpts_conf: Optional[np.ndarray], conf_thr: float) -> None:
    # draw edges
    for a, b in COCO17_EDGES:
        if a >= kpts_xy.shape[0] or b >= kpts_xy.shape[0]:
            continue
        xa, ya = kpts_xy[a]
        xb, yb = kpts_xy[b]
        if (xa <= 0 and ya <= 0) or (xb <= 0 and yb <= 0):
            continue
        if kpts_conf is not None:
            if float(kpts_conf[a]) < conf_thr or float(kpts_conf[b]) < conf_thr:
                continue
        cv2.line(frame, (int(xa), int(ya)), (int(xb), int(yb)), (0, 255, 255), 2)
    # draw keypoints
    for i in range(kpts_xy.shape[0]):
        x, y = kpts_xy[i]
        if x <= 0 and y <= 0:
            continue
        if kpts_conf is not None and float(kpts_conf[i]) < conf_thr:
            continue
        cv2.circle(frame, (int(x), int(y)), 3, (0, 255, 0), -1)


def clamp_xyxy(xyxy: np.ndarray, width: int, height: int) -> np.ndarray:
    x1, y1, x2, y2 = [float(v) for v in xyxy]
    x1 = max(0.0, min(x1, width - 1.0))
    x2 = max(0.0, min(x2, width - 1.0))
    y1 = max(0.0, min(y1, height - 1.0))
    y2 = max(0.0, min(y2, height - 1.0))
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return np.asarray([x1, y1, x2, y2], dtype=np.float32)


def project_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def pick_default_ckpt(models_dir: Path, classifier: str) -> Optional[Path]:
    # common naming in this repo
    candidates = [
        models_dir / f"{classifier}_pose_masked.pt",
        models_dir / f"{classifier}_pose.pt",
        models_dir / f"{classifier}.pt",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def pick_default_yolo_pose_model(models_dir: Path) -> Optional[Path]:
    # Prefer exported deployment formats if present
    patterns = [
        "*pose*.engine",
        "*pose*.torchscript",
        "*pose*.onnx",
        "*pose*.pt",
    ]
    for pat in patterns:
        for p in sorted(models_dir.glob(pat)):
            if p.is_file():
                return p
    return None


def main() -> None:
    args = parse_args()
    video_path = Path(args.video)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    device = pick_device(args.device)

    project_root = project_root_from_script()
    models_dir = project_root / "models"

    # Auto-pick ckpt from ./models when not provided
    if args.ckpt is None:
        auto_ckpt = pick_default_ckpt(models_dir, args.classifier)
        if auto_ckpt is None:
            raise FileNotFoundError(
                f"Could not find a default {args.classifier} checkpoint under {models_dir}. "
                f"Please pass --ckpt explicitly."
            )
        args.ckpt = str(auto_ckpt)

    # Load classifier
    clf_model, mask_value, _ = load_classifier(args.classifier, Path(args.ckpt), device=device)

    # Load YOLO pose model
    if args.yolo_model is None:
        auto_yolo = pick_default_yolo_pose_model(models_dir)
        yolo_model_name = str(auto_yolo) if auto_yolo is not None else "yolo26n-pose.pt"
    else:
        yolo_model_name = args.yolo_model
    yolo = YOLO(str(yolo_model_name))

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if width <= 0 or height <= 0:
        raise RuntimeError("Could not read video width/height.")

    from collections import deque

    tracks: Dict[int, TrackState] = {}

    frame_idx = 0
    skip_yolo_frames = 0
    last_yolo_ms = 0.0

    last_display_t = time.perf_counter()
    disp_fps = 0.0
    max_stale_frames = 60  # drop tracks not seen for N frames

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        now_t = time.perf_counter()
        dt = now_t - last_display_t
        if dt > 0:
            disp_fps = 0.9 * disp_fps + 0.1 * (1.0 / dt) if disp_fps > 0 else (1.0 / dt)
        last_display_t = now_t

        detections: Dict[int, Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], np.ndarray]] = {}
        # track_id -> (bbox_xyxy, kpts_xy_pix(K,2), kpts_conf(K,) or None, feat_row_raw(F,))

        ran_yolo = False
        if skip_yolo_frames <= 0:
            t0 = time.perf_counter()
            results = yolo.track(
                frame,
                persist=True,
                verbose=False,
                tracker=args.tracker,
                conf=float(args.yolo_conf),
                iou=float(args.yolo_iou),
                imgsz=int(args.imgsz),
            )
            t1 = time.perf_counter()
            last_yolo_ms = (t1 - t0) * 1000.0
            ran_yolo = True

            # If YOLO is slow, schedule skipping for future frames to maintain ~20fps logic.
            if last_yolo_ms > float(args.budget_ms):
                extra = int(np.ceil(last_yolo_ms / float(args.budget_ms))) - 1
                skip_yolo_frames = max(skip_yolo_frames, extra)

            if results and len(results) > 0:
                r = results[0]
                boxes = r.boxes
                kpts = r.keypoints
                if boxes is not None and kpts is not None and boxes.xyxy is not None:
                    ids = None
                    if boxes.id is not None:
                        ids = boxes.id.detach().cpu().numpy().astype(np.int64)
                    else:
                        # no tracking id -> use index as pseudo-id for this frame
                        ids = np.arange(int(boxes.xyxy.shape[0]), dtype=np.int64)

                    b_xyxy = boxes.xyxy.detach().cpu().numpy()
                    k_xy = kpts.xy.detach().cpu().numpy()  # (N,K,2)
                    k_conf = None
                    if kpts.conf is not None:
                        k_conf = kpts.conf.detach().cpu().numpy()  # (N,K)

                    n = min(len(ids), b_xyxy.shape[0], k_xy.shape[0])
                    for i in range(n):
                        tid = int(ids[i])
                        bbox = clamp_xyxy(b_xyxy[i], width, height)
                        kxy = k_xy[i][:NUM_KEYPOINTS].astype(np.float32, copy=False)
                        kcf = k_conf[i][:NUM_KEYPOINTS].astype(np.float32, copy=False) if k_conf is not None else None
                        feat_row_raw = kpts_to_feat_row(kxy, kcf, float(args.kpt_conf))
                        detections[tid] = (bbox, kxy, kcf, feat_row_raw)
        else:
            skip_yolo_frames -= 1

        # Update track buffers (for all known tracks + current detections)
        seen_ids = set(detections.keys())
        known_ids = set(tracks.keys())
        all_ids = seen_ids | known_ids

        for tid in all_ids:
            if tid not in tracks:
                tracks[tid] = TrackState(buffer=deque(maxlen=int(args.window)))
            st = tracks[tid]

            if tid in detections:
                bbox, kxy, kcf, feat_raw = detections[tid]
                st.last_bbox_xyxy = bbox
                st.last_kpts_xy = kxy
                st.last_kpts_conf = kcf
                st.last_seen_frame_idx = frame_idx
                row = feat_raw.reshape(1, -1)
                row_norm = normalize_xy_by_wh(row, width, height, mask_value=mask_value)[0]
                st.buffer.append(row_norm.astype(np.float32, copy=False))
            else:
                if args.missing == "reuse" and len(st.buffer) > 0:
                    st.buffer.append(st.buffer[-1].copy())
                else:
                    st.buffer.append(np.full((NUM_KEYPOINTS * 2,), mask_value, dtype=np.float32))

        # Classifier inference per track
        for tid, st in list(tracks.items()):
            if len(st.buffer) == 0:
                continue
            seq = np.stack(list(st.buffer), axis=0).astype(np.float32, copy=False)  # (T,F)

            # pad to window (left-pad with mask_value)
            if seq.shape[0] < int(args.window):
                pad = np.full((int(args.window) - seq.shape[0], seq.shape[1]), mask_value, dtype=np.float32)
                seq = np.concatenate([pad, seq], axis=0)

            x = torch.from_numpy(seq).unsqueeze(0).to(device)  # (1,T,F)
            x_filled, lengths = compute_lengths_and_mask(x, mask_value=mask_value)
            with torch.no_grad():
                logits = clf_model(x_filled, lengths)
                prob = float(torch.sigmoid(logits).item())
            st.last_prob = prob
            st.last_label = "FALL" if prob >= float(args.threshold) else "NORMAL"

        # Drop stale tracks to prevent unbounded growth
        for tid in list(tracks.keys()):
            st = tracks[tid]
            if st.last_seen_frame_idx >= 0 and (frame_idx - st.last_seen_frame_idx) > max_stale_frames:
                del tracks[tid]

        # Draw overlay
        for tid, st in tracks.items():
            if st.last_bbox_xyxy is not None:
                x1, y1, x2, y2 = st.last_bbox_xyxy
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 2)
                text = f"id={tid} {st.last_label} {st.last_prob:.2f}"
                cv2.putText(
                    frame,
                    text,
                    (int(x1), max(0, int(y1) - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255) if st.last_label == "FALL" else (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )
            if st.last_kpts_xy is not None:
                draw_skeleton(frame, st.last_kpts_xy, st.last_kpts_conf, float(args.kpt_conf))

        if args.show_fps:
            status = "YOLO" if ran_yolo else "REUSE"
            cv2.putText(
                frame,
                f"disp_fps={disp_fps:.1f} yolo_ms={last_yolo_ms:.1f} mode={status} skip={skip_yolo_frames}",
                (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

        cv2.imshow("Fall Detection (YOLO-Pose + RNN)", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 27 or key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

