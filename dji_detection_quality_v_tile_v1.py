"""Two vertical tiles on frozen E2 V; development set only."""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from recovery_v1_evaluate import digest, evaluate_class, iou


def nms(predictions, overlap):
    kept = []
    for box in sorted(predictions, key=lambda item: item["confidence"], reverse=True):
        if all(box["class"] != previous["class"] or
               iou(box["xyxy"], previous["xyxy"]) <= overlap for previous in kept):
            kept.append(box)
    return kept


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    work = root / "detection_quality_v2"
    out = work / "V_tile2_960_development"
    if out.exists():
        raise FileExistsError(out)
    os.environ["WANDB_MODE"] = "disabled"
    os.environ["WANDB_DISABLED"] = "true"
    policy_path = work / "policy_tile.json"
    weights = root / "runs/E2_V_960_s0/weights/best.pt"
    baseline = root / "evaluations/E2_V_960_s0/predictions.json"
    original = json.loads(baseline.read_text(encoding="utf-8"))["rows"]
    if len(original) != 61:
        raise ValueError("unexpected development image count")
    project = Path(__file__).resolve().parents[1] / "projects/ultralytics"
    sys.path.insert(0, str(project))
    from ultralytics import YOLO
    model = YOLO(str(weights))
    for module in model.model.modules():
        if type(module).__name__ == "GELU" and not hasattr(module, "approximate"):
            module.approximate = "none"
    rows = []
    for old in original:
        image_path = root / "dataset_review_applied_v1/V/images/validation" / (old["observation_id"] + ".jpg")
        if digest(image_path) != old["image_sha256"]:
            raise ValueError("development image hash mismatch: " + str(image_path))
        with Image.open(image_path) as source:
            source = source.convert("RGB")
            width, height = source.size
            tile_width = round(width * 0.60)
            starts = (0, width - tile_width)
            predictions = []
            for left in starts:
                tile = source.crop((left, 0, left + tile_width, height))
                result = model.predict(source=np.asarray(tile)[:, :, ::-1].copy(),
                                       imgsz=960, conf=0.001, iou=0.7,
                                       max_det=300, device="0", half=False,
                                       augment=False, save=False, verbose=False)[0]
                for xyxy, confidence, cls in zip(result.boxes.xyxy.cpu().tolist(),
                                                 result.boxes.conf.cpu().tolist(),
                                                 result.boxes.cls.cpu().tolist()):
                    box = [(left + xyxy[0]) / width, xyxy[1] / height,
                           (left + xyxy[2]) / width, xyxy[3] / height]
                    predictions.append({"class": int(cls), "confidence": float(confidence),
                                        "xyxy": [max(0.0, min(1.0, x)) for x in box]})
        rows.append({**old, "predictions": nms(predictions, 0.7)})
    flame = evaluate_class(rows, 1, "flame")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    gate = policy["gate"]
    m = flame["work_metrics"]
    eligible = bool(m and m["precision"] >= gate["P_min"] and m["recall"] >= gate["R_min"]
                    and flame["ap50"] >= gate["AP50_min"] and m["tp"] >= gate["TP_min"]
                    and m["fp"] <= gate["FP_max"])
    out.mkdir(parents=True)
    (out / "predictions.json").write_text(json.dumps({"sensor": "V", "rows": rows},
                                                       ensure_ascii=False) + "\n", encoding="utf-8")
    result = {"schema_version": "dji_b4_v_tile2_960_development_v1",
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "policy_sha256": digest(policy_path), "weights_sha256": digest(weights),
              "baseline_predictions_sha256": digest(baseline),
              "predictions_sha256": digest(out / "predictions.json"),
              "V_flame": flame, "development_eligible": eligible,
              "confirmation_used": False,
              "image_count": len(rows)}
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"threshold": flame["work_threshold"], "metrics": m,
                      "AP50": flame["ap50"], "eligible": eligible}, ensure_ascii=False))


if __name__ == "__main__":
    main()
