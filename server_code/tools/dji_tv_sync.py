#!/usr/bin/env python3
"""Summarize T/V video synchrony from a dji_b4f1_audit report."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict

def number(value: Any):
    try: return float(value)
    except (TypeError, ValueError): return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    args=ap.parse_args()
    report=json.loads(args.audit.read_text(encoding="utf-8"))
    by_source={x.get("source"): x for x in report.get("videos",{}).get("probes",[])}
    pairs=[]
    for pair in report.get("videos",{}).get("pairs",[]):
        if not pair.get("T") or not pair.get("V"): continue
        values={}
        for camera in ("T","V"):
            probe=by_source.get(pair[camera],{})
            fmt=probe.get("format",{})
            stream=next((s for s in probe.get("streams",[]) if s.get("codec_type")=="video"),{})
            values[camera]={"duration_s":number(fmt.get("duration") or stream.get("duration")),"start_s":number(fmt.get("start_time") or stream.get("start_time")),"frames":number(stream.get("nb_frames")),"fps":stream.get("avg_frame_rate") or stream.get("r_frame_rate"),"size":[stream.get("width"),stream.get("height")]}
        pairs.append({"pair_key":pair["pair_key"],"T":pair["T"],"V":pair["V"],"T_info":values["T"],"V_info":values["V"],"duration_delta_s":abs((values["T"]["duration_s"] or 0)-(values["V"]["duration_s"] or 0)),"start_delta_s":abs((values["T"]["start_s"] or 0)-(values["V"]["start_s"] or 0)),"frame_delta":abs((values["T"]["frames"] or 0)-(values["V"]["frames"] or 0))})
    result={"pairs":pairs,"summary":{"pair_count":len(pairs),"max_duration_delta_s":max((x["duration_delta_s"] for x in pairs),default=None),"max_start_delta_s":max((x["start_delta_s"] for x in pairs),default=None),"max_frame_delta":max((x["frame_delta"] for x in pairs),default=None)}}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result["summary"],indent=2,ensure_ascii=False))

if __name__=="__main__": main()
