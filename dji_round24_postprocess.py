#!/usr/bin/env python3
"""Validate Round24 standard YOLOv8n V/T models on unchanged held-out split."""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

work = Path("/home/member/xmy/xmy")
sys.path.insert(0, str(work / "code/tools"))
import dji_round17_postprocess as common

root = work / "results/dji_adaptation/b4_trial_v7"
runs = {"V": root / "runs_round24_yolov8n/V_full100", "T": root / "runs_round24_yolov8n/T_full100"}
common.OUT = root / "validation_round24_yolov8n"
deadline = time.monotonic() + 4 * 3600
while not all(common.valid_completion(run) for run in runs.values()):
    if time.monotonic() > deadline:
        raise SystemExit("Round24 full training incomplete after four hours; inspect logs")
    time.sleep(60)
common.OUT.mkdir(parents=True, exist_ok=True)
results = {sensor: common.validate(sensor, run) for sensor, run in runs.items()}
gate = {"precision": .60, "recall": .70, "mAP50": .50}
passed = {sensor: all(row["validation_instances"] >= 20 and all(row[key] >= threshold for key, threshold in gate.items()) for row in result["classes"].values()) for sensor, result in results.items()}
reference = {"V": json.loads((root / "validation_round18_smoke_qc/V_640_auto/metrics.json").read_text(encoding="utf-8")), "T": json.loads((root / "validation_round19_thermal_qc/T_640_auto/metrics.json").read_text(encoding="utf-8"))}
deltas = {sensor: {cls: {metric: row[metric] - reference[sensor]["classes"][cls][metric] for metric in gate} for cls, row in result["classes"].items()} for sensor, result in results.items()}
payload = {"schema_version": "dji_round24_yolov8n_comparison_v1", "generated_utc": datetime.now(timezone.utc).isoformat(), "validation_only": True, "blind_test_accessed": False, "yolov8n": results, "reference_custom_model": reference, "delta": deltas, "gate": {"criteria": gate, "passed_by_sensor": passed, "both_passed": all(passed.values())}, "interpretation": "Alternative standard YOLOv8n initialization/architecture compared on same train label versions and unchanged validation split; no blind-test claim."}
out = common.OUT / "comparison.json"
if out.exists():
    raise SystemExit("comparison exists; refusing to overwrite")
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
state_path = root / "state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
state["stage"] = "round24_yolov8n_validation_passed" if all(passed.values()) else "round24_yolov8n_validation_failed_next_independent_labels"
state["round24"] = {"status": state["stage"], "comparison": str(out), "blind_test_accessed": False}
state["next_action"] = "If both sensors pass, freeze and evaluate the sealed blind test once; otherwise build independent-scene training labels, inspect class definition/false positives, and retain degraded localization only."
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"stage": state["stage"], "comparison": str(out), "gate": payload["gate"], "delta": deltas}, ensure_ascii=False), flush=True)
