#!/usr/bin/env python3
"""Automatically validate Round18 after successful training, blind test sealed."""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

work = Path("/home/member/xmy/xmy")
sys.path.insert(0, str(work / "code/tools"))
import dji_round17_postprocess as common

root = work / "results/dji_adaptation/b4_trial_v7"
run = root / "runs_round18_smoke_qc/V_640_auto"
common.OUT = root / "validation_round18_smoke_qc"
deadline = time.monotonic() + 3 * 3600
while not common.valid_completion(run):
    if time.monotonic() > deadline:
        raise SystemExit("Round18 training not complete within 3 hours; inspect log and run_config")
    time.sleep(60)
common.OUT.mkdir(parents=True, exist_ok=True)
new = common.validate("V_640_auto", run)
prior = json.loads((root / "validation_round17_control/reviewed_labels_auto/metrics.json").read_text(encoding="utf-8"))
gate = {"precision": 0.60, "recall": 0.70, "mAP50": 0.50}
classes = new["classes"]
passed = all(row["validation_instances"] >= 20 and all(row[key] >= threshold for key, threshold in gate.items()) for row in classes.values())
comparison = {"schema_version": "dji_round18_smoke_qc_comparison_v1", "generated_utc": datetime.now(timezone.utc).isoformat(), "validation_only": True, "blind_test_accessed": False, "round18": new, "round17_reviewed_auto": prior, "delta": {cls: {metric: classes[cls][metric] - prior["classes"][cls][metric] for metric in gate} for cls in classes}, "gate": {"criteria": gate, "passed": passed}, "interpretation": "Training-label changes are compared under the same base checkpoint, automatic optimizer, 640 input, 100 epochs, seed 0 and unchanged validation set. This does not establish independent-test generalization."}
out = common.OUT / "comparison.json"
if out.exists():
    raise SystemExit("comparison exists; refusing to overwrite")
out.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
state_path = root / "state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
state["stage"] = "round18_validation_passed_freeze_candidate" if passed else "round18_validation_failed_more_independent_scenes"
state["round18"] = {"status": state["stage"], "comparison": str(out), "blind_test_accessed": False}
state["next_action"] = "If passed, freeze model and evaluate sealed blind test once. If failed, expand independently reviewed smoke/hotspot scenarios and consider tiled small-target training; do not fabricate localization parameters."
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"stage": state["stage"], "comparison": str(out), "delta": comparison["delta"]}, ensure_ascii=False), flush=True)
