from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(r"D:\课题\_dji_preview")
INVENTORY = ROOT / "fire_coordinate_inventory_v3.csv"
OUT_COORD = ROOT / "fire_point_coordinate_match_v3.csv"
OUT_FIRE = ROOT / "fire_point_one_to_one_status_v3.csv"
OUT_JSON = ROOT / "fire_point_correspondence_v3.json"
OUT_IMAGE = ROOT / "fire_point_correspondence_confirmation_v3.jpg"


def get_font(size: int):
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def resize(path: Path, width: int) -> Image.Image:
    im = Image.open(path).convert("RGB")
    h = max(1, round(im.height * width / im.width))
    return im.resize((width, h), Image.Resampling.LANCZOS)


def write_csv(path: Path, rows: list[dict]):
    fields = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def build_rows():
    inventory = {}
    with INVENTORY.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            inventory[row["point_id"]] = row

    def row(coord_id, fire_id, status, confidence, need, event_scope, note):
        src = inventory[coord_id]
        return {
            "coordinate_id": coord_id,
            "coordinate_batch": src["batch_id"],
            "latitude": src["latitude"],
            "longitude": src["longitude"],
            "coordinate_source": src["source"],
            "fire_point_id_or_none": fire_id,
            "relation_status": status,
            "confidence": confidence,
            "needs_user_confirmation": "是" if need else "否",
            "event_scope": event_scope,
            "evidence_note": note,
        }

    coordinate_rows = [
        row("B1_F1_LRF", "B1_F1_video", "高概率对应", "高", False, "当前 B1 事件", "B1 多张 T/V 激光观测落在同一处炭化火堆附近；约 0.91 m。"),
        row("B2_F1_LRF", "B2_F1_video", "放火前参考对应", "中", False, "当前 B2 事件，放火前", "图像是放火前木柴堆；可作为位置参考，但不是燃烧期火焰中心真值。"),
        row("B3_F1_LRF", "B3_N_video / B3_S_video", "二选一待确认", "待确认", True, "当前 B3 事件", "需要判断 F1 激光落点对应北侧还是南侧火点。"),
        row("B3_F2_LRF", "B3_N_video / B3_S_video", "二选一待确认", "待确认", True, "当前 B3 事件", "需要判断 F2 激光落点对应北侧还是南侧火点。"),
        row("B4_F1_LRF", "无", "不对应当前六点", "已排除", False, "另一场放火事件", "时间为 11:21-11:24，和当前 10:54 东/西两个火点不是同一场事件。"),
        row("B4_F2_candidate_northwest_charred", "无", "不对应当前六点", "已排除", False, "另一场放火事件", "事后影像候选，已判为另一场放火事件。"),
        row("B4_F2_candidate_middle_gray", "无", "不对应当前六点", "已排除", False, "另一场放火事件", "事后影像候选，已判为另一场放火事件。"),
        row("B4_F2_candidate_south_charred", "无", "不对应当前六点", "已排除", False, "另一场放火事件", "事后影像候选，已判为另一场放火事件。"),
    ]

    fire_rows = [
        {"fire_point_id": "B1_F1_video", "batch_id": "B1", "fire_point_name": "B1 单火点", "video_time_local": "2026-09-07 16:03", "video_latitude": "31.2891367878", "video_longitude": "120.4727593553", "matched_coordinate_id": "B1_F1_LRF", "mapping_status": "高概率对应", "needs_user_confirmation": "否", "note": "事后激光参考；不等于视觉独立绝对定位。"},
        {"fire_point_id": "B2_F1_video", "batch_id": "B2", "fire_point_name": "B2 单火点", "video_time_local": "2026-09-08 09:25", "video_latitude": "31.2895088594", "video_longitude": "120.4727937180", "matched_coordinate_id": "B2_F1_LRF", "mapping_status": "放火前参考对应", "needs_user_confirmation": "否", "note": "仅作放火前木柴堆参考，不作为燃烧期火焰真值。"},
        {"fire_point_id": "B3_N_video", "batch_id": "B3", "fire_point_name": "B3 北侧火点", "video_time_local": "2026-09-08 10:07", "video_latitude": "31.2899036006", "video_longitude": "120.4726785084", "matched_coordinate_id": "B3_F1_LRF 或 B3_F2_LRF", "mapping_status": "待确认", "needs_user_confirmation": "是", "note": "与 B3 南侧共同组成 F1/F2 互斥配对。"},
        {"fire_point_id": "B3_S_video", "batch_id": "B3", "fire_point_name": "B3 南侧火点", "video_time_local": "2026-09-08 10:07", "video_latitude": "31.2896677352", "video_longitude": "120.4727986134", "matched_coordinate_id": "B3_F1_LRF 或 B3_F2_LRF", "mapping_status": "待确认", "needs_user_confirmation": "是", "note": "与 B3 北侧共同组成 F1/F2 互斥配对。"},
        {"fire_point_id": "B4_E_video", "batch_id": "B4", "fire_point_name": "B4 东侧靠道路火点", "video_time_local": "2026-09-08 10:54", "video_latitude": "31.2887792678", "video_longitude": "120.4727584031", "matched_coordinate_id": "无（保留影像近似坐标）", "mapping_status": "当前事件无可用激光对应", "needs_user_confirmation": "否", "note": "B4_F1 和三个 B4_F2 候选属于另一场放火事件。"},
        {"fire_point_id": "B4_W_video", "batch_id": "B4", "fire_point_name": "B4 西侧靠树木火点", "video_time_local": "2026-09-08 10:54", "video_latitude": "31.2888262887", "video_longitude": "120.4724890680", "matched_coordinate_id": "无（保留影像近似坐标）", "mapping_status": "当前事件无可用激光对应", "needs_user_confirmation": "否", "note": "B4_F1 和三个 B4_F2 候选属于另一场放火事件。"},
    ]
    return coordinate_rows, fire_rows


def make_confirmation_image():
    panels = [
        ("B1：B1_F1 激光坐标 → B1 单火点（高概率对应）", ROOT / "b1_ref_projection.jpg"),
        ("B2：B2_F1 激光坐标 → B2 放火前木柴堆（不是燃烧期真值）", ROOT / "b2_ref_projection.jpg"),
        ("B3：请只确认 F1/F2 与北侧/南侧哪一组对应", ROOT / "B3_LRF_video_correspondence_confirmation.jpg"),
        ("B4：当前 10:54 的东/西两个火点；已有 B4 坐标均属另一场事件，不分配", ROOT / "B4_current_fire_correspondence_confirmation.jpg"),
    ]
    width = 920
    title_h = 90
    gap = 18
    rendered = []
    for title, path in panels:
        if not path.exists():
            continue
        im = resize(path, width)
        c = Image.new("RGB", (width, title_h + im.height), "white")
        d = ImageDraw.Draw(c)
        d.text((16, 10), title, fill=(18, 18, 18), font=get_font(28))
        d.text((16, 52), "只需看 B3：判断 F1=北/F2=南，或 F1=南/F2=北，也可以选都不对应。", fill=(70, 70, 70), font=get_font(21))
        c.paste(im, (0, title_h))
        rendered.append(c)
    out = Image.new("RGB", (width, sum(x.height for x in rendered) + gap * max(0, len(rendered) - 1)), "white")
    y = 0
    for c in rendered:
        out.paste(c, (0, y))
        y += c.height + gap
    out.save(OUT_IMAGE, quality=92, subsampling=0)


def main():
    coordinate_rows, fire_rows = build_rows()
    write_csv(OUT_COORD, coordinate_rows)
    write_csv(OUT_FIRE, fire_rows)
    make_confirmation_image()
    payload = {
        "schema_version": "fire_point_correspondence_v3",
        "created_local": datetime.now().isoformat(timespec="seconds"),
        "video_fire_point_count": 6,
        "coordinate_record_count": len(coordinate_rows),
        "one_to_one_fire_rows": fire_rows,
        "coordinate_rows": coordinate_rows,
        "pending_user_decision": "B3_F1_LRF 与 B3_F2_LRF 分别对应北侧还是南侧火点；也可判定都不对应。",
        "outputs": {
            "coordinate_match_csv": str(OUT_COORD),
            "fire_point_status_csv": str(OUT_FIRE),
            "confirmation_image": str(OUT_IMAGE),
        },
        "limits": [
            "视频经纬度是名义内参、姿态和假设地面高程下的影像近似坐标。",
            "LRF 坐标是激光命中参考，不等于燃烧中火焰中心。",
            "B4 当前 10:54 视频的东/西火点没有同一事件的可用 LRF 坐标。",
        ],
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"coordinate_csv": str(OUT_COORD), "fire_csv": str(OUT_FIRE), "json": str(OUT_JSON), "image": str(OUT_IMAGE)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
