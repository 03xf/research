#!/usr/bin/env python3
"""Build a reproducible, unlabeled DJI annotation manifest and split plan."""
import argparse
import json
import math
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fps_value(info):
    if not info:
        return None
    value = info.get("fps")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and "/" in value:
        try:
            a, b = value.split("/", 1)
            return float(a) / float(b)
        except Exception:
            return None
    try:
        return float(value)
    except Exception:
        return None


def nearest_record(records, t, fps):
    if not records:
        return None, None
    best = min(records, key=lambda r: abs((r.get("sample_index", 0) / fps) - t))
    return best, abs(best.get("sample_index", 0) / fps - t)


def result_index(inference_root):
    index = {}
    for path in Path(inference_root).rglob("*.json"):
        if path.name == "summary.json":
            continue
        try:
            data = load_json(path)
        except Exception:
            continue
        source = data.get("source")
        if source and "records" in data:
            index[source] = (path, data)
    return index


def detection_indices(data):
    return {int(r.get("sample_index", 0)) for r in data.get("records", []) if r.get("boxes")}


def make_candidates(group, t_data, v_data, pair_info, target):
    t_records, v_records = t_data.get("records", []), v_data.get("records", [])
    if not t_records or not v_records:
        return []
    tfps = fps_value(pair_info.get("T_info", {})) or 30.0
    vfps = fps_value(pair_info.get("V_info", {})) or 30.0
    n = min(len(t_records), len(v_records))
    step = max(1, int(math.ceil(n / max(1, target))))
    idxs = set(range(0, n, step))
    idxs.update(detection_indices(t_data))
    idxs.update(detection_indices(v_data))
    rows = []
    for i in sorted(idxs):
        tr = t_records[min(i, len(t_records) - 1)]
        t = int(tr.get("sample_index", 0)) / tfps
        vr, sync_delta = nearest_record(v_records, t, vfps)
        if vr is None:
            continue
        rows.append({
            "batch_id": group["batch_id"],
            "session_id": group.get("session_id"),
            "drone_id": group.get("drone_id"),
            "video_group": group.get("video_group"),
            "source_video": {"thermal": group.get("thermal_video"), "visible": group.get("visible_video")},
            "sensor": "T/V",
            "timestamp_s": round(float(t), 6),
            "thermal_frame": int(tr.get("sample_index", 0)),
            "visible_frame": int(vr.get("sample_index", 0)),
            "sync_delta_s": round(float(sync_delta), 6),
            "pair_status": "paired" if sync_delta <= 0.1 else "ambiguous",
            "thermal_detection": {"boxes": tr.get("boxes", []), "confidence": tr.get("confidence", []), "class": tr.get("class", [])},
            "visible_detection": {"boxes": vr.get("boxes", []), "confidence": vr.get("confidence", []), "class": vr.get("class", [])},
            "annotation": {"visible_labels": [], "thermal_labels": [], "fire_event_id": None, "visibility": "unlabeled", "annotation_quality": "unlabeled"},
            "metadata_reference": {"inventory_group": group.get("video_group"), "sync_pair_key": pair_info.get("pair_key"), "inference_vid_stride": t_data.get("vid_stride")}
        })
    if len(rows) <= target:
        return rows
    positive = [r for r in rows if r["thermal_detection"]["boxes"] or r["visible_detection"]["boxes"]]
    background = [r for r in rows if not (r["thermal_detection"]["boxes"] or r["visible_detection"]["boxes"])]
    keep = positive[:target]
    if len(keep) < target:
        stride = max(1, len(background) // max(1, target - len(keep)))
        keep.extend(background[::stride][:target - len(keep)])
    return keep[:target]


def assign_splits(rows):
    groups = sorted({(r["batch_id"], r.get("session_id"), r.get("drone_id")) for r in rows})
    labels = {}
    for i, key in enumerate(groups):
        frac = i / max(1, len(groups))
        labels[key] = "train" if frac < 0.6 else ("validation" if frac < 0.8 else "test")
    for row in rows:
        row["split"] = labels[(row["batch_id"], row.get("session_id"), row.get("drone_id"))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", required=True, type=Path)
    ap.add_argument("--sync-dir", required=True, type=Path)
    ap.add_argument("--inference-root", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--target-b4", type=int, default=300)
    ap.add_argument("--target-b1", type=int, default=200)
    ap.add_argument("--target-b2", type=int, default=100)
    ap.add_argument("--target-b3", type=int, default=250)
    args = ap.parse_args()
    inventory = load_json(args.inventory)
    idx = result_index(args.inference_root)
    sync = {}
    for path in sorted(args.sync_dir.glob("B*.json")):
        for pair in load_json(path).get("pairs", []):
            sync[(pair.get("T"), pair.get("V"))] = pair
    targets = {"B1": args.target_b1, "B2": args.target_b2, "B3": args.target_b3, "B4": args.target_b4}
    rows, group_status = [], []
    for group in inventory.get("groups", []):
        tv = (group.get("thermal_video"), group.get("visible_video"))
        if not all(tv):
            continue
        pair = sync.get(tv)
        t_entry, v_entry = idx.get(tv[0]), idx.get(tv[1])
        if not pair or not t_entry or not v_entry:
            group_status.append({"batch_id": group["batch_id"], "video_group": group.get("video_group"), "status": "inference_unavailable"})
            continue
        selected = make_candidates(group, t_entry[1], v_entry[1], pair, targets.get(group["batch_id"], 100))
        rows.extend(selected)
        group_status.append({"batch_id": group["batch_id"], "video_group": group.get("video_group"), "status": "ready", "candidate_count": len(selected)})
    # Apply targets at batch level, not once per video group.
    grouped = []
    for batch_id, target in targets.items():
        batch_rows = [r for r in rows if r["batch_id"] == batch_id]
        if len(batch_rows) <= target:
            grouped.extend(batch_rows)
            continue
        # Round-robin over video groups to retain drone/session coverage.
        by_group = {}
        for row in batch_rows:
            by_group.setdefault(row.get("video_group"), []).append(row)
        for values in by_group.values():
            values.sort(key=lambda r: (not bool(r["thermal_detection"]["boxes"] or r["visible_detection"]["boxes"]), r.get("timestamp_s", 0.0)))
        keep = []
        cursor = 0
        groups = list(by_group.values())
        while len(keep) < target and groups:
            next_groups = []
            for values in groups:
                if values:
                    keep.append(values.pop(0))
                    if len(keep) >= target:
                        break
                if values:
                    next_groups.append(values)
            groups = next_groups
        grouped.extend(keep[:target])
    rows = grouped
    assign_splits(rows)
    for i, row in enumerate(rows, 1):
        row["observation_id"] = f"obs_{i:06d}"
    summary = {"targets": targets, "observation_count": len(rows), "by_batch": {b: sum(r["batch_id"] == b for r in rows) for b in sorted(targets)}, "by_split": {s: sum(r.get("split") == s for r in rows) for s in ("train", "validation", "test")}, "label_status": "unlabeled", "note": "Rows are annotation candidates only; model outputs are suggestions, not ground truth.", "group_status": group_status}
    payload = {"schema_version": "dji_annotation_manifest_v1", "summary": summary, "observations": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    split_path = args.output.with_name("annotation_splits.json")
    split_path.write_text(json.dumps({"schema_version": "dji_annotation_splits_v1", "summary": summary, "splits": [{"observation_id": r["observation_id"], "split": r["split"], "batch_id": r["batch_id"], "session_id": r.get("session_id"), "drone_id": r.get("drone_id")} for r in rows]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
