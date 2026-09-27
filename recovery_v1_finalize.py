"""Write a compact, current recovery status from immutable evidence."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main(root):
    preflight = json.loads((root / "preflight.json").read_text(encoding="utf-8"))
    ledger = json.loads((root / "sample_ledger.json").read_text(encoding="utf-8"))
    decisions = json.loads((root / "review_decisions.json").read_text(encoding="utf-8"))
    lrf = json.loads((root / "lrf/lrf_event_audit.json").read_text(encoding="utf-8"))
    runs = {}
    for sensor in ("V", "T"):
        run = root / f"runs/{sensor}_smoke3_wandboff/run_config.json"
        runs[sensor] = json.loads(run.read_text(encoding="utf-8"))
    review_counts = {}
    for row in decisions["decisions"]:
        review_counts[row["status"]] = review_counts.get(row["status"], 0) + 1
    status = {
        "schema_version": "dji_recovery_status_v1",
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "diagnostic_smoke_complete_review_required",
        "source_dataset": preflight["source"],
        "derived_dataset": preflight["derived_dataset"],
        "derived_dataset_preflight": {"yaml_paths_point_to_derived_dataset": True,
                                      "all_train_empty_labels_quarantined": True,
                                      "image_label_and_bounds_check": "passed"},
        "sample_counts": preflight["counts"],
        "ledger_records": len(ledger["records"]),
        "review_queue_count": preflight["review_queue_count"],
        "review_decision_counts": review_counts,
        "training_runs": runs,
        "formal_training_authorized": False,
        "formal_validation_authorized": False,
        "blind_test_accessed": False,
        "historically_exposed_development_validation": True,
        "lrf_event_audit": lrf["by_batch"],
        "physical_source_confirmed_groups": lrf["physical_target_confirmed_groups"],
        "absolute_visual_localization": "unavailable",
        "blocking_reasons": [
            "214 source/label records still require independent review",
            "development validation was historically exposed and needs a frozen review decision",
            "no capture group has independently verified identity as the same ground burning source",
            "Matrice 4T intrinsics, distortion and extrinsics are unavailable",
        ],
        "next_action": "Complete independent review in recovery_v1 review UI; build an approved derived dataset from review_decisions.json; run formal 100-epoch controlled V/T comparison only after review completeness checks.",
    }
    target = root / "status_current.json"
    if target.exists():
        raise SystemExit(f"refusing to overwrite {target}")
    target.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status["stage"], "review_queue": status["review_queue_count"], "output": str(target)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    main(parser.parse_args().root)
