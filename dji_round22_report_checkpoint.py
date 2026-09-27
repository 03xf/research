#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
report_json = root / "consolidated_report_round22.json"
report_md = root / "consolidated_report_round22.md"
assert report_json.is_file() and report_md.is_file()
state_path = root / "state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
report = json.loads(report_json.read_text(encoding="utf-8"))
state["stage"] = "round22_consolidated_report_complete_next_independent_scene_review"
state["consolidated_report"] = {"status": "complete", "json": str(report_json), "markdown": str(report_md), "detector_gate": report["detector_gate"]["status"], "absolute_localization": report["calibration"]["status"], "blind_test_accessed": False}
state["next_action"] = "Continue with independent-scene label audit and tiled/small-target controlled training; keep the detector gate, blind test, T/V spatial correspondence and absolute localization conditions explicit."
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(state["stage"])
