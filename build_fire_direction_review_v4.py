"""Build vector annotations over unchanged DJI evidence photos."""
from __future__ import annotations

import base64
from pathlib import Path

ROOT = Path(r"D:\课题\_dji_preview")


def svg(photo: str, crop_x: int, title: str, subtitle: str, labels: list[dict]) -> str:
    encoded = base64.b64encode((ROOT / photo).read_bytes()).decode("ascii")
    # The source contact sheet is 1920 x 1158. Each top-row panel is 640 x 386.
    image_x = 70 - crop_x * 1.5
    shapes = []
    for item in labels:
        cx = 70 + item["x"] * 1.5
        cy = 132 + item["y"] * 1.5
        tx, ty = item["text_x"], item["text_y"]
        color = item["color"]
        label = item["label"]
        shapes.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="34" fill="none" stroke="#fff" stroke-width="11"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="34" fill="none" stroke="{color}" stroke-width="7"/>'
            f'<line x1="{tx+8}" y1="{ty+22}" x2="{cx:.1f}" y2="{cy:.1f}" stroke="#fff" stroke-width="10"/>'
            f'<line x1="{tx+8}" y1="{ty+22}" x2="{cx:.1f}" y2="{cy:.1f}" stroke="{color}" stroke-width="6"/>'
            f'<rect x="{tx}" y="{ty}" width="{item["box_width"]}" height="51" rx="8" fill="{color}" stroke="#fff" stroke-width="3"/>'
            f'<text x="{tx+12}" y="{ty+37}" font-size="32" font-weight="700" fill="#fff">{label}</text>'
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="800" viewBox="0 0 1100 800">
<defs><clipPath id="photo"><rect x="70" y="132" width="960" height="579"/></clipPath></defs>
<rect width="1100" height="800" fill="#f6f7f9"/>
<text x="70" y="58" font-size="39" font-weight="700" fill="#111">{title}</text>
<text x="70" y="105" font-size="24" fill="#333">{subtitle}</text>
<image x="{image_x}" y="132" width="2880" height="1737" href="data:image/jpeg;base64,{encoded}" clip-path="url(#photo)"/>
<rect x="70" y="132" width="960" height="579" fill="none" stroke="#202733" stroke-width="3"/>
{''.join(shapes)}
<text x="70" y="752" font-size="23" fill="#333">圈在燃烧位置；原图中的 F1/F2 小圈是激光坐标投影，身份仍待确认。</text>
</svg>'''


b3 = svg(
    "b3_ref_projection.jpg", 0,
    "第三批：两处火点的南北位置", "无人机 D02 同一画面；按地理方位命名，与画面左右无关。",
    [
        {"x": 465, "y": 324, "text_x": 585, "text_y": 558, "box_width": 264, "label": "北侧火点 N", "color": "#b02222"},
        {"x": 123, "y": 114, "text_x": 277, "text_y": 202, "box_width": 264, "label": "南侧火点 S", "color": "#006f94"},
    ],
)
(ROOT / "B3_南北火点标注_v4.svg").write_text(b3, encoding="utf-8")

b4 = svg(
    "b4_fire_geo_projection_check.jpg", 640,
    "第四批：两处火点的东西位置", "无人机 D02 同一画面；东侧靠道路，西侧靠树木。",
    [
        {"x": 83, "y": 101, "text_x": 265, "text_y": 210, "box_width": 340, "label": "东侧 E（靠道路）", "color": "#b02222"},
        {"x": 557, "y": 274, "text_x": 607, "text_y": 579, "box_width": 340, "label": "西侧 W（靠树木）", "color": "#006f94"},
    ],
)
b4 = b4.replace("圈在燃烧位置；原图中的 F1/F2 小圈是激光坐标投影，身份仍待确认。", "圈在燃烧位置；两个方向以现场地理位置为准。")
(ROOT / "B4_东西火点标注_v4.svg").write_text(b4, encoding="utf-8")
print(ROOT / "B3_南北火点标注_v4.svg")
print(ROOT / "B4_东西火点标注_v4.svg")
