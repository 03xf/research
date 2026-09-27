#!/usr/bin/env python3
"""Create compact T/V contact sheets for manual annotation review."""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
import cv2


def thumb(path, width=320, height=220):
    image = cv2.imread(str(path))
    if image is None:
        return None
    h, w = image.shape[:2]
    scale = min(width / max(1, w), height / max(1, h))
    image = cv2.resize(image, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    canvas = 255 * __import__("numpy").ones((height, width, 3), dtype="uint8")
    y, x = (height - image.shape[0]) // 2, (width - image.shape[1]) // 2
    canvas[y:y + image.shape[0], x:x + image.shape[1]] = image
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames-index", required=True, type=Path)
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--output-root", required=True, type=Path)
    ap.add_argument("--per-page", type=int, default=12)
    args = ap.parse_args()
    idx = json.loads(args.frames_index.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    by_id = {x["observation_id"]: x for x in manifest.get("observations", [])}
    groups = defaultdict(list)
    for obs_id, frames in idx.get("frames", {}).items():
        obs = by_id.get(obs_id)
        if not obs:
            continue
        if frames.get("T", {}).get("path") and frames.get("V", {}).get("path"):
            groups[(obs["batch_id"], obs.get("split", "unassigned"))].append((obs, frames))
    sheet_index = []
    for (batch, split), items in sorted(groups.items()):
        items.sort(key=lambda x: x[0]["observation_id"])
        out_dir = args.output_root / str(batch) / str(split)
        out_dir.mkdir(parents=True, exist_ok=True)
        for page_start in range(0, len(items), args.per_page):
            page_items = items[page_start:page_start + args.per_page]
            rows = []
            for obs, frames in page_items:
                t = thumb(frames["T"]["path"])
                v = thumb(frames["V"]["path"])
                if t is None or v is None:
                    continue
                tile = __import__("numpy").hstack([t, v])
                cv2.putText(tile, f'{obs["observation_id"]}  t={obs["timestamp_s"]:.1f}s', (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
                rows.append(tile)
            if not rows:
                continue
            cols = 2
            blank = 255 * __import__("numpy").ones_like(rows[0])
            while len(rows) < args.per_page:
                rows.append(blank)
            sheet = __import__("numpy").vstack([__import__("numpy").hstack(rows[i:i + cols]) for i in range(0, len(rows), cols)])
            path = out_dir / f"page_{page_start // args.per_page + 1:03d}.jpg"
            cv2.imwrite(str(path), sheet, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            sheet_index.append({"batch_id": batch, "split": split, "path": str(path), "observation_ids": [x[0]["observation_id"] for x in page_items]})
    out = {"schema_version": "dji_contact_sheets_v1", "sheet_count": len(sheet_index), "sheets": sheet_index}
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "sheets_index.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sheet_count": len(sheet_index)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
