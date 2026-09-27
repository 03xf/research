"""Extract fixed 10-second confirmation pairs without touching development data."""

import argparse
import hashlib
import json
import math
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


PTS = re.compile(r"\bn:\s*(\d+).*?\bpts_time:\s*([-+0-9.eE]+)")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def decode(video, destination):
    destination.mkdir(parents=True)
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "info", "-i", str(video),
               "-vf", "select='isnan(prev_selected_t)+gte(t,10*(floor((prev_selected_t+0.001)/10)+1))',showinfo",
               "-vsync", "0", "-q:v", "3", str(destination / "%06d.jpg")]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            encoding="utf-8", errors="replace", check=False)
    (destination / "ffmpeg.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"ffmpeg failed: {video}: {result.returncode}")
    times = [float(match.group(2)) for line in result.stderr.splitlines()
             for match in [PTS.search(line)] if "showinfo" in line and match]
    images = sorted(destination.glob("*.jpg"))
    if len(times) != len(images) or not images:
        raise ValueError(f"frame/PTS mismatch: {video}: {len(images)} images, {len(times)} PTS")
    if not all(math.isfinite(t) for t in times) or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError(f"invalid timestamps: {video}")
    rows = []
    for image, timestamp in zip(images, times):
        with Image.open(image) as handle:
            size = list(handle.size)
        rows.append({"file": str(image), "pts_s": timestamp, "sha256": digest(image), "size": size})
    return rows


def pair(visible, thermal):
    unused = set(range(len(thermal)))
    pairs = []
    unpaired_v = []
    for v in visible:
        if not unused:
            unpaired_v.append(v)
            continue
        delta, index = min((abs(v["pts_s"] - thermal[i]["pts_s"]), i) for i in unused)
        if delta > 0.05:
            unpaired_v.append(v)
            continue
        unused.remove(index)
        pairs.append({"V": v, "T": thermal[index], "delta_s": delta})
    return pairs, unpaired_v, [thermal[i] for i in sorted(unused)]


def run(root, output):
    reservation = root.parent / "validation_label_audit_v1/fresh_holdout_reservation_v1.json"
    source = json.loads(reservation.read_text(encoding="utf-8"))
    if len(source["candidates"]) != 2:
        raise ValueError("unexpected confirmation candidate count")
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    records = []
    unpaired = []
    jobs = []
    for session_index, candidate in enumerate(source["candidates"]):
        session = candidate["session_id"]
        for sensor, key in (("V", "visible_video"), ("T", "thermal_video")):
            video = Path(candidate[key])
            if not video.is_file():
                raise FileNotFoundError(video)
            jobs.append((session, sensor, video, output / "frames" / session / sensor))
    rows_by_session = {candidate["session_id"]: {} for candidate in source["candidates"]}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [(session, sensor, pool.submit(decode, video, target))
                   for session, sensor, video, target in jobs]
        for session, sensor, future in futures:
            rows_by_session[session][sensor] = future.result()
    for session_index, candidate in enumerate(source["candidates"]):
        session = candidate["session_id"]
        rows = rows_by_session[session]
        pairs, missing_v, missing_t = pair(rows["V"], rows["T"])
        unpaired.extend({"session_id": session, "sensor": sensor, **row}
                        for sensor, missing in (("V", missing_v), ("T", missing_t)) for row in missing)
        for local_index, item in enumerate(pairs):
            records.append({"pair_id": f"confirm_{session_index + 1}_{local_index:04d}",
                            "session_id": session, "video_group": candidate["video_group"],
                            "batch_id": "B4", "V": item["V"], "T": item["T"],
                            "delta_s": item["delta_s"], "selection_rule": "first frame at or after each absolute 10 s PTS boundary"})
    manifest = {"schema_version": "dji_confirmation_pairs_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
                "reservation_file": str(reservation), "reservation_sha256": digest(reservation),
                "sampling_interval_s": 10, "max_pair_delta_s": 0.05,
                "session_counts": {x["session_id"]: sum(r["session_id"] == x["session_id"] for r in records)
                                   for x in source["candidates"]},
                "pair_count": len(records), "unpaired_count": len(unpaired),
                "pairs": records, "unpaired": unpaired}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "decisions.json").write_text(json.dumps({"schema_version": "dji_confirmation_decisions_v1",
                                                   "decisions": {}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pair_count": len(records), "session_counts": manifest["session_counts"],
                      "unpaired_count": len(unpaired), "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.root.resolve(), args.output.resolve())
