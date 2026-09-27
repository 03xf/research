#!/usr/bin/env python3
"""Build a prioritized manual-review queue from DJI association outputs."""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def max_conf(det):
    values = det.get("confidence", []) if det else []
    return max([float(x) for x in values], default=0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--association", required=True, type=Path)
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--frames-index", required=True, type=Path)
    ap.add_argument("--quality", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    association = json.loads(args.association.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    frame_index = json.loads(args.frames_index.read_text(encoding="utf-8")).get("frames", {})
    manifest_rows = manifest.get("observations", [])
    manifest_by_group = defaultdict(list)
    for item in manifest_rows:
        manifest_by_group[(item.get("batch_id"), item.get("video_group"))].append(item)
    quality = json.loads(args.quality.read_text(encoding="utf-8"))
    queue_by_id = {}
    for row in association.get("observations", []):
        t = row.get("thermal_detection", {})
        v = row.get("visible_detection", {})
        t_boxes, v_boxes = t.get("boxes", []), v.get("boxes", [])
        t_conf, v_conf = max_conf(t), max_conf(v)
        reasons = []
        if row.get("association_status") in {"thermal_only", "visible_only", "ambiguous", "unpaired"}:
            reasons.append(row.get("association_status"))
        if t_boxes and v_boxes and len(t_boxes) != len(v_boxes):
            reasons.append("different_target_count")
        if t_boxes and t_conf < 0.2:
            reasons.append("low_thermal_confidence")
        if v_boxes and v_conf < 0.2:
            reasons.append("low_visible_confidence")
        if not t_boxes and not v_boxes:
            reasons.append("background_confirmation")
        if not reasons:
            continue
        candidates = manifest_by_group.get((row.get("batch_id"), row.get("video_group")), [])
        if not candidates:
            continue
        candidate = min(candidates, key=lambda x: abs(float(x.get("timestamp_s", 0.0)) - float(row.get("timestamp_s", 0.0))))
        if abs(float(candidate.get("timestamp_s", 0.0)) - float(row.get("timestamp_s", 0.0))) > 0.25:
            continue
        obs_id = candidate["observation_id"]
        priority = 0
        priority += 3 if "ambiguous" in reasons or "unpaired" in reasons else 0
        priority += 2 if "different_target_count" in reasons else 0
        priority += 1 if "low_thermal_confidence" in reasons or "low_visible_confidence" in reasons else 0
        priority += 1 if "background_confirmation" in reasons else 0
        item = {
            "priority": priority, "observation_id": obs_id,
            "batch_id": candidate.get("batch_id"), "session_id": candidate.get("session_id"),
            "drone_id": candidate.get("drone_id"), "video_group": candidate.get("video_group"),
            "timestamp_s": candidate.get("timestamp_s"), "association_status": row.get("association_status"),
            "sync_delta_s": row.get("sync_delta_s"), "thermal_confidence": t_conf,
            "visible_confidence": v_conf, "reasons": reasons, "frame_paths": frame_index.get(obs_id, {})
        }
        if obs_id not in queue_by_id or priority > queue_by_id[obs_id]["priority"]:
            queue_by_id[obs_id] = item
    queue = list(queue_by_id.values())
    queue.sort(key=lambda x: (-x["priority"], x.get("batch_id") or "", x.get("video_group") or "", x.get("timestamp_s") or 0))
    by_batch = defaultdict(int)
    for row in queue:
        by_batch[row.get("batch_id")] += 1
    result = {"schema_version": "dji_manual_review_queue_v1", "queue_count": len(queue), "by_batch": dict(sorted(by_batch.items())), "note": "Review priority only; no row is a ground-truth label.", "items": queue}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"queue_count": len(queue), "by_batch": dict(sorted(by_batch.items()))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
