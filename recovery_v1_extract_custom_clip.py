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
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "info", "-copyts",
           "-ss", str(start), "-i", str(video), "-t", str(start + duration),
           "-vf", "select='isnan(prev_selected_t)+gte(t-prev_selected_t,0.19)',showinfo",
           "-vsync", "0", "-q:v", "3", str(output / "%06d.jpg")]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       encoding="utf-8", errors="replace", check=False)
    (output / "ffmpeg.log").write_text(p.stderr, encoding="utf-8")
    if p.returncode:
        raise RuntimeError(f"ffmpeg failed: {video}")
    stamps = []
    for line in p.stderr.splitlines():
        m = PTS_PATTERN.search(line)
        if m and "showinfo" in line:
            stamps.append(float(m.group(2)))
    images = sorted(output.glob("*.jpg"))
    if len(stamps) == len(images) + 1 and stamps[-1] >= start + duration - 0.2:
        stamps.pop()
    if len(images) != len(stamps) or not images:
        raise ValueError(f"frame/PTS mismatch: {video}: {len(images)} / {len(stamps)}")
    if any(not math.isfinite(x) for x in stamps) or any(b <= a for a, b in zip(stamps, stamps[1:])):
        raise ValueError(f"invalid PTS: {video}")
    rows = [{"frame_file": image.name, "decoded_pts_s": stamp}
            for image, stamp in zip(images, stamps)]
    (output / "frames.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rows

def pair(thermal, visible):
    pairs = []
    used = set()
    for t in thermal:
        options = [(abs(t["decoded_pts_s"] - v["decoded_pts_s"]), i)
                   for i, v in enumerate(visible) if i not in used]
        if not options:
            break
        delta, i = min(options)
        if delta > 0.05:
            continue
        used.add(i)
        v = visible[i]
        pairs.append({"thermal_frame": t["frame_file"], "visible_frame": v["frame_file"],
                      "thermal_pts_s": t["decoded_pts_s"], "visible_pts_s": v["decoded_pts_s"],
                      "delta_s": delta, "same_target_status": "unverified"})
    return pairs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--visible", type=Path, required=True)
    ap.add_argument("--thermal", type=Path, required=True)
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--batch", default="B3")
    ap.add_argument("--session", required=True)
    ap.add_argument("--video-group", required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    t = decode(args.thermal, args.start, args.duration, args.output / "T")
    v = decode(args.visible, args.start, args.duration, args.output / "V")
    pairs = pair(t, v)
    payload = {
        "schema_version": "dji_recovery_decoded_custom_clip_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": {"batch_id": args.batch, "session_id": args.session,
                   "video_group": args.video_group, "visible_video": str(args.visible),
                   "thermal_video": str(args.thermal), "start_s": args.start,
                   "duration_s": args.duration},
        "sampling_rule": "decoded frame PTS; >=0.19 s since prior selected frame",
        "pairing_rule": "nearest unused V frame within 0.05 s of T decoded PTS",
        "temporal_pairs_are_same_target": False,
        "frames": {"T": len(t), "V": len(v)}, "paired_frames": len(pairs),
        "unpaired_T": len(t) - len(pairs), "unpaired_V": len(v) - len(pairs),
        "pairs": pairs,
    }
    (args.output / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "frames": payload["frames"],
                      "paired_frames": len(pairs)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
