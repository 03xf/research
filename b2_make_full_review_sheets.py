#!/usr/bin/env python3
"""Render every B2 ledger image with its original target boxes and review state."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument('--ledger', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--sensor', choices=['V', 'T'], required=True)
a = ap.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
rows = [r for r in json.loads(a.ledger.read_text(encoding='utf-8'))['records'] if r['sensor'] == a.sensor]
rows.sort(key=lambda x: (x['split'], x['video_group'], x['timestamp_s']))
cols, per_page, cell_w, cell_h = 4, 20, 450, 310
for page in range((len(rows) + per_page - 1)//per_page):
    subset = rows[page*per_page:(page+1)*per_page]
    sheet = Image.new('RGB', (cols*cell_w, 5*cell_h), 'white')
    dr = ImageDraw.Draw(sheet)
    for i, row in enumerate(subset):
        image = Image.open(row['source_image']).convert('RGB')
        iw, ih = image.size
        image.thumbnail((cell_w-8, cell_h-55))
        x0 = (i % cols)*cell_w + (cell_w-image.width)//2
        y0 = (i // cols)*cell_h + 52
        sheet.paste(image, (x0, y0))
        d = ImageDraw.Draw(sheet)
        field = 'visible_labels' if a.sensor == 'V' else 'thermal_labels'
        for label in row['original_annotation'].get(field, []):
            if label.get('class') != ('flame' if a.sensor == 'V' else 'hotspot'):
                continue
            box = label['bbox_xyxy']
            sx, sy = image.width/iw, image.height/ih
            d.rectangle((x0+box[0]*sx, y0+box[1]*sy, x0+box[2]*sx, y0+box[3]*sy), outline='lime', width=3)
        caption = f"{row['observation_id']} {row['split']} {row['video_group'][-5:]} t={row['timestamp_s']}\n{row['review_status']} {row['phase_hint']}"
        d.text(((i % cols)*cell_w+5, (i // cols)*cell_h+5), caption, fill='black')
    sheet.save(a.out/f'{a.sensor}_{page+1:02d}.jpg', quality=92)
print(len(rows), 'images', (len(rows)+per_page-1)//per_page, 'sheets')
