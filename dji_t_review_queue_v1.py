"""Build a 32-pair B4 T/V training-source thermal review queue."""
import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from dji_t_probe_v1 import frame


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    ledger = json.loads((root / "sample_ledger.json").read_text(encoding="utf-8"))["records"]
    training = [x for x in ledger if x.get("batch_id") == "B4" and x.get("sensor") == "T"
                and x.get("split") == "train"]
    sessions = {
        "DJI_202609081039_005": {"existing": [530, 540, 550, 560],
                                   "new": [60, 180, 300, 420, 620, 720, 840, 930]},
        "DJI_202609081040_006": {"existing": [420, 450, 510, 550, 590, 620, 650, 680, 710, 740, 770, 810],
                                   "new": [60, 120, 180, 240, 300, 360, 400, 835]},
    }
    # Every known indexed sample from each selected source video belongs to train.
    for session in sessions:
        sources = {x["source_video"]["thermal"] for x in training if x["session_id"] == session}
        if len(sources) != 1:
            raise ValueError("ambiguous T source: " + session)
        video = next(iter(sources))
        if any(x["split"] != "train" for x in ledger
               if x.get("source_video", {}).get("thermal") == video):
            raise ValueError("source video crosses split: " + session)
    images = output / "images"
    labels = output / "original_labels"
    images.mkdir(parents=True)
    labels.mkdir()
    records = []
    all_hashes = {x["image_sha256"] for x in ledger if x.get("image_sha256")}
    for session, selection in sessions.items():
        same = [x for x in training if x["session_id"] == session]
        videos = same[0]["source_video"]
        old_times = [float(x["timestamp_s"]) for x in same]
        for target in selection["existing"]:
            candidates = [x for x in same if abs(float(x["timestamp_s"]) - target) < 0.01]
            if len(candidates) != 1:
                raise ValueError(f"existing sample missing/ambiguous: {session} {target}")
            original = candidates[0]
            key = original["observation_id"]
            t_dest = images / f"{key}_T.jpg"
            v_dest = images / f"{key}_V.jpg"
            source_t = root / "dataset_review_applied_v1/T/images/train" / f"{key}.jpg"
            source_label = root / "dataset_review_applied_v1/T/labels/train" / f"{key}.txt"
            if digest(source_t) != original["image_sha256"]:
                raise ValueError("existing image hash mismatch: " + key)
            shutil.copyfile(source_t, t_dest)
            shutil.copyfile(source_label, labels / f"{key}.txt")
            v_pts = frame(videos["visible"], target, v_dest)
            if abs(v_pts - target) > 0.2:
                raise ValueError("V PTS mismatch: " + key)
            records.append({"key": key, "kind": "existing", "session_id": session,
                            "target_s": target, "T_pts_s": float(original["timestamp_s"]),
                            "V_pts_s": v_pts, "T_image": str(t_dest), "V_image": str(v_dest),
                            "T_sha256": digest(t_dest), "V_sha256": digest(v_dest),
                            "original_label": str(labels / f"{key}.txt"),
                            "source_videos": videos})
        for target in selection["new"]:
            if min(abs(target - stamp) for stamp in old_times) < 10:
                raise ValueError(f"new frame too close to indexed sample: {session} {target}")
            key = f"tnew_{session[-7:]}_{target:04d}"
            t_dest = images / f"{key}_T.jpg"
            v_dest = images / f"{key}_V.jpg"
            t_pts = frame(videos["thermal"], target, t_dest)
            v_pts = frame(videos["visible"], target, v_dest)
            if abs(t_pts - v_pts) > 0.05:
                raise ValueError("V/T PTS mismatch: " + key)
            if digest(t_dest) in all_hashes:
                raise ValueError("new T frame exactly duplicates indexed sample: " + key)
            all_hashes.add(digest(t_dest))
            original_label = labels / f"{key}.txt"
            original_label.write_text("", encoding="utf-8")
            records.append({"key": key, "kind": "new", "session_id": session,
                            "target_s": target, "T_pts_s": t_pts, "V_pts_s": v_pts,
                            "T_image": str(t_dest), "V_image": str(v_dest),
                            "T_sha256": digest(t_dest), "V_sha256": digest(v_dest),
                            "original_label": str(original_label), "source_videos": videos})
    records.sort(key=lambda x: (x["session_id"], x["target_s"], x["kind"]))
    if len(records) != 32 or sum(x["kind"] == "existing" for x in records) != 16:
        raise ValueError("unexpected queue size")
    (output / "queue.json").write_text(json.dumps({
        "schema_version": "dji_b4_thermal_review_queue_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "B4 T fire-related hotspot versus non-fire hot background; training sources only",
        "temporal_pairing_is_not_physical_source_identity": True,
        "records": records,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "decisions.json").write_text("{\"decisions\":{}}\n", encoding="utf-8")
    (output / "history.jsonl").touch()
    print(json.dumps({"count": len(records), "existing": 16, "new": 16,
                      "max_pair_delta_s": max(abs(x["T_pts_s"] - x["V_pts_s"]) for x in records)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
