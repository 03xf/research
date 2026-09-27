#!/usr/bin/env python3
"""Run resumable coarse T/V inference over DJI batch videos."""
from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path
from typing import Any
TOOLS=Path(__file__).resolve().parent
sys.path.insert(0,str(TOOLS.parent/"projects"/"ultralytics"))
from ultralytics import YOLO

def load_model(weights):
 m=YOLO(weights)
 for x in m.model.modules():
  if type(x).__name__=="GELU" and not hasattr(x,"approximate"): x.approximate="none"
 return m

def process(model, source: Path, out: Path, args):
 if out.exists() and out.stat().st_size>0: return "skip"
 records=[]
 try:
  stream=model.predict(source=str(source),imgsz=args.imgsz,device=args.device,conf=args.conf,vid_stride=args.vid_stride,stream=True,verbose=False)
  for index,result in enumerate(stream):
   boxes=result.boxes
   records.append({"sample_index":index,"source":str(source),"boxes":boxes.xyxy.detach().cpu().tolist() if boxes is not None else [],"confidence":boxes.conf.detach().cpu().tolist() if boxes is not None else [],"class":boxes.cls.detach().cpu().tolist() if boxes is not None else []})
  out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps({"source":str(source),"vid_stride":args.vid_stride,"records":records},ensure_ascii=False)+"\n",encoding="utf-8")
  return f"ok:{len(records)}"
 except Exception as exc:
  out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps({"source":str(source),"error":repr(exc)},ensure_ascii=False)+"\n",encoding="utf-8"); return "error"

def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--root",required=True,type=Path); ap.add_argument("--weights",required=True); ap.add_argument("--output",required=True,type=Path); ap.add_argument("--vid-stride",type=int,default=300); ap.add_argument("--imgsz",type=int,default=640); ap.add_argument("--conf",type=float,default=.1); ap.add_argument("--device",default="0"); ap.add_argument("--sensor",choices=("T","V","TV"),default="TV"); args=ap.parse_args()
 thermal=list(args.root.rglob("*_T.MP4"))+list(args.root.rglob("*_T.mp4")) if args.sensor in ("T","TV") else []
 visible=list(args.root.rglob("*_V.MP4"))+list(args.root.rglob("*_V.mp4")) if args.sensor in ("V","TV") else []
 sources=sorted(thermal+visible)
 model=load_model(args.weights); summary={"root":str(args.root),"sources":len(sources),"results":[],"started":time.time()}
 for i,source in enumerate(sources,1):
  rel=source.relative_to(args.root).with_suffix(".json"); out=args.output/rel
  status=process(model,source,out,args); summary["results"].append({"source":str(source),"status":status}); print(f"[{i}/{len(sources)}] {status} {source}",flush=True)
 summary["finished"]=time.time(); args.output.mkdir(parents=True,exist_ok=True); (args.output/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

if __name__=="__main__": main()
