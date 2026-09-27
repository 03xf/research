#!/usr/bin/env python3
"""Check a DJI YOLO dataset before committing GPU time to training."""

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import yaml


def inspect(data_file):
    config = yaml.safe_load(data_file.read_text(encoding="utf-8"))
    root = Path(config["path"])
    if not root.is_absolute():
        raise ValueError("dataset path must be absolute")
    names = config["names"]
    class_ids = {int(k) for k in names} if isinstance(names, dict) else set(range(len(names)))
    report = {"data_yaml": str(data_file.resolve()), "root": str(root), "splits": {}, "errors": []}
    if class_ids != set(range(len(class_ids))):
        report["errors"].append("class IDs are not contiguous from zero")
    for split in ("train", "val"):
        image_dir = root / config[split]
        label_dir = image_dir.parent.parent / "labels" / image_dir.name
        images = sorted(p for p in image_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}) if image_dir.is_dir() else []
        counts = Counter()
        if not images:
            report["errors"].append(f"{split}: no images at {image_dir}")
        for image in images:
            label = label_dir / f"{image.stem}.txt"
            if not label.is_file():
                report["errors"].append(f"{split}: missing label {label}")
                continue
            contents = label.read_text(encoding="utf-8")
            if "\\n" in contents:
                report["errors"].append(f"{split}: literal backslash-n in {label}")
            for line_number, line in enumerate(contents.splitlines(), 1):
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) != 5:
                    report["errors"].append(f"{label}:{line_number}: expected 5 fields, found {len(parts)}")
                    continue
                try:
                    category = int(parts[0])
                    x, y, width, height = map(float, parts[1:])
                except ValueError:
                    report["errors"].append(f"{label}:{line_number}: nonnumeric label")
                    continue
                if category not in class_ids or not all(math.isfinite(v) for v in (x, y, width, height)) or not (0 <= x <= 1 and 0 <= y <= 1 and 0 < width <= 1 and 0 < height <= 1):
                    report["errors"].append(f"{label}:{line_number}: invalid class or coordinates")
                counts[category] += 1
        report["splits"][split] = {"image_count": len(images), "label_counts": dict(counts)}
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = inspect(args.data)
    if args.output:
        if args.output.exists():
            raise SystemExit(f"refusing to overwrite {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"splits": report["splits"], "error_count": len(report["errors"]), "first_errors": report["errors"][:10]}, ensure_ascii=False))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
