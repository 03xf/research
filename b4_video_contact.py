from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
import json, subprocess

root=Path('/home/member/xmy/data/苏州放火_实验数据集/04_第四批_20260908_1053_多火点与余热点/01_正式视频')
out=Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1/b4_f2_audit')
out.mkdir(parents=True,exist_ok=True)
videos=sorted(root.rglob('*_V.MP4'))
target=datetime.fromisoformat('2026-09-08T02:54:10+00:00')
canvas=Image.new('RGB',(640*3,(360+26)*3),'white')
draw=ImageDraw.Draw(canvas)
for i,p in enumerate(videos):
    raw=subprocess.check_output(['ffprobe','-v','error','-show_entries','format_tags=creation_time','-of','json',str(p)])
    start=datetime.fromisoformat(json.loads(raw)['format']['tags']['creation_time'].replace('Z','+00:00'))
    offset=(target-start).total_seconds()
    if offset<0:continue
    frame=out/(p.parent.parent.name+'_'+p.parent.name+'_105410.jpg')
    subprocess.run(['ffmpeg','-y','-v','error','-ss',str(offset),'-i',str(p),'-frames:v','1',str(frame)],check=True)
    with Image.open(frame) as im:
        im=ImageOps.contain(im.convert('RGB'),(640,360))
        x=i%3*640+(640-im.width)//2
        y=i//3*386+26+(360-im.height)//2
        canvas.paste(im,(x,y))
    draw.text((i%3*640+5,i//3*386+5),f'{p.parent.parent.name} {offset:.1f}s',fill='black')
canvas.save(out/'b4_all_drones_105410.jpg',quality=85)
print(len(videos),out/'b4_all_drones_105410.jpg')
