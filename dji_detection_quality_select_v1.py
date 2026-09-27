"""Freeze the predeclared B4 V/T development comparison without using confirmation data."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from recovery_v1_evaluate import digest, iou


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def thermal_error_types(rows, threshold):
    counts = {name: 0 for name in
              ("negative_image", "separate_from_truth", "near_truth", "duplicate_or_misaligned")}
    for row in rows:
        truth = [box for box in row["truth"] if box["class"] == 0]
        predictions = sorted((box for box in row["predictions"]
                              if box["class"] == 0 and box["confidence"] >= threshold),
                             key=lambda box: box["confidence"], reverse=True)
        used = set()
        for box in predictions:
            unmatched = [(iou(box["xyxy"], target["xyxy"]), index)
                         for index, target in enumerate(truth) if index not in used]
            score, index = max(unmatched, default=(0, -1))
            if score >= 0.5:
                used.add(index)
                continue
            best = max((iou(box["xyxy"], target["xyxy"]) for target in truth), default=0)
            key = ("negative_image" if not truth else
                   "duplicate_or_misaligned" if best >= 0.5 else
                   "near_truth" if best > 0.1 else "separate_from_truth")
            counts[key] += 1
    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    work = root / "detection_quality_v2"
    output = work / "development_selection_v1.json"
    if output.exists():
        raise FileExistsError(output)
    policy_path = work / "policy.json"
    policy = load(policy_path)
    baseline_v = load(root / "evaluations/E2_V_960_s0/result.json")["classes"][1]
    v = []
    for size in (1280, 1536):
        path = work / f"V{size}_development/result.json"
        result = load(path)
        flame = result["classes"][1]
        m = flame["work_metrics"]
        gate = policy["V_development_gate"]
        eligible = bool(m and m["precision"] >= gate["minimum"]["P"]
                        and m["recall"] >= gate["minimum"]["R"]
                        and flame["ap50"] >= gate["minimum"]["AP50"]
                        and m["tp"] >= gate["minimum"]["TP"]
                        and m["fp"] <= gate["maximum_FP"])
        v.append({"input": size, "result_sha256": digest(path),
                  "threshold": flame["work_threshold"], "metrics": m,
                  "AP50": flame["ap50"], "eligible": eligible})
    thermal_path = work / "T_nms045_development.json"
    thermal = load(thermal_path)
    gate = policy["T_development_gate"]
    eligible_thresholds = [row for row in thermal["class"]["threshold_scan"]
                           if row["tp"] >= gate["minimum_TP"]
                           and row["fp"] <= gate["maximum_FP"]
                           and row["negative_false_positive_images"] <= gate["maximum_negative_false_positive_images"]
                           and row["precision"] >= gate["minimum_P"]
                           and row["recall"] >= gate["minimum_R"]]
    if thermal["class"]["ap50"] < gate["minimum_AP50"]:
        eligible_thresholds = []
    chosen = max(eligible_thresholds,
                 key=lambda row: (row["tp"], -row["fp"], row["threshold"]), default=None)
    baseline_rows = load(root / "evaluations/E2_T_960_s0/predictions.json")["rows"]
    baseline_types = thermal_error_types(baseline_rows, 0.14)
    status = {
        "schema_version": "dji_b4_detection_quality_development_selection_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "policy_sha256": digest(policy_path),
        "confirmation_used_for_selection": False,
        "V_baseline": {"threshold": baseline_v["work_threshold"],
                       "metrics": baseline_v["work_metrics"], "AP50": baseline_v["ap50"]},
        "V_candidates": v,
        "V_selected": next((f"V{x['input']}" for x in v if x["eligible"]), None),
        "T_baseline": thermal["baseline_at_014"],
        "T_baseline_false_positive_types": baseline_types,
        "T_NMS045_at_original_threshold": thermal["candidate_at_014"],
        "T_NMS045_AP50": thermal["class"]["ap50"],
        "T_eligible_thresholds": eligible_thresholds,
        "T_selected": chosen,
        "T_explanation": "NMS mainly removes boxes around an already labeled heat source; negative-image alarms must be checked separately.",
    }
    output.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"V_candidates": v, "V_selected": status["V_selected"],
                      "T_baseline_FP_types": baseline_types,
                      "T_fixed": thermal["candidate_at_014"],
                      "T_selected": chosen}, ensure_ascii=False))


if __name__ == "__main__":
    main()
