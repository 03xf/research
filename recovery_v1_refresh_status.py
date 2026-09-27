"""Refresh one current recovery status from server-side evidence."""

import argparse
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def refresh(root):
    root = root.resolve()
    decisions_path = root / "review_decisions.json"
    snapshot = root / "dataset_review_applied_v1/review_decisions_snapshot.json"
    queue = read_json(root / "review_queue.json")["items"]
    decisions = read_json(decisions_path)["decisions"]
    manifest = read_json(root / "dataset_review_applied_v1/manifest.json")
    audits = {sensor: read_json(root / f"dataset_review_applied_v1/{sensor}/preflight.json")
              for sensor in ("V", "T")}
    ledger = read_json(root / "sample_ledger.json")["records"]
    lrf = read_json(root / "lrf/lrf_event_audit.json")

    def sample_key(row):
        return f"{row['sensor']}:{row['split']}:{row['observation_id']}"

    review_keys = {row["key"] for row in decisions}
    queue_keys = {sample_key(row) for row in queue}
    review_complete = (len(review_keys) == len(decisions) == len(queue_keys) == len(queue)
                       and review_keys == queue_keys
                       and all(row["status"] in ("approved_complete", "confirmed_negative") for row in decisions))
    frozen = (digest(decisions_path) == digest(snapshot) == manifest["review_decisions_sha256"])
    preflight_ok = all(not audit["errors"] for audit in audits.values())
    controlled_runs = {}
    for path in sorted((root / "runs").glob("*/run_config.json")):
        config = read_json(path)
        if config.get("purpose") == "controlled":
            controlled_runs[path.parent.name] = {"status": config["status"],
                                                 "data_yaml_sha256": config["data_yaml_sha256"],
                                                 "base_weights_sha256": config["base_weights_sha256"],
                                                 "epochs": config["epochs"],
                                                 "imgsz": config["imgsz"], "seed": config["seed"],
                                                 "error": config.get("error")}
    development_evaluations = {}
    for path in sorted((root / "evaluations").glob("*/result.json")):
        result = read_json(path)
        if result.get("schema_version") == "dji_recovery_confirmation_evaluation_v1":
            continue
        development_evaluations[path.parent.name] = {"status": result["status"],
                                                     "passed_class_count": result.get("passed_class_count"),
                                                     "all_classes_passed": result.get("all_classes_passed")}
    confirmation_path = root / "evaluations/confirmation_frozen_v1/result.json"
    confirmation = read_json(confirmation_path) if confirmation_path.exists() else None
    confirmation_complete = bool(confirmation and confirmation.get("status") == "complete")
    confirmation_labels = root / "confirmation_10s_v2/decisions_frozen_v1.json"
    confirmation_labels_frozen = bool(confirmation_complete and confirmation_labels.exists()
                                      and digest(confirmation_labels) == confirmation["decisions_sha256"])
    localization_path = root / "localization_confirmation_v1/summary.json"
    localization = read_json(localization_path) if localization_path.exists() else None
    report_path = root / "REPORT_20260925.md"
    tracking_v2 = {}
    for path in sorted((root / "tracking_v2").glob("*/manifest.json")):
        record = read_json(path)
        tracking_v2[path.parent.name] = record["summaries"]
    expected_runs = {f"E1_{sensor}_640_s{seed}"
                     for sensor in ("V", "T") for seed in (0, 1, 2)}
    expected_runs.update({f"E2_{sensor}_960_s{seed}"
                          for sensor in ("V", "T") for seed in (0, 1, 2)})
    unevaluated = sorted(name for name, run in controlled_runs.items()
                         if run["status"] == "complete"
                         and development_evaluations.get(name, {}).get("status") != "complete")
    failed_runs = sorted(name for name, run in controlled_runs.items() if run["status"] == "failed")
    interrupted_runs = sorted(name for name, run in controlled_runs.items()
                               if run["status"] == "interrupted_by_user")
    if confirmation_complete:
        gate_passed = all(sensor["all_classes_passed"] for sensor in confirmation["sensors"].values())
        stage = "report_complete_detection_gate_passed" if gate_passed else "report_complete_detection_gate_failed"
        if not report_path.exists() or not localization or len(tracking_v2) != 4:
            stage = "confirmation_complete_reporting_pending"
            next_action = "Finish the tracking and localization capability report; preserve the frozen confirmation result without threshold tuning."
        else:
            next_action = "Current-data workflow complete. Future improvement requires new independent scenes, source-point truth and Matrice 4T calibration."
    elif interrupted_runs:
        stage = "paused_by_user"
        next_action = "On resume, archive interrupted run directories and rerun those seeds from the shared initialization."
    elif failed_runs:
        stage = "controlled_training_failed"
        next_action = "Inspect the failed run configurations and logs before continuing."
    elif any(run["status"] == "running" for run in controlled_runs.values()):
        stage = "controlled_training_in_progress"
        next_action = "Finish the current controlled runs and evaluate their best weights on the frozen development split."
    elif unevaluated:
        stage = "development_evaluation_pending"
        next_action = "Evaluate the completed controlled runs on the frozen development split."
    elif expected_runs.issubset(controlled_runs):
        stage = "controlled_experiments_complete_confirmation_pending"
        next_action = "Freeze the model and thresholds; review the reserved confirmation set before one confirmation evaluation."
    elif controlled_runs:
        stage = "controlled_experiments_in_progress"
        next_action = "Continue the prespecified E1/E2 seed replications."
    else:
        stage = "review_applied_controlled_training_pending"
        next_action = "Start E1 V/T at 640 pixels from the shared YOLOv8n initialization."
    status = {
        "schema_version": "dji_recovery_status_v2",
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "source_dataset": manifest["source_dataset"],
        "derived_dataset": manifest["derived_dataset"],
        "derived_dataset_manifest_sha256": digest(root / "dataset_review_applied_v1/manifest.json"),
        "review_decisions_sha256": digest(decisions_path),
        "review_queue_count": len(queue),
        "review_decision_count": len(decisions),
        "review_decision_counts": dict(Counter(row["status"] for row in decisions)),
        "review_complete": review_complete,
        "review_snapshot_frozen": frozen,
        "dataset_preflight": {sensor: {"error_count": len(audit["errors"]),
                                         "splits": audit["splits"]} for sensor, audit in audits.items()},
        "dataset_preflight_passed": preflight_ok,
        "sample_counts": manifest["counts"],
        "ledger_records": len(ledger),
        "legacy_positive_unreviewed": manifest["legacy_positive_unreviewed"],
        "controlled_training_authorized": review_complete and frozen and preflight_ok,
        "controlled_runs": controlled_runs,
        "development_evaluations": development_evaluations,
        "expected_E1_E2_runs": len(expected_runs),
        "completed_E1_E2_runs": len(expected_runs.intersection(
            name for name, run in controlled_runs.items() if run["status"] == "complete")),
        "unevaluated_controlled_runs": unevaluated,
        "failed_controlled_runs": failed_runs,
        "interrupted_controlled_runs": interrupted_runs,
        "historically_exposed_development_validation": True,
        "strictly_unseen_test_available": False,
        "confirmation_evaluation_performed": confirmation_complete,
        "confirmation_labels_frozen": confirmation_labels_frozen,
        "confirmation_labels_sha256": digest(confirmation_labels) if confirmation_labels.exists() else None,
        "confirmation_result_sha256": digest(confirmation_path) if confirmation_complete else None,
        "confirmation_pair_count": confirmation["pair_count"] if confirmation_complete else None,
        "confirmation_metrics": {sensor: {entry["class_name"]: {
            "ground_truth": entry["ground_truth"],
            "precision": entry["work_metrics"]["precision"],
            "recall": entry["work_metrics"]["recall"],
            "ap50": entry["ap50"], "gate_passed": entry["gate_passed"]}
            for entry in result["classes"]}
            for sensor, result in confirmation["sensors"].items()} if confirmation_complete else None,
        "image_localization": localization,
        "tracking_v2": tracking_v2,
        "final_report_sha256": digest(report_path) if report_path.exists() else None,
        "lrf_event_audit": lrf["by_batch"],
        "physical_source_confirmed_groups": lrf["physical_target_confirmed_groups"],
        "absolute_visual_localization": "unavailable",
        "known_limits": [
            "750 legacy-positive training images retain historical labels without full-image independent review",
            "development validation was exposed during historical model selection",
            "reserved confirmation sessions have historical exposure and are not a strict blind test",
            "ground burning source identity has not been verified for LRF capture groups",
            "Matrice 4T intrinsics, distortion, and extrinsics are unavailable",
        ],
        "next_action": next_action,
    }
    target = root / "status_current.json"
    history = root / "status_history"
    history.mkdir(exist_ok=True)
    if target.exists():
        archived = history / (digest(target) + ".json")
        if not archived.exists():
            archived.write_bytes(target.read_bytes())
    temp = root / "status_current.json.new"
    if temp.exists():
        raise FileExistsError(temp)
    temp.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, target)
    print(json.dumps({"stage": stage, "review_complete": review_complete,
                      "frozen": frozen, "preflight_passed": preflight_ok,
                      "controlled_runs": controlled_runs}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    refresh(parser.parse_args().root)
