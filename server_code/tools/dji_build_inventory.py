#!/usr/bin/env python3
"""Build a reproducible inventory for the Suzhou DJI batches."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Dict, List

VIDEO_SUFFIXES=("_T","_V","_S")
EXTS={".mp4",".MP4",".jpg",".JPG",".mrk",".MRK"}

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(8*1024*1024),b""): h.update(block)
    return h.hexdigest()

def batch_record(label: str, root: Path):
    files=[p for p in root.rglob("*") if p.is_file() and p.suffix in EXTS]
    groups: Dict[str, Dict[str,object]]={}
    for path in files:
        stem=path.stem; camera=""
        base=stem
        for suffix in VIDEO_SUFFIXES:
            if stem.endswith(suffix):
                base=stem[:-len(suffix)]; camera=suffix[1:]; break
        drone=next((x.name for x in path.parents if x.name.startswith("无人机")),"")
        session=path.parent.name
        key=str(path.parent / base)
        rec=groups.setdefault(key,{"batch_id":label,"session_id":session,"drone_id":drone,"video_group":base,"thermal_video":None,"visible_video":None,"side_video":None,"photo_files":[],"mrk_files":[],"files":[]})
        info={"path":str(path),"size":path.stat().st_size,"sha256":sha256(path)}
        rec["files"].append(info)
        if path.suffix.lower()==".mp4":
            rec[{"T":"thermal_video","V":"visible_video","S":"side_video"}.get(camera,"side_video")]=str(path)
        elif path.suffix.lower()==".jpg":
            rec["photo_files"].append(info)
        elif path.suffix.lower()==".mrk":
            rec["mrk_files"].append(info)
    return list(groups.values()), len(files)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--data-root",required=True,type=Path); ap.add_argument("--output",required=True,type=Path); args=ap.parse_args()
    specs=[("B1","01_第一批_20260907_1602_单火点"),("B2","02_第二批_20260908_0924_单火点"),("B3","03_第三批_20260908_1006_多火点"),("B4","04_第四批_20260908_1053_多火点与余热点")]
    groups=[]; counts={}
    for label,name in specs:
        data,count=batch_record(label,args.data_root/name); groups.extend(data); counts[label]=count
    result={"data_root":str(args.data_root),"batch_file_counts":counts,"video_group_count":len(groups),"groups":groups}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"batch_file_counts":counts,"video_group_count":len(groups)},ensure_ascii=False))

if __name__=="__main__": main()
