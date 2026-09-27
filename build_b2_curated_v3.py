#!/usr/bin/env python3
"""Build a traceable B2 V dataset after full-image visual review.

Boxes are approximate flame extents in source 1920x1080 images. The prior
model's proposals were used only as prompts and each selected frame was
checked visually. Unlisted frames remain ignored. Neither history nor the
sealed B2 replay video is modified.
"""
import argparse, hashlib, json, shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HOLDOUT = 'DJI_20260908092431_0003'
DEVELOPMENT = 'DJI_20260908092422_0002'

# one visible fire site per image; values are manually reviewed xyxy pixels
POSITIVE = {
 'obs_000283': [886, 614, 928, 686],
 'obs_000291': [860, 468, 1115, 706],
 'obs_000219': [936, 432, 1074, 670],
 'obs_000227': [895, 395, 1140, 690],
 'obs_000235': [895, 375, 1140, 700],
 'obs_000257': [1100, 490, 1210, 628],
 'obs_000273': [685, 0, 1245, 685],
 'obs_000281': [800, 0, 1225, 705],
 'obs_000297': [710, 220, 1195, 800],
 'obs_000217': [830, 420, 1080, 705],
 'obs_000294': [300, 0, 910, 1080],
 'obs_000205': [900, 420, 1150, 700],
 'obs_000253': [900, 355, 1150, 710],
 'obs_000269': [925, 325, 1185, 710],
 'obs_000207': [350, 855, 740, 1080],
 'obs_000215': [590, 700, 775, 990],
 'obs_000212': [695, 0, 1270, 1000],
 'obs_000276': [640, 345, 1255, 1040],
 'obs_000292': [785, 270, 1270, 890],
 'obs_000300': [890, 470, 1190, 815],
 'obs_000250': [815, 630, 1060, 980],
 # sealed holdout truth, evaluated only after training
 'obs_000296': [1035, 680, 1120, 835],
 'obs_000232': [735, 255, 1170, 980],
 'obs_000248': [695, 560, 1190, 1030],
}
NEGATIVE = {
 'obs_000259', 'obs_000267', 'obs_000233', 'obs_000241',
 'obs_000249', 'obs_000278', 'obs_000286', 'obs_000285',
 'obs_000293', 'obs_000279', 'obs_000295',
 'obs_000208', 'obs_000288',
}

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--ledger',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists(): raise SystemExit('output exists')
 ledger=json.loads(a.ledger.read_text(encoding='utf-8'))
 rows=[r for r in ledger['records'] if r['sensor']=='V']
 ids={r['observation_id'] for r in rows}
 if not set(POSITIVE).issubset(ids) or not NEGATIVE.issubset(ids): raise ValueError('unknown observation')
 if set(POSITIVE)&NEGATIVE: raise ValueError('conflicting review')
 if sum(r['video_group']==HOLDOUT for r in rows)!=5: raise ValueError('unexpected holdout size')
 records=[]
 for r in rows:
  oid=r['observation_id'];box=POSITIVE.get(oid)
  status='positive' if box else 'negative' if oid in NEGATIVE else 'ignore'
  split='holdout' if r['video_group']==HOLDOUT else 'development' if r['video_group']==DEVELOPMENT else 'train'
  if status=='ignore':
   records.append({'observation_id':oid,'split':split,'status':status,'old_status':r['review_status'],
                   'session_id':r['session_id'],'video_group':r['video_group'],
                   'source_image':r['source_image'],'source_sha256':r['source_image_sha256'],
                   'reason':'visual_review_uncertain_or_obscured'})
   continue
  src=Path(r['source_image']);dst=a.output/'V'/'images'/split/(oid+'.jpg');label=a.output/'V'/'labels'/split/(oid+'.txt')
  dst.parent.mkdir(parents=True,exist_ok=True);label.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
  if box:
   x1,y1,x2,y2=box
   if not(0<=x1<x2<=1920 and 0<=y1<y2<=1080):raise ValueError(oid)
   line=f'0 {(x1+x2)/3840:.10f} {(y1+y2)/2160:.10f} {(x2-x1)/1920:.10f} {(y2-y1)/1080:.10f}\n'
  else:line=''
  label.write_text(line,encoding='utf-8')
  records.append({'observation_id':oid,'split':split,'status':status,'box_xyxy_px':box,
                  'old_status':r['review_status'],'session_id':r['session_id'],'video_group':r['video_group'],
                  'source_image':str(src),'source_sha256':r['source_image_sha256'],
                  'reviewed_image_sha256':sha(dst),'label_sha256':sha(label),
                  'review_method':'full_image_visual_with_model_proposal_prompt'})
 root=a.output/'V';root.mkdir(parents=True,exist_ok=True)
 (root/'dataset.yaml').write_text(f'path: {root}\ntrain: images/train\nval: images/development\nnames: {{0: flame}}\n',encoding='utf-8')
 counts={s:dict(Counter(x['status'] for x in records if x['split']==s)) for s in ('train','development','holdout')}
 tr={x['video_group'] for x in records if x.get('split')=='train'}
 dev={x['video_group'] for x in records if x.get('split')=='development'}
 hold={x['video_group'] for x in records if x.get('split')=='holdout'}
 if tr&dev or tr&hold or dev&hold:raise ValueError('video leakage')
 manifest={'schema_version':'b2_curated_v3','created_utc':datetime.now(timezone.utc).isoformat(),
           'source_ledger':str(a.ledger),'source_ledger_sha256':sha(a.ledger),
           'holdout_video_group':HOLDOUT,'development_video_group':DEVELOPMENT,
           'counts':counts,'video_cross_contamination':False,'records':records,
           'note':'Held-out images are never referenced by YOLO training dataset.yaml; all old files preserved.'}
 (a.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(counts,ensure_ascii=False))
if __name__=='__main__':main()
