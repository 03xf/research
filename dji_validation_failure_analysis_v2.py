#!/usr/bin/env python3
"""Save class-specific held-out validation TP/FP/FN cases for label review."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/home/member/xmy/xmy/code/projects/ultralytics")
from ultralytics import YOLO


def iou(a, b):
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_a = max(0, a[2]-a[0]) * max(0, a[3]-a[1])
    area_b = max(0, b[2]-b[0]) * max(0, b[3]-b[1])
    return inter / max(1e-12, area_a + area_b - inter)


def truth(path, w, h):
    out = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        cls = int(parts[0]); cx, cy, bw, bh = map(float, parts[1:])
        out.append({"class_id": cls, "bbox_xyxy": [(cx-bw/2)*w, (cy-bh/2)*h, (cx+bw/2)*w, (cy+bh/2)*h]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True, type=Path)
    ap.add_argument("--data-root", required=True, type=Path)
    ap.add_argument("--sensor", required=True, choices=("V", "T"))
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--conf", type=float, default=.1)
    ap.add_argument("--match-iou", type=float, default=.5)
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit("output exists; refusing to overwrite")
    model = YOLO(str(args.weights))
    for module in model.model.modules():
        if type(module).__name__ == "GELU" and not hasattr(module, "approximate"):
            module.approximate = "none"
    names = model.names
    rows = []
    totals = Counter()
    by_class = {str(name): Counter() for name in (names.values() if isinstance(names, dict) else names)}
    for image in sorted((args.data_root / "images/validation").glob("*.jpg")):
        result = model.predict(source=str(image), imgsz=args.imgsz, conf=args.conf, device="0", verbose=False)[0]
        h, w = result.orig_shape
        gt = truth(args.data_root / "labels/validation" / (image.stem + ".txt"), w, h)
        boxes = result.boxes
        preds = []
        if boxes is not None and len(boxes):
            for box, confidence, cls in zip(boxes.xyxy.cpu().tolist(), boxes.conf.cpu().tolist(), boxes.cls.cpu().tolist()):
                preds.append({"class_id": int(cls), "confidence": float(confidence), "bbox_xyxy": box})
        candidates = sorted(((iou(pred["bbox_xyxy"], target["bbox_xyxy"]), pi, gi) for pi, pred in enumerate(preds) for gi, target in enumerate(gt) if pred["class_id"] == target["class_id"]), reverse=True)
        used_p, used_g = set(), set()
        for overlap, pi, gi in candidates:
            if overlap < args.match_iou or pi in used_p or gi in used_g:
                continue
            used_p.add(pi); used_g.add(gi)
            name = names[preds[pi]["class_id"]]
            by_class[str(name)]["tp"] += 1
            totals["tp"] += 1
        false_positive = [p for i, p in enumerate(preds) if i not in used_p]
        false_negative = [g for i, g in enumerate(gt) if i not in used_g]
        for p in false_positive:
            by_class[str(names[p["class_id"]])]["fp"] += 1; totals["fp"] += 1
        for g in false_negative:
            by_class[str(names[g["class_id"]])]["fn"] += 1; totals["fn"] += 1
        if false_positive or false_negative:
            rows.append({"image": str(image), "observation_id": image.stem, "sensor": args.sensor, "ground_truth": gt, "predictions": preds, "false_positives": false_positive, "false_negatives": false_negative, "annotation_split": "validation"})
    payload = {"schema_version": "dji_validation_failure_analysis_v2", "generated_utc": datetime.now(timezone.utc).isoformat(), "sensor": args.sensor, "weights": str(args.weights), "weights_sha256": hashlib.sha256(args.weights.read_bytes()).hexdigest(), "data_root": str(args.data_root), "conf": args.conf, "match_iou": args.match_iou, "imgsz": args.imgsz, "blind_test_accessed": False, "validation_labels_modified": False, "counts": dict(totals), "by_class": {name: dict(stat) for name, stat in by_class.items()}, "failure_image_count": len(rows), "failures": rows, "review_policy": "Failures select training-session scenarios for new samples; held-out validation images are not relabelled or copied into training."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": dict(totals), "by_class": payload["by_class"], "failure_image_count": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
