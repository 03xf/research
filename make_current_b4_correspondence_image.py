from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"D:\课题\_dji_preview")
src = ROOT / "b4_fire_geo_projection_check.jpg"
out = ROOT / "B4_current_fire_correspondence_confirmation.jpg"
font_path = r"C:\Windows\Fonts\msyh.ttc"

data = np.fromfile(src, dtype=np.uint8)
image = cv2.imdecode(data, cv2.IMREAD_COLOR)
header_h = 150
canvas = np.full((image.shape[0] + header_h, image.shape[1], 3), 255, np.uint8)
canvas[header_h:] = image

pil = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
draw = ImageDraw.Draw(pil)
font_title = ImageFont.truetype(font_path, 36)
font_body = ImageFont.truetype(font_path, 25)
draw.text((24, 12), "当前 B4 10:54 视频火点对应关系", font=font_title, fill=(20, 20, 20))
draw.text((24, 60), "红圈：东侧靠道路火源，影像近似坐标 31.2887792678, 120.4727584031", font=font_body, fill=(190, 0, 0))
draw.text((24, 96), "青圈：西侧靠树木火源，影像近似坐标 31.2888262887, 120.4724890680", font=font_body, fill=(0, 130, 160))
result = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
cv2.imencode(".jpg", result, [cv2.IMWRITE_JPEG_QUALITY, 94])[1].tofile(out)
print(out)
