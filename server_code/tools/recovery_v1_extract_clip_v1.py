"""Extract source-PTS 5 Hz T/V frames for a development tracking clip."""

import argparse
import json
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


PTS_PATTERN = re.compile(r"\bn:\s*(\d+).*?\bpts_time:\s*([-+0-9.eE]+)")


def decode(video, start, duration, output):
    output.mkdir(parents=True)
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "info", "-copyts",
               "-ss", str(start), "-i", str(video), "-t", str(duration),
               "-vf", "select='isnan(prev_selected_t)+gte(t-prev_selected_t,0.19)',showinfo",
               "-vsync", "0", "-q:v", "3", str(output / "%06d.jpg")]
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             encoding="utf-8", errors="replace", check=False)
    (output / "ffmpeg.log").write_text(process.stderr, encoding="utf-8")
    if process.returncode:
        raise RuntimeError(f"ffmpeg failed for {video}: {process.returncode}")
    timestamps = []
    for line in process.stderr.splitlines():
        matched = PTS_PATTERN.search(line)
        if matched and "showinfo" in line:
            timestamps.append(float(matched.group(2)))
    images = sorted(output.glob("*.jpg"))
    if len(images) != len(timestamps) or not images:
        raise ValueError(f"decoded frame/PTS mismatch: {video}: {len(images)} images, {len(timestamps)} PTS")
    if any(not math.isfinite(value) for value in timestamps):
        raise ValueError(f"nonfinite decoded PTS: {video}")
    if timestamps[0] < start - 0.5 or timestamps[-1] > start + duration + 0.5:
        raise ValueError(f"decoded PTS outside requested interval: {video}: {timestamps[0]}..{timestamps[-1]}")
    if any(later <= earlier for earlier, later in zip(timestamps, timestamps[1:])):
        raise ValueError(f"decoded PTS do not increase: {video}")
    rows = [{"frame_file": image.name, "decoded_pts_s": timestamp}
            for image, timestamp in zip(images, timestamps)]
    (output / "frames.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rows


def pair(thermal, visible):
    output = []
    used = set()
    for t in thermal:
        options = [(abs(t["decoded_pts_s"] - v["decoded_pts_s"]), index)
                   for index, v in enumerate(visible) if index not in used]
        if not options:
            break
        delta, index = min(options)
        if delta > 0.05:
            continue
        used.add(index)
        v = visible[index]
        output.append({"thermal_frame": t["frame_file"],
                       "visible_frame": v["frame_file"],
                       "thermal_pts_s": t["decoded_pts_s"],
                       "visible_pts_s": v["decoded_pts_s"],
                       "delta_s": delta, "same_target_status": "unverified"})
    return output


def extract(root, phase, index):
    root = root.resolve()
    candidates = json.loads((root / "clip_candidates_v1.json").read_text(encoding="utf-8"))
    choice = candidates["candidates"][phase][index]
    if candidates["source_split"] != "historically_exposed_development_validation":
        raise ValueError("clip source is not the development split")
    output = root / "video_clips" / f"{phase}_{index}_{choice['session_id']}"
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    start, duration = choice["start_s"], choice["duration_s"]
    thermal = decode(Path(choice["thermal_video"]), start, duration, output / "T")
    visible = decode(Path(choice["visible_video"]), start, duration, output / "V")
    pairs = pair(thermal, visible)
    payload = {"schema_version": "dji_recovery_decoded_clip_v1",
               "created_utc": datetime.now(timezone.utc).isoformat(),
               "source": choice, "sampling_rule": "decoded frame PTS; first frame, then >=0.19 s since prior selected frame",
               "nominal_sampling_hz": 5,
               "pairing_rule": "nearest unused V frame within 0.05 s of T decoded PTS",
               "temporal_pairs_are_same_target": False,
               "frames": {"T": len(thermal), "V": len(visible)},
               "paired_frames": len(pairs),
               "unpaired_T": len(thermal) - len(pairs),
               "unpaired_V": len(visible) - len(pairs),
               "pair_delta_s": {"max": max((row["delta_s"] for row in pairs), default=None),
                                "median": sorted(row["delta_s"] for row in pairs)[len(pairs) // 2] if pairs else None},
               "pairs": pairs}
    (output / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "frames": payload["frames"],
                      "paired_frames": len(pairs), "pair_delta_s": payload["pair_delta_s"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--index", type=int, required=True)
    args = parser.parse_args()
    extract(args.root, args.phase, args.index)
