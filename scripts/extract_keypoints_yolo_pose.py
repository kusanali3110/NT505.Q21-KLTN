import os
import shutil
import logging
from pathlib import Path
import csv
from typing import List

import cv2
import numpy as np
import torch
from ultralytics import YOLO


# Target sampling rate: one frame every 50 ms (20 FPS)
FRAME_INTERVAL_SECONDS = 0.05
TARGET_FPS = 1.0 / FRAME_INTERVAL_SECONDS  # 20.0

# Number of pose keypoints produced by yolo26n-pose.pt.
# YOLOv8 pose models (like yolo26n-pose) use 17 COCO keypoints.
NUM_KEYPOINTS = 17
KPT_CONF_THRESHOLD = 0.5

# Base model checkpoint name used for export if no deployment model exists.
MODEL_NAME = "yolo26n-pose.pt"

# Export formats to create automatically if missing.
# You can change this list, e.g. ["torchscript"] or ["onnx", "torchscript"].
EXPORT_FORMATS = ["torchscript"]

# Inference backend priority. The script will try these formats in order
# when selecting which exported model to use.
INFERENCE_FORMAT_PRIORITY = ["torchscript"]

# File suffix mapping for key Ultralytics export formats we care about.
FORMAT_SUFFIX = {
    "onnx": ".onnx",
    "engine": ".engine",      # TensorRT
    "torchscript": ".torchscript",
}


logger = logging.getLogger(__name__)


def get_sample_frame_indices(frame_count: int, fps: float) -> List[int]:
    """
    Compute frame indices to sample at ~20 FPS (every 50 ms) based on the
    video's native FPS and total frame count.
    """
    if frame_count <= 0:
        return []

    if fps is None or fps <= 0:
        # FPS is unknown; fall back to using every frame.
        return list(range(frame_count))

    duration = frame_count / fps
    if duration <= 0:
        return []

    num_samples = int(duration / FRAME_INTERVAL_SECONDS) + 1
    indices = set()

    for i in range(num_samples):
        t = i * FRAME_INTERVAL_SECONDS
        frame_idx = int(round(t * fps))
        if 0 <= frame_idx < frame_count:
            indices.add(frame_idx)

    return sorted(indices)


def build_header() -> List[str]:
    """
    Build CSV header: sequence, frame, then (x, y) for each keypoint.
    """
    header = ["sequence", "frame"]
    for k in range(NUM_KEYPOINTS):
        header.append(f"kpt_{k}_x")
        header.append(f"kpt_{k}_y")
    return header


def extract_keypoints_from_frame(results, num_keypoints: int) -> List[float]:
    """
    Extract (x, y) for one person from YOLO pose results.
    If no person is detected, return [-1, -1, ...].
    """
    if results is None or len(results) == 0:
        return [-1.0] * (num_keypoints * 2)

    result = results[0]

    # If there are no detected keypoints/persons, return -1.
    if result.keypoints is None or result.keypoints.data.shape[0] == 0:
        return [-1.0] * (num_keypoints * 2)

    # Select the person with highest box confidence, if boxes exist.
    person_index = 0
    if result.boxes is not None and result.boxes.conf is not None and len(result.boxes.conf) > 0:
        confs = result.boxes.conf.cpu().numpy()
        person_index = int(np.argmax(confs))

    kpts_xy = result.keypoints.xy[person_index].cpu().numpy()  # (num_kpts, 2)
    kpts_conf = None
    if result.keypoints.conf is not None:
        kpts_conf = result.keypoints.conf[person_index].cpu().numpy()  # (num_kpts,)

    # Ensure we only use the expected number of keypoints.
    kpts_xy = kpts_xy[:num_keypoints]
    if kpts_conf is not None:
        kpts_conf = kpts_conf[:num_keypoints]

    # If confidence exists and ALL keypoints are below threshold,
    # treat as "cannot be extracted" for this frame.
    if kpts_conf is not None and np.all(kpts_conf < KPT_CONF_THRESHOLD):
        return [-1.0] * (num_keypoints * 2)

    row: List[float] = []
    for i in range(num_keypoints):
        if kpts_conf is not None and float(kpts_conf[i]) < KPT_CONF_THRESHOLD:
            # Human detected but this keypoint is unreliable -> use 0.
            row.extend([0.0, 0.0])
        else:
            x, y = float(kpts_xy[i, 0]), float(kpts_xy[i, 1])
            row.extend([x, y])

    return row


def process_video(
    model: YOLO,
    video_path: Path,
    output_dir: Path,
    split_name: str,
) -> None:
    """
    Extract pose keypoints from a single video and save them to a CSV file.
    The CSV will be saved in output_dir with the same base name as the video.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.error("Failed to open video: %s", video_path)
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    frame_indices = get_sample_frame_indices(frame_count, fps)
    if not frame_indices:
        cap.release()
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    sequence_name = video_path.stem
    csv_path = output_dir / f"{sequence_name}.csv"

    header = build_header()

    logger.info(
        "Processing video '%s' (frames=%d, fps=%.2f) -> sampling %d frames, output=%s",
        sequence_name,
        frame_count,
        fps if fps is not None else -1.0,
        len(frame_indices),
        csv_path,
    )

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)

        total_samples = len(frame_indices)
        for i, frame_idx in enumerate(frame_indices, start=1):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                logger.warning(
                    "Failed to read frame %d (index=%d) from '%s'",
                    i,
                    frame_idx,
                    sequence_name,
                )
                continue

            # Run pose inference.
            results = model(frame, verbose=False)

            kpt_values = extract_keypoints_from_frame(results, NUM_KEYPOINTS)
            if all(v == -1.0 for v in kpt_values):
                logger.debug(
                    "No detection for sequence='%s', frame_index=%d",
                    sequence_name,
                    frame_idx,
                )

            row = [sequence_name, frame_idx] + kpt_values
            writer.writerow(row)

            logger.info(
                "Sequence '%s': processed %d/%d sampled frames (current index=%d)",
                sequence_name,
                i,
                total_samples,
                frame_idx,
            )

    cap.release()
    logger.info("Finished processing video '%s'. CSV saved to %s", sequence_name, csv_path)


def collect_videos(folder: Path) -> List[Path]:
    """
    Collect video files recursively under a folder.
    """
    exts = {".mp4", ".avi", ".mov", ".mkv"}
    videos: List[Path] = []
    if not folder.exists():
        return videos

    for root, _, files in os.walk(folder):
        root_path = Path(root)
        for name in files:
            if Path(name).suffix.lower() in exts:
                videos.append(root_path / name)
    return sorted(videos)


def ensure_pose_models(project_root: Path) -> None:
    """
    Ensure that deployment models for yolo26n-pose exist under project_root / 'models'.
    If not, download the base .pt model and export to the formats defined in EXPORT_FORMATS.

    Reference: Ultralytics export docs for supported formats and arguments:
    https://docs.ultralytics.com/modes/export/#key-features-of-export-mode
    """
    models_dir = project_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    model_stem = Path(MODEL_NAME).stem

    # Determine which model files are already present for the requested formats.
    existing = {}
    for fmt in EXPORT_FORMATS:
        suffix = FORMAT_SUFFIX.get(fmt)
        if suffix is None:
            logger.warning("Unsupported export format '%s' in EXPORT_FORMATS, skipping.", fmt)
            continue
        target_path = models_dir / f"{model_stem}{suffix}"
        if target_path.is_file():
            existing[fmt] = target_path

    if existing and len(existing) == len(
        [f for f in EXPORT_FORMATS if FORMAT_SUFFIX.get(f) is not None]
    ):
        # All requested formats already exist.
        return

    logger.info(
        "No deployment models found for some formats (%s). "
        "Downloading base model '%s' and exporting...",
        ", ".join(fmt for fmt in EXPORT_FORMATS if fmt not in existing),
        MODEL_NAME,
    )

    # Download/load base .pt model (Ultralytics handles caching).
    base_model = YOLO(MODEL_NAME)

    # Export each requested format if missing.
    for fmt in EXPORT_FORMATS:
        suffix = FORMAT_SUFFIX.get(fmt)
        if suffix is None:
            continue

        target_path = models_dir / f"{model_stem}{suffix}"
        if target_path.is_file():
            logger.info("Export format '%s' already present at %s", fmt, target_path)
            continue

        # For TensorRT, only try if CUDA is available.
        if fmt == "engine" and not torch.cuda.is_available():
            logger.info(
                "Skipping TensorRT export because CUDA is not available. "
                "You can still run with other formats (e.g. ONNX or torchscript)."
            )
            continue

        try:
            logger.info("Exporting model to format='%s'...", fmt)
            exported_path = Path(
                base_model.export(
                    format=fmt,
                )
            )
            if exported_path.is_file():
                if exported_path.resolve() != target_path.resolve():
                    shutil.move(str(exported_path), str(target_path))
                logger.info("Saved %s model to: %s", fmt, target_path)
            else:
                logger.error(
                    "Expected exported model file not found after export. "
                    "Format='%s', returned path=%s",
                    fmt,
                    exported_path,
                )
        except Exception as e:
            logger.error("Export to format='%s' failed: %s", fmt, e)


def select_model_path(project_root: Path) -> Path:
    """
    Ensure pose models exist and then select a YOLO pose deployment model
    based on the current hardware and the preferred formats.

    Priority (INFERENCE_FORMAT_PRIORITY):
    1. TensorRT engine ('engine') on GPU if available
    2. ONNX ('onnx')
    3. TorchScript ('torchscript')
    """
    models_dir = project_root / "models"
    ensure_pose_models(project_root)

    model_stem = Path(MODEL_NAME).stem

    # Try formats in priority order.
    for fmt in INFERENCE_FORMAT_PRIORITY:
        suffix = FORMAT_SUFFIX.get(fmt)
        if suffix is None:
            continue

        # For TensorRT, only consider if CUDA is available.
        if fmt == "engine" and not torch.cuda.is_available():
            continue

        candidate = models_dir / f"{model_stem}{suffix}"
        if candidate.is_file():
            logger.info("Using %s model for inference: %s", fmt, candidate)
            return candidate

    raise FileNotFoundError(
        "No suitable YOLO pose model found for inference, and automatic export "
        "either failed or produced unsupported formats. "
        "Please verify that the base checkpoint exists and that export "
        "dependencies for your chosen formats are installed."
    )


def main() -> None:
    """
    Entry point: process fall and normal videos and save keypoints CSVs.
    """
    # Basic logging configuration. Adjust level to DEBUG for more verbosity.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    # Assume this script is in ./scripts and project root is one level up.
    script_path = Path(__file__).resolve()
    project_root = script_path.parents[1]

    # Input video directories.
    raw_videos_root = project_root / "dataset" / "raw_videos"
    fall_videos_dir = raw_videos_root / "fall"
    normal_videos_dir = raw_videos_root / "normal"

    # Output keypoints directories (per user spec).
    extracted_root = project_root / "dataset" / "extracted_keypoints"
    fall_output_dir = extracted_root / "fall"
    normal_output_dir = extracted_root / "normal"

    # Load YOLO pose model in one of the exported deployment formats.
    model_path = select_model_path(project_root)
    model = YOLO(str(model_path))

    # Process fall videos.
    fall_videos = collect_videos(fall_videos_dir)
    for vp in fall_videos:
        process_video(model, vp, fall_output_dir, split_name="fall")

    # Process normal videos.
    normal_videos = collect_videos(normal_videos_dir)
    for vp in normal_videos:
        process_video(model, vp, normal_output_dir, split_name="normal")


if __name__ == "__main__":
    main()

