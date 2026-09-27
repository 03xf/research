#!/usr/bin/env python3
"""Checkpoint the train-only Round18 smoke-label QC experiment."""
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
out = root / "round18_smoke_qc_plan.json"
state_path = root / "state.json"
if out.exists():
    raise SystemExit("plan exists; refusing to overwrite")
dataset = root / "datasets_round18_smoke_qc_v/V"
run = root / "runs_round18_smoke_qc/V_640_auto"
assert (dataset / "dataset_manifest.json").exists() and (run / "run_config.json").exists()
doc = {"schema_version": "dji_round18_smoke_qc_plan_v1", "created_utc": datetime.now(timezone.utc).isoformat(), "hypothesis": "Removing clearly misplaced train-only smoke boxes and adding bounded independent plumes may improve V smoke validation without changing optimizer or base checkpoint.", "dataset_manifest": str(dataset / "dataset_manifest.json"), "run": str(run), "log": str(root / "logs_round18_smoke_qc/V_640_auto.log"), "same_base_as_round17": True, "same_optimizer_as_round17_reviewed_auto": True, "validation_unchanged": True, "blind_test_accessed": False, "gate": {"precision": 0.60, "recall": 0.70, "mAP50": 0.50}, "next_action": "Validate Round18 on the unchanged split after 100 successful epochs; if it fails, sample additional distinct smoke and hotspot scenes rather than changing the blind test."}
out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
state = json.loads(state_path.read_text(encoding="utf-8"))
state["stage"] = "round18_smoke_qc_training"
state["round18"] = {"plan": str(out), "status": "training_running", "blind_test_accessed": False}
state["next_action"] = doc["next_action"]
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(out)
