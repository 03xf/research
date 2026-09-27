"""Build a video-grouped B1-B3 V/T candidate dataset.

The output is intentionally an *unreviewed candidate* dataset.  It contains
paired frames and provenance, but no automatic flame/hotspot ground truth.
Annotations are added in a later human-review step.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path) -> dict:
    command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "format=duration:stream=width,height,avg_frame_rate,nb_frames",
        "-of", "json", str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"ffprobe failed for {path}: {result.stderr[-500:]}")
    payload = json.loads(result.stdout)
    stream = next(iter(payload.get("streams", [])), {})
    duration = payload.get("format", {}).get("duration")
    return {
        "duration_s": float(duration) if duration else None,
        "width": stream.get("width"),
        "height": stream.get("height"),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "nb_frames": stream.get("nb_frames"),
    }


def parse_batch(row: dict) -> str | None:
    if row.get("batch_id") in {"01", "02", "03"}:
        return f"B{int(row['batch_id'])}"
    match = re.search(r"关联批次\s*=\s*0([1-3])", row.get("notes", ""))
    return f"B{int(match.group(1))}" if match else None


def split_for(group_key: str) -> str:
    # Stable, video-level split. V and T from one recording always share it.
    value = int(hashlib.sha256(group_key.encode("utf-8")).hexdigest()[:8], 16)
    return "dev" if value % 5 == 0 else "train"


def load_groups(manifest: Path, source_root: Path) -> list[dict]:
    grouped: dict[tuple[str, str, str, str, str], dict] = {}
    with manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            batch = parse_batch(row)
            channel = row.get("channel", "").upper()
            if batch not in {"B1", "B2", "B3"} or channel not in {"V", "T"}:
                continue
            prefix = row.get("recording_prefix", "")
            suffix = prefix.rsplit("_", 1)[-1]
            if not suffix.isdigit():
                continue
            # DJI V and T files may have a one-second difference in their
            # filename timestamps while sharing the same recording counter.
            key = (batch, row.get("drone_serial", ""), row.get("session", ""),
                   suffix, row.get("category", ""))
            item = grouped.setdefault(key, {
                "batch": batch,
                "drone_id": row.get("drone_id", ""),
                "drone_serial": row.get("drone_serial", ""),
                "session": row.get("session", ""),
                "recording_id": suffix,
                "category": row.get("category", ""),
                "point_timing": row.get("point_timing", ""),
                "channels": {},
            })
            # The source-relative field points into the historical numeric
            # copy layout. The server's canonical dataset uses target paths.
            relative = Path(row["target_relative_path"])
            item["channels"][channel] = {
                "source_relative_path": row["source_relative_path"],
                "target_relative_path": row["target_relative_path"],
                "recording_prefix": prefix,
                "path": str(source_root / relative),
                "size_bytes": int(row["file_size"]),
                "sha256": row["sha256"].lower(),
            }
    groups = []
    for item in grouped.values():
        if set(item["channels"]) != {"V", "T"}:
            continue
        item["group_key"] = "|".join([
            item["batch"], item["drone_serial"], item["session"],
            item["recording_id"], item["category"],
        ])
        item["recording_prefix"] = item["channels"]["V"]["recording_prefix"]
        item["split"] = split_for(item["group_key"])
        groups.append(item)
    groups.sort(key=lambda item: item["group_key"])
    # Guard against a hash split accidentally leaving a batch without dev data.
    for batch in ("B1", "B2", "B3"):
        batch_groups = [item for item in groups if item["batch"] == batch]
        if batch_groups and not any(item["split"] == "dev" for item in batch_groups):
            batch_groups[0]["split"] = "dev"
    return groups


def extract_group(group: dict, group_index: int, output: Path, interval_s: float) -> list[dict]:
    metadata = {}
    for channel in ("V", "T"):
        source = Path(group["channels"][channel]["path"])
        if not source.is_file():
            raise FileNotFoundError(source)
        metadata[channel] = probe(source)
    duration = min(metadata["V"]["duration_s"], metadata["T"]["duration_s"])
    count = max(0, int(math.floor((duration - 0.05) / interval_s)) + 1)
    group_token = f"{group['batch']}_g{group_index:03d}"
    temp_root = output / "_extract" / group_token
    temp_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for channel in ("V", "T"):
        channel_temp = temp_root / channel
        channel_temp.mkdir(parents=True, exist_ok=True)
        pattern = channel_temp / "frame_%06d.jpg"
        command = [
            "ffmpeg", "-y", "-v", "error", "-i", group["channels"][channel]["path"],
            "-vf", f"fps=1/{interval_s:g}", "-q:v", "2", "-start_number", "0", str(pattern),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(f"ffmpeg failed for {group['channels'][channel]['path']}: {result.stderr[-500:]}")
    extracted_files = {
        channel: sorted((temp_root / channel).glob("frame_*.jpg"))
        for channel in ("V", "T")
    }
    # ffmpeg/image2 may start numbering at 1 despite the requested start
    # number on some short streams. Pair by output order, never by filename.
    actual_count = min(count, len(extracted_files["V"]), len(extracted_files["T"]))
    for index in range(actual_count):
        candidate_id = f"{group_token}_f{index:06d}"
        row = {
            "candidate_id": candidate_id,
            "group_index": group_index,
            "batch": group["batch"],
            "split": group["split"],
            "category": group["category"],
            "drone_id": group["drone_id"],
            "drone_serial": group["drone_serial"],
            "session": group["session"],
            "recording_prefix": group["recording_prefix"],
            "point_timing": group["point_timing"],
            "group_key": group["group_key"],
            "frame_index": index,
            "pts_s": round(index * interval_s, 6),
            "sampling_policy": f"uniform_{interval_s:g}s",
            "review_status": "candidate_unreviewed",
            "v_source_relative_path": group["channels"]["V"]["source_relative_path"],
            "t_source_relative_path": group["channels"]["T"]["source_relative_path"],
            "v_target_relative_path": group["channels"]["V"]["target_relative_path"],
            "t_target_relative_path": group["channels"]["T"]["target_relative_path"],
            "v_image": None,
            "t_image": None,
            "v_image_sha256": None,
            "t_image_sha256": None,
        }
        for channel in ("V", "T"):
            source_image = extracted_files[channel][index]
            destination = output / "images" / channel / group["split"] / f"{candidate_id}.jpg"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source_image), str(destination))
            row[f"{channel.lower()}_image"] = str(destination)
            row[f"{channel.lower()}_image_sha256"] = sha256(destination)
        rows.append(row)
    shutil.rmtree(temp_root, ignore_errors=True)
    return rows


def write_dataset(output: Path, groups: list[dict], rows: list[dict], interval_s: float, manifest_path: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    rows.sort(key=lambda row: row["candidate_id"])
    candidate_path = output / "candidate_frames.jsonl"
    with candidate_path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    group_rows = []
    for group_index, group in enumerate(groups, 1):
        item = {key: value for key, value in group.items() if key != "channels"}
        item["v"] = {key: value for key, value in group["channels"]["V"].items() if key != "path"}
        item["t"] = {key: value for key, value in group["channels"]["T"].items() if key != "path"}
        item["v_probe"] = probe(Path(group["channels"]["V"]["path"]))
        item["t_probe"] = probe(Path(group["channels"]["T"]["path"]))
        item["candidate_count"] = sum(row["group_index"] == group_index for row in rows)
        group_rows.append(item)
    (output / "video_groups.json").write_text(json.dumps(group_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {
        "groups": len(groups),
        "groups_by_batch": {batch: sum(item["batch"] == batch for item in groups) for batch in ("B1", "B2", "B3")},
        "groups_by_split": {split: sum(item["split"] == split for item in groups) for split in ("train", "dev")},
        "frames": len(rows),
        "frames_by_split": {split: sum(item["split"] == split for item in rows) for split in ("train", "dev")},
        "paired_v_t": sum(bool(item["v_image"]) and bool(item["t_image"]) for item in rows),
        "missing_v": sum(not item["v_image"] for item in rows),
        "missing_t": sum(not item["t_image"] for item in rows),
    }
    manifest = {
        "schema_version": "dji_b1_b3_vt_candidate_dataset_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "candidate_unreviewed",
        "purpose": "B1-B3 V/T paired frame candidate pool for human annotation",
        "source_manifest": str(manifest_path),
        "source_manifest_sha256": sha256(manifest_path),
        "source_scope": "B1-B3 only; B4 is intentionally excluded and reserved for final evaluation",
        "split_unit": "complete V/T recording group (same session and recording prefix)",
        "sampling_interval_s": interval_s,
        "annotation_policy": {
            "V": "human review required; flame / confirmed_negative / ignore",
            "T": "human review required; hotspot / confirmed_negative / ignore",
            "smoke": "do not label as flame",
            "non_fire_heat": "do not label as hotspot without review",
        },
        "counts": counts,
        "groups": group_rows,
        "candidate_frames": str(candidate_path),
        "blind_test_accessed": False,
        "labels_frozen": False,
    }
    (output / "dataset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "README.md").write_text(
        "# B1-B3 V/T candidate dataset v1\n\n"
        "This directory contains uniformly sampled paired V/T frames from B1-B3. "
        "The frames are candidates only: no flame/hotspot label is considered ground truth "
        "until human review writes an annotation ledger. B4 is excluded and reserved for final evaluation.\n\n"
        "- `dataset_manifest.json`: provenance, video groups, split and counts\n"
        "- `video_groups.json`: one row per complete V/T recording group\n"
        "- `candidate_frames.jsonl`: one row per paired timestamp candidate\n"
        "- `images/V|T/{train,dev}`: extracted native-resolution frames\n",
        encoding="utf-8",
    )
    shutil.rmtree(output / "_extract", ignore_errors=True)
    print(json.dumps({"output": str(output), "counts": counts}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval-s", type=float, default=10.0)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    groups = load_groups(args.manifest, args.source_root)
    if not groups:
        raise SystemExit("no complete B1-B3 V/T groups found")
    if args.output.exists():
        raise SystemExit(f"output exists: {args.output}")
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(extract_group, group, index, args.output, args.interval_s): (index, group)
            for index, group in enumerate(groups, 1)
        }
        for future in as_completed(futures):
            index, group = futures[future]
            result = future.result()
            rows.extend(result)
            print(f"extracted {index}/{len(groups)} {group['group_key']} candidates={len(result)}", flush=True)
    write_dataset(args.output, groups, rows, args.interval_s, args.manifest)


if __name__ == "__main__":
    main()
