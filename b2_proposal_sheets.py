import argparse, json
from pathlib import Path
from PIL import Image, ImageDraw

p=argparse.ArgumentParser(); p.add_argument('--images',type=Path,required=True); p.add_argument('--proposals',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
rows=json.loads(a.proposals.read_text(encoding='utf-8'))
cols,per_page,cell_w,cell_h=4,20,450,310
for page in range((len(rows)+per_page-1)//per_page):
 sheet=Image.new('RGB',(cols*cell_w,5*cell_h),'white');d=ImageDraw.Draw(sheet)
 for i,r in enumerate(rows[page*per_page:(page+1)*per_page]):
  im=Image.open(a.images/(r['observation_id']+'.jpg')).convert('RGB');w,h=im.size;im.thumbnail((cell_w-8,cell_h-55))
  x=(i%cols)*cell_w+(cell_w-im.width)//2;y=(i//cols)*cell_h+52;sheet.paste(im,(x,y))
  for j,pred in enumerate(sorted(r['predictions'],key=lambda x:-x['confidence'])[:3]):
   b=pred['box'];sx,sy=im.width/w,im.height/h
   d.rectangle((x+b[0]*sx,y+b[1]*sy,x+b[2]*sx,y+b[3]*sy),outline=['red','yellow','cyan'][j],width=3)
   d.text((x+b[0]*sx,y+b[1]*sy),f"{pred['confidence']:.2f}",fill='red')
  d.text(((i%cols)*cell_w+5,(i//cols)*cell_h+5),r['observation_id'],fill='black')
 sheet.save(a.out/f'proposal_{page+1:02d}.jpg',quality=92)
