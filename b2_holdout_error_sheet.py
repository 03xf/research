import json
from pathlib import Path
from PIL import Image, ImageDraw

root = Path('D:/课题/b2_reports')
data = {name: {r['image']: r for r in json.loads((root/f'{name}_holdout_v4.json').read_text())['rows']}
        for name in ('R2','R4')}
ids = ('obs_000232','obs_000248','obs_000296')
sheet = Image.new('RGB', (1800, 1050), 'white')
d = ImageDraw.Draw(sheet)
for row_index, oid in enumerate(ids):
    for col_index, model in enumerate(('R2','R4')):
        im = Image.open(root/'review_images'/(oid+'.jpg')).convert('RGB')
        im.thumbnail((850,300))
        x, y = 25+900*col_index, 40+350*row_index
        sheet.paste(im,(x,y))
        r = data[model][oid]
        for box in r['truth']:
            x1,y1,x2,y2 = box
            d.rectangle((x+x1*im.width,y+y1*im.height,x+x2*im.width,y+y2*im.height),outline='lime',width=4)
        for pred in r['predictions']:
            if pred['confidence'] < 0.37:
                continue
            x1,y1,x2,y2 = pred['box']
            d.rectangle((x+x1*im.width,y+y1*im.height,x+x2*im.width,y+y2*im.height),outline='red',width=4)
        peak = max((p['confidence'] for p in r['predictions']),default=0)
        d.text((x,y-25),f'{oid} {model}  max_conf={peak:.3f}  green=reference  red=detected>=0.37',fill='black')
sheet.save(root/'B2_R2_R4_holdout_errors.jpg',quality=90)
