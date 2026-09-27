#!/usr/bin/env python3
"""Build separate YOLO V/T datasets from reviewed annotation manifest rows.

The command refuses to produce training data from unlabeled observations.
Labels must be entered under observation.annotation.visible_labels or
observation.annotation.thermal_labels as objects with class and bbox_xyxy.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


CLASS_MAP = {"V": {"smoke": 0, "flame": 1}, "T": {"hotspot": 0}}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def norm_box(box, width, height):
    x1, y1, x2, y2 = map(float, box)
    x1, x2 = sorted((max(0.0, min(width, x1)), max(0.0, min(width, x2))))
    y1, y2 = sorted((max(0.0, min(height, y1)), max(0.0, min(height, y2))))
    if x2 <= x1 or y2 <= y1:
        return None
    return ((x1 + x2) / 2 / width, (y1 + y2) / 2 / height, (x2 - x1) / width, (y2 - y1) / height)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--frames-index", required=True, type=Path)
    ap.add_argument("--sensor", choices=("V", "T"), required=True)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--copy-images", action="store_true")
    args = ap.parse_args()
    manifest = load(args.manifest)
    frames = load(args.frames_index).get("frames", {})
    mapping = CLASS_MAP[args.sensor]
    root = args.output
    image_root, label_root = root / "images", root / "labels"
    rows, skipped = [], []
    for obs in manifest.get("observations", []):
        ann = obs.get("annotation", {})
        labels = ann.get("visible_labels" if args.sensor == "V" else "thermal_labels") or []
        quality = ann.get("annotation_quality")
        if quality in {"ambiguous", "unusable", "unlabeled"}:
            skipped.append({"observation_id": obs.get("observation_id"), "reason": "unlabeled_or_unusable"})
            continue
        if not labels and quality != "clear":
            skipped.append({"observation_id": obs.get("observation_id"), "reason": "weak_without_explicit_negative"})
            continue
        info = frames.get(obs.get("observation_id"), {}).get(args.sensor)
        if not info or not Path(info.get("path", "")).exists():
            skipped.append({"observation_id": obs.get("observation_id"), "reason": "frame_missing"})
            continue
        width, height = int(info["width"]), int(info["height"])
        converted = []
        for label in labels:
            cls = label.get("class") if isinstance(label, dict) else None
            box = label.get("bbox_xyxy") if isinstance(label, dict) else None
            if cls not in mapping or not box:
                skipped.append({"observation_id": obs.get("observation_id"), "reason": "invalid_label"})
                continue
            norm = norm_box(box, width, height)
            if norm:
                converted.append((mapping[cls], norm))
        # A clear empty annotation is an explicit negative sample.
        if labels and not converted:
            continue
        split = obs.get("split", "train")
        stem = obs["observation_id"]
        image_dir, label_dir = image_root / split, label_root / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        source = Path(info["path"])
        destination = image_dir / f"{stem}.jpg"
        if args.copy_images:
            shutil.copy2(source, destination)
        else:
            if not destination.exists():
                destination.symlink_to(source)
        (label_dir / f"{stem}.txt").write_text("\n".join(f"{c} {cx:.8f} {cy:.8f} {w:.8f} {h:.8f}" for c, (cx, cy, w, h) in converted) + "\n", encoding="utf-8")
        rows.append({"observation_id": stem, "split": split, "image": str(destination), "labels": len(converted), "batch_id": obs.get("batch_id"), "session_id": obs.get("session_id"), "drone_id": obs.get("drone_id")})
    if not rows:
        raise SystemExit("no reviewed labels found; annotate the manifest before building a YOLO dataset")
    names = ["smoke", "flame"] if args.sensor == "V" else ["hotspot"]
    (root / "data.yaml").write_text("path: " + str(root.resolve()) + "\ntrain: images/train\nval: images/validation\ntest: images/test\nnames:\n" + "\n".join(f"  {i}: {n}" for i, n in enumerate(names)) + "\nnc: " + str(len(names)) + "\n", encoding="utf-8")
    digest = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    report = {"schema_version": "dji_yolo_dataset_v1", "sensor": args.sensor, "class_names": names, "manifest_sha256": digest, "labeled_observation_count": len(rows), "by_split": {s: sum(r["split"] == s for r in rows) for s in ("train", "validation", "test")}, "skipped_count": len(skipped), "rows": rows, "skipped": skipped}
    (root / "dataset_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("sensor", "labeled_observation_count", "by_split", "skipped_count")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
