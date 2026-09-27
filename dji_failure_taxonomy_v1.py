#!/usr/bin/env python3
"""Separate background false positives from fragmented/poor-IoU detections."""
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/validation_round24_yolov8n")
out = root / "failure_taxonomy_conf010.json"
if out.exists():
    raise SystemExit("output exists; refusing to overwrite")


def iou(a, b):
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    aa = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    ab = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    return inter / max(1e-12, aa + ab - inter)


sensor_results = {}
for sensor in ("V", "T"):
    path = root / f"{sensor}_failure_cases_conf010.json"
    source = json.loads(path.read_text(encoding="utf-8"))
    names = {0: "smoke", 1: "flame"} if sensor == "V" else {0: "hotspot"}
    counts = {name: Counter() for name in names.values()}
    examples = {name: {"background": [], "fragmented_or_misaligned": [], "near_match": []} for name in names.values()}
    for row in source["failures"]:
        for prediction in row["false_positives"]:
            name = names[prediction["class_id"]]
            same = [target for target in row["ground_truth"] if target["class_id"] == prediction["class_id"]]
            best = max((iou(prediction["bbox_xyxy"], target["bbox_xyxy"]) for target in same), default=0)
            category = "near_match" if best >= .3 else ("fragmented_or_misaligned" if best >= .05 else "background")
            counts[name][category] += 1
            if len(examples[name][category]) < 12:
                examples[name][category].append({"observation_id": row["observation_id"], "confidence": prediction["confidence"], "max_same_class_iou": best})
    sensor_results[sensor] = {"counts": {name: dict(counter) for name, counter in counts.items()}, "examples": examples}
payload = {"schema_version": "dji_failure_taxonomy_conf010_v1", "generated_utc": datetime.now(timezone.utc).isoformat(), "source": {sensor: str(root / f"{sensor}_failure_cases_conf010.json") for sensor in ("V", "T")}, "categories": {"background": "IoU < 0.05 with any same-class GT", "fragmented_or_misaligned": "0.05 <= maximum same-class IoU < 0.30", "near_match": "0.30 <= maximum same-class IoU < 0.50 or duplicate after matching"}, "results": sensor_results, "interpretation": "This is a diagnostic at conf=0.1 and IoU=0.5, not final precision/recall. A prediction fragment within a large smoke/hotspot GT can count as FP under box IoU even if a visually relevant region is detected."}
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({sensor: value["counts"] for sensor, value in sensor_results.items()}, ensure_ascii=False))
