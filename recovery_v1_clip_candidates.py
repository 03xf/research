"""Index development video groups for dense tracking clip selection."""

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


CLASS_NAMES = {"V": ("smoke", "flame"), "T": ("hotspot",)}


def classes(path, sensor):
    counts = Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            fields = line.split()
            counts[CLASS_NAMES[sensor][int(fields[0])]] += 1
    return counts


def build(root):
    root = root.resolve()
    target = root / "clip_candidates_v1.json"
    if target.exists():
        raise FileExistsError(target)
    dataset = root / "dataset_review_applied_v1"
    ledger = json.loads((root / "sample_ledger.json").read_text(encoding="utf-8"))["records"]
    groups = defaultdict(list)
    for row in ledger:
        if row["split"] != "validation":
            continue
        key = (row["batch_id"], row["session_id"], row["video_group"])
        label = dataset / row["sensor"] / "labels" / "validation" / (row["observation_id"] + ".txt")
        groups[key].append({"observation_id": row["observation_id"],
                            "sensor": row["sensor"], "timestamp_s": row["timestamp_s"],
                            "classes": dict(classes(label, row["sensor"])),
                            "thermal_video": row["source_video"]["thermal"],
                            "visible_video": row["source_video"]["visible"]})
    output_groups = []
    candidates = defaultdict(list)
    for (batch, session, video_group), rows in sorted(groups.items()):
        rows.sort(key=lambda row: (row["timestamp_s"], row["sensor"]))
        thermal_paths = {row["thermal_video"] for row in rows}
        visible_paths = {row["visible_video"] for row in rows}
        if len(thermal_paths) != 1 or len(visible_paths) != 1:
            raise ValueError(f"inconsistent source videos: {session} {video_group}")
        thermal = next(iter(thermal_paths))
        visible = next(iter(visible_paths))
        if not Path(thermal).is_file() or not Path(visible).is_file():
            raise FileNotFoundError(f"paired source video missing: {session} {video_group}")
        by_time = defaultdict(dict)
        for row in rows:
            by_time[row["timestamp_s"]][row["sensor"]] = row
        evidence = []
        first_positive = None
        for timestamp, pair in sorted(by_time.items()):
            visible_classes = pair.get("V", {}).get("classes", {})
            thermal_classes = pair.get("T", {}).get("classes", {})
            has_flame = visible_classes.get("flame", 0) > 0
            has_smoke = visible_classes.get("smoke", 0) > 0
            has_heat = thermal_classes.get("hotspot", 0) > 0
            if first_positive is None and (has_flame or has_smoke or has_heat):
                first_positive = timestamp
            phases = []
            if has_flame:
                phases.append("visible_flame")
            if has_smoke and not has_flame:
                phases.append("visible_smoke_only")
            if has_heat and not has_flame and "V" in pair:
                phases.append("thermal_heat_without_visible_flame")
            if sum(visible_classes.values()) > 1 or sum(thermal_classes.values()) > 1:
                phases.append("multiple_boxes")
            if not has_flame and not has_smoke and not has_heat and "V" in pair and "T" in pair:
                phases.append("paired_negative")
            for phase in phases:
                candidate = {"phase_candidate": phase, "batch_id": batch,
                             "session_id": session, "video_group": video_group,
                             "anchor_timestamp_s": timestamp,
                             "start_s": max(0.0, float(timestamp) - 15.0),
                             "duration_s": 30.0,
                             "thermal_video": thermal, "visible_video": visible,
                             "evidence": {"V": visible_classes, "T": thermal_classes}}
                candidates[phase].append(candidate)
            evidence.append({"timestamp_s": timestamp,
                             "V": visible_classes, "T": thermal_classes})
        if first_positive is not None:
            candidates["first_positive_observation"].append({
                "phase_candidate": "first_positive_observation", "batch_id": batch,
                "session_id": session, "video_group": video_group,
                "anchor_timestamp_s": first_positive,
                "start_s": max(0.0, float(first_positive) - 15.0), "duration_s": 30.0,
                "thermal_video": thermal, "visible_video": visible,
                "evidence": "first sparse positive observation; ignition is unverified"})
        output_groups.append({"batch_id": batch, "session_id": session,
                              "video_group": video_group, "thermal_video": thermal,
                              "visible_video": visible, "observations": evidence})
    payload = {"schema_version": "dji_recovery_clip_candidates_v1",
               "created_utc": datetime.now(timezone.utc).isoformat(),
               "source_split": "historically_exposed_development_validation",
               "selection_basis": "reviewed sparse labels and source timestamps",
               "time_basis": "source sample timestamps; actual decoded PTS not yet checked",
               "clip_duration_s": 30.0, "target_sampling_hz": 5,
               "phase_ground_truth": "unverified",
               "video_group_count": len(output_groups),
               "candidate_counts": {phase: len(rows) for phase, rows in candidates.items()},
               "candidates": dict(candidates), "groups": output_groups}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"video_groups": len(output_groups),
                      "candidate_counts": payload["candidate_counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    build(parser.parse_args().root)
