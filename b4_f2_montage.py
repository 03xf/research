from pathlib import Path
from PIL import Image, ImageOps, ImageDraw

root = Path('/home/member/xmy/data/苏州放火_实验数据集/04_第四批_20260908_1053_多火点与余热点/02_激光打点与定位验证')
paths = sorted(root.rglob('*.JPG'))
groups = {}
for p in paths:
    if 'DJI_202609081117_006' not in str(p):
        continue
    stem = p.stem
    idx = stem.split('_')[-2]
    channel = stem.split('_')[-1]
    if channel in {'T', 'V'}:
        groups.setdefault(idx, {})[channel] = p
groups = sorted(groups.items())
w, h = 480, 360
canvas = Image.new('RGB', (w*2, (h+28)*len(groups)), 'white')
d = ImageDraw.Draw(canvas)
for row, (idx, sensors) in enumerate(groups):
    for col, channel in enumerate(('V', 'T')):
        p = sensors.get(channel)
        if not p:
            continue
        with Image.open(p) as im:
            im = ImageOps.contain(im.convert('RGB'), (w, h))
            canvas.paste(im, (col*w+(w-im.width)//2, row*(h+28)+28+(h-im.height)//2))
        d.text((col*w+5,row*(h+28)+5), f'{idx} {channel}', fill='black')
out = Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1/b4_f2_audit')
out.mkdir(parents=True, exist_ok=True)
canvas.save(out/'b4_lrf_jpg_contact_sheet.jpg', quality=85)
print(out/'b4_lrf_jpg_contact_sheet.jpg', len(groups))
