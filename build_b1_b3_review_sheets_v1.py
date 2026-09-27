"""Render paired V/T candidate frames as human-review contact sheets."""

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def load_font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def render_sheet(rows, output: Path, page: int, pages: int, thumb_w: int, thumb_h: int):
    columns, rows_per_page = 2, 10
    card_w = 2 * thumb_w + 28
    card_h = thumb_h + 48
    pad = 14
    canvas = Image.new("RGB", (columns * card_w + 3 * pad, rows_per_page * card_h + (rows_per_page + 1) * pad), "#f3f4f6")
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(15)
    label_font = load_font(12)
    small_font = load_font(10)

    for i, row in enumerate(rows):
        col, line = i % columns, i // columns
        x = pad + col * (card_w + pad)
        y = pad + line * (card_h + pad)
        if hasattr(draw, "rounded_rectangle"):
            draw.rounded_rectangle((x, y, x + card_w, y + card_h), radius=5, fill="white", outline="#cbd5e1", width=1)
        else:
            draw.rectangle((x, y, x + card_w, y + card_h), fill="white", outline="#cbd5e1", width=1)
        draw.text((x + 8, y + 5), f"{row['candidate_id']}  {row['pts_s']:.1f}s", fill="#111827", font=title_font)
        draw.text((x + 8, y + 25), f"{row['batch']} {row['split']}  {row['drone_id']}  {row['recording_prefix']}", fill="#4b5563", font=small_font)
        for sensor, offset, label in (("v", 8, "V"), ("t", thumb_w + 16, "T")):
            path = row.get(f"{sensor}_image")
            frame_x, frame_y = x + offset, y + 42
            draw.text((frame_x, frame_y - 15), label, fill="#374151", font=label_font)
            if path:
                with Image.open(path) as source:
                    thumb = source.convert("RGB")
                    if hasattr(ImageOps, "contain"):
                        thumb = ImageOps.contain(thumb, (thumb_w, thumb_h))
                    else:
                        thumb.thumbnail((thumb_w, thumb_h), Image.ANTIALIAS)
                canvas.paste(thumb, (frame_x + (thumb_w - thumb.width) // 2,
                                     frame_y + (thumb_h - thumb.height) // 2))
            else:
                draw.rectangle((frame_x, frame_y, frame_x + thumb_w, frame_y + thumb_h), fill="#e5e7eb")
                draw.text((frame_x + 10, frame_y + 10), "MISSING", fill="#b91c1c", font=small_font)

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=88, optimize=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-sheet", type=int, default=20)
    parser.add_argument("--thumb-width", type=int, default=300)
    parser.add_argument("--thumb-height", type=int, default=170)
    args = parser.parse_args()

    manifest = args.dataset / "candidate_frames.jsonl"
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    partitions = defaultdict(list)
    for row in rows:
        partitions[(row["split"], row["batch"])].append(row)
    index = {"schema_version": "dji_b1_b3_review_sheets_v1", "dataset": str(args.dataset), "sheets": []}
    for (split, batch), items in sorted(partitions.items()):
        items.sort(key=lambda row: (row["group_index"], row["frame_index"]))
        page_count = math.ceil(len(items) / args.per_sheet)
        for page in range(page_count):
            chunk = items[page * args.per_sheet:(page + 1) * args.per_sheet]
            filename = f"{split}_{batch}_{page + 1:03d}.jpg"
            path = args.output / split / batch / filename
            render_sheet(chunk, path, page + 1, page_count, args.thumb_width, args.thumb_height)
            index["sheets"].append({
                "path": str(path), "split": split, "batch": batch,
                "page": page + 1, "page_count": page_count,
                "candidate_count": len(chunk),
                "candidate_ids": [row["candidate_id"] for row in chunk],
            })
    (args.output / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sheets": len(index["sheets"]), "candidates": len(rows), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
