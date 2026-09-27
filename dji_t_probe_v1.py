"""Make a small V/T contact sheet from B4 training-only videos."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw


PTS = re.compile(r"\bpts_time:\s*([-+0-9.eE]+)")


def frame(video, target, output):
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "info",
               "-copyts", "-ss", str(target), "-i", str(video),
               "-frames:v", "1", "-vf", "showinfo", "-q:v", "3", str(output)]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            encoding="utf-8", errors="replace")
    if result.returncode or not output.exists():
        raise RuntimeError(f"decode failed: {video} @ {target}: {result.stderr[-500:]}")
    stamps = [float(PTS.search(line).group(1)) for line in result.stderr.splitlines()
              if "showinfo" in line and PTS.search(line)]
    if not stamps:
        raise ValueError(f"PTS missing: {video} @ {target}")
    return stamps[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    ledger = json.loads((args.root / "sample_ledger.json").read_text(encoding="utf-8"))["records"]
    schedule = {
        "DJI_202609081039_005": [60, 180, 300, 420, 530, 550, 620, 720, 840, 930],
        "DJI_202609081040_006": [60, 180, 300, 400, 440, 500, 560, 620, 680, 740, 810],
    }
    args.output.mkdir(parents=True)
    tiles = []
    rows = []
    for session, times in schedule.items():
        reference = next(row for row in ledger if row.get("batch_id") == "B4"
                         and row.get("sensor") == "T" and row.get("split") == "train"
                         and row.get("session_id") == session)
        for target in times:
            decoded = {}
            for sensor, key in [("T", "thermal"), ("V", "visible")]:
                output = args.output / f"{session}_{target:04d}_{sensor}.jpg"
                pts = frame(reference["source_video"][key], target, output)
                decoded[sensor] = {"path": str(output), "pts_s": pts,
                                   "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
            if abs(decoded["T"]["pts_s"] - decoded["V"]["pts_s"]) > 0.2:
                raise ValueError(f"V/T PTS mismatch: {session} @ {target}")
            rows.append({"session_id": session, "target_s": target, "frames": decoded,
                         "delta_s": abs(decoded["T"]["pts_s"] - decoded["V"]["pts_s"])})
            tile = Image.new("RGB", (800, 260), "white")
            draw = ImageDraw.Draw(tile)
            for i, sensor in enumerate(("V", "T")):
                with Image.open(decoded[sensor]["path"]) as image:
                    preview = image.convert("RGB")
                    preview.thumbnail((390, 228))
                    tile.paste(preview, (i * 400, 25))
                draw.text((i * 400 + 5, 5), f"{session[-7:]}  {target}s  {sensor}  {decoded[sensor]['pts_s']:.3f}", fill="black")
            tiles.append(tile)
    sheet = Image.new("RGB", (1600, 260 * ((len(tiles) + 1) // 2)), "white")
    for i, tile in enumerate(tiles):
        sheet.paste(tile, (i % 2 * 800, i // 2 * 260))
    sheet.save(args.output / "contact_sheet.jpg", quality=85)
    (args.output / "probe.json").write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pairs": len(rows), "max_delta_s": max(x["delta_s"] for x in rows),
                      "contact_sheet": str(args.output / "contact_sheet.jpg")}))


if __name__ == "__main__":
    main()
