"""Run sensor-specific ByteTrack on PTS-indexed development clips."""

import argparse
import hashlib
import json
import os
import platform
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


CLASS_NAMES = {"V": ("smoke", "flame"), "T": ("hotspot",)}
COLORS = {"smoke": (210, 195, 40), "flame": (30, 130, 255), "hotspot": (40, 50, 230)}


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_sensor(clip, sensor, weights, evaluation, output, imgsz, device):
    import cv2
    from ultralytics import YOLO

    source = clip / sensor
    frames = json.loads((source / "frames.json").read_text(encoding="utf-8"))
    class_names = CLASS_NAMES[sensor]
    eval_classes = {row["class_name"]: row for row in evaluation["classes"]}
    thresholds = {}
    models = {}
    for cls, name in enumerate(class_names):
        entry = eval_classes[name]
        threshold = entry["work_threshold"]
        if threshold is None:
            raise ValueError(f"no precision-qualified development threshold: {sensor} {name}")
        thresholds[name] = threshold
        model = YOLO(str(weights))
        for module in model.model.modules():
            if type(module).__name__ == "GELU" and not hasattr(module, "approximate"):
                module.approximate = "none"
        models[cls] = model
    rows = []
    trajectories = defaultdict(list)
    untracked = Counter()
    writer = None
    output.mkdir(parents=True)
    for index, entry in enumerate(frames):
        image_path = source / entry["frame_file"]
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"frame unreadable: {image_path}")
        height, width = image.shape[:2]
        if writer is None:
            writer = cv2.VideoWriter(str(output / "tracked.mp4"), cv2.VideoWriter_fourcc(*"mp4v"),
                                     5.0, (width, height))
            if not writer.isOpened():
                raise RuntimeError("tracked video writer failed")
        detections = []
        for cls, name in enumerate(class_names):
            result = models[cls].track(source=str(image_path), persist=True, tracker="bytetrack.yaml",
                                       conf=thresholds[name], iou=0.7, imgsz=imgsz, device=device,
                                       classes=[cls], max_det=300, verbose=False, save=False)[0]
            boxes = result.boxes
            coords = boxes.xyxy.cpu().tolist()
            confidences = boxes.conf.cpu().tolist()
            track_ids = boxes.id.cpu().tolist() if boxes.id is not None else [None] * len(coords)
            for xyxy, confidence, track_id in zip(coords, confidences, track_ids):
                identifier = f"{sensor}_{name}_{int(track_id)}" if track_id is not None else None
                if identifier is None:
                    untracked[name] += 1
                elif identifier in {row["track_id"] for row in detections}:
                    raise ValueError(f"track assigned twice in frame: {image_path}: {identifier}")
                x1, y1, x2, y2 = xyxy
                source_point = ([(x1 + x2) / (2 * width), y2 / height]
                                if name == "flame" else None)
                detection = {"class_id": cls, "class_name": name,
                             "confidence": confidence, "track_id": identifier,
                             "bbox_xyxy_px": xyxy,
                             "source_point_image_normalized": source_point,
                             "source_point_method": "flame_bbox_bottom_midpoint_candidate" if source_point else None,
                             "absolute_coordinate": None,
                             "absolute_coordinate_unavailable_reason": "Matrice 4T calibration and verified ground correspondence missing"}
                detections.append(detection)
                if identifier:
                    trajectories[identifier].append({"frame_index": index,
                                                     "decoded_pts_s": entry["decoded_pts_s"],
                                                     "bbox_xyxy_px": xyxy})
                cv2.rectangle(image, (round(x1), round(y1)), (round(x2), round(y2)), COLORS[name], 2)
                cv2.putText(image, f"{name} {identifier or '-'} {confidence:.2f}",
                            (round(x1), max(18, round(y1) - 5)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.55, COLORS[name], 2, cv2.LINE_AA)
        if len([row["track_id"] for row in detections if row["track_id"]]) != len(
                {row["track_id"] for row in detections if row["track_id"]}):
            raise ValueError(f"duplicate track id in one frame: {image_path}")
        cv2.putText(image, f"PTS {entry['decoded_pts_s']:.3f}s", (18, height - 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
        writer.write(image)
        rows.append({"frame_index": index, "frame_file": entry["frame_file"],
                     "decoded_pts_s": entry["decoded_pts_s"], "detections": detections})
    if writer:
        writer.release()
    summary = {"sensor": sensor, "frames": len(rows), "tracks": len(trajectories),
               "tracked_detections": sum(len(track) for track in trajectories.values()),
               "untracked_detections": dict(untracked),
               "tracks_with_multiple_frames": sum(len(track) > 1 for track in trajectories.values()),
               "classes": dict(Counter(row["class_name"] for frame in rows for row in frame["detections"])),
               "identity_switches": None, "identity_switches_unavailable_reason": "no human track identity ground truth",
               "source_point_pixel_error": None,
               "source_point_pixel_error_unavailable_reason": "no human ground burning source point ground truth"}
    write_json(output / "detections.json", {"sensor": sensor, "rows": rows})
    write_json(output / "tracks.json", {"sensor": sensor, "tracks": dict(trajectories), "summary": summary})
    return summary


def run(args):
    os.environ["WANDB_MODE"] = "disabled"
    os.environ["WANDB_DISABLED"] = "true"
    os.environ["COMET_MODE"] = "DISABLED"
    if args.output.exists():
        raise FileExistsError(args.output)
    if not args.clip.is_dir():
        raise FileNotFoundError(args.clip)
    manifest = json.loads((args.clip / "manifest.json").read_text(encoding="utf-8"))
    if not manifest["paired_frames"]:
        raise ValueError("clip contains no time pairs")
    project = Path(__file__).resolve().parents[1] / "projects" / "ultralytics"
    sys.path.insert(0, str(project))
    import torch
    import ultralytics

    args.output.mkdir(parents=True)
    summaries = {}
    for sensor, weights, evaluation, imgsz, device in (
            ("V", args.v_weights, args.v_evaluation, args.v_imgsz, args.v_device),
            ("T", args.t_weights, args.t_evaluation, args.t_imgsz, args.t_device)):
        result = json.loads(evaluation.read_text(encoding="utf-8"))
        if result["status"] != "complete" or result["sensor"] != sensor or result["weights_sha256"] != digest(weights):
            raise ValueError(f"evaluation and weights disagree: {sensor}")
        summaries[sensor] = run_sensor(args.clip, sensor, weights, result,
                                       args.output / sensor, imgsz, device)
    write_json(args.output / "manifest.json", {
        "schema_version": "dji_recovery_provisional_tracking_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_clip": str(args.clip), "source_clip_manifest_sha256": digest(args.clip / "manifest.json"),
        "method": "per-sensor per-class Ultralytics ByteTrack; persistent state across decoded frames",
        "time_pairing": "source clip PTS pairs; same physical target unverified",
        "weights": {"V": {"path": str(args.v_weights), "sha256": digest(args.v_weights)},
                    "T": {"path": str(args.t_weights), "sha256": digest(args.t_weights)}},
        "development_evaluations": {"V": str(args.v_evaluation), "T": str(args.t_evaluation)},
        "summaries": summaries,
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "torch": torch.__version__, "ultralytics": ultralytics.__version__},
        "absolute_visual_localization": "unavailable"})
    print(json.dumps({"output": str(args.output), "summaries": summaries}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--v-weights", type=Path, required=True)
    parser.add_argument("--t-weights", type=Path, required=True)
    parser.add_argument("--v-evaluation", type=Path, required=True)
    parser.add_argument("--t-evaluation", type=Path, required=True)
    parser.add_argument("--v-imgsz", type=int, required=True)
    parser.add_argument("--t-imgsz", type=int, required=True)
    parser.add_argument("--v-device", default="0")
    parser.add_argument("--t-device", default="1")
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())
