#!/usr/bin/env python3
"""Read-only loadability and provenance audit of local alternative YOLO weights."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

work = Path("/home/member/xmy/xmy")
sys.path.insert(0, str(work / "code/projects/ultralytics"))
from ultralytics import YOLO

root = work / "results/dji_adaptation/b4_trial_v7"
out = root / "alternative_model_audit_v1.json"
if out.exists():
    raise SystemExit("audit exists; refusing to overwrite")
weights = [work / "weights/pretrained/ultralytics/yolov8n.pt", work / "weights/pretrained/yolov11/yolo11n.pt"]
rows = []
for path in weights:
    row = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size_bytes": path.stat().st_size}
    try:
        model = YOLO(str(path))
        row.update({"loadable": True, "task": model.task, "class_count": len(model.names), "architecture": model.model.__class__.__name__})
    except Exception as exc:
        row.update({"loadable": False, "error": repr(exc)})
    rows.append(row)
out.write_text(json.dumps({"schema_version": "dji_alternative_model_audit_v1", "generated_utc": datetime.now(timezone.utc).isoformat(), "current_project_ultralytics": str(work / "code/projects/ultralytics"), "candidates": rows, "purpose": "Test architecture/pretrained initialization only after current controlled validation; keep all data splits and labels unchanged."}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(rows, ensure_ascii=False))
