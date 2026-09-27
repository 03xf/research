#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
inference = root / "inference_round22_B2_provisional/observations.json"
association = root / "association_round22_B2_provisional.json"
tracking = root / "tracking_round22_B2_provisional.json"
for p in (inference, association, tracking):
    assert p.is_file(), p
state_path = root / "state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
inf, assoc, track = [json.loads(p.read_text(encoding="utf-8")) for p in (inference, association, tracking)]
state["stage"] = "round22_B2_prefire_association_tracking_complete"
state["round22"] = {"status": "complete", "inference": str(inference), "association": str(association), "tracking": str(tracking), "semantics": "B2 pre-fire/hotspot candidate only; not burning-fire truth", "blind_test_accessed": False, "absolute_localization": "unavailable", "summary": {"inference": inf["summary"], "association": assoc["summary"], "tracking": track["summary"]}}
state["next_action"] = "Generate the consolidated B1-B4 provisional report and keep B2 excluded from burning-fire truth and absolute-localization metrics. Continue calibration recovery and image-plane/LRF reference analysis."
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(state["round22"]["summary"], ensure_ascii=False))
