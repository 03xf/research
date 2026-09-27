#!/usr/bin/env python3
"""Audit DJI Matrice 4T photo/video metadata and T/V file relationships."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

DJI_FIELDS = [
    "ImageSource", "GpsStatus", "GpsLatitude", "GpsLongitude",
    "AbsoluteAltitude", "RelativeAltitude", "GimbalRollDegree",
    "GimbalYawDegree", "GimbalPitchDegree", "FlightRollDegree",
    "FlightYawDegree", "FlightPitchDegree", "RtkFlag", "RtkStdLon",
    "RtkStdLat", "RtkStdHgt", "RtkDiffAge", "DewarpFlag", "DewarpData",
    "DewarpDataK6", "CalibratedFocalLength", "CalibratedOpticalCenterX",
    "CalibratedOpticalCenterY", "UTCAtExposure", "LRFTargetDistance",
    "LRFTargetLon", "LRFTargetLat", "LRFTargetAlt", "LRFTargetAbsAlt",
]
VIDEO_SUFFIXES = ("_T", "_V", "_S")
ALIASES = {"GpsLatitude": ("GpsLatitude", "GPSLatitude"), "GpsLongitude": ("GpsLongitude", "GPSLongitude")}


def run_json(command: List[str]) -> Any:
    try:
        completed = subprocess.run(
            command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return {"error": str(exc), "command": command}


def suffix_value(record: Dict[str, Any], field: str) -> Any:
    for candidate in ALIASES.get(field, (field,)):
        for key, value in record.items():
            if key == candidate or key.endswith(":" + candidate):
                return value
    return None


def audit_images(files: List[Path]) -> Dict[str, Any]:
    if not files:
        return {"tool": shutil.which("exiftool"), "files": [], "availability": {}}
    if not shutil.which("exiftool"):
        return {"tool": None, "files": [], "availability": {}, "error": "exiftool unavailable"}
    requested = sorted(set(DJI_FIELDS + ["GPSLatitude", "GPSLongitude"]))
    raw = run_json(
        ["exiftool", "-j", "-n", "-G1", "-s"]
        + ["-" + field for field in requested]
        + [str(path) for path in files]
    )
    if not isinstance(raw, list):
        return {"tool": "exiftool", "files": [], "availability": {}, "error": raw}
    records = []
    counts = {field: 0 for field in DJI_FIELDS}
    for item in raw:
        normalized = {"source": item.get("SourceFile")}
        for field in DJI_FIELDS:
            value = suffix_value(item, field)
            normalized[field] = value
            if value is not None and value != "":
                counts[field] += 1
        records.append(normalized)
    return {"tool": "exiftool", "files": records, "availability": counts}


def video_key(path: Path) -> Tuple[str, str]:
    stem = path.stem
    for suffix in VIDEO_SUFFIXES:
        if stem.endswith(suffix):
            return str(path.parent / stem[: -len(suffix)]), suffix[1:]
    return str(path.parent / stem), ""


def probe_video(path: Path) -> Dict[str, Any]:
    if not shutil.which("ffprobe"):
        return {"source": str(path), "error": "ffprobe unavailable"}
    result = run_json(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration,start_time,size:stream=index,codec_type,width,height,"
            "r_frame_rate,avg_frame_rate,start_time,duration,nb_frames,time_base",
            "-of", "json", str(path),
        ]
    )
    if isinstance(result, dict):
        result["source"] = str(path)
    return result


def audit_videos(files: List[Path]) -> Dict[str, Any]:
    pairs: Dict[str, Dict[str, str]] = defaultdict(dict)
    probes = []
    for path in files:
        key, camera = video_key(path)
        pairs[key][camera] = str(path)
        probes.append(probe_video(path))
    pair_records = []
    for key, members in sorted(pairs.items()):
        pair_records.append(
            {
                "pair_key": key,
                "T": members.get("T"),
                "V": members.get("V"),
                "S": members.get("S"),
                "has_tv_pair": bool(members.get("T") and members.get("V")),
            }
        )
    return {"probes": probes, "pairs": pair_records}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_mrk(files: List[Path]) -> List[Dict[str, Any]]:
    return [
        {"source": str(path), "size": path.stat().st_size, "sha256": sha256(path)}
        for path in files
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = args.root
    photos = sorted(root.rglob("*.JPG")) + sorted(root.rglob("*.jpg"))
    videos = sorted(root.rglob("*.MP4")) + sorted(root.rglob("*.mp4"))
    mrk = sorted(root.rglob("*.MRK")) + sorted(root.rglob("*.mrk"))
    report = {
        "dataset_root": str(root),
        "manual_fields": DJI_FIELDS,
        "counts": {"photos": len(photos), "videos": len(videos), "mrk": len(mrk)},
        "images": audit_images(photos),
        "videos": audit_videos(videos),
        "mrk": audit_mrk(mrk),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "availability": report["images"].get("availability", {})}, indent=2, ensure_ascii=False))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
