#!/usr/bin/env python3
"""Quality checks for coarse DJI inference outputs."""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", required=True, type=Path)
    ap.add_argument("--sync-dir", required=True, type=Path)
    ap.add_argument("--inference-root", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    info = {}
    for p in args.sync_dir.glob("B*.json"):
        for pair in load(p).get("pairs", []):
            info[pair.get("T")] = pair.get("T_info", {})
            info[pair.get("V")] = pair.get("V_info", {})
    source_to_meta = {}
    for g in load(args.inventory).get("groups", []):
        for sensor, source in (("T", g.get("thermal_video")), ("V", g.get("visible_video"))):
            if source:
                source_to_meta[source] = {"batch_id": g.get("batch_id"), "session_id": g.get("session_id"), "drone_id": g.get("drone_id"), "sensor": sensor}
    rows, batch = [], defaultdict(lambda: {"sources": 0, "sampled_frames": 0, "detection_frames": 0, "boxes": 0, "invalid_boxes": 0, "mean_confidence_values": [], "max_zero_run": 0})
    for path in Path(args.inference_root).rglob("*.json"):
        if path.name == "summary.json":
            continue
        try:
            data = load(path)
        except Exception:
            continue
        source = data.get("source")
        records = data.get("records")
        if not source or not isinstance(records, list):
            continue
        meta = source_to_meta.get(source, {})
        dims = (info.get(source) or {}).get("size") or []
        width, height = (float(dims[0]), float(dims[1])) if len(dims) == 2 else (None, None)
        zero_run = longest_zero_run = 0
        detection_frames = boxes = invalid = 0
        conf = []
        for rec in records:
            det = rec.get("boxes", [])
            if det:
                detection_frames += 1
                zero_run = 0
            else:
                zero_run += 1
                longest_zero_run = max(longest_zero_run, zero_run)
            boxes += len(det)
            conf.extend(float(x) for x in rec.get("confidence", []) if isinstance(x, (int, float)) and math.isfinite(float(x)))
            for box in det:
                if len(box) != 4 or not all(isinstance(x, (int, float)) and math.isfinite(float(x)) for x in box):
                    invalid += 1
                    continue
                x1, y1, x2, y2 = map(float, box)
                if x2 < x1 or y2 < y1 or x1 < 0 or y1 < 0 or (width is not None and x2 > width) or (height is not None and y2 > height):
                    invalid += 1
        row = {"source": source, **meta, "sampled_frames": len(records), "detection_frames": detection_frames, "detection_frame_rate": detection_frames / len(records) if records else 0.0, "boxes": boxes, "invalid_boxes": invalid, "mean_confidence": sum(conf) / len(conf) if conf else None, "max_zero_run": longest_zero_run, "image_size": [width, height] if width is not None else None}
        rows.append(row)
        b = batch[row.get("batch_id", "unknown")]
        b["sources"] += 1; b["sampled_frames"] += len(records); b["detection_frames"] += detection_frames; b["boxes"] += boxes; b["invalid_boxes"] += invalid; b["mean_confidence_values"].extend(conf); b["max_zero_run"] = max(b["max_zero_run"], longest_zero_run)
    summary = {}
    for key, value in batch.items():
        vals = value.pop("mean_confidence_values")
        value["detection_frame_rate"] = value["detection_frames"] / value["sampled_frames"] if value["sampled_frames"] else 0.0
        value["mean_confidence"] = sum(vals) / len(vals) if vals else None
        summary[key] = value
    payload = {"schema_version": "dji_detection_quality_v1", "summary": summary, "sources": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
