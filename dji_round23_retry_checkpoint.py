#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
path = root / "state.json"
state = json.loads(path.read_text(encoding="utf-8"))
state["stage"] = "round23_tiled_v_t_training_retry1"
state["round23"] = {"status": "training_running", "dataset": str(root / "datasets_round23_tiled_retry1"), "V_run": str(root / "runs_round23_tiled_retry1/V_640_auto"), "T_run": str(root / "runs_round23_tiled_retry1/T_640_auto"), "failed_attempt": {"dataset": str(root / "datasets_round23_tiled"), "reason": "relative data.yaml path resolved against default Ultralytics dataset directory; no epoch started"}, "validation_original": True, "blind_test_accessed": False, "purpose": "small-target/tile controlled experiment"}
state["next_action"] = "Complete the corrected V/T tiled training, validate on the unchanged original validation split, and preserve the failed-path evidence."
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(state["stage"])
