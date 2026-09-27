#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
path = root / "state.json"
state = json.loads(path.read_text(encoding="utf-8"))
state["stage"] = "round23_tiled_v_t_training"
state["round23"] = {"status": "training_running", "dataset": str(root / "datasets_round23_tiled"), "V_run": str(root / "runs_round23_tiled/V_640_auto"), "T_run": str(root / "runs_round23_tiled/T_640_auto"), "validation_original": True, "blind_test_accessed": False, "purpose": "small-target/tile controlled experiment"}
state["next_action"] = "Complete V/T tiled training, validate on the unchanged original 71-image validation split, and compare per-class metrics with the non-tiled controls. If useful, rerun aligned B4/B1/B2/B3 inference with the better candidate."
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(state["stage"])
