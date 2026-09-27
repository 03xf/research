"""Read-only comparison of stricter T NMS on frozen E2 development predictions."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from recovery_v1_evaluate import digest, evaluate_class, iou, totals


def suppress(predictions, threshold):
    ordered = sorted(predictions, key=lambda row: row["confidence"], reverse=True)
    kept = []
    for row in ordered:
        if all(row["class"] != old["class"] or iou(row["xyxy"], old["xyxy"]) <= threshold
               for old in kept):
            kept.append(row)
    return kept


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = root / "detection_quality_v2" / "T_nms045_development.json"
    if output.exists():
        raise FileExistsError(output)
    source = root / "evaluations/E2_T_960_s0/predictions.json"
    policy = root / "detection_quality_v2/policy.json"
    old_rows = json.loads(source.read_text(encoding="utf-8"))["rows"]
    rows = [{**row, "predictions": suppress(row["predictions"], 0.45)} for row in old_rows]
    if len(rows) != 66 or any(a["truth"] != b["truth"] or a["image_sha256"] != b["image_sha256"]
                              for a, b in zip(old_rows, rows)):
        raise ValueError("development truth or images changed")
    result = {
        "schema_version": "dji_b4_thermal_post_nms_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "policy_sha256": digest(policy),
        "source_predictions_sha256": digest(source),
        "change": "additional class-aware NMS at IoU 0.45; E2 T weights and source predictions unchanged",
        "baseline_at_014": totals(old_rows, 0, 0.14),
        "candidate_at_014": totals(rows, 0, 0.14),
        "class": evaluate_class(rows, 0, "hotspot"),
        "kept_predictions": sum(len(row["predictions"]) for row in rows),
        "source_predictions": sum(len(row["predictions"]) for row in old_rows),
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"baseline": result["baseline_at_014"],
                      "candidate": result["candidate_at_014"],
                      "work_threshold": result["class"]["work_threshold"],
                      "work_metrics": result["class"]["work_metrics"],
                      "AP50": result["class"]["ap50"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
