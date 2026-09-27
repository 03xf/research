#!/usr/bin/env python3
"""Associate detections from synchronized T/V videos by timestamp."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List

def load(path: Path) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--thermal",required=True,type=Path)
    ap.add_argument("--visible",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    ap.add_argument("--thermal-fps",type=float,default=30.0)
    ap.add_argument("--visible-fps",type=float,default=30.0)
    ap.add_argument("--offset-s",type=float,default=0.0)
    ap.add_argument("--tolerance-s",type=float,default=0.05)
    args=ap.parse_args()
    thermal=load(args.thermal); visible=load(args.visible)
    v_times=[i/args.visible_fps for i in range(len(visible))]
    observations=[]
    for ti,t in enumerate(thermal):
        t_time=ti/args.thermal_fps+args.offset_s
        if not v_times: continue
        vi=min(range(len(v_times)),key=lambda j:abs(v_times[j]-t_time))
        delta=abs(v_times[vi]-t_time)
        observations.append({"observation_id":f"{ti:06d}","timestamp_s":ti/args.thermal_fps,"thermal_frame":ti,"visible_frame":vi,"sync_delta_s":delta,"association_status":"paired" if delta<=args.tolerance_s else "unpaired","thermal_detection":{"boxes":t.get("boxes",[]),"confidence":t.get("confidence",[]),"class":t.get("class",[])}, "visible_detection":{"boxes":visible[vi].get("boxes",[]),"confidence":visible[vi].get("confidence",[]),"class":visible[vi].get("class",[])}})
    result={"source":{"thermal":str(args.thermal),"visible":str(args.visible)},"parameters":{"thermal_fps":args.thermal_fps,"visible_fps":args.visible_fps,"offset_s":args.offset_s,"tolerance_s":args.tolerance_s},"observations":observations}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    paired=sum(x["association_status"]=="paired" for x in observations)
    print(json.dumps({"observations":len(observations),"paired":paired,"unpaired":len(observations)-paired},ensure_ascii=False))

if __name__=="__main__": main()
