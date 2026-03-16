import argparse
import csv
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - optional dependency
    plt = None


logger = logging.getLogger(__name__)


VIDEO_EXTS = (".mp4", ".avi", ".mov", ".mkv", ".m4v", ".webm")


@dataclass(frozen=True)
class WindowConfig:
    window: int = 20
    stride: int = 5
    sample_interval_s: float = 0.05  # 20 FPS target in extractor


def discover_extracted_root(project_root: Path, override: Optional[Path] = None) -> Path:
    if override is not None:
        return override
    candidates = [
        project_root / "dataset" / "extracted_keypoints",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Default to the (more likely) plural path even if it doesn't exist yet.
    return candidates[0]


def list_csvs(extracted_root: Path, split: str) -> List[Path]:
    split_dir = extracted_root / split
    if not split_dir.exists():
        return []
    return sorted([p for p in split_dir.glob("*.csv") if p.is_file()])


def read_keypoint_csv(csv_path: Path) -> Tuple[str, np.ndarray, np.ndarray, List[str]]:
    """
    Returns:
      - sequence_name (string)
      - frames: int64 array shape (T,)
      - feats: float32 array shape (T, F)
      - feature_names: list[str] length F
    """
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        if len(header) < 3 or header[0] != "sequence" or header[1] != "frame":
            raise ValueError(f"Unexpected CSV header in {csv_path}: {header[:5]}")

        feature_names = header[2:]
        frames: List[int] = []
        feats: List[List[float]] = []
        seq_name: Optional[str] = None

        for row in reader:
            if not row:
                continue
            if seq_name is None:
                seq_name = row[0]
            frames.append(int(float(row[1])))
            feats.append([float(x) for x in row[2:]])

    if seq_name is None:
        raise ValueError(f"Empty CSV: {csv_path}")

    frames_arr = np.asarray(frames, dtype=np.int64)
    feats_arr = np.asarray(feats, dtype=np.float32)
    return seq_name, frames_arr, feats_arr, feature_names


def build_raw_video_index(raw_root: Path) -> Dict[str, Path]:
    """
    Index all videos under raw_root by their stem (basename without extension).
    If duplicates exist, the last one encountered wins.
    """
    index: Dict[str, Path] = {}
    if not raw_root.exists():
        return index

    for root, _, files in os.walk(raw_root):
        for name in files:
            if name.lower().endswith(VIDEO_EXTS):
                p = Path(root) / name
                index[p.stem] = p
    return index


def get_video_wh(video_path: Path) -> Optional[Tuple[int, int, float, int]]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    if w <= 0 or h <= 0:
        return None
    return w, h, fps, n


def expected_sample_indices(frame_count: int, fps: float, interval_s: float) -> List[int]:
    if frame_count <= 0:
        return []
    if fps <= 0:
        # Unknown FPS: fall back to using every frame index.
        return list(range(frame_count))

    duration = frame_count / fps
    if duration <= 0:
        return []

    num_samples = int(duration / interval_s) + 1
    indices = set()
    for i in range(num_samples):
        t = i * interval_s
        idx = int(round(t * fps))
        if 0 <= idx < frame_count:
            indices.add(idx)
    return sorted(indices)


def densify_to_expected_frames(
    frames: np.ndarray,
    feats: np.ndarray,
    expected_frames: Optional[List[int]],
    fill_value: float = -1.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Align features onto expected sampled frames. If expected_frames is None,
    returns original (sorted by frame).
    """
    order = np.argsort(frames)
    frames = frames[order]
    feats = feats[order]

    if expected_frames is None or len(expected_frames) == 0:
        return frames, feats

    frame_to_row = {int(frames[i]): i for i in range(frames.shape[0])}
    dense_feats = np.full((len(expected_frames), feats.shape[1]), fill_value, dtype=np.float32)
    dense_frames = np.asarray(expected_frames, dtype=np.int64)

    for i, fr in enumerate(expected_frames):
        j = frame_to_row.get(int(fr))
        if j is not None:
            dense_feats[i] = feats[j]

    return dense_frames, dense_feats


def normalize_xy_by_wh(feats: np.ndarray, width: int, height: int) -> np.ndarray:
    """
    Features are [kpt0_x, kpt0_y, kpt1_x, kpt1_y, ...].
    Keep -1 as -1. Only normalize x,y where value != -1.
    """
    out = feats.copy()
    if width <= 0 or height <= 0:
        return out

    # x at even indices, y at odd indices.
    x_idx = np.arange(0, out.shape[1], 2)
    y_idx = x_idx + 1

    x = out[:, x_idx]
    y = out[:, y_idx]

    x_mask = x != -1.0
    y_mask = y != -1.0

    x[x_mask] = x[x_mask] / float(width)
    y[y_mask] = y[y_mask] / float(height)

    out[:, x_idx] = x
    out[:, y_idx] = y
    return out


def make_windows(
    seq_name: str,
    frames: np.ndarray,
    feats: np.ndarray,
    label: int,
    cfg: WindowConfig,
) -> Tuple[List[np.ndarray], List[int], List[str], List[int]]:
    """
    Returns:
      - windows: list of (window, F) arrays
      - labels: list of int
      - seq_ids: list of str
      - start_frames: list of int
    """
    T = feats.shape[0]
    windows: List[np.ndarray] = []
    labels: List[int] = []
    seq_ids: List[str] = []
    start_frames: List[int] = []

    if T < cfg.window:
        # Pad a single window to length cfg.window by repeating the last frame.
        padded = np.empty((cfg.window, feats.shape[1]), dtype=np.float32)
        padded[:T] = feats
        padded[T:] = feats[T - 1]  # repeat last valid frame
        windows.append(padded)
        labels.append(int(label))
        seq_ids.append(seq_name)
        start_frames.append(int(frames[0]))
        return windows, labels, seq_ids, start_frames

    for start in range(0, T - cfg.window + 1, cfg.stride):
        end = start + cfg.window
        windows.append(feats[start:end].astype(np.float32, copy=False))
        labels.append(int(label))
        seq_ids.append(seq_name)
        start_frames.append(int(frames[start]))

    return windows, labels, seq_ids, start_frames


def run_eda_plots(
    X: np.ndarray,
    y: np.ndarray,
    out_dir: Path,
) -> None:
    """
    Generate simple EDA charts and save them as PNG files in out_dir.

    - Label distribution bar chart.
    - Per-feature mean (over all windows) line plot.
    """
    if plt is None:
        logger.warning("matplotlib is not available; skipping EDA plots.")
        return

    try:
        # Label distribution.
        unique, counts = np.unique(y, return_counts=True)
        fig, ax = plt.subplots()
        ax.bar([str(int(u)) for u in unique], counts)
        ax.set_xlabel("Label")
        ax.set_ylabel("Count")
        ax.set_title("Label distribution (0=normal, 1=fall)")
        fig.tight_layout()
        fig_path = out_dir / "eda_label_distribution.png"
        fig.savefig(fig_path)
        plt.close(fig)
        logger.info("Saved EDA label distribution plot to %s", fig_path)

        # Per-feature mean across all windows.
        feat_means = X.mean(axis=(0, 1))
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(np.arange(feat_means.shape[0]), feat_means)
        ax.set_xlabel("Feature index")
        ax.set_ylabel("Mean value")
        ax.set_title("Per-feature mean across all windows")
        fig.tight_layout()
        fig_path = out_dir / "eda_feature_means.png"
        fig.savefig(fig_path)
        plt.close(fig)
        logger.info("Saved EDA feature means plot to %s", fig_path)
    except Exception as e:
        logger.warning("Failed to generate EDA plots: %s", e)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare extracted keypoints for GRU training.")
    parser.add_argument("--project_root", type=str, default=None, help="Project root (defaults to script/..).")
    parser.add_argument("--extracted_root", type=str, default=None, help="Root folder of extracted CSVs.")
    parser.add_argument("--raw_root", type=str, default=None, help="Root folder of raw videos.")
    parser.add_argument("--window", type=int, default=20)
    parser.add_argument("--stride", type=int, default=5)
    parser.add_argument(
        "--out",
        type=str,
        default="dataset/dataset_ready",
        help="Output directory for GRU dataset (default: ./dataset/dataset_ready).",
    )
    parser.add_argument("--train_frac", type=float, default=0.7, help="Fraction of samples for training set.")
    parser.add_argument("--val_frac", type=float, default=0.2, help="Fraction of samples for validation set.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for shuffling before split.")
    parser.add_argument(
        "--eda",
        action="store_true",
        help="If set, generate basic EDA plots (label distribution, feature means) into the output directory.",
    )
    parser.add_argument("--log_level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    script_path = Path(__file__).resolve()
    project_root = Path(args.project_root).resolve() if args.project_root else script_path.parents[1]

    extracted_root = discover_extracted_root(project_root, Path(args.extracted_root).resolve() if args.extracted_root else None)
    raw_root = (Path(args.raw_root).resolve() if args.raw_root else (project_root / "dataset" / "raw_videos"))

    cfg = WindowConfig(window=int(args.window), stride=int(args.stride))

    out_dir = (project_root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "meta.json"

    logger.info("Project root: %s", project_root)
    logger.info("Extracted root: %s", extracted_root)
    logger.info("Raw videos root: %s", raw_root)
    logger.info("Window=%d, stride=%d", cfg.window, cfg.stride)
    logger.info("Output directory: %s", out_dir)

    raw_index = build_raw_video_index(raw_root)
    if not raw_index:
        logger.warning(
            "No raw videos found under %s. x,y normalization by (w,h) will be skipped.",
            raw_root,
        )

    splits = [("fall", 1), ("normal", 0)]

    all_windows: List[np.ndarray] = []
    all_labels: List[int] = []
    all_seq_ids: List[str] = []
    all_start_frames: List[int] = []
    feature_names: Optional[List[str]] = None

    per_split_stats = {}

    for split_name, label in splits:
        csvs = list_csvs(extracted_root, split_name)
        logger.info("Split '%s': found %d CSV files", split_name, len(csvs))
        split_windows = 0
        split_sequences = 0
        split_skipped = 0

        for csv_path in csvs:
            try:
                seq_name, frames, feats, feat_names = read_keypoint_csv(csv_path)
                if feature_names is None:
                    feature_names = feat_names
                elif feature_names != feat_names:
                    logger.warning("Feature header mismatch in %s. Proceeding anyway.", csv_path)

                expected_frames: Optional[List[int]] = None

                video_path = raw_index.get(seq_name)
                if video_path is not None:
                    wh = get_video_wh(video_path)
                    if wh is not None:
                        w, h, fps, n = wh
                        expected_frames = expected_sample_indices(n, fps, cfg.sample_interval_s)
                        feats = normalize_xy_by_wh(feats, w, h)
                    else:
                        logger.warning("Could not read video metadata for %s (%s). Skipping normalization.", seq_name, video_path)
                else:
                    logger.debug("No raw video found for sequence '%s' in %s", seq_name, raw_root)

                frames_d, feats_d = densify_to_expected_frames(frames, feats, expected_frames, fill_value=-1.0)

                windows, labels_list, seq_ids, start_frames = make_windows(
                    seq_name=seq_name,
                    frames=frames_d,
                    feats=feats_d,
                    label=label,
                    cfg=cfg,
                )

                if not windows:
                    logger.info("Skipping '%s' (too short: T=%d < window=%d)", seq_name, feats_d.shape[0], cfg.window)
                    split_skipped += 1
                    continue

                all_windows.extend(windows)
                all_labels.extend(labels_list)
                all_seq_ids.extend(seq_ids)
                all_start_frames.extend(start_frames)

                split_windows += len(windows)
                split_sequences += 1

                logger.info(
                    "Sequence '%s' (%s): T=%d -> windows=%d",
                    seq_name,
                    split_name,
                    feats_d.shape[0],
                    len(windows),
                )
            except Exception as e:
                logger.error("Failed processing %s: %s", csv_path, e)
                split_skipped += 1

        per_split_stats[split_name] = {
            "csv_files": len(csvs),
            "sequences_used": split_sequences,
            "sequences_skipped": split_skipped,
            "windows": split_windows,
            "label": label,
        }

    if feature_names is None:
        raise RuntimeError(f"No CSV files found under {extracted_root} for splits fall/normal.")

    X = np.stack(all_windows, axis=0).astype(np.float32, copy=False) if all_windows else np.zeros((0, cfg.window, len(feature_names)), dtype=np.float32)
    y = np.asarray(all_labels, dtype=np.int64)
    seq_id_arr = np.asarray(all_seq_ids, dtype=object)
    start_frame_arr = np.asarray(all_start_frames, dtype=np.int64)
    feature_names_arr = np.asarray(feature_names, dtype=object)

    logger.info("Final dataset (before split): X=%s, y=%s", X.shape, y.shape)

    # Optional EDA plots on the full dataset before splitting.
    if args.eda:
        run_eda_plots(X, y, out_dir)

    # Train/val/test split.
    n_samples = X.shape[0]
    if n_samples == 0:
        logger.warning("No samples generated; skipping save.")
        return

    train_frac = float(args.train_frac)
    val_frac = float(args.val_frac)
    if train_frac <= 0 or val_frac < 0 or train_frac + val_frac >= 1.0:
        raise ValueError(
            "Invalid train/val fractions. Require train_frac>0, val_frac>=0, train_frac+val_frac<1."
        )

    test_frac = 1 - train_frac - val_frac

    rng = np.random.default_rng(args.seed)
    indices = np.arange(n_samples, dtype=np.int64)
    rng.shuffle(indices)

    n_train = int(round(train_frac * n_samples))
    n_val = int(round(val_frac * n_samples))
    n_train = max(1, min(n_train, n_samples))
    n_val = max(0, min(n_val, n_samples - n_train))
    n_test = n_samples - n_train - n_val

    idx_train = indices[:n_train]
    idx_val = indices[n_train : n_train + n_val]
    idx_test = indices[n_train + n_val :]

    X_train, y_train = X[idx_train], y[idx_train]
    X_val, y_val = X[idx_val], y[idx_val]
    X_test, y_test = X[idx_test], y[idx_test]

    logger.info(
        "Split sizes: train=%d, val=%d, test=%d (total=%d)",
        X_train.shape[0],
        X_val.shape[0],
        X_test.shape[0],
        n_samples,
    )

    # Save per-split arrays in the requested format.
    np.save(out_dir / "X_train.npy", X_train)
    np.save(out_dir / "y_train.npy", y_train)
    np.save(out_dir / "X_val.npy", X_val)
    np.save(out_dir / "y_val.npy", y_val)
    np.save(out_dir / "X_test.npy", X_test)
    np.save(out_dir / "y_test.npy", y_test)

    # Also save auxiliary arrays for reference.
    np.save(out_dir / "seq_id.npy", seq_id_arr)
    np.save(out_dir / "start_frame.npy", start_frame_arr)
    np.save(out_dir / "feature_names.npy", feature_names_arr)

    meta = {
        "window": cfg.window,
        "stride": cfg.stride,
        "sample_interval_s": cfg.sample_interval_s,
        "extracted_root": str(extracted_root),
        "raw_root": str(raw_root),
        "out_dir": str(out_dir),
        "num_features": int(len(feature_names)),
        "num_samples": int(X.shape[0]),
        "train_frac": train_frac,
        "val_frac": val_frac,
        "test_frac": test_frac,
        "n_train": int(X_train.shape[0]),
        "n_val": int(X_val.shape[0]),
        "n_test": int(X_test.shape[0]),
        "splits": per_split_stats,
    }

    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("Saved train/val/test arrays under %s", out_dir)
    logger.info("Saved metadata to %s", meta_path)


if __name__ == "__main__":
    main()

