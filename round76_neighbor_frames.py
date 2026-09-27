"""Extract neighboring frames for second-review of Round75 train patch proposals."""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
PROPOSALS = ROOT / "data_integrity/round75_manual_patch_proposals_v1.json"
MANIFEST = ROOT / "manifest_round12.json"
OUT = ROOT / "data_integrity/round76_neighbor_review_v1"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    if OUT.exists():
        raise SystemExit(f"Refusing overwrite: {OUT}")
    p = json.loads(PROPOSALS.read_text())
    m = {x["observation_id"]: x for x in json.loads(MANIFEST.read_text())["observations"]}
    OUT.mkdir(parents=True)
    records = []
    for proposal in p["proposals"]:
        source = m[proposal["observation_id"]]["source_video"]["visible" if proposal["sensor"] == "V" else "thermal"]
        center = m[proposal["observation_id"]]["timestamp_s"]
        times = sorted(set([max(0.0, center - 5.0), center, center + 5.0]))
        item = {"observation_id": proposal["observation_id"], "sensor": proposal["sensor"],
                "center_timestamp_s": center, "source_video": source, "frames": []}
        for index, time_s in enumerate(times):
            target = OUT / f"{proposal['observation_id']}_{proposal['sensor']}_{index}.jpg"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(time_s),
                            "-i", source, "-frames:v", "1", "-q:v", "2", "-n", str(target)],
                           check=True, capture_output=True, text=True)
            assert target.is_file() and target.stat().st_size > 1000
            item["frames"].append({"seek_s": time_s, "image": str(target), "image_sha256": sha(target)})
        records.append(item)
    sheets = []
    for item in records:
        first = Image.open(item["frames"][0]["image"]).convert("RGB")
        w, h = first.size
        tile_w, tile_h = min(640, w), min(480, h)
        sheet = Image.new("RGB", (tile_w * 3, tile_h + 35), "white")
        draw = ImageDraw.Draw(sheet)
        for i, frame in enumerate(item["frames"]):
            with Image.open(frame["image"]) as source:
                tile = source.convert("RGB")
            tile.thumbnail((tile_w, tile_h))
            sheet.paste(tile, (i * tile_w, 30))
            draw.text((i * tile_w + 4, 5), f"{frame['seek_s']:.1f}s", fill="black")
        target = OUT / f"{item['observation_id']}_{item['sensor']}_neighbors.jpg"
        sheet.save(target, quality=91)
        sheets.append({"observation_id": item["observation_id"], "sensor": item["sensor"],
                       "path": str(target), "sha256": sha(target)})
    report = {"schema_version": "dji_round76_neighbor_review_v1",
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "proposals": str(PROPOSALS), "proposals_sha256": sha(PROPOSALS),
              "blind_test_accessed": False, "no_labels_created": True,
              "records": records, "contact_sheets": sheets}
    (OUT / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"manifest": str(OUT / "manifest.json"), "sheets": sheets}))


if __name__ == "__main__":
    main()
