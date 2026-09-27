#!/usr/bin/env python3
"""Sensor-specific coarse tracks and image-plane positions; never 3-D geolocate."""
import argparse
import json
import math
from collections import defaultdict, Counter
from pathlib import Path

SIZE = {"T": (1280, 1024), "V": (1920, 1080)}


def center(box):
    x1, y1, x2, y2 = map(float, box)
    return [(x1 + x2) / 2, (y1 + y2) / 2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--max-gap-s", type=float, default=20)
    ap.add_argument("--max-distance-px", type=float, default=180)
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit("output exists; refusing to overwrite")
    source = json.loads(args.input.read_text(encoding="utf-8"))
    rows = sorted(source["observations"], key=lambda r: (r["session_id"], r["drone_id"], r["video_group"], r["timestamp_s"]))
    states = defaultdict(dict)
    counters = defaultdict(int)
    tracks = {}
    points = []
    for row in rows:
        for sensor, field, frame_field, time_field in (("T", "thermal_detection", "thermal_frame", "thermal_timestamp_s"), ("V", "visible_detection", "visible_frame", "visible_timestamp_s")):
            frame = row.get(frame_field)
            t = row.get(time_field)
            if frame is None or t is None:
                continue
            key = (row["batch_id"], row["session_id"], row["drone_id"], row["video_group"], sensor)
            boxes = row[field].get("boxes", [])
            confs = row[field].get("confidence", [])
            classes = row[field].get("class", [])
            used = set()
            for i, box in enumerate(boxes):
                c = center(box)
                options = []
                for tid, s in states[key].items():
                    dt = t - s["time"]
                    if tid in used or dt < 0 or dt > args.max_gap_s:
                        continue
                    d = math.hypot(c[0] - s["center"][0], c[1] - s["center"][1])
                    if d <= args.max_distance_px:
                        options.append((d, tid))
                if options:
                    _, tid = min(options)
                else:
                    counters[key] += 1
                    tid = counters[key]
                used.add(tid)
                states[key][tid] = {"time": t, "center": c}
                track_id = ":".join(map(str, key)) + ":" + str(tid)
                w, h = SIZE[sensor]
                point = {"observation_id": row["observation_id"], "track_id": track_id, "sensor": sensor, "class_id": int(classes[i]) if i < len(classes) else None, "confidence": float(confs[i]) if i < len(confs) else None, "timestamp_s": t, "frame_index": frame, "pixel_center": c, "normalized_center": [c[0] / w, c[1] / h], "bbox_xyxy": box, "bbox_area_px2": max(0, float(box[2]) - float(box[0])) * max(0, float(box[3]) - float(box[1])), "image_size": [w, h], "localization_mode": "image_plane_only", "absolute_coordinate": "unavailable", "metadata_reference": row.get("metadata_reference")}
                points.append(point)
                stat = tracks.setdefault(track_id, {"sensor": sensor, "count": 0, "first_timestamp_s": t, "last_timestamp_s": t, "centers": [], "confidence": []})
                stat["count"] += 1
                stat["last_timestamp_s"] = t
                stat["centers"].append(c)
                if point["confidence"] is not None:
                    stat["confidence"].append(point["confidence"])
    for stat in tracks.values():
        centers = stat.pop("centers")
        conf = stat.pop("confidence")
        stat["duration_s"] = stat["last_timestamp_s"] - stat["first_timestamp_s"]
        stat["mean_confidence"] = sum(conf) / len(conf) if conf else None
        if len(centers) > 1:
            motions = [math.hypot(centers[i][0]-centers[i-1][0], centers[i][1]-centers[i-1][1]) for i in range(1,len(centers))]
            stat["mean_step_px"] = sum(motions)/len(motions)
        else:
            stat["mean_step_px"] = None
    out = {"schema_version": "dji_degraded_tracking_v3", "provisional_detector": True, "cross_sensor_fusion": "disabled; no verified spatial correspondence", "absolute_3d": "unavailable", "limits": {"max_gap_s": args.max_gap_s, "max_distance_px": args.max_distance_px}, "summary": {"point_count": len(points), "track_count": len(tracks), "sensor_points": dict(Counter(p["sensor"] for p in points)), "multi_observation_track_count": sum(v["count"]>1 for v in tracks.values())}, "tracks": tracks, "image_plane_points": points}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
