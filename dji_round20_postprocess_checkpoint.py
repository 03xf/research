#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
inference = root / "inference_round20_aligned_provisional/observations.json"
association = root / "association_round20_aligned_provisional.json"
tracking = root / "tracking_round20_aligned_provisional.json"
lrf = root / "localization/detection_lrf_association_v1.json"
for path in (inference, association, tracking, lrf):
    assert path.is_file(), path
state_path = root / "state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
inf = json.loads(inference.read_text(encoding="utf-8"))
assoc = json.loads(association.read_text(encoding="utf-8"))
track = json.loads(tracking.read_text(encoding="utf-8"))
lrf_data = json.loads(lrf.read_text(encoding="utf-8"))
state["stage"] = "round20_aligned_provisional_association_tracking_complete"
state["round20"] = {"status": "complete", "inference": str(inference), "association": str(association), "tracking": str(tracking), "lrf_detection_association": str(lrf), "blind_test_accessed": False, "absolute_localization": "unavailable", "summary": {"inference": inf["summary"], "association": assoc["summary"], "tracking": track["summary"], "lrf": lrf_data["summary"]}}
state["next_action"] = "Use the aligned B4 provisional observations for temporal-only fire-event candidates and image-plane stability analysis; inspect LRF photo candidates manually, continue calibration recovery, and keep absolute coordinates unavailable until true intrinsics, distortion and extrinsics are obtained."
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(state["round20"]["summary"], ensure_ascii=False))
