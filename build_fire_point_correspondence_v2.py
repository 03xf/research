from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(r"D:\课题\_dji_preview")
OUT_CSV = ROOT / "fire_point_correspondence_v2.csv"
OUT_JSON = ROOT / "fire_point_correspondence_v2.json"
OUT_IMAGE = ROOT / "fire_point_correspondence_confirmation_v2.jpg"
INVENTORY = ROOT / "fire_coordinate_inventory_v3.csv"


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Local equirectangular distance is sufficient for these short separations.
    north = (lat1 - lat2) * 111_320.0
    east = (lon1 - lon2) * 111_320.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(north, east)


def font(size: int):
    for path in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def load_image(path: Path, width: int) -> Image.Image:
    im = Image.open(path).convert("RGB")
    ratio = width / im.width
    return im.resize((width, max(1, round(im.height * ratio))), Image.Resampling.LANCZOS)


def make_confirmation_image():
    # Existing contact/projection images are evidence panels; they are not changed.
    panels = [
        ("B1：单火点 + B1_F1 激光参考（高度概率对应）", ROOT / "b1_ref_projection.jpg"),
        ("B2：单火点 + B2_F1 放火前木柴堆参考（不是燃烧期真值）", ROOT / "b2_ref_projection.jpg"),
        ("B3：请确认 F1/F2 分别对应北侧还是南侧火点", ROOT / "B3_LRF_video_correspondence_confirmation.jpg"),
        ("B4：当前 10:54 视频东西两个火点；现有 B4 激光点属于另一场事件，不配入", ROOT / "B4_current_fire_correspondence_confirmation.jpg"),
    ]
    panel_width = 920
    gap = 22
    title_h = 84
    rendered = []
    for title, path in panels:
        if not path.exists():
            continue
        im = load_image(path, panel_width)
        canvas = Image.new("RGB", (panel_width, title_h + im.height), "white")
        d = ImageDraw.Draw(canvas)
        d.text((18, 12), title, fill=(20, 20, 20), font=font(28))
        d.text((18, 48), "只需确认：对应 / 不对应。无需填写理由。", fill=(80, 80, 80), font=font(22))
        canvas.paste(im, (0, title_h))
        rendered.append(canvas)
    total_h = sum(im.height for im in rendered) + gap * max(0, len(rendered) - 1)
    out = Image.new("RGB", (panel_width, total_h), "white")
    y = 0
    for im in rendered:
        out.paste(im, (0, y))
        y += im.height + gap
    out.save(OUT_IMAGE, quality=92, subsampling=0)


def build_rows():
    # The six video fire points are the primary objects. LRF is a separate relation.
    sites = {
        "B1_F1_video": ("B1", "B1 单火点", "2026-09-07 16:03", 31.2891367878, 120.4727593553, "视频多视角近似"),
        "B2_F1_video": ("B2", "B2 单火点", "2026-09-08 09:25", 31.2895088594, 120.4727937180, "视频多视角近似"),
        "B3_N_video": ("B3", "B3 北侧火点", "2026-09-08 10:07", 31.2899036006, 120.4726785084, "视频多视角近似"),
        "B3_S_video": ("B3", "B3 南侧火点", "2026-09-08 10:07", 31.2896677352, 120.4727986134, "视频多视角近似"),
        "B4_E_video": ("B4", "B4 东侧靠道路火点", "2026-09-08 10:54", 31.2887792678, 120.4727584031, "视频多视角近似"),
        "B4_W_video": ("B4", "B4 西侧靠树木火点", "2026-09-08 10:54", 31.2888262887, 120.4724890680, "视频多视角近似"),
    }
    lrf = {
        "B1_F1_LRF": ("B1", 31.2891377000, 120.4727498500, "2026-09-07 16:40-16:43", "事后激光参考"),
        "B2_F1_LRF": ("B2", 31.2894735000, 120.4728031000, "2026-09-08 09:22", "放火前木柴堆参考"),
        "B3_F1_LRF": ("B3", 31.2897849000, 120.4727221000, "2026-09-08 10:20", "事后激光参考"),
        "B3_F2_LRF": ("B3", 31.2896853000, 120.4727531500, "2026-09-08 10:19-10:20", "事后激光参考"),
        "B4_F1_LRF": ("B4", 31.2894814000, 120.4728076000, "2026-09-08 11:21-11:24", "另一场放火事件的激光参考"),
        "B4_F2_candidate_northwest": ("B4", 31.2897240930, 120.4727676677, "事后影像", "另一场放火事件候选"),
        "B4_F2_candidate_middle": ("B4", 31.2895964971, 120.4727907382, "事后影像", "另一场放火事件候选"),
        "B4_F2_candidate_south": ("B4", 31.2893640206, 120.4728224004, "事后影像", "另一场放火事件候选"),
    }

    rows = []

    def add(site_id, lrf_id, status, need, note):
        batch, name, video_time, vlat, vlon, vsource = sites[site_id]
        if lrf_id:
            lb, llat, llon, ltime, lsource = lrf[lrf_id]
            dist = distance_m(vlat, vlon, llat, llon)
        else:
            lb = llat = llon = ltime = lsource = ""
            dist = ""
        rows.append({
            "batch_id": batch,
            "fire_point_id": site_id,
            "fire_point_name": name,
            "video_time_local": video_time,
            "video_latitude": f"{vlat:.10f}",
            "video_longitude": f"{vlon:.10f}",
            "video_coordinate_source": vsource,
            "lrf_candidate_id": lrf_id or "",
            "lrf_batch_id": lb,
            "lrf_latitude": f"{llat:.10f}" if llat != "" else "",
            "lrf_longitude": f"{llon:.10f}" if llon != "" else "",
            "lrf_time_or_source": ltime,
            "lrf_coordinate_source": lsource,
            "distance_m": f"{dist:.2f}" if dist != "" else "",
            "match_status": status,
            "needs_user_confirmation": "是" if need else "否",
            "evidence_note": note,
        })

    add("B1_F1_video", "B1_F1_LRF", "高概率对应", False, "同一批次；多张 T/V 激光观测稳定落在同一处炭化火堆，距离约 0.91 m。")
    add("B2_F1_video", "B2_F1_LRF", "放火前参考，较可能对应", False, "同一批次；激光图明确是放火前木柴堆，距离约 4.04 m；不能作为燃烧期火焰中心。")
    add("B3_N_video", "B3_F1_LRF", "待确认：F1 是否对应北侧", True, "距离约 13.83 m；编号不能证明物理对应，请看 B3 确认图。")
    add("B3_N_video", "B3_F2_LRF", "备选：F2 是否对应北侧", True, "距离约 25.29 m；仅作备选，不自动采用。")
    add("B3_S_video", "B3_F2_LRF", "待确认：F2 是否对应南侧", True, "距离约 4.75 m；空间较近但仍需你确认同一火堆。")
    add("B3_S_video", "B3_F1_LRF", "备选：F1 是否对应南侧", True, "距离约 14.93 m；仅作备选，不自动采用。")
    add("B4_E_video", "B4_F1_LRF", "不对应当前视频事件", False, "激光时间为 11:21-11:24，坐标距当前 10:54 东侧火点约 78 m；已判为另一场放火事件。")
    add("B4_W_video", "B4_F1_LRF", "不对应当前视频事件", False, "激光时间为 11:21-11:24，坐标距当前 10:54 西侧火点约 79 m；已判为另一场放火事件。")
    for site_id in ("B4_E_video", "B4_W_video"):
        for candidate in ("B4_F2_candidate_northwest", "B4_F2_candidate_middle", "B4_F2_candidate_south"):
            add(site_id, candidate, "不对应当前视频事件", False, "事后炭化斑候选已确认属于另一场放火事件，不分配给当前 B4 东/西火点。")
    return rows


def main():
    rows = build_rows()
    fields = list(rows[0])
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "schema_version": "fire_point_correspondence_v2",
        "created_local": datetime.now().isoformat(timespec="seconds"),
        "video_fire_point_count": 6,
        "batch_fire_point_counts": {"B1": 1, "B2": 1, "B3": 2, "B4": 2},
        "confirmed_or_probable": ["B1_F1_video", "B2_F1_video"],
        "needs_user_confirmation": ["B3_N_video", "B3_S_video"],
        "no_lrf_for_current_event": ["B4_E_video", "B4_W_video"],
        "confirmation_image": str(OUT_IMAGE),
        "rows": rows,
        "limits": [
            "视频坐标是名义内参、姿态和假设地面高程下的影像近似坐标。",
            "LRF 坐标是激光命中参考，不等同于火焰中心。",
            "B4 当前视频的两个火点暂时没有同一事件的激光坐标。",
        ],
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    make_confirmation_image()
    print(json.dumps({"csv": str(OUT_CSV), "json": str(OUT_JSON), "image": str(OUT_IMAGE), "row_count": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
