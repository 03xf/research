from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"D:\课题\_dji_preview")
src = ROOT / "b3_ref_projection.jpg"
out = ROOT / "B3_LRF_video_correspondence_confirmation.jpg"
font_path = r"C:\Windows\Fonts\msyh.ttc"

image = cv2.imdecode(np.fromfile(src, dtype=np.uint8), cv2.IMREAD_COLOR)
header_h = 205
canvas = np.full((image.shape[0] + header_h, image.shape[1], 3), 255, np.uint8)
canvas[header_h:] = image
pil = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
draw = ImageDraw.Draw(pil)
title = ImageFont.truetype(font_path, 35)
body = ImageFont.truetype(font_path, 24)
draw.text((22, 9), "B3 激光参考点与两处视频明火：请确认物理对应", font=title, fill=(20, 20, 20))
draw.text((22, 60), "红圈 B3 F1 LRF：31.2897849000, 120.4727221000；距北侧视频点约 13.83 m", font=body, fill=(190, 0, 0))
draw.text((22, 95), "青圈 B3 F2 LRF：31.2896853000, 120.4727531500；距南侧视频点约 4.75 m", font=body, fill=(0, 130, 160))
draw.text((22, 130), "图中红/青圈是 LRF 坐标投影；北侧、南侧明火都能直接从画面看到。", font=body, fill=(30, 30, 30))
draw.text((22, 165), "请分别判断：F1=北侧明火？F2=南侧明火？也可以回答“都不是”。", font=body, fill=(30, 30, 30))
result = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
cv2.imencode(".jpg", result, [cv2.IMWRITE_JPEG_QUALITY, 94])[1].tofile(out)
print(out)
