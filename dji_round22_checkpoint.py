#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
path = root / "state.json"
state = json.loads(path.read_text(encoding="utf-8"))
state["stage"] = "round22_B2_prefire_provisional_inference"
state["round22"] = {"status": "running", "batch": "B2", "schedule": str(root / "b2_aligned_frame_schedule_v1.json"), "output": str(root / "inference_round22_B2_provisional/observations.json"), "semantics": "pre-fire/hotspot candidate only; not burning-fire truth", "blind_test_accessed": False, "absolute_localization": "unavailable"}
state["next_action"] = "Complete B2 temporal candidates and image-plane tracks, then generate the consolidated round22 report for B1-B4. B2 will remain separate from flame-truth and absolute-localization statistics."
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(state["stage"])
