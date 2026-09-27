#!/usr/bin/env python3
import argparse,subprocess,time
from pathlib import Path
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--data-root",required=True); ap.add_argument("--weights",required=True); ap.add_argument("--output-root",required=True); ap.add_argument("--device",default="1"); ap.add_argument("--vid-stride",type=int,default=300); args=ap.parse_args()
 specs=[("B1","01_第一批_20260907_1602_单火点"),("B2","02_第二批_20260908_0924_单火点"),("B3","03_第三批_20260908_1006_多火点")]
 for label,name in specs:
  out=Path(args.output_root)/label; out.mkdir(parents=True,exist_ok=True)
  cmd=["/home/member/bin/python","/home/member/xmy/xmy/code/tools/dji_batch_inference.py","--root",str(Path(args.data_root)/name),"--weights",args.weights,"--output",str(out),"--vid-stride",str(args.vid_stride),"--device",args.device]
  log=(out.parent/(label+"_inference.log")).open("a")
  subprocess.run(cmd,stdout=log,stderr=log,check=False); log.close()
if __name__=="__main__": main()
