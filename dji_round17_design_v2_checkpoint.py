#!/usr/bin/env python3
"""Append the fourth controlled cell without rewriting Round17 v1 evidence."""
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
source = root / "round17_control_design.json"
target = root / "round17_control_design_v2.json"
state_path = root / "state.json"
if target.exists():
    raise SystemExit("v2 design exists; refusing to overwrite")
design = json.loads(source.read_text(encoding="utf-8"))
run = root / "runs_round17_control/V_base_labels_auto_visible_gpu1"
assert (run / "run_config.json").exists()
design["schema_version"] = "dji_round17_optimizer_label_control_v2"
design["supersedes"] = str(source)
design["updated_utc"] = datetime.now(timezone.utc).isoformat()
design["cells"]["original_labels_auto"] = {"run": str(run), "status": "running", "run_config": str(run / "run_config.json"), "CUDA_VISIBLE_DEVICES": "1", "note": "Physical GPU1 explicitly selected; logical CUDA device0."}
design.pop("missing_cell", None)
design["next_action"] = "Wait for all three active controlled runs; validate each against the unchanged validation split, compare label and optimizer effects, then decide whether Round18 smoke-label proposals should enter a separate training dataset."
target.write_text(json.dumps(design, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
state = json.loads(state_path.read_text(encoding="utf-8"))
state["round17"] = {"design": str(target), "status": "three_controls_running_one_historical", "blind_test_accessed": False}
state["next_action"] = design["next_action"]
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(target)
