#!/usr/bin/env python3
"""Build B2 round-2 data by adding weak frames that still have target boxes.

The frozen review ledger remains unchanged.  Only weak records with an
explicit flame/hotspot annotation are promoted into this experiment; smoke,
ambiguous, and weak empty frames remain excluded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    records = ledger["records"]
    sensors = {"V": "flame", "T": "hotspot"}
    holdout = ledger["holdout_video_group"]
    rows = []
    for r in records:
        target = sensors[r["sensor"]]
        labels = [x for x in r.get("candidate_labels", []) if x.get("class") == target]
        if not labels and r.get("review_status") == "needs_review":
            ann = r.get("original_annotation", {})
            field = "visible_labels" if r["sensor"] == "V" else "thermal_labels"
            labels = [x for x in ann.get(field, []) if x.get("class") == target]
        status = r.get("review_status")
        # Round 1 approved clear labels plus explicitly boxed weak targets.
        include = status in ("approved_complete", "confirmed_negative") or (
            status == "needs_review" and bool(labels) and r.get("phase_hint", "").endswith("_weak")
        )
        if not include:
            continue
        split = "validation" if r["video_group"] == holdout else "train"
        src = Path(r["source_image"])
        dst_img = args.output / r["sensor"] / "images" / split / f"{r['observation_id']}.jpg"
        dst_lbl = args.output / r["sensor"] / "labels" / split / f"{r['observation_id']}.txt"
        dst_img.parent.mkdir(parents=True, exist_ok=True)
        dst_lbl.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst_img)
        w, h = r["image_size"]
        out = []
        for x in labels:
            x1, y1, x2, y2 = map(float, x["bbox_xyxy"])
            out.append(f"0 {((x1+x2)/2)/w:.12f} {((y1+y2)/2)/h:.12f} {(x2-x1)/w:.12f} {(y2-y1)/h:.12f}")
        dst_lbl.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
        rows.append({"sensor": r["sensor"], "split": split, "observation_id": r["observation_id"],
                     "video_group": r["video_group"], "session_id": r["session_id"],
                     "review_status": status, "phase_hint": r.get("phase_hint"),
                     "source_image": str(src), "source_image_sha256": r["source_image_sha256"],
                     "labels": len(out), "promotion": "weak_target" if status == "needs_review" else "round1_reviewed"})
    for sensor, name in sensors.items():
        root = args.output / sensor
        root.mkdir(parents=True, exist_ok=True)
        (root / "dataset.yaml").write_text(
            f"path: {root}\ntrain: images/train\nval: images/validation\nnames: {{0: {name}}}\n", encoding="utf-8")
    counts = {}
    for sensor in sensors:
        counts[sensor] = {}
        for split in ("train", "validation"):
            part = [x for x in rows if x["sensor"] == sensor and x["split"] == split]
            counts[sensor][split] = {"images": len(part), "positive_images": sum(x["labels"] > 0 for x in part),
                                     "instances": sum(x["labels"] for x in part),
                                     "status": dict(Counter(x["review_status"] for x in part)),
                                     "promotion": dict(Counter(x["promotion"] for x in part))}
    out = {"schema_version": "dji_b2_round2_dataset_v1", "batch_id": "B2",
           "holdout_video_group": holdout, "source_review_ledger": str(args.ledger),
           "source_review_ledger_sha256": digest(args.ledger), "policy": "approved plus weak explicit target boxes",
           "counts": counts, "video_cross_contamination": False, "records": rows}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "counts": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
