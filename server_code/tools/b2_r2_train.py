from ultralytics import YOLO
import argparse, json, hashlib, pathlib, os
p=argparse.ArgumentParser(); p.add_argument('--weights'); p.add_argument('--data'); p.add_argument('--out'); p.add_argument('--name'); p.add_argument('--imgsz',type=int,default=1280); p.add_argument('--device',default='1'); p.add_argument('--epochs',type=int,default=100); p.add_argument('--batch',type=int,default=4); p.add_argument('--lr0',type=float,default=0.00015)
a=p.parse_args(); os.environ['WANDB_MODE']='disabled'; os.environ['WANDB_DISABLED']='true'; os.environ['COMET_MODE']='DISABLED'
model=YOLO(a.weights)
model.train(data=a.data, epochs=a.epochs, imgsz=a.imgsz, batch=a.batch, freeze=10, lr0=a.lr0, device=a.device, workers=2, seed=0, deterministic=True, project=a.out, name=a.name, exist_ok=True, pretrained=True, verbose=True, plots=True, amp=True, close_mosaic=10)
