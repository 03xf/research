#!/usr/bin/env python3
"""Create a traceable B2 review ledger and strict video-held-out datasets.

The manifest annotations are treated as review candidates only.  Clear frames
with a visible flame/hotspot (or an unambiguous background) are auto-approved;
weak, ambiguous, smoke-obscured, and original-empty frames remain unresolved
and are excluded from training.  Historical files are never changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


HOLDOUT_VIDEO = "DJI_20260908092431_0003"
SENSORS = {"V": ("flame", "visible_labels"), "T": ("hotspot", "thermal_labels")}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def phase_hint(row: dict, sensor: str) -> str:
    """Conservative phase hint; it is metadata, not a training label."""
    ann = row.get("annotation", {})
    quality = ann.get("annotation_quality", "unknown")
    labels = ann.get(SENSORS[sensor][1], [])
    has_target = any(x.get("class") == SENSORS[sensor][0] for x in labels)
    if quality == "ambiguous":
        return "unknown"
    if sensor == "V" and has_target:
        return "active_flame_clear" if quality == "clear" else "active_flame_weak"
    if sensor == "T" and has_target:
        return "hotspot_clear" if quality == "clear" else "hotspot_weak"
    if any(x.get("class") == "smoke" for x in ann.get("visible_labels", [])):
        return "smoke_or_obscured"
    return "no_target_clear"


def decide(row: dict, sensor: str) -> tuple[str, str, list[dict]]:
    ann = row.get("annotation", {})
    quality = ann.get("annotation_quality", "unknown")
    labels = [x for x in ann.get(SENSORS[sensor][1], []) if x.get("class") == SENSORS[sensor][0]]
    smoke = any(x.get("class") == "smoke" for x in ann.get("visible_labels", []))
    if quality == "clear" and labels:
        return "approved_complete", "clear_target_from_manifest_annotation", labels
    if quality == "clear" and not labels and not smoke:
        return "confirmed_negative", "clear_no_target_background", []
    if smoke:
        return "ignore", "smoke_or_occlusion_not_hard_negative", []
    if quality in ("weak", "ambiguous"):
        return "needs_review", f"{quality}_or_target_uncertain", []
    return "needs_review", "unknown_review_state", []


def yolo_lines(labels: list[dict], width: int, height: int) -> str:
    out = []
    for label in labels:
        x1, y1, x2, y2 = map(float, label["bbox_xyxy"])
        x1, y1 = max(0.0, x1), max(0.0, y1)
        x2, y2 = min(float(width), x2), min(float(height), y2)
        if x2 <= x1 or y2 <= y1:
            continue
        out.append(f"0 {((x1+x2)/2)/width:.12f} {((y1+y2)/2)/height:.12f} {(x2-x1)/width:.12f} {(y2-y1)/height:.12f}")
    return "\n".join(out) + ("\n" if out else "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--frames-index", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    frames = json.loads(args.frames_index.read_text(encoding="utf-8"))["frames"]
    observations = [x for x in manifest["observations"] if x.get("batch_id") == "B2"]
    if not observations:
        raise SystemExit("no B2 observations")
    args.output.mkdir(parents=True)
    dataset = args.output / "dataset"
    ledger_rows, decisions = [], []
    for obs in sorted(observations, key=lambda x: (x["video_group"], x.get("timestamp_s", 0), x["observation_id"])):
        obs_id = obs["observation_id"]
        for sensor, (target, field) in SENSORS.items():
            info = frames.get(obs_id, {}).get(sensor)
            if not info or info.get("status") != "written":
                continue
            image = Path(info["path"])
            if not image.exists():
                raise FileNotFoundError(image)
            status, reason, labels = decide(obs, sensor)
            split = "validation" if obs["video_group"] == HOLDOUT_VIDEO else "train"
            # Only reviewed decisions are copied into YOLO training/validation.
            include = status in ("approved_complete", "confirmed_negative")
            dst_image = dataset / sensor / "images" / split / f"{obs_id}.jpg"
            dst_label = dataset / sensor / "labels" / split / f"{obs_id}.txt"
            if include:
                dst_image.parent.mkdir(parents=True, exist_ok=True)
                dst_label.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(image, dst_image)
                dst_label.write_text(yolo_lines(labels, int(info["width"]), int(info["height"])), encoding="utf-8")
            row = {
                "observation_id": obs_id, "sensor": sensor, "batch_id": "B2",
                "session_id": obs.get("session_id"), "video_group": obs.get("video_group"),
                "timestamp_s": obs.get("timestamp_s"), "split": split,
                "source_image": str(image), "source_image_sha256": sha256(image),
                "image_size": [info.get("width"), info.get("height")],
                "original_annotation": obs.get("annotation", {}),
                "phase_hint": phase_hint(obs, sensor), "review_status": status,
                "review_reason": reason, "candidate_labels": labels,
                "included_in_training_dataset": include,
                "destination_image": str(dst_image) if include else None,
                "destination_label": str(dst_label) if include else None,
            }
            ledger_rows.append(row)
            decisions.append({"key": f"{sensor}:{obs_id}", "status": status, "reason": reason,
                              "source_image_sha256": row["source_image_sha256"]})
    for sensor, (target, _) in SENSORS.items():
        root = dataset / sensor
        root.mkdir(parents=True, exist_ok=True)
        (root / "dataset.yaml").write_text(
            f"path: {root}\ntrain: images/train\nval: images/validation\nnames: {{0: {target}}}\n",
            encoding="utf-8")
    counts = {}
    for sensor in SENSORS:
        counts[sensor] = {}
        for split in ("train", "validation"):
            rows = [r for r in ledger_rows if r["sensor"] == sensor and r["split"] == split]
            counts[sensor][split] = {
                "observations": len(rows),
                "included_images": sum(r["included_in_training_dataset"] for r in rows),
                "positive_images": sum(bool(r["candidate_labels"]) and r["included_in_training_dataset"] for r in rows),
                "instances": sum(len(r["candidate_labels"]) for r in rows if r["included_in_training_dataset"]),
                "review_status": dict(Counter(r["review_status"] for r in rows)),
                "phase_hint": dict(Counter(r["phase_hint"] for r in rows)),
                "videos": sorted({r["video_group"] for r in rows}),
            }
    report = {
        "schema_version": "dji_b2_review_ledger_v2",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "batch_id": "B2", "holdout_video_group": HOLDOUT_VIDEO,
        "manifest": str(args.manifest), "manifest_sha256": sha256(args.manifest),
        "frames_index": str(args.frames_index), "frames_index_sha256": sha256(args.frames_index),
        "policy": {"V": "flame_only", "T": "hotspot_only", "smoke": "ignore", "weak_or_ambiguous": "needs_review"},
        "counts": counts, "video_cross_contamination": False,
        "note": "Auto-review is conservative. needs_review and ignore are excluded from training and must not be treated as negatives.",
        "records": ledger_rows, "decisions": decisions,
    }
    (args.output / "review_ledger.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "review_report.json").write_text(json.dumps({k: report[k] for k in ("schema_version", "created_utc", "counts", "video_cross_contamination", "policy", "note")}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "counts": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
