#!/usr/bin/env python3
"""Time-correct, conservative T/V observations from strided inference.

This does not establish cross-camera spatial correspondence: in the absence
of calibrated T/V extrinsics, simultaneous boxes are temporal candidates.
"""
import argparse
import json
import math
from collections import Counter
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fps(info):
    value = info.get("fps")
    if isinstance(value, str) and "/" in value:
        a, b = value.split("/", 1)
        return float(a) / float(b)
    return float(value)


def data_by_source(root):
    out = {}
    for path in Path(root).rglob("*.json"):
        if path.name == "summary.json":
            continue
        try:
            data = read(path)
        except (ValueError, OSError):
            continue
        if data.get("source") and isinstance(data.get("records"), list):
            out[data["source"]] = data
    return out


def timed_records(data, info):
    rate = fps(info)
    stride = int(data.get("vid_stride", 1))
    start = float(info.get("start_s", 0) or 0)
    return [
        (start + int(rec["sample_index"]) * stride / rate,
         int(rec["sample_index"]) * stride, rec)
        for rec in data["records"]
    ]


def detection(rec):
    return {name: rec.get(name, []) for name in ("boxes", "confidence", "class")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", required=True, type=Path)
    ap.add_argument("--sync", required=True, type=Path)
    ap.add_argument("--visible-root", required=True, type=Path)
    ap.add_argument("--thermal-root", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--tolerance-s", type=float, default=0.1)
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit("output exists; refusing to overwrite")
    inventory = read(args.inventory)
    pairs = {(p["T"], p["V"]): p for p in read(args.sync)["pairs"]}
    visible = data_by_source(args.visible_root)
    thermal = data_by_source(args.thermal_root)
    rows = []
    missing = []
    for group in inventory["groups"]:
        if group.get("batch_id") != "B4":
            continue
        t_src, v_src = group.get("thermal_video"), group.get("visible_video")
        if not t_src or not v_src:
            continue
        pair = pairs.get((t_src, v_src))
        td, vd = thermal.get(t_src), visible.get(v_src)
        if not pair or not td or not vd:
            missing.append({"video_group": group.get("video_group"), "thermal": bool(td), "visible": bool(vd), "sync": bool(pair)})
            continue
        tr = timed_records(td, pair["T_info"])
        vr = timed_records(vd, pair["V_info"])
        used_v = set()
        for ti, (tt, tf, trec) in enumerate(tr):
            candidate = min(enumerate(vr), key=lambda x: abs(x[1][0] - tt)) if vr else None
            vi = candidate[0] if candidate is not None else None
            vdelt = abs(candidate[1][0] - tt) if candidate is not None else None
            if vdelt is not None and vdelt <= args.tolerance_s and vi not in used_v:
                vt, vf, vrec = vr[vi]
                used_v.add(vi)
                vdet = detection(vrec)
                status = "temporal_candidate" if trec.get("boxes") and vrec.get("boxes") else ("thermal_only" if trec.get("boxes") else ("visible_only" if vrec.get("boxes") else "no_detection"))
            else:
                vt = vf = vrec = None
                vdet = {"boxes": [], "confidence": [], "class": []}
                status = "unpaired_thermal"
            rows.append({"observation_id": "B4:%s:%s:%s:T%d" % (group.get("session_id"), group.get("drone_id"), group["video_group"], tf), "batch_id": "B4", "session_id": group.get("session_id"), "drone_id": group.get("drone_id"), "video_group": group["video_group"], "timestamp_s": tt, "thermal_timestamp_s": tt, "visible_timestamp_s": vt, "thermal_frame": tf, "visible_frame": vf, "thermal_detection": detection(trec), "visible_detection": vdet, "association_status": status, "sync_delta_s": vdelt if vt is not None else None, "nearest_sample_delta_s": vdelt, "spatial_correspondence": "unverified", "fire_event_id": None, "metadata_reference": {"thermal_source": t_src, "visible_source": v_src, "sync_pair_key": pair.get("pair_key")}})
        for vi, (vt, vf, vrec) in enumerate(vr):
            if vi in used_v:
                continue
            rows.append({"observation_id": "B4:%s:%s:%s:V%d" % (group.get("session_id"), group.get("drone_id"), group["video_group"], vf), "batch_id": "B4", "session_id": group.get("session_id"), "drone_id": group.get("drone_id"), "video_group": group["video_group"], "timestamp_s": vt, "thermal_timestamp_s": None, "visible_timestamp_s": vt, "thermal_frame": None, "visible_frame": vf, "thermal_detection": {"boxes": [], "confidence": [], "class": []}, "visible_detection": detection(vrec), "association_status": "unpaired_visible", "sync_delta_s": None, "spatial_correspondence": "unverified", "fire_event_id": None, "metadata_reference": {"thermal_source": t_src, "visible_source": v_src, "sync_pair_key": pair.get("pair_key")}})
    rows.sort(key=lambda r: (r["session_id"], r["video_group"], r["timestamp_s"]))
    deltas = sorted(r["sync_delta_s"] for r in rows if r["sync_delta_s"] is not None)
    summary = {"observation_count": len(rows), "status_counts": dict(Counter(r["association_status"] for r in rows)), "missing_groups": missing, "time_paired_count": len(deltas), "max_paired_delta_s": max(deltas) if deltas else None, "median_paired_delta_s": deltas[len(deltas)//2] if deltas else None, "spatially_verified_pairs": 0}
    payload = {"schema_version": "dji_temporal_association_v3", "provisional_detector": True, "frame_index_rule": "sample_index * vid_stride", "time_rule": "start_s + frame_index/fps", "tolerance_s": args.tolerance_s, "cross_sensor_spatial_rule": "unverified; temporal coincidence is not a confirmed same-target association", "summary": summary, "observations": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
