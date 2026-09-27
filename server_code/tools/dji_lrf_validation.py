#!/usr/bin/env python3
"""Validate DJI LRF target coordinates against a fixed reference point."""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
from statistics import mean

def distance_m(lat1, lon1, lat2, lon2):
    r=6371000.0
    p1,p2=math.radians(lat1),math.radians(lat2)
    dp=math.radians(lat2-lat1); dl=math.radians(lon2-lon1)
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(math.sqrt(a))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",required=True,type=Path)
    ap.add_argument("--lat",type=float,default=31.28948135)
    ap.add_argument("--lon",type=float,default=120.47280755)
    ap.add_argument("--alt",type=float,default=1.221)
    ap.add_argument("--output",required=True,type=Path)
    args=ap.parse_args()
    report=json.loads(args.audit.read_text(encoding="utf-8")); rows=[]
    for item in report.get("images",{}).get("files",[]):
        try:
            lat=float(item["LRFTargetLat"]); lon=float(item["LRFTargetLon"]); alt=float(item["LRFTargetAlt"])
        except (TypeError,ValueError,KeyError): continue
        horizontal=distance_m(args.lat,args.lon,lat,lon)
        rows.append({"source":item.get("source"),"target_lat":lat,"target_lon":lon,"target_alt":alt,"horizontal_error_m":horizontal,"vertical_error_m":alt-args.alt,"distance_error_m":math.sqrt(horizontal**2+(alt-args.alt)**2)})
    summary={"count":len(rows),"mean_horizontal_error_m":mean([x["horizontal_error_m"] for x in rows]) if rows else None,"max_horizontal_error_m":max([x["horizontal_error_m"] for x in rows],default=None),"mean_vertical_error_m":mean([x["vertical_error_m"] for x in rows]) if rows else None,"rmse_3d_m":math.sqrt(mean([x["distance_error_m"]**2 for x in rows])) if rows else None,"reference":{"lat":args.lat,"lon":args.lon,"alt":args.alt}}
    result={"summary":summary,"observations":rows}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); print(json.dumps(summary,indent=2,ensure_ascii=False))

if __name__=="__main__": main()
