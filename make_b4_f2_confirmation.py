from pathlib import Path
import csv, json
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"D:\课题\_dji_preview")
OUT = ROOT / "B4_F2_candidates_confirmation.jpg"
FONT = r"C:\Windows\Fonts\msyh.ttc"

with open(ROOT / "b4_postfire_patches.json", encoding="utf-8") as f:
    patches = json.load(f)["patches"]

candidate_meta = {
    "northwest_charred_patch": ("候选 1", "31.2897240930, 120.4727676677", "西北侧炭化斑"),
    "middle_gray_brush_patch": ("候选 2", "31.2895964971, 120.4727907382", "中部灰色区域"),
    "south_charred_patch": ("候选 3", "31.2893640206, 120.4728224004", "南侧炭化斑"),
}

def load_image(name):
    data = np.fromfile(ROOT / name, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)

def make_crop(image, x, y, size=900):
    h, w = image.shape[:2]
    half = size // 2
    x0, y0 = max(0, int(x) - half), max(0, int(y) - half)
    x1, y1 = min(w, int(x) + half), min(h, int(y) + half)
    crop = image[y0:y1, x0:x1].copy()
    canvas = np.full((size, size, 3), 255, np.uint8)
    yy = (size - crop.shape[0]) // 2
    xx = (size - crop.shape[1]) // 2
    canvas[yy:yy + crop.shape[0], xx:xx + crop.shape[1]] = crop
    cx, cy = xx + int(x) - x0, yy + int(y) - y0
    cv2.circle(canvas, (cx, cy), 28, (0, 0, 255), 6)
    cv2.drawMarker(canvas, (cx, cy), (0, 0, 255), cv2.MARKER_CROSS, 80, 5)
    return canvas

def put_cn(image, text, xy, size, fill=(20, 20, 20)):
    pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    draw.text(xy, text, font=ImageFont.truetype(FONT, size), fill=tuple(reversed(fill)))
    return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)

rows = []
for patch in patches:
    pid = patch["point_id"]
    title, coords, location = candidate_meta[pid]
    cards = []
    for view in patch["views"]:
        image = load_image(view["image"])
        crop = make_crop(image, view["x_px"], view["y_px"])
        cv2.putText(crop, view["image"], (18, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 0, 0), 2, cv2.LINE_AA)
        cards.append(crop)
    row = np.full((1040, 3 * 900, 3), 245, np.uint8)
    header = f"{title}  |  {location}  |  {coords}"
    row = put_cn(row, header, (18, 12), 34)
    row = put_cn(row, "用户已确认属于另一场放火；排除当前 B4 视频。红色十字为历史候选位置。", (18, 62), 25, (160, 0, 0))
    for i, card in enumerate(cards[:3]):
        row[120:1020, i * 900:(i + 1) * 900] = card
    rows.append(row)

sheet = np.vstack(rows)
cv2.imencode(".jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 94])[1].tofile(OUT)
print(OUT)
