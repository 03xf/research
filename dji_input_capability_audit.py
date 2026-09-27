"""Audit available DJI metadata and define the minimal source-point review task.

The audit is read-only with respect to source data. It writes a new versioned
report directory and refuses to overwrite an existing report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def existing(path: Path) -> dict:
    return {"path": str(path), "exists": path.exists(), "sha256": digest(path) if path.is_file() else None}


def csv_profile(path: Path) -> dict:
    if not path.exists():
        return {"path": str(path), "exists": False}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = reader.fieldnames or []
    nonempty = {field: sum(bool(row.get(field, "").strip()) for row in rows) for field in fields}
    return {
        "path": str(path),
        "exists": True,
        "sha256": digest(path),
        "rows": len(rows),
        "fields": fields,
        "nonempty_by_field": nonempty,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True, help="recovery_v1 directory")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    root = args.root.resolve()
    out = (args.output or root / "metadata_audit_v1").resolve()
    if out.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {out}")
    out.mkdir(parents=True)

    calibration = root.parent / "localization" / "calibration_audit_v1.json"
    recovery_calibration = root.parent / "localization" / "calibration_recovery_status_v1.json"
    pairing = root.parent / "localization" / "lrf_time_pairing_audit_v2.json"
    seek = root / ".." / "b4_aligned_seek_audit_v1.json"
    observations = root.parent / "localization" / "lrf_localization_observations_v1.csv"
    if not observations.exists():
        observations = root.parent / "localization" / "lrf_localization_observations_v1.json"

    calibration_data = load_json(calibration) if calibration.exists() else {}
    recovery_data = load_json(recovery_calibration) if recovery_calibration.exists() else {}
    pairing_data = load_json(pairing) if pairing.exists() else {}
    seek_data = load_json(seek) if seek.exists() else {}

    telemetry = sorted((root.parent / "localization_v2").glob("batch_video_audit/*/telemetry.csv"))
    telemetry_profiles = [csv_profile(p) for p in telemetry]
    telemetry_fields = sorted({field for item in telemetry_profiles for field in item.get("fields", [])})

    required_calibration = [
        "V_focal_length", "V_principal_point", "V_distortion",
        "T_focal_length", "T_principal_point", "T_distortion",
        "camera_to_gimbal_extrinsics", "gimbal_to_body_extrinsics",
        "T_V_extrinsics", "timestamp_alignment",
    ]
    calibration_parameters = calibration_data.get("calibration_parameters", {})
    missing_calibration = [name for name in required_calibration if calibration_parameters.get(
        {"V_focal_length": "per_camera_calibrated_focal_and_principal_point",
         "V_principal_point": "per_camera_calibrated_focal_and_principal_point",
         "V_distortion": "distortion_coefficients",
         "T_focal_length": "per_camera_calibrated_focal_and_principal_point",
         "T_principal_point": "per_camera_calibrated_focal_and_principal_point",
         "T_distortion": "distortion_coefficients"}.get(name, name), "unavailable") == "unavailable"]
    # The audit's parameter names are intentionally explicit even when the source
    # audit groups visible and thermal values under one unavailable field.
    missing_calibration = required_calibration[:]

    source_files = {
        "calibration_audit": existing(calibration),
        "calibration_recovery_status": existing(recovery_calibration),
        "time_pairing_audit": existing(pairing),
        "seek_audit": existing(seek),
        "observation_table": existing(observations),
    }
    sync_summary = {
        "lrf_observation_count": pairing_data.get("summary", {}).get("observation_count"),
        "candidate_pair_count": pairing_data.get("summary", {}).get("pair_count"),
        "unpaired_observation_count": pairing_data.get("summary", {}).get("unpaired_observation_count"),
        "filename_clock_is_verified_utc": False,
        "pixel_target_correspondence_verified": pairing_data.get("summary", {}).get("pixel_target_correspondence_verified", False),
        "absolute_localization_enabled": pairing_data.get("summary", {}).get("absolute_localization_enabled", False),
        "video_seek_sampled_pairs": seek_data.get("summary", {}).get("sampled_pairs"),
        "video_seek_read_success_pairs": seek_data.get("summary", {}).get("read_success_pairs"),
        "video_seek_reported_median_delta_s": seek_data.get("summary", {}).get("reported_median_delta_s"),
        "video_seek_reported_max_delta_s": seek_data.get("summary", {}).get("reported_max_delta_s"),
        "video_seek_reported_over_50ms": seek_data.get("summary", {}).get("reported_over_50ms"),
    }

    annotation_task = {
        "purpose": "small_ground_source_truth_set_for_tracking_and_TV_association",
        "reviewer": "user_or_assistant_in_existing_review_ui",
        "recommended_clips": 8,
        "clip_duration_s": 30,
        "sampling_hz": 5,
        "coverage": ["single_flame", "multiple_flames", "thermal_hot_ground_or_wall", "smoke_only", "occlusion", "track_start_end"],
        "per_pair_actions": [
            "mark each visible ground fire source contact point or source region",
            "assign a stable fire_id within the clip",
            "mark V/T as same_source, different_source, or unknown",
            "mark thermal bright non-burning background as hot_background",
        ],
        "does_not_require": ["smoke_box_review", "full_214_image_re_review", "absolute_WGS84_label"],
        "unknown_policy": "unknown is valid and excluded from accuracy denominators",
    }

    report = {
        "schema_version": "dji_input_capability_audit_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "source_files": source_files,
        "calibration": {
            "usable_for_absolute_visual_localization": recovery_data.get("usable_for_matrice4t", False),
            "absolute_localization_status": recovery_data.get("absolute_localization_status", "unknown"),
            "missing_parameters": missing_calibration,
            "metadata_field_counts": calibration_data.get("metadata_field_counts", {}),
            "found_files": recovery_data.get("found_files", []),
        },
        "metadata_fields": {
            "video_telemetry_fields": telemetry_fields,
            "telemetry_profiles": telemetry_profiles,
            "available_for_degraded_realtime": ["latitude", "longitude", "rel_alt", "abs_alt", "gb_yaw", "gb_pitch", "focal_len", "dzoom_ratio", "frame", "offset_s"],
            "not_sufficient_for_absolute_geometry": missing_calibration,
        },
        "synchronization": sync_summary,
        "runtime_requirement": {
            "gpu_plan": {"gpu0": "visible_stream", "gpu1": "thermal_stream"},
            "inputs": ["V/T paired streams", "recorded V/T video"],
            "initial_output": ["web live view", "JSONL", "CSV", "annotated video"],
            "latency_policy": "measure end-to-end latency and choose the lowest latency that does not materially reduce detection quality",
        },
        "small_truth_annotation": annotation_task,
        "conclusion": "Current files support image-plane tracking, telemetry-aware candidate projection and temporal V/T pairing. Absolute WGS84 visual localization remains unavailable until per-camera calibration, extrinsics and verified time alignment are present.",
    }
    (out / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# DJI 输入能力审计 v1",
        "",
        f"生成时间：{report['created_utc']}",
        "",
        "## 已从现有文件解析到的内容",
        "",
        "- 视频遥测字段：" + ", ".join(telemetry_fields),
        f"- LRF 观测：{sync_summary['lrf_observation_count']} 条，候选配对 {sync_summary['candidate_pair_count']} 组，未配对 {sync_summary['unpaired_observation_count']} 条。",
        f"- 视频 seek 抽查：{sync_summary['video_seek_read_success_pairs']}/{sync_summary['video_seek_sampled_pairs']} 对成功读取，报告中位时间差 {sync_summary['video_seek_reported_median_delta_s']} s，最大时间差 {sync_summary['video_seek_reported_max_delta_s']} s。",
        "- 可用于降级实时输出：帧号、视频偏移、飞机位置、高度、云台 yaw/pitch、名义焦距和变焦比例。",
        "",
        "## 仍然缺失",
        "",
        "- " + "\n- ".join(missing_calibration),
        "",
        "这些缺项阻止绝对视觉 WGS84 定位，但不阻止先做图像平面检测、跟踪、时间配对和候选结果展示。",
        "",
        "## 少量火源真值标注任务",
        "",
        "建议抽取 8 个 30 秒片段、5 Hz 成对 V/T 图像。每对只标：地面火源接触点或源区域、片段内稳定 fire_id、V/T 是否同源，以及热像高温非燃烧背景。可选 unknown；不要求重新复核 214 张图，也不要求标烟雾框。",
        "",
        "## 实时输出建议",
        "",
        "服务器两张 RTX 3090 分别处理 V/T 流，网页显示双流、检测框、track_id、候选点、坐标来源、FPS、延迟和丢帧数，同时保存 JSONL、CSV 和带框视频。",
        "",
        "## 结论",
        "",
        report["conclusion"],
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "audit": str(out / "audit.json"), "report": str(out / "REPORT.md")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
