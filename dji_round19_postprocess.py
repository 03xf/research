#!/usr/bin/env python3
"""Validate Round19 T hotspot QC training on the unchanged validation split."""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

work = Path("/home/member/xmy/xmy")
sys.path.insert(0, str(work / "code/tools"))
import dji_round17_postprocess as common

root = work / "results/dji_adaptation/b4_trial_v7"
run = root / "runs_round19_thermal_qc/T_640_auto"
common.OUT = root / "validation_round19_thermal_qc"
deadline = time.monotonic() + 3 * 3600
while not common.valid_completion(run):
    if time.monotonic() > deadline:
        raise SystemExit("Round19 training did not complete within 3 hours; inspect the log")
    time.sleep(60)
common.OUT.mkdir(parents=True, exist_ok=True)
new = common.validate("T_640_auto", run)
state_path = root / "state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
old = state["metrics"]["T_640_round12"]
gate = {"precision": 0.60, "recall": 0.70, "mAP50": 0.50}
row = new["classes"].get("hotspot")
old_values = {"precision": old["mp"], "recall": old["mr"], "mAP50": old["map50"]}
comparison = {
    "schema_version": "dji_round19_thermal_qc_comparison_v1",
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "validation_only": True,
    "blind_test_accessed": False,
    "round19": new,
    "round12_reference": old,
    "delta_vs_round12": {metric: row[metric] - old_values[metric] for metric in gate},
    "gate": {"criteria": gate, "passed": row["validation_instances"] >= 20 and all(row[metric] >= threshold for metric, threshold in gate.items())},
    "interpretation": "This compares train-only thermal label corrections on the unchanged validation split. Hotspot is not treated as flame center or LRF truth."
}
out = common.OUT / "comparison.json"
if out.exists():
    raise SystemExit("comparison exists; refusing to overwrite")
out.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
state["stage"] = "round19_validation_complete" if comparison["gate"]["passed"] else "round19_validation_failed_next_hotspot_review"
state["round19"] = {"status": state["stage"], "comparison": str(out), "blind_test_accessed": False}
state["next_action"] = "If T gate passes, keep this model as a thermal candidate and validate B4 on the aligned timestamp schedule. If it fails, review additional independent hotspot scenes and retain degraded localization only."
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"stage": state["stage"], "comparison": str(out), "delta_vs_round12": comparison["delta_vs_round12"]}, ensure_ascii=False), flush=True)
