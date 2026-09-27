import json
from pathlib import Path
from PIL import Image, ImageDraw

root = Path('D:/课题/b2_reports')
rows = json.loads((root/'v4_manifest.json').read_text())['records']
rows = [r for r in rows if r['status'] != 'ignore']
out = root/'curated_v4_sheets'
out.mkdir(exist_ok=True)
for start in range(0, len(rows), 16):
    sheet = Image.new('RGB', (1600, 1200), 'white')
    d = ImageDraw.Draw(sheet)
    for j, r in enumerate(rows[start:start+16]):
        oid = r['observation_id']
        im = Image.open(root/'review_images'/(oid+'.jpg')).convert('RGB')
        w, h = im.size
        im.thumbnail((395, 260))
        x, y = (j % 4)*400 + 2, (j // 4)*300 + 35
        sheet.paste(im, (x, y))
        if r['status'] == 'positive':
            x1,y1,x2,y2 = r['box_xyxy_px']
            d.rectangle((x+x1*im.width/w, y+y1*im.height/h,
                         x+x2*im.width/w, y+y2*im.height/h), outline='lime', width=3)
        d.text(((j%4)*400+4,(j//4)*300+4), f'{oid} {r["split"]} {r["status"]}', fill='black')
    sheet.save(out/f'v4_{start//16+1:02d}.jpg')
