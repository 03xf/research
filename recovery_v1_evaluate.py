"""Evaluate a frozen DJI detector on the repaired development split."""

import argparse
import hashlib
import json
import math
import os
import platform
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iou(box_a, box_b):
    left = max(box_a[0], box_b[0])
    top = max(box_a[1], box_b[1])
    right = min(box_a[2], box_b[2])
    bottom = min(box_a[3], box_b[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    return intersection / (area_a + area_b - intersection) if area_a + area_b > intersection else 0.0


def load_ground_truth(path, class_count):
    boxes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5 or not fields[0].isdigit():
            raise ValueError(f"invalid label: {path}: {line}")
        cls = int(fields[0])
        x, y, width, height = (float(value) for value in fields[1:])
        if (cls not in range(class_count) or not all(math.isfinite(v) for v in (x, y, width, height))
                or width <= 0 or height <= 0):
            raise ValueError(f"invalid class or box: {path}: {line}")
        edges = [x - width / 2, y - height / 2, x + width / 2, y + height / 2]
        if min(edges[:2]) < -1e-6 or max(edges[2:]) > 1 + 1e-6:
            raise ValueError(f"box outside image: {path}: {line}")
        boxes.append({"class": cls, "xyxy": [max(0.0, edges[0]), max(0.0, edges[1]),
                                               min(1.0, edges[2]), min(1.0, edges[3])]})
    return boxes


def image_matches(row, cls, confidence, overlap):
    truth = [box for box in row["truth"] if box["class"] == cls]
    predictions = sorted((box for box in row["predictions"]
                          if box["class"] == cls and box["confidence"] >= confidence),
                         key=lambda box: box["confidence"], reverse=True)
    used = set()
    true_positive = 0
    for box in predictions:
        candidates = [(iou(box["xyxy"], target["xyxy"]), index)
                      for index, target in enumerate(truth) if index not in used]
        best = max(candidates, default=(0.0, -1))
        if best[0] >= overlap:
            used.add(best[1])
            true_positive += 1
    return true_positive, len(predictions) - true_positive, len(truth) - true_positive


def totals(rows, cls, confidence, overlap=0.5):
    tp = fp = fn = negative_fp_images = 0
    for row in rows:
        a, b, c = image_matches(row, cls, confidence, overlap)
        tp += a
        fp += b
        fn += c
        if not any(box["class"] == cls for box in row["truth"]) and b:
            negative_fp_images += 1
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
            "negative_false_positive_images": negative_fp_images}


def average_precision(rows, cls, overlap):
    support = sum(box["class"] == cls for row in rows for box in row["truth"])
    if not support:
        return None
    predictions = sorted(((box["confidence"], row_index, box["xyxy"])
                          for row_index, row in enumerate(rows)
                          for box in row["predictions"] if box["class"] == cls), reverse=True)
    used = defaultdict(set)
    tp = fp = 0
    recalls = []
    precisions = []
    for confidence, row_index, xyxy in predictions:
        truth = [box for box in rows[row_index]["truth"] if box["class"] == cls]
        candidates = [(iou(xyxy, target["xyxy"]), index) for index, target in enumerate(truth)
                      if index not in used[row_index]]
        best = max(candidates, default=(0.0, -1))
        if best[0] >= overlap:
            used[row_index].add(best[1])
            tp += 1
        else:
            fp += 1
        recalls.append(tp / support)
        precisions.append(tp / (tp + fp))
    return sum(max((precision for recall, precision in zip(recalls, precisions)
                    if recall >= point / 100), default=0.0) for point in range(101)) / 101


def evaluate_class(rows, cls, name):
    support = sum(box["class"] == cls for row in rows for box in row["truth"])
    thresholds = []
    for integer in range(1, 91):
        threshold = integer / 100
        values = totals(rows, cls, threshold)
        thresholds.append({"threshold": threshold, **values})
    candidates = [row for row in thresholds if row["precision"] >= 0.60 and support]
    chosen = max(candidates, key=lambda row: (row["recall"], row["precision"], row["threshold"])) if candidates else None
    aps = [average_precision(rows, cls, round(0.50 + integer * 0.05, 2)) for integer in range(10)]
    ap50 = aps[0]
    ap5095 = sum(aps) / len(aps) if support else None
    sessions = []
    if chosen:
        for session in sorted({row["session_id"] or "unknown" for row in rows}):
            subset = [row for row in rows if (row["session_id"] or "unknown") == session]
            sessions.append({"session_id": session, "images": len(subset),
                             "ground_truth": sum(box["class"] == cls for row in subset for box in row["truth"]),
                             **totals(subset, cls, chosen["threshold"])})
    return {"class_id": cls, "class_name": name, "ground_truth": support,
            "negative_images": sum(not any(box["class"] == cls for box in row["truth"]) for row in rows),
            "ap50": ap50, "ap50_95": ap5095,
            "work_threshold": chosen["threshold"] if chosen else None,
            "work_metrics": {key: value for key, value in chosen.items() if key != "threshold"} if chosen else None,
            "gate_passed": bool(chosen and chosen["recall"] >= 0.70 and ap50 is not None and ap50 >= 0.50),
            "sessions": sessions, "threshold_scan": thresholds}


def run(args):
    os.environ["WANDB_MODE"] = "disabled"
    os.environ["WANDB_DISABLED"] = "true"
    os.environ["COMET_MODE"] = "DISABLED"
    if args.output.exists():
        raise FileExistsError(args.output)
    if not args.weights.is_file() or not args.data.is_file():
        raise FileNotFoundError("weights or data YAML missing")
    dataset = args.data.parent.parent.resolve()
    manifest_path = dataset / "manifest.json"
    snapshot = dataset / "review_decisions_snapshot.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    config = yaml.safe_load(args.data.read_text(encoding="utf-8"))
    if (Path(config["path"]).resolve() != args.data.parent.resolve()
            or Path(manifest["derived_dataset"]).resolve() != dataset
            or digest(snapshot) != manifest["review_decisions_sha256"]):
        raise ValueError("dataset provenance mismatch")
    names = [config["names"][index] for index in range(config["nc"])]
    image_dir = args.data.parent / config["val"]
    label_dir = image_dir.parent.parent / "labels" / image_dir.name
    images = sorted(image_dir.glob("*.jpg"))
    if not images:
        raise ValueError("development validation images missing")
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))["records"]
    sensor = args.data.parent.name
    metadata = {(row["sensor"], row["split"], row["observation_id"]): row for row in ledger}
    args.output.mkdir(parents=True)
    report = {"schema_version": "dji_recovery_development_evaluation_v1",
              "status": "running", "model_id": args.model_id,
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "weights": str(args.weights), "weights_sha256": digest(args.weights),
              "data_yaml": str(args.data), "data_yaml_sha256": digest(args.data),
              "dataset_manifest_sha256": digest(manifest_path),
              "review_decisions_sha256": digest(snapshot),
              "entrypoint_sha256": digest(Path(__file__)),
              "imgsz": args.imgsz, "device": args.device,
              "protocol": {"split": "historically_exposed_development_validation",
                           "same_class_one_to_one_iou": 0.5,
                           "prediction_confidence_floor": 0.001, "nms_iou": 0.7,
                           "work_thresholds": "0.01..0.90 step 0.01; max recall with P>=0.60; ties P then higher threshold",
                           "ap": "101-point interpolated precision at IoU 0.50:0.05:0.95"},
              "environment": {"python": sys.version, "platform": platform.platform()}}
    write_json(args.output / "run_config.json", report)
    try:
        project = Path(__file__).resolve().parents[1] / "projects" / "ultralytics"
        sys.path.insert(0, str(project))
        import torch
        import ultralytics
        from ultralytics import YOLO

        report["environment"].update({"torch": torch.__version__, "cuda": torch.version.cuda,
                                      "ultralytics": ultralytics.__version__})
        model = YOLO(str(args.weights))
        for module in model.model.modules():
            if type(module).__name__ == "GELU" and not hasattr(module, "approximate"):
                module.approximate = "none"
        rows = []
        for image in images:
            ledger_row = metadata.get((sensor, "validation", image.stem))
            if not ledger_row:
                raise ValueError(f"image absent from ledger: {image}")
            image_hash = digest(image)
            if image_hash != ledger_row["image_sha256"]:
                raise ValueError(f"image differs from frozen ledger: {image}")
            label = label_dir / (image.stem + ".txt")
            if not label.is_file():
                raise ValueError(f"label missing: {label}")
            result = model.predict(source=str(image), imgsz=args.imgsz, conf=0.001, iou=0.7,
                                   max_det=300, device=args.device, half=False, augment=False,
                                   save=False, verbose=False)[0]
            height, width = result.orig_shape
            predictions = []
            for coords, confidence, cls in zip(result.boxes.xyxy.cpu().tolist(),
                                               result.boxes.conf.cpu().tolist(),
                                               result.boxes.cls.cpu().tolist()):
                category = int(cls)
                if category not in range(len(names)):
                    raise ValueError(f"prediction class outside dataset: {image}: {category}")
                predictions.append({"class": category, "confidence": float(confidence),
                                    "xyxy": [coords[0] / width, coords[1] / height,
                                             coords[2] / width, coords[3] / height]})
            rows.append({"observation_id": image.stem, "session_id": ledger_row["session_id"],
                         "batch_id": ledger_row["batch_id"], "image_sha256": image_hash,
                         "truth": load_ground_truth(label, len(names)), "predictions": predictions})
        write_json(args.output / "predictions.json", {"sensor": sensor, "rows": rows})
        classes = [evaluate_class(rows, cls, name) for cls, name in enumerate(names)]
        report.update({"status": "complete", "finished_utc": datetime.now(timezone.utc).isoformat(),
                       "sensor": sensor, "images": len(rows),
                       "fully_negative_images": sum(not row["truth"] for row in rows),
                       "classes": classes, "passed_class_count": sum(row["gate_passed"] for row in classes),
                       "all_classes_passed": all(row["gate_passed"] for row in classes),
                       "predictions_sha256": digest(args.output / "predictions.json")})
    except Exception as error:
        report.update({"status": "failed", "error": repr(error),
                       "finished_utc": datetime.now(timezone.utc).isoformat()})
        write_json(args.output / "result.json", report)
        raise
    write_json(args.output / "result.json", report)
    print(json.dumps({"model_id": args.model_id, "sensor": sensor, "images": len(rows),
                      "classes": [{"name": row["class_name"], "P": row["work_metrics"]["precision"] if row["work_metrics"] else None,
                                   "R": row["work_metrics"]["recall"] if row["work_metrics"] else None,
                                   "AP50": row["ap50"], "passed": row["gate_passed"]} for row in classes]},
                     ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--imgsz", type=int, required=True)
    parser.add_argument("--device", required=True)
    run(parser.parse_args())
