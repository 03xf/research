#!/usr/bin/env python3
"""Build train-only overlapping-tile datasets; validation remains original."""
import argparse
import json
import math
import shutil
from pathlib import Path

from PIL import Image


def tiles(w, h, sensor):
    if sensor == "V":
        tw, th, ox, oy = 960, 540, 96, 108
    else:
        tw, th, ox, oy = 640, 512, 64, 52
    xs = [0, max(0, w - tw)]
    ys = [0, max(0, h - th)]
    return [(x, y, min(w, x + tw), min(h, y + th)) for y in ys for x in xs]


def make_one(base, out, sensor):
    if out.exists():
        raise SystemExit(f"output exists: {out}")
    out.mkdir(parents=True)
    counts = {}
    for split in ("train", "validation", "test"):
        src_i, src_l = base / "images" / split, base / "labels" / split
        dst_i, dst_l = out / "images" / split, out / "labels" / split
        dst_i.mkdir(parents=True)
        dst_l.mkdir(parents=True)
        if not src_i.exists():
            counts[split] = {"images": 0, "labels": 0}
            continue
        for image_path in sorted(src_i.glob("*.jpg")):
            if split != "train":
                shutil.copy2(image_path, dst_i / image_path.name)
                label = src_l / (image_path.stem + ".txt")
                if label.exists():
                    shutil.copy2(label, dst_l / label.name)
                continue
            image = Image.open(image_path).convert("RGB")
            w, h = image.size
            source_labels = []
            label_path = src_l / (image_path.stem + ".txt")
            if label_path.exists():
                for line in label_path.read_text(encoding="utf-8").splitlines():
                    parts = line.split()
                    if len(parts) != 5:
                        continue
                    cls, cx, cy, bw, bh = int(parts[0]), *map(float, parts[1:])
                    source_labels.append((cls, (cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h))
            for tile_index, (x0, y0, x1, y1) in enumerate(tiles(w, h, sensor)):
                tile = image.crop((x0, y0, x1, y1))
                tile_name = f"{image_path.stem}__tile{tile_index}.jpg"
                tile.save(dst_i / tile_name, quality=95)
                lines = []
                tile_area = (x1 - x0) * (y1 - y0)
                for cls, bx0, by0, bx1, by1 in source_labels:
                    ix0, iy0, ix1, iy1 = max(x0, bx0), max(y0, by0), min(x1, bx1), min(y1, by1)
                    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
                    original = max(1, (bx1 - bx0) * (by1 - by0))
                    if inter / original < 0.20:
                        continue
                    tx0, ty0, tx1, ty1 = ix0 - x0, iy0 - y0, ix1 - x0, iy1 - y0
                    lines.append(f"{cls} {(tx0+tx1)/(2*(x1-x0)):.8f} {(ty0+ty1)/(2*(y1-y0)):.8f} {(tx1-tx0)/(x1-x0):.8f} {(ty1-ty0)/(y1-y0):.8f}")
                (dst_l / tile_name.replace(".jpg", ".txt")).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        counts[split] = {"images": len(list(dst_i.glob("*.jpg"))), "labels": len(list(dst_l.glob("*.txt")))}
    names = "smoke\n  1: flame" if sensor == "V" else "hotspot"
    yaml_path = out / "data.yaml"
    yaml_path.write_text(f"path: {out.resolve()}\ntrain: images/train\nval: images/validation\ntest: images/test\nnames:\n  0: {names}\nnc: {2 if sensor == 'V' else 1}\n", encoding="utf-8")
    (out / "dataset_manifest.json").write_text(json.dumps({"schema_version": "dji_round23_tiled_dataset_v1", "sensor": sensor, "base_dataset": str(base), "train_tiled": True, "validation_original": True, "blind_test_accessed": False, "counts": counts, "tile_policy": "overlap 10% horizontally and vertically; retain boxes with >=20% original-area intersection; clip to tile"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v-base", required=True, type=Path)
    ap.add_argument("--t-base", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    result = {"V": make_one(args.v_base, args.output / "V", "V"), "T": make_one(args.t_base, args.output / "T", "T")}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
