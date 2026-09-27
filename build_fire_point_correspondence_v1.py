from pathlib import Path
import csv, json

ROOT = Path(r"D:\课题\_dji_preview")
inventory_path = ROOT / "fire_coordinate_inventory_v3.csv"
out_csv = ROOT / "fire_point_correspondence_v1.csv"
out_json = ROOT / "fire_point_correspondence_v1.json"

rows = list(csv.DictReader(inventory_path.open(encoding="utf-8-sig")))
relations = {
    "B1_F1_LRF": ("B1", "当前批次", "B1 F1 单火点", "reference_confirmed", "已对应", "B1 批次激光参考；不是视觉独立预测"),
    "B2_F1_LRF": ("B2", "当前批次的放火前参考", "放火前木柴堆", "prefire_reference", "已确认但不属于燃烧火点", "只作放火前位置参考，不作为燃烧期间火焰真值"),
    "B3_F1_LRF": ("B3", "当前批次", "B3 北侧视频明火？", "reference_confirmed", "待人工确认", "LRF 点距北侧视频估计点约 13.83 m，投影没有直接落在火堆上；不能仅凭 F1 编号断定同一物理点"),
    "B3_F2_LRF": ("B3", "当前批次", "B3 南侧视频明火？", "reference_confirmed", "待人工确认", "LRF 点距南侧视频估计点约 4.75 m；空间接近但仍需确认同一物理火堆"),
    "B4_F1_LRF": ("B4", "另一场放火事件", "不对应当前 10:54 视频火点", "reference_confirmed", "排除当前事件", "用户确认属于另一场放火；不分配给东侧或西侧当前视频火点"),
    "B3_video_north_fire": ("B3", "当前批次", "北侧视频明火", "provisional_visual", "已对应", "影像多视角地面近似坐标；无独立 LRF 真值"),
    "B3_video_south_fire": ("B3", "当前批次", "南侧视频明火", "provisional_visual", "已对应", "影像多视角地面近似坐标；无独立 LRF 真值"),
    "B4_video_east_near_road": ("B4", "当前 10:54 视频事件", "东侧靠道路明火", "provisional_visual", "已对应", "当前视频影像多视角近似坐标；不使用 B4 F1 LRF"),
    "B4_video_west_near_tree": ("B4", "当前 10:54 视频事件", "西侧靠树木明火", "provisional_visual", "已对应", "当前视频影像多视角近似坐标；不使用 B4 F1 LRF"),
    "B4_F2_candidate_northwest_charred": ("B4", "另一场放火事件", "不对应当前 B4 火点", "candidate_only", "排除当前事件", "用户确认候选影像属于另一场放火；不作为 B4 F2 当前事件坐标"),
    "B4_F2_candidate_middle_gray": ("B4", "另一场放火事件", "不对应当前 B4 火点", "candidate_only", "排除当前事件", "用户确认候选影像属于另一场放火；不作为 B4 F2 当前事件坐标"),
    "B4_F2_candidate_south_charred": ("B4", "另一场放火事件", "不对应当前 B4 火点", "candidate_only", "排除当前事件", "用户确认候选影像属于另一场放火；不作为 B4 F2 当前事件坐标"),
}

out = []
for row in rows:
    rel = relations.get(row["point_id"])
    if rel is None:
        raise RuntimeError(f"missing relation for {row['point_id']}")
    batch, scope, target, role, status, note = rel
    out.append({
        "point_id": row["point_id"],
        "batch_id": batch,
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "coordinate_source": row["source"],
        "coordinate_role": role,
        "event_scope": scope,
        "fire_point": target,
        "correspondence_status": status,
        "correspondence_note": note,
    })

with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(out[0]))
    writer.writeheader()
    writer.writerows(out)

summary = {
    "version": "fire_point_correspondence_v1",
    "coordinate_count": len(out),
    "current_event_points": [r["point_id"] for r in out if r["correspondence_status"] in ("已对应", "已对应但为近似关联")],
    "excluded_other_event_points": [r["point_id"] for r in out if r["correspondence_status"] == "排除当前事件"],
    "pending_identity_points": [r["point_id"] for r in out if r["correspondence_status"] == "待人工确认"],
    "user_ruling": "B4 F1 and all three B4 F2 candidate images are from another fire event and are excluded from the current B4 video event.",
    "limits": [
        "provisional_visual coordinates are approximate image-derived ground-plane estimates",
        "LRF reference coordinates are not independent visual predictions",
        "B2 is a prefire reference and not a burning-period fire truth",
    ],
}
out_json.write_text(json.dumps({"summary": summary, "rows": out}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
