#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
path = root / "state.json"
state = json.loads(path.read_text(encoding="utf-8"))
state["stage"] = "round20_aligned_provisional_inference"
state["round20"] = {"status": "running", "schedule": str(root / "b4_aligned_frame_schedule_v1.json"), "output": str(root / "inference_round20_aligned_provisional/observations.json"), "v_weights": str(root / "runs_round17_control/V_base_labels_auto_visible_gpu1/weights/best.pt"), "t_weights": str(root / "runs_round19_thermal_qc/T_640_auto/weights/best.pt"), "blind_test_accessed": False, "absolute_localization": "unavailable", "spatial_correspondence": "unverified"}
state["next_action"] = "Finish timestamp-aligned provisional B4 inference, build temporal-only association and sensor-specific image-plane tracks, then compare detections with grouped LRF references. Do not claim absolute coordinates without calibration."
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(state["stage"])
