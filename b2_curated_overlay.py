import argparse
from pathlib import Path
from PIL import Image, ImageDraw
from build_b2_curated_v3 import POSITIVE, NEGATIVE

p=argparse.ArgumentParser();p.add_argument('--images',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
ids=list(POSITIVE)+list(NEGATIVE);a.out.mkdir(parents=True,exist_ok=True)
cols,per_page,cell_w,cell_h=4,20,450,310
for page in range((len(ids)+per_page-1)//per_page):
 sheet=Image.new('RGB',(cols*cell_w,5*cell_h),'white');d=ImageDraw.Draw(sheet)
 for i,oid in enumerate(ids[page*per_page:(page+1)*per_page]):
  im=Image.open(a.images/(oid+'.jpg')).convert('RGB');w,h=im.size;im.thumbnail((cell_w-8,cell_h-55))
  x=(i%cols)*cell_w+(cell_w-im.width)//2;y=(i//cols)*cell_h+52;sheet.paste(im,(x,y))
  if oid in POSITIVE:
   b=POSITIVE[oid];sx,sy=im.width/w,im.height/h
   d.rectangle((x+b[0]*sx,y+b[1]*sy,x+b[2]*sx,y+b[3]*sy),outline='lime',width=4)
  d.text(((i%cols)*cell_w+5,(i//cols)*cell_h+5),oid+(' POS' if oid in POSITIVE else ' NEG'),fill='black')
 sheet.save(a.out/f'curated_{page+1:02d}.jpg',quality=92)
