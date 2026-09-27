from datetime import datetime
from pathlib import Path
import csv, json, re, subprocess

root=Path('/home/member/xmy/data/苏州放火_实验数据集/04_第四批_20260908_1053_多火点与余热点/01_正式视频')
out=Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1/b4_f2_audit')
target=datetime.fromisoformat('2026-09-08T02:54:10+00:00')
records=[]
for p in sorted(root.rglob('*_V.MP4')):
    raw=subprocess.check_output(['ffprobe','-v','error','-show_entries','format_tags=creation_time','-of','json',str(p)])
    start=datetime.fromisoformat(json.loads(raw)['format']['tags']['creation_time'].replace('Z','+00:00'))
    offset=(target-start).total_seconds()
    sub=subprocess.check_output(['ffmpeg','-v','error','-ss',str(offset),'-t','0.04','-i',str(p),'-map','0:3','-f','srt','-'],stderr=subprocess.DEVNULL).decode('utf-8','replace')
    first=sub.split('\n\n',1)[0]
    fields={}
    for key in ('latitude','longitude','rel_alt','abs_alt','gb_yaw','gb_pitch','focal_len','dzoom_ratio'):
        match=re.search(r'\b'+key+r':\s*([-+\d.]+)',first)
        if match:fields[key]=float(match.group(1))
    records.append({'drone':p.parent.parent.name,'session':p.parent.name,'offset_s':round(offset,3),'file':str(p),**fields})
path=out/'b4_105410_telemetry.csv'
with path.open('w',encoding='utf-8',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(records[0]))
    writer.writeheader();writer.writerows(records)
print(path)
