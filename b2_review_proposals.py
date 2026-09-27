"""Generate model-assisted V box proposals for visual review only."""
import argparse, json
from pathlib import Path
from ultralytics import YOLO

ap=argparse.ArgumentParser()
ap.add_argument('--ledger',required=True); ap.add_argument('--weights',required=True); ap.add_argument('--output',required=True)
ap.add_argument('--device',default='1')
a=ap.parse_args()
rows=[r for r in json.load(open(a.ledger))['records'] if r['sensor']=='V' and r['split']=='train']
m=YOLO(a.weights); out=[]
for r in rows:
 result=m.predict(r['source_image'],imgsz=1280,conf=0.05,iou=0.7,device=a.device,verbose=False,max_det=20)[0]
 preds=[{'box':list(map(float,b)),'confidence':float(c)} for b,c in zip(result.boxes.xyxy.cpu().tolist(),result.boxes.conf.cpu().tolist())]
 out.append({'observation_id':r['observation_id'],'image':r['source_image'],'predictions':preds})
Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(len(out))
