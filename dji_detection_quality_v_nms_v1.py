"""Evaluate one predeclared extra NMS step on V1280 development predictions."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from recovery_v1_evaluate import digest, evaluate_class, iou


def suppress(predictions, overlap):
    kept = []
    for box in sorted(predictions, key=lambda x: x["confidence"], reverse=True):
        if all(box["class"] != prior["class"] or iou(box["xyxy"], prior["xyxy"]) <= overlap
               for prior in kept):
            kept.append(box)
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    work = root / "detection_quality_v2"
    output = work / "V1280_NMS045_development.json"
    if output.exists():
        raise FileExistsError(output)
    source = work / "V1280_development/predictions.json"
    policy_path = work / "policy_extension.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    old = json.loads(source.read_text(encoding="utf-8"))["rows"]
    rows = [{**row, "predictions": suppress(row["predictions"], 0.45)} for row in old]
    if len(rows) != 61 or any(a["image_sha256"] != b["image_sha256"] or a["truth"] != b["truth"]
                              for a, b in zip(old, rows)):
        raise ValueError("validation data changed")
    flame = evaluate_class(rows, 1, "flame")
    gate = policy["gate"]
    m = flame["work_metrics"]
    eligible = bool(m and m["precision"] >= gate["P_min"] and m["recall"] >= gate["R_min"]
                    and flame["ap50"] >= gate["AP50_min"]
                    and m["tp"] >= gate["TP_min"] and m["fp"] <= gate["FP_max"])
    result = {"schema_version": "dji_b4_v1280_nms_development_v1",
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "source_predictions_sha256": digest(source), "policy_sha256": digest(policy_path),
              "flame": flame, "eligible": eligible,
              "suppressed_boxes": sum(len(a["predictions"])-len(b["predictions"])
                                      for a, b in zip(old, rows)),
              "confirmation_used": False}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"flame_threshold": flame["work_threshold"], "metrics": m,
                      "AP50": flame["ap50"], "eligible": eligible,
                      "suppressed_boxes": result["suppressed_boxes"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
