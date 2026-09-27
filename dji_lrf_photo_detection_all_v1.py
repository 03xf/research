#!/usr/bin/env python3
"""Run provisional V/T detection on all grouped LRF photos."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/home/member/xmy/xmy/code/projects/ultralytics")
from ultralytics import YOLO


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--observations", required=True, type=Path)
    ap.add_argument("--v-weights", required=True, type=Path)
    ap.add_argument("--t-weights", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--conf", type=float, default=.1)
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--device", default="0")
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit("output exists; refusing to overwrite")
    raw = json.loads(args.observations.read_text(encoding="utf-8"))
    models = {"V": YOLO(str(args.v_weights)), "T": YOLO(str(args.t_weights))}
    hashes = {sensor: digest(path) for sensor, path in (("V", args.v_weights), ("T", args.t_weights))}
    rows = []
    for index, obs in enumerate(raw["observations"], 1):
        sensor, image = obs.get("sensor"), Path(obs["source_image"])
        if sensor not in models or not image.exists():
            continue
        result = models[sensor].predict(source=str(image), imgsz=args.imgsz, conf=args.conf, device=args.device, verbose=False)[0]
        boxes = result.boxes
        detections = []
        if boxes is not None and len(boxes):
            for box, conf, cls in zip(boxes.xyxy.cpu().tolist(), boxes.conf.cpu().tolist(), boxes.cls.cpu().tolist()):
                detections.append({"class_id": int(cls), "class_name": "hotspot" if sensor == "T" else ("smoke" if int(cls) == 0 else "flame"), "confidence": conf, "bbox_xyxy": box, "pixel_center": [(box[0]+box[2])/2, (box[1]+box[3])/2]})
        rows.append({"observation_id": obs["observation_id"], "batch_id": obs.get("batch_id"), "session_id": obs.get("session_id"), "drone_id": obs.get("drone_id"), "capture_key": obs.get("capture_key"), "sensor": sensor, "source_image": str(image), "image_sha256": digest(image), "timestamp_utc": obs.get("timestamp_utc"), "lrf_reference": obs.get("lrf_reference"), "detections": detections, "detection_to_lrf_same_target": "unverified", "lrf_pixel_target": "unavailable", "localization_mode": "image_plane_plus_independent_lrf_reference", "absolute_fire_coordinate": "unavailable", "model_hash": hashes[sensor]})
        if index % 10 == 0:
            print(f"[{index}/{len(raw['observations'])}]", flush=True)
    payload = {"schema_version": "dji_lrf_photo_detection_all_v1", "generated_utc": datetime.now(timezone.utc).isoformat(), "provisional_detector": True, "source_observations": str(args.observations), "weights": {"V": str(args.v_weights), "T": str(args.t_weights)}, "model_hashes": hashes, "semantics": "Detection and LRF target coordinates remain independent; target identity is unverified; no absolute fire localization.", "summary": {"photo_count": len(rows), "batch_counts": dict(Counter(r["batch_id"] for r in rows)), "photo_sensor_count": dict(Counter(r["sensor"] for r in rows)), "detection_count": sum(len(r["detections"]) for r in rows), "images_with_detections": sum(bool(r["detections"]) for r in rows)}, "observations": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
