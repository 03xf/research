#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
paths = {
    "B1_inference": root / "inference_round21_B1_provisional/observations.json",
    "B1_association": root / "association_round21_B1_provisional.json",
    "B1_tracking": root / "tracking_round21_B1_provisional.json",
    "B3_inference": root / "inference_round21_B3_provisional/observations.json",
    "B3_association": root / "association_round21_B3_provisional.json",
    "B3_tracking": root / "tracking_round21_B3_provisional.json",
    "all_batch_lrf_photo_association": root / "localization/detection_lrf_association_all_round20.json",
}
assert all(path.is_file() for path in paths.values())
state_path = root / "state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
state["stage"] = "round21_B1_B3_inference_association_tracking_complete"
state["round21"] = {"status": "complete", "paths": {name: str(path) for name, path in paths.items()}, "blind_test_accessed": False, "absolute_localization": "unavailable", "summaries": {name: json.loads(path.read_text(encoding="utf-8"))["summary"] for name, path in paths.items()}}
state["next_action"] = "Use B1/B3 tracks only for temporal and image-plane analysis; combine them with the grouped LRF dispersion report, never average distinct targets. Continue calibration recovery and determine whether a known-target calibration collection is possible."
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(state["round21"]["summaries"], ensure_ascii=False))
