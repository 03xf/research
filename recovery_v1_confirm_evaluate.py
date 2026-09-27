"""One-time confirmation evaluation with models and thresholds frozen on development data."""

import argparse
import json
import math
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from recovery_v1_evaluate import average_precision, digest, totals, write_json


CLASS_NAMES = {"V": ["smoke", "flame"], "T": ["hotspot"]}


def parse_labels(raw, sensor, pair_id):
    boxes = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5 or not parts[0].isdigit():
            raise ValueError("invalid label format: {} {}".format(pair_id, sensor))
        category = int(parts[0])
        coordinates = [float(value) for value in parts[1:]]
        if category not in range(len(CLASS_NAMES[sensor])) or not all(
                math.isfinite(value) for value in coordinates):
            raise ValueError("invalid class or coordinate: {} {}".format(pair_id, sensor))
        x, y, width, height = coordinates
        if width <= 0 or height <= 0:
            raise ValueError("empty box: {} {}".format(pair_id, sensor))
        left, top, right, bottom = (x - width / 2, y - height / 2,
                                    x + width / 2, y + height / 2)
        if left < -1e-6 or top < -1e-6 or right > 1 + 1e-6 or bottom > 1 + 1e-6:
            raise ValueError("box outside image: {} {}".format(pair_id, sensor))
        boxes.append({"class": category,
                      "xyxy": [max(0.0, left), max(0.0, top),
                               min(1.0, right), min(1.0, bottom)]})
    return boxes


def preflight(manifest, decisions, freeze):
    if manifest["pair_count"] != len(manifest["pairs"]):
        raise ValueError("manifest pair count mismatch")
    if manifest["unpaired_count"] or manifest["pair_count"] != 194:
        raise ValueError("unexpected confirmation cohort")
    pair_ids = [pair["pair_id"] for pair in manifest["pairs"]]
    if len(pair_ids) != len(set(pair_ids)) or set(pair_ids) != set(decisions["decisions"]):
        raise ValueError("confirmation decisions incomplete or contain extra IDs")
    if freeze["schema_version"] != "dji_recovery_confirmation_freeze_v1":
        raise ValueError("freeze schema mismatch")
    if set(freeze["models"]) != set(CLASS_NAMES):
        raise ValueError("freeze must provide V and T models")
    for sensor, names in CLASS_NAMES.items():
        model = freeze["models"][sensor]
        if set(model["thresholds"]) != set(names):
            raise ValueError("threshold classes mismatch: " + sensor)
        if not all(0 < value <= 1 for value in model["thresholds"].values()):
            raise ValueError("invalid fixed threshold: " + sensor)
        weights = Path(model["weights"])
        if not weights.is_file() or digest(weights) != model["weights_sha256"]:
            raise ValueError("frozen weights mismatch: " + sensor)
    for pair in manifest["pairs"]:
        pair_id = pair["pair_id"]
        decision = decisions["decisions"][pair_id]
        if decision["pair_id"] != pair_id:
            raise ValueError("decision ID mismatch: " + pair_id)
        for sensor in CLASS_NAMES:
            observation = pair[sensor]
            reviewed = decision[sensor]
            image = Path(observation["file"])
            if reviewed["status"] != "complete":
                raise ValueError("unresolved image: {} {}".format(pair_id, sensor))
            if reviewed["image_sha256"] != observation["sha256"] or digest(image) != observation["sha256"]:
                raise ValueError("image provenance mismatch: {} {}".format(pair_id, sensor))
            parse_labels(reviewed["label_text"], sensor, pair_id)


def class_result(rows, class_id, name, threshold):
    support = sum(box["class"] == class_id for row in rows for box in row["truth"])
    work = totals(rows, class_id, threshold)
    aps = [average_precision(rows, class_id, round(0.50 + index * 0.05, 2))
           for index in range(10)]
    ap50 = aps[0]
    sessions = []
    for session in sorted({row["session_id"] for row in rows}):
        subset = [row for row in rows if row["session_id"] == session]
        sessions.append({"session_id": session, "images": len(subset),
                         "ground_truth": sum(box["class"] == class_id
                                             for row in subset for box in row["truth"]),
                         **totals(subset, class_id, threshold)})
    return {"class_id": class_id, "class_name": name, "ground_truth": support,
            "negative_images": sum(not any(box["class"] == class_id for box in row["truth"])
                                   for row in rows),
            "threshold_from_development": threshold, "work_metrics": work,
            "ap50": ap50, "ap50_95": sum(aps) / len(aps) if support else None,
            "gate_passed": bool(support and work["precision"] >= 0.60
                                and work["recall"] >= 0.70
                                and ap50 is not None and ap50 >= 0.50),
            "sessions": sessions}


def run(args):
    os.environ["WANDB_MODE"] = "disabled"
    os.environ["WANDB_DISABLED"] = "true"
    os.environ["COMET_MODE"] = "DISABLED"
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    preflight(manifest, decisions, freeze)
    args.output.mkdir(parents=True)
    report = {"schema_version": "dji_recovery_confirmation_evaluation_v1",
              "status": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
              "historically_exposed_confirmation": True,
              "strict_blind_test": False,
              "review_method": "assistant visual review in paired browser UI",
              "pair_count": len(manifest["pairs"]),
              "manifest_sha256": digest(args.manifest),
              "decisions_sha256": digest(args.decisions),
              "freeze_sha256": digest(args.freeze),
              "entrypoint_sha256": digest(Path(__file__)),
              "protocol": {"same_class_one_to_one_iou": 0.5,
                           "prediction_confidence_floor": 0.001,
                           "nms_iou": 0.7,
                           "threshold_source": "frozen development evaluation; no confirmation scan",
                           "gate": "P>=0.60, R>=0.70, AP50>=0.50"},
              "environment": {"python": sys.version, "platform": platform.platform()}}
    write_json(args.output / "run_config.json", report)
    try:
        project = Path(__file__).resolve().parents[1] / "projects" / "ultralytics"
        sys.path.insert(0, str(project))
        import torch
        import ultralytics
        from ultralytics import YOLO
        report["environment"].update({"torch": torch.__version__,
                                      "cuda": torch.version.cuda,
                                      "ultralytics": ultralytics.__version__})
        report["sensors"] = {}
        for sensor, names in CLASS_NAMES.items():
            frozen = freeze["models"][sensor]
            model = YOLO(frozen["weights"])
            for module in model.model.modules():
                if type(module).__name__ == "GELU" and not hasattr(module, "approximate"):
                    module.approximate = "none"
            rows = []
            for pair in manifest["pairs"]:
                pair_id = pair["pair_id"]
                image = pair[sensor]["file"]
                truth = parse_labels(decisions["decisions"][pair_id][sensor]["label_text"],
                                     sensor, pair_id)
                result = model.predict(source=image, imgsz=frozen["imgsz"], conf=0.001,
                                       iou=0.7, max_det=300, device=args.device,
                                       half=False, augment=False, save=False, verbose=False)[0]
                height, width = result.orig_shape
                predictions = []
                for coords, confidence, category in zip(result.boxes.xyxy.cpu().tolist(),
                                                        result.boxes.conf.cpu().tolist(),
                                                        result.boxes.cls.cpu().tolist()):
                    category = int(category)
                    if category not in range(len(names)):
                        raise ValueError("model class mismatch: " + sensor)
                    predictions.append({"class": category, "confidence": float(confidence),
                                        "xyxy": [coords[0] / width, coords[1] / height,
                                                 coords[2] / width, coords[3] / height]})
                rows.append({"pair_id": pair_id, "session_id": pair["session_id"],
                             "image_sha256": pair[sensor]["sha256"],
                             "truth": truth, "predictions": predictions})
            prediction_file = args.output / ("predictions_" + sensor + ".json")
            write_json(prediction_file, {"sensor": sensor, "rows": rows})
            classes = [class_result(rows, category, name, frozen["thresholds"][name])
                       for category, name in enumerate(names)]
            report["sensors"][sensor] = {"model_id": frozen["model_id"],
                                         "weights_sha256": frozen["weights_sha256"],
                                         "images": len(rows),
                                         "fully_negative_images": sum(not row["truth"] for row in rows),
                                         "classes": classes,
                                         "passed_class_count": sum(row["gate_passed"] for row in classes),
                                         "all_classes_passed": all(row["gate_passed"] for row in classes),
                                         "predictions_sha256": digest(prediction_file)}
        report["status"] = "complete"
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    except Exception as error:
        report["status"] = "failed"
        report["error"] = repr(error)
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(args.output / "result.json", report)
        raise
    write_json(args.output / "result.json", report)
    print(json.dumps({"status": report["status"], "pair_count": report["pair_count"],
                      "sensors": {sensor: {"passed_class_count": value["passed_class_count"],
                                           "all_classes_passed": value["all_classes_passed"]}
                                  for sensor, value in report["sensors"].items()}},
                     ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="0")
    run(parser.parse_args())
