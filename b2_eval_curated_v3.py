"""Compare V fire detectors on sealed, video-level B2 holdout images."""
import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ.update({"WANDB_MODE": "disabled", "WANDB_DISABLED": "true", "COMET_START_ONLINE": "0", "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION": "python"})
from ultralytics import YOLO


def iou(a, b):
    iw = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    ih = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = iw * ih
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter) if area_a + area_b - inter else 0


def read_yolo_labels(path):
    out = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        cls, x, y, w, h = map(float, line.split())
        assert cls == 0, (path, cls)
        out.append([x - w / 2, y - h / 2, x + w / 2, y + h / 2])
    return out


def score_images(rows, threshold):
    ranked = []
    count_truth = sum(len(row["truth"]) for row in rows)
    matched = {row["image"]: set() for row in rows}
    for row in rows:
        for pred in row["predictions"]:
            ranked.append((pred["confidence"], row, pred))
    ranked.sort(key=lambda p: p[0], reverse=True)
    tp, fp, scores = 0, 0, []
    per_image = {row["image"]: {"tp": 0, "fp": 0, "gt": len(row["truth"])} for row in rows}
    for confidence, row, pred in ranked:
        candidates = [(iou(pred["box"], truth), n) for n, truth in enumerate(row["truth"])
                      if n not in matched[row["image"]]]
        best = max(candidates, default=(0, -1))
        hit = best[0] >= 0.5
        if hit:
            matched[row["image"]].add(best[1])
            tp += 1
        else:
            fp += 1
        if confidence >= threshold:
            per_image[row["image"]]["tp" if hit else "fp"] += 1
        scores.append((confidence, tp, fp))
    # Integral of monotonically enveloped precision over recall changes.
    recalls = [0.0] + [t / count_truth for _, t, _ in scores] + [1.0]
    precisions = [1.0] + [t / (t + f) for _, t, f in scores] + [0.0]
    for j in range(len(precisions) - 2, -1, -1):
        precisions[j] = max(precisions[j], precisions[j + 1])
    ap = sum((recalls[j] - recalls[j - 1]) * precisions[j]
             for j in range(1, len(recalls)) if recalls[j] > recalls[j - 1]) if count_truth else None
    op_tp = sum(v["tp"] for v in per_image.values())
    op_fp = sum(v["fp"] for v in per_image.values())
    for v in per_image.values():
        v["fn"] = v["gt"] - v["tp"]
    return {"ap50": ap, "confidence_threshold": threshold, "tp": op_tp,
            "fp": op_fp, "fn": count_truth - op_tp,
            "precision": op_tp / (op_tp + op_fp) if op_tp + op_fp else 0,
            "recall": op_tp / count_truth if count_truth else None,
            "per_image": per_image}


parser = argparse.ArgumentParser()
parser.add_argument("--weights", required=True, type=Path)
parser.add_argument("--images", required=True, type=Path)
parser.add_argument("--labels", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
parser.add_argument("--model-id", required=True)
parser.add_argument("--imgsz", default=1280, type=int)
parser.add_argument("--device", default="1")
parser.add_argument("--threshold", default=0.37, type=float)
args = parser.parse_args()
model = YOLO(str(args.weights))
names = model.names
flame_indices = [int(index) for index, name in names.items() if str(name).casefold() == "flame"]
if not flame_indices:
    raise ValueError(f"No flame class in model.names: {names}")
rows = []
for image in sorted(args.images.glob("*.jpg")):
    truth = read_yolo_labels(args.labels / (image.stem + ".txt"))
    result = model.predict(str(image), imgsz=args.imgsz, conf=0.001, iou=0.7,
                           device=args.device, classes=flame_indices, verbose=False)[0]
    h, w = result.orig_shape
    predictions = [{"box": [x1 / w, y1 / h, x2 / w, y2 / h], "confidence": conf}
                   for (x1, y1, x2, y2), conf in zip(result.boxes.xyxy.cpu().tolist(),
                                                       result.boxes.conf.cpu().tolist())]
    rows.append({"image": image.stem, "truth": truth, "predictions": predictions})
report = {"model_id": args.model_id, "weights": str(args.weights),
          "weights_sha256": hashlib.sha256(args.weights.read_bytes()).hexdigest(),
          "class_names": names, "flame_indices": flame_indices,
          "images": len(rows), "truth_boxes": sum(len(row["truth"]) for row in rows),
          "imgsz": args.imgsz, "selection_confidence_floor": 0.001,
          "note": "Five correlated frames from one held-out video; scenario diagnostic only.",
          "metrics": score_images(rows, args.threshold), "rows": rows}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({key: report[key] for key in ("model_id", "images", "truth_boxes", "metrics")}, ensure_ascii=False))
