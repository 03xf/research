from datetime import datetime
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
import csv, json, re, subprocess, sys

batch=sys.argv[1]
target=datetime.fromisoformat(sys.argv[2])
root=next(Path('/home/member/xmy/data/苏州放火_实验数据集').glob(batch+'_*'))/'01_正式视频'
out=Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/localization_v2')/'batch_video_audit'/batch
out.mkdir(parents=True,exist_ok=True)
videos=sorted(root.rglob('*_V.MP4'))
valid=[]
for p in videos:
    raw=subprocess.check_output(['ffprobe','-v','error','-show_entries','format_tags=creation_time:format=duration','-of','json',str(p)])
    meta=json.loads(raw)['format']
    start=datetime.fromisoformat(meta['tags']['creation_time'].replace('Z','+00:00'))
    offset=(target-start).total_seconds()
    if not 0<=offset<float(meta['duration']):continue
    frame=out/(p.parent.parent.name+'_'+p.parent.name+'_frame.jpg')
    subprocess.run(['ffmpeg','-y','-v','error','-ss',str(offset),'-i',str(p),'-frames:v','1',str(frame)],check=True)
    rawsub=subprocess.check_output(['ffmpeg','-v','error','-ss',str(offset),'-t','0.04','-i',str(p),'-map','0:s:0','-f','srt','-'],stderr=subprocess.DEVNULL).decode('utf-8','replace')
    first=rawsub.split('\n\n',1)[0]
    fields={}
    for key in ('latitude','longitude','rel_alt','abs_alt','gb_yaw','gb_pitch','focal_len','dzoom_ratio'):
        match=re.search(r'\b'+key+r':\s*([-+\d.]+)',first)
        if match:fields[key]=float(match.group(1))
    valid.append({'drone':p.parent.parent.name,'session':p.parent.name,'offset_s':offset,'file':str(p),'frame':str(frame),**fields})
cols=3; rows=(len(valid)+cols-1)//cols
canvas=Image.new('RGB',(640*cols,(360+26)*rows),'white');draw=ImageDraw.Draw(canvas)
for i,rec in enumerate(valid):
    with Image.open(rec['frame']) as im:
        im=ImageOps.contain(im.convert('RGB'),(640,360))
        x=i%cols*640+(640-im.width)//2;y=i//cols*386+26+(360-im.height)//2
        canvas.paste(im,(x,y))
    m=re.search(r'无人机(\d+)',rec['drone']);label='D'+(m.group(1) if m else '?')
    draw.text((i%cols*640+5,i//cols*386+5),f'{label} {rec["offset_s"]:.1f}s',fill='black')
canvas.save(out/'contact.jpg',quality=85)
with (out/'telemetry.csv').open('w',encoding='utf-8',newline='') as f:
    if valid:
        writer=csv.DictWriter(f,fieldnames=list(valid[0]));writer.writeheader();writer.writerows(valid)
print(batch,len(valid),out)
