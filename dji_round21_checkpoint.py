#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
state_path = root / "state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
state["stage"] = "round21_B1_B3_aligned_provisional_inference"
state["round21"] = {"status": "running", "batches": ["B1", "B3"], "schedules": [str(root / "b1_aligned_frame_schedule_v1.json"), str(root / "b3_aligned_frame_schedule_v1.json")], "outputs": [str(root / "inference_round21_B1_provisional/observations.json"), str(root / "inference_round21_B3_provisional/observations.json")], "blind_test_accessed": False, "absolute_localization": "unavailable"}
state["next_action"] = "Complete B1/B3 timestamp-aligned provisional inference, temporal-only association and sensor-specific tracks; compare against grouped LRF metadata without averaging unrelated targets."
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(state["stage"])
