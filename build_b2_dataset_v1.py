#!/usr/bin/env python3
"""Build a B2-only, video-held-out YOLO dataset from the frozen sample ledger."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


HOLDOUT_VIDEO_GROUP = "DJI_20260908092431_0003"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_label(src: Path, dst: Path, sensor: str) -> dict:
    kept = []
    source_lines = 0
    if src.exists():
        for raw in src.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            source_lines += 1
            parts = raw.split()
            if len(parts) != 5:
                raise ValueError(f"invalid YOLO row: {src}: {raw!r}")
            category = int(parts[0])
            # Source V uses 0=flame, 1=smoke. Source T uses 0=hotspot.
            if sensor == "V" and category != 0:
                continue
            kept.append("0 " + " ".join(parts[1:]))
    dst.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")
    return {"source_lines": source_lines, "kept_lines": len(kept)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    records = [x for x in ledger["records"] if x.get("batch_id") == "B2"]
    if not records:
        raise SystemExit("no B2 records in ledger")

    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    for sensor in ("V", "T"):
        for split in ("train", "validation"):
            (args.output / sensor / "images" / split).mkdir(parents=True, exist_ok=True)
            (args.output / sensor / "labels" / split).mkdir(parents=True, exist_ok=True)

    rows = []
    for row in records:
        sensor = row["sensor"]
        if sensor not in ("V", "T"):
            continue
        split = "validation" if row.get("video_group") == HOLDOUT_VIDEO_GROUP else "train"
        src_image = Path(row["image"])
        src_label = Path(row["label"])
        if not src_image.exists() or not src_label.exists():
            raise FileNotFoundError(f"missing source for {row['observation_id']}: {src_image} / {src_label}")
        stem = row["observation_id"]
        dst_image = args.output / sensor / "images" / split / f"{stem}{src_image.suffix.lower()}"
        dst_label = args.output / sensor / "labels" / split / f"{stem}.txt"
        shutil.copy2(src_image, dst_image)
        label_info = write_label(src_label, dst_label, sensor)
        rows.append({
            "observation_id": row["observation_id"],
            "sensor": sensor,
            "split": split,
            "batch_id": row["batch_id"],
            "session_id": row["session_id"],
            "video_group": row["video_group"],
            "timestamp_s": row.get("timestamp_s"),
            "source_image": str(src_image),
            "source_label": str(src_label),
            "source_image_sha256": row.get("image_sha256") or sha256(src_image),
            "source_label_sha256": row.get("label_sha256") or sha256(src_label),
            "review_status": row.get("review_status"),
            "included_in_diagnostic": row.get("included_in_diagnostic"),
            **label_info,
        })

    counts = {}
    for sensor in ("V", "T"):
        counts[sensor] = {}
        for split in ("train", "validation"):
            subset = [x for x in rows if x["sensor"] == sensor and x["split"] == split]
            counts[sensor][split] = {
                "images": len(subset),
                "positive_images": sum(x["kept_lines"] > 0 for x in subset),
                "instances": sum(x["kept_lines"] for x in subset),
                "review_status": {},
            }
            for x in subset:
                status = x.get("review_status") or "missing"
                counts[sensor][split]["review_status"][status] = counts[sensor][split]["review_status"].get(status, 0) + 1

    for sensor, names in (("V", {0: "flame"}), ("T", {0: "hotspot"})):
        root = args.output / sensor
        (root / "dataset.yaml").write_text(
            "path: %s\ntrain: images/train\nval: images/validation\nnames: %s\n" % (root, json.dumps(names, ensure_ascii=False)),
            encoding="utf-8",
        )
    manifest = {
        "schema_version": "dji_b2_video_holdout_dataset_v1",
        "batch_id": "B2",
        "holdout_video_group": HOLDOUT_VIDEO_GROUP,
        "task": {"V": "flame_only", "T": "hotspot_only"},
        "source_ledger": str(args.ledger),
        "counts": counts,
        "records": rows,
        "label_warning": "B2 source labels include legacy records not all reviewed at full-image level; candidate training only until review is complete.",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "counts": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
