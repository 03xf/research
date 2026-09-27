#!/usr/bin/env python3
import argparse,json,statistics
from pathlib import Path
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--root",required=True,type=Path); ap.add_argument("--output",required=True,type=Path); args=ap.parse_args()
 rows=[]; total_frames=0; total_boxes=0; conf=[]
 for p in sorted(args.root.rglob("*.json")):
  if p.name=="summary.json": continue
  try:d=json.loads(p.read_text(encoding="utf-8"))
  except Exception: continue
  if "records" not in d: continue
  frames=len(d["records"]); boxes=sum(len(x.get("boxes",[])) for x in d["records"]); vals=[float(v) for x in d["records"] for v in x.get("confidence",[])]
  rows.append({"source":d.get("source"),"frames":frames,"detections":boxes,"detection_frame_rate":(sum(bool(x.get("boxes")) for x in d["records"])/frames if frames else 0),"mean_confidence":(statistics.mean(vals) if vals else None)})
  total_frames+=frames; total_boxes+=boxes; conf.extend(vals)
 result={"source_count":len(rows),"sampled_frames":total_frames,"detections":total_boxes,"detection_frame_rate":(sum(x["detection_frame_rate"]*x["frames"] for x in rows)/total_frames if total_frames else 0),"mean_confidence":(statistics.mean(conf) if conf else None),"sources":rows}
 args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); print(json.dumps({k:result[k] for k in ("source_count","sampled_frames","detections","detection_frame_rate","mean_confidence")},ensure_ascii=False))
if __name__=="__main__": main()
