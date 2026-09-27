"""Train B2 V round 3 from frozen E2 with a true internal development video."""
import argparse, json, hashlib, os
from datetime import datetime, timezone
from pathlib import Path

os.environ['WANDB_MODE']='disabled'
os.environ['WANDB_DISABLED']='true'
os.environ['COMET_START_ONLINE']='0'
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION']='python'
from ultralytics import YOLO

p=argparse.ArgumentParser()
p.add_argument('--weights',type=Path,required=True);p.add_argument('--data',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);p.add_argument('--device',default='1')
p.add_argument('--name',default='B2R3_V_E2_curated_1280')
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
def sha(x):return hashlib.sha256(Path(x).read_bytes()).hexdigest()
config={'base_weights':str(a.weights),'base_sha256':sha(a.weights),'data':str(a.data),
        'data_sha256':sha(a.data),'epochs':100,'imgsz':1280,'batch':2,'freeze':10,
        'optimizer':'AdamW','lr0':0.00015,'seed':0,'device':a.device,
        'run_name':a.name,'created_utc':datetime.now(timezone.utc).isoformat()}
(a.out/'run_config.json').write_text(json.dumps(config,indent=2)+'\n')
m=YOLO(str(a.weights))
m.train(data=str(a.data),epochs=100,imgsz=1280,batch=2,freeze=10,optimizer='AdamW',
        lr0=0.00015,device=a.device,workers=0,seed=0,deterministic=True,
        project=str(a.out),name=a.name,exist_ok=True,
        pretrained=True,verbose=True,plots=True,amp=False,close_mosaic=10)
best=a.out/a.name/'weights'/'best.pt'
config['finished_utc']=datetime.now(timezone.utc).isoformat()
config['best_weights']=str(best);config['best_sha256']=sha(best)
(a.out/'run_config.json').write_text(json.dumps(config,indent=2)+'\n')
print(json.dumps({'best':str(best),'sha256':config['best_sha256']}))
