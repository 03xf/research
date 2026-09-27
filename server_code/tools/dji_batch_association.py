#!/usr/bin/env python3
"""Associate coarse T/V detection records on a common time axis.

Association is deliberately conservative: temporal pairing alone is not
treated as a confirmed spatial correspondence.  Ambiguous multi-target
observations remain ambiguous.
"""
import argparse
import json
from collections import Counter
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fps(info):
    value = (info or {}).get("fps")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and "/" in value:
        try:
            a, b = value.split("/", 1)
            return float(a) / float(b)
        except Exception:
            return 30.0
    try:
        return float(value)
    except Exception:
        return 30.0


def result_index(root):
    out = {}
    for path in Path(root).rglob("*.json"):
        if path.name == "summary.json":
            continue
        try:
            d = load(path)
        except Exception:
            continue
        if d.get("source") and "records" in d:
            out[d["source"]] = d
    return out


def nearest(records, target_s, frame_fps):
    if not records:
        return None, None
    rec = min(records, key=lambda r: abs(int(r.get("sample_index", 0)) / frame_fps - target_s))
    return rec, abs(int(rec.get("sample_index", 0)) / frame_fps - target_s)


def status(t_boxes, v_boxes, delta):
    if delta is None or delta > 0.1:
        return "unpaired"
    if t_boxes and v_boxes:
        return "paired" if len(t_boxes) == 1 and len(v_boxes) == 1 else "ambiguous"
    if t_boxes:
        return "thermal_only"
    if v_boxes:
        return "visible_only"
    return "paired"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", required=True, type=Path)
    ap.add_argument("--sync-dir", required=True, type=Path)
    ap.add_argument("--inference-root", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    inventory = load(args.inventory)
    results = result_index(args.inference_root)
    sync = {}
    for path in sorted(args.sync_dir.glob("B*.json")):
        for pair in load(path).get("pairs", []):
            sync[(pair.get("T"), pair.get("V"))] = pair
    observations = []
    missing = []
    for group in inventory.get("groups", []):
        t_source, v_source = group.get("thermal_video"), group.get("visible_video")
        if not t_source or not v_source:
            continue
        pair = sync.get((t_source, v_source))
        t_data, v_data = results.get(t_source), results.get(v_source)
        if not pair or not t_data or not v_data:
            missing.append({"batch_id": group.get("batch_id"), "video_group": group.get("video_group"), "status": "inference_unavailable"})
            continue
        t_fps, v_fps = fps(pair.get("T_info")), fps(pair.get("V_info"))
        t_records, v_records = t_data.get("records", []), v_data.get("records", [])
        used_v = set()
        for t_rec in t_records:
            t_frame = int(t_rec.get("sample_index", 0))
            t_time = t_frame / t_fps
            v_rec, delta = nearest(v_records, t_time, v_fps)
            if v_rec is not None:
                used_v.add(int(v_rec.get("sample_index", 0)))
            t_boxes, v_boxes = t_rec.get("boxes", []), (v_rec or {}).get("boxes", [])
            row = {
                "observation_id": f"{group.get('batch_id')}_{group.get('video_group')}_t{t_frame:06d}",
                "batch_id": group.get("batch_id"), "session_id": group.get("session_id"),
                "drone_id": group.get("drone_id"), "video_group": group.get("video_group"),
                "timestamp_s": round(t_time, 6), "thermal_frame": t_frame,
                "visible_frame": int(v_rec.get("sample_index", 0)) if v_rec is not None else None,
                "thermal_detection": {"boxes": t_boxes, "confidence": t_rec.get("confidence", []), "class": t_rec.get("class", [])},
                "visible_detection": {"boxes": v_boxes, "confidence": (v_rec or {}).get("confidence", []), "class": (v_rec or {}).get("class", [])},
                "association_status": status(t_boxes, v_boxes, delta),
                "sync_delta_s": round(delta, 6) if delta is not None else None,
                "track_id": None,
                "metadata_reference": {"sync_pair_key": pair.get("pair_key"), "thermal_source": t_source, "visible_source": v_source}
            }
            observations.append(row)
        # Preserve visible samples that had no thermal counterpart.
        for v_rec in v_records:
            v_frame = int(v_rec.get("sample_index", 0))
            if v_frame in used_v:
                continue
            v_time = v_frame / v_fps
            t_rec, delta = nearest(t_records, v_time, t_fps)
            if delta is not None and delta <= 0.1:
                continue
            observations.append({
                "observation_id": f"{group.get('batch_id')}_{group.get('video_group')}_v{v_frame:06d}",
                "batch_id": group.get("batch_id"), "session_id": group.get("session_id"),
                "drone_id": group.get("drone_id"), "video_group": group.get("video_group"),
                "timestamp_s": round(v_time, 6), "thermal_frame": None, "visible_frame": v_frame,
                "thermal_detection": {"boxes": [], "confidence": [], "class": []},
                "visible_detection": {"boxes": v_rec.get("boxes", []), "confidence": v_rec.get("confidence", []), "class": v_rec.get("class", [])},
                "association_status": "visible_only", "sync_delta_s": round(delta, 6) if delta is not None else None,
                "track_id": None, "metadata_reference": {"sync_pair_key": pair.get("pair_key"), "thermal_source": t_source, "visible_source": v_source}
            })
    counts = Counter(row["association_status"] for row in observations)
    summary = {"observation_count": len(observations), "status_counts": dict(sorted(counts.items())), "missing_group_count": len(missing), "missing_groups": missing}
    payload = {"schema_version": "dji_tv_association_v1", "summary": summary, "observations": observations}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
