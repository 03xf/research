"""Freeze T1/T2 selection criteria before reading their development results."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    work = root / "thermal_background_v1"
    target = work / "selection_policy_v1.json"
    if target.exists():
        raise FileExistsError(target)
    baseline_path = root / "evaluations/E2_T_960_s0/result.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    cls = baseline["classes"][0]
    metrics = cls["work_metrics"]
    if cls["class_name"] != "hotspot" or cls["ground_truth"] != 73 or cls["work_threshold"] != 0.14:
        raise ValueError("E2 T baseline changed")
    payload = {
        "schema_version": "dji_b4_thermal_selection_policy_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_result": str(baseline_path), "baseline_result_sha256": digest(baseline_path),
        "baseline": {"threshold": cls["work_threshold"], "tp": metrics["tp"], "fp": metrics["fp"],
                     "fn": metrics["fn"], "negative_false_positive_images": metrics["negative_false_positive_images"],
                     "P": metrics["precision"], "R": metrics["recall"], "AP50": cls["ap50"]},
        "development_rule": {
            "threshold_scan": "original 0.01..0.90, highest recall among P>=0.60; no confirmation tuning",
            "eligibility": "P>=0.60, R>=0.70, AP50>=0.50, TP>=E2-2, FP<=E2-3, negative_false_positive_images<E2",
            "ranking": "fewest FP, then highest TP, then highest AP50, then simpler T1",
            "if_none_eligible": "stop without new confirmation evaluation; E2 T remains default",
            "replication": "selected mode seeds 1 and 2; seed 0 predeclared for one confirmation and point comparison",
        },
        "deployment_rule": {
            "confirmation": "P>=0.60, R>=0.70, AP50>=0.50 at development-frozen seed-0 threshold",
            "source_points": "T matched >=52/72 overall and B4 loss <=2 from baseline; T negative frames with detection <9",
            "throughput": "one RTX 3090 >=5 processed frames/s on B4 replay",
            "if_failed": "E2 T remains default",
        },
        "limitations": ["32 reviewed B4 T pairs all contain fire-related source boxes; no new source-negative image was added",
                        "development and 50-pair point sets were historically exposed; outcomes are exploratory"],
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"policy_sha256": digest(target), "baseline": payload["baseline"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
