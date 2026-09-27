#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
state_path = root / "state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
state["stage"] = "round24_yolov8n_architecture_training"
state["round24"] = {"status": "training_running", "base_weights": "/home/member/xmy/xmy/weights/pretrained/ultralytics/yolov8n.pt", "V_dataset": str(root / "datasets_round18_smoke_qc_v/V/data.yaml"), "T_dataset": str(root / "datasets_round19_thermal_qc_t/T/data.yaml"), "V_run": str(root / "runs_round24_yolov8n/V_full100"), "T_run": str(root / "runs_round24_yolov8n/T_full100"), "smoke_runs": [str(root / "runs_round24_yolov8n/V_smoke1"), str(root / "runs_round24_yolov8n/T_smoke1")], "blind_test_accessed": False, "validation_unchanged": True}
state["next_action"] = "Finish full YOLOv8n V/T training and compare on unchanged validation split. Keep blind test sealed until both sensors pass detection gate; continue LRF/calibration work independently."
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(state["stage"])
