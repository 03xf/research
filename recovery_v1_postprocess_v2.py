from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import os
import shutil

ROOT = Path(os.environ.get("RECOVERY_ROOT", "/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1"))
LOC = ROOT.parent / "localization_v2"
OUT = ROOT / "postprocess_v2"
OUT.mkdir(parents=True, exist_ok=True)

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def read_json(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)

def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

now = datetime.now(timezone.utc).isoformat()
inventory_path = LOC / "fire_coordinate_inventory_v3.csv"
inventory = list(csv.DictReader(inventory_path.open(encoding="utf-8-sig")))
if any(not r["latitude"] or not r["longitude"] for r in inventory):
    raise RuntimeError("coordinate inventory contains blank coordinates")

# Each row makes the distinction between a coordinate reference and a model output explicit.
assoc_rows = []
assoc_fields = ["point_id", "batch_id", "latitude", "longitude", "coordinate_source",
                "source_artifact", "association_status", "physical_target_status", "notes"]
for r in inventory:
    status = r["status"]
    if status == "reference_confirmed":
        association = "reference_only_not_model_prediction"
        physical = "lrf_reference_not_independently_verified_as_video_source"
        artifact = str(LOC / "lrf_reference_event_centers.csv")
    elif status == "prefire_reference":
        association = "prefire_reference_only"
        physical = "prefire_fuel_pile"
        artifact = str(LOC / "lrf_reference_event_centers.csv")
    elif status == "provisional_visual":
        association = "visual_multiview_candidate"
        physical = "burning_source_candidate"
        artifact = str(LOC / ("b4_video_multiview_projection_preview.jpg" if r["batch_id"] == "B4" else "batch_video_audit/03/contact.jpg"))
    else:
        association = "unresolved_candidate_set"
        physical = "postfire_image_patch_candidate"
        artifact = str(LOC / "b4_patch_projection.jpg")
    assoc_rows.append({"point_id": r["point_id"], "batch_id": r["batch_id"],
                       "latitude": r["latitude"], "longitude": r["longitude"],
                       "coordinate_source": r["source"], "source_artifact": artifact,
                       "association_status": association,
                       "physical_target_status": physical, "notes": r["notes"]})
write_csv(OUT / "fire_source_association_v1.csv", assoc_rows, assoc_fields)
write_json(OUT / "fire_source_association_v1.json", {
    "schema_version": "dji_fire_source_association_v1",
    "created_utc": now,
    "inventory": str(inventory_path),
    "inventory_sha256": sha(inventory_path),
    "rows": assoc_rows,
    "interpretation": "association is a coordinate/source classification; it is not a validated model localization error"
})

# Summarize all tracked clips and explicitly record why metric identity/source errors are unavailable.
track_rows = []
track_fields = ["clip_id", "sensor", "frames", "tracks", "tracked_detections", "untracked_detections",
                "candidate_coordinate_set", "association_status", "identity_metrics_status", "source_pixel_error_status"]
for manifest_path in sorted((ROOT / "tracking_v2").glob("*/manifest.json")):
    m = read_json(manifest_path)
    clip_id = manifest_path.parent.name
    for sensor, summary in sorted(m.get("summaries", {}).items()):
        if clip_id.startswith("B3_"):
            candidate_set = "B3_video_north_fire|B3_video_south_fire"
        elif clip_id.startswith(("visible_", "paired_", "multiple_")):
            candidate_set = "B4_video_east_near_road|B4_video_west_near_tree"
        else:
            candidate_set = ""
        track_rows.append({
            "clip_id": clip_id,
            "sensor": sensor,
            "frames": summary.get("frames"),
            "tracks": summary.get("tracks"),
            "tracked_detections": summary.get("tracked_detections"),
            "untracked_detections": json.dumps(summary.get("untracked_detections", {}), ensure_ascii=False),
            "candidate_coordinate_set": candidate_set,
            "association_status": "unresolved_same_target_not_verified",
            "identity_metrics_status": "unavailable_no_human_track_identity_ground_truth",
            "source_pixel_error_status": "unavailable_no_ground_source_point_truth",
        })
write_csv(OUT / "tracking_coordinate_association_v1.csv", track_rows, track_fields)
write_json(OUT / "tracking_coordinate_association_v1.json", {
    "schema_version": "dji_tracking_coordinate_association_v1",
    "created_utc": now,
    "rows": track_rows,
    "coordinate_inventory": str(inventory_path),
    "decision": "tracking outputs remain candidate associations because clips and coordinate estimates are not the same-time independently surveyed target truth"
})

# Convert frozen confirmation metrics into a compact, auditable error-attribution table.
eval_path = ROOT / "evaluations" / "confirmation_frozen_v1" / "result.json"
evaluation = read_json(eval_path)
error_rows = []
error_fields = ["sensor", "class_name", "session_id", "images", "ground_truth", "tp", "fp", "fn",
                "precision", "recall", "ap50", "negative_false_positive_images", "error_pattern",
                "cause_status", "evidence_boundary"]
for sensor, sensor_data in evaluation["sensors"].items():
    for c in sensor_data["classes"]:
        for s in c.get("sessions", []):
            if sensor == "T" and c["class_name"] == "hotspot" and s.get("negative_false_positive_images", 0) > 0:
                pattern = "high_temperature_background_false_positive_proxy"
                boundary = "negative-image false-positive count; temperature cause not independently measured"
            elif s.get("recall", 0) < 0.70:
                pattern = "missed_targets_or_view_change"
                boundary = "low session recall; small-target and boundary causes remain hypotheses"
            elif s.get("precision", 0) < 0.60:
                pattern = "false_positive_detections"
                boundary = "low session precision; object-level cause not independently adjudicated"
            else:
                pattern = "no_primary_gate_failure"
                boundary = "session metrics only"
            error_rows.append({"sensor": sensor, "class_name": c["class_name"], "session_id": s["session_id"],
                               "images": s["images"], "ground_truth": s["ground_truth"], "tp": s["tp"],
                               "fp": s["fp"], "fn": s["fn"], "precision": s["precision"],
                               "recall": s["recall"], "ap50": c["ap50"],
                               "negative_false_positive_images": s.get("negative_false_positive_images", 0),
                               "error_pattern": pattern, "cause_status": "hypothesis_not_proven",
                               "evidence_boundary": boundary})
write_csv(OUT / "confirmation_error_attribution_v1.csv", error_rows, error_fields)
write_json(OUT / "confirmation_error_attribution_v1.json", {
    "schema_version": "dji_confirmation_error_attribution_v1",
    "created_utc": now,
    "evaluation": str(eval_path),
    "evaluation_sha256": sha(eval_path),
    "rows": error_rows,
    "rule": "numeric session evidence is reported; causal labels are hypotheses unless independently verified"
})

# Package a final report without altering the original dated report.
base_report = ROOT / "REPORT_20260925.md"
coord_report = LOC / "REPORT.md"
base_text = base_report.read_text(encoding="utf-8")
coord_text = coord_report.read_text(encoding="utf-8") if coord_report.exists() else ""
report = base_text + "\n\n## 6. 坐标与火源关联后处理\n\n"
report += "本次后处理使用已冻结模型、确认评估和跟踪结果，不重新训练、不在确认集调阈值。坐标总表为 `localization_v2/fire_coordinate_inventory_v3.csv`，共 12 条记录：5 条 LRF 参考、4 条多视角视频估计、3 条 B4 F2 影像候选。所有纬度和经度字段非空。\n\n"
report += "B2 仅作为放火前木柴堆参考。B4 F2 没有独立 LRF 事件，三个候选分别保留，未选择单一真值。视频坐标依赖名义焦距和假设地面高程；在 Matrice 4T 标定缺失时只作为近似位置。\n\n"
report += "## 7. 误差归因结果\n\n"
report += "逐 session 表见 `postprocess_v2/confirmation_error_attribution_v1.csv`。V 烟雾和火焰主要表现为低召回；T 热点在明确无热点图像中仍产生误检，作为高温背景误检的代理证据。上述原因标签均为待验证假设，不能从当前指标单独证明。\n\n"
report += "## 8. 跟踪与定位输出\n\n"
report += "逐片段汇总见 `postprocess_v2/tracking_coordinate_association_v1.csv`。跟踪 ID、火焰框下边中点和坐标候选已保存，但没有人工逐帧身份真值，因此 ID 切换率、覆盖率和像素定位误差仍为不可评估。\n\n"
report += "B3 代表片段 `B3_10m07_D02_pts_v2_E2_s0` 已用冻结 E2 模型处理；B4 四段既有带 ID 片段保留。片段与坐标的关系仅是候选坐标集合，未证明某条轨迹对应某一个物理火源。\n\n"
report += "## 9. 后处理文件\n\n"
report += "- `postprocess_v2/fire_source_association_v1.csv`：点位来源与火源关联状态；\n- `postprocess_v2/confirmation_error_attribution_v1.csv`：冻结确认集逐 session 误差表；\n- `postprocess_v2/tracking_coordinate_association_v1.csv`：带 ID 轨迹和坐标关联状态；\n- `postprocess_v2/*json`：输入哈希、规则和复现摘要。\n\n"
report += "坐标详细说明见 `localization_v2/REPORT.md`。当前可交付的是检测失败分析、视频候选位置和参考关联；绝对视觉定位精度仍不可用。\n"
final_report = ROOT / "REPORT_FINAL_20260925.md"
final_report.write_text(report, encoding="utf-8")

# Update the live status after preserving the previous state.
status_path = ROOT / "status_current.json"
status = read_json(status_path)
history = ROOT / "status_history"
history.mkdir(exist_ok=True)
old_hash = sha(status_path)
shutil.copy2(status_path, history / f"pre_postprocess_v2_{old_hash}.json")
status["updated_utc"] = now
status["stage"] = "postprocess_coordinate_association_and_error_attribution_complete"
status["postprocess_v2"] = {
    "status": "complete",
    "coordinate_inventory": str(inventory_path),
    "coordinate_inventory_sha256": sha(inventory_path),
    "association_csv": str(OUT / "fire_source_association_v1.csv"),
    "error_attribution_csv": str(OUT / "confirmation_error_attribution_v1.csv"),
    "tracking_association_csv": str(OUT / "tracking_coordinate_association_v1.csv"),
    "final_report": str(final_report),
    "absolute_visual_localization": "unavailable",
    "b4_f2": "three_candidate_coordinates_retained_no_unique_lrf_truth",
    "training": "frozen_no_additional_training",
}
status["next_action"] = "No further current-data training. Use postprocess_v2 artifacts for handoff; absolute localization requires Matrice 4T calibration or new known-coordinate data."
write_json(status_path, status)

summary = {
    "status": "complete",
    "coordinate_rows": len(inventory),
    "association_rows": len(assoc_rows),
    "tracking_rows": len(track_rows),
    "error_rows": len(error_rows),
    "final_report": str(final_report),
    "outputs": [str(p) for p in sorted(OUT.iterdir())],
}
write_json(OUT / "postprocess_v2_summary.json", summary)
print(json.dumps(summary, ensure_ascii=False, indent=2))
