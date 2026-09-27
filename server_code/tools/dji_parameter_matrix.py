#!/usr/bin/env python3
import argparse,json
from pathlib import Path
FIELDS=["ImageSource","GpsStatus","GpsLatitude","GpsLongitude","AbsoluteAltitude","RelativeAltitude","GimbalRollDegree","GimbalYawDegree","GimbalPitchDegree","FlightRollDegree","FlightYawDegree","FlightPitchDegree","RtkFlag","RtkStdLon","RtkStdLat","RtkStdHgt","RtkDiffAge","DewarpFlag","DewarpData","DewarpDataK6","CalibratedFocalLength","CalibratedOpticalCenterX","CalibratedOpticalCenterY","UTCAtExposure","LRFTargetDistance","LRFTargetLon","LRFTargetLat","LRFTargetAlt","LRFTargetAbsAlt"]
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--audit-dir",required=True,type=Path); ap.add_argument("--output",required=True,type=Path); args=ap.parse_args()
 batches={}
 for p in sorted(args.audit_dir.glob("B*.json")):
  d=json.loads(p.read_text(encoding="utf-8")); total=d.get("counts",{}).get("photos",0); availability=d.get("images",{}).get("availability",{})
  batches[p.stem]={f:{"available_count":availability.get(f,0),"missing_count":max(total-availability.get(f,0),0),"source_type":"DJI XMP","usable_for_localization":f in {"GimbalRollDegree","GimbalYawDegree","GimbalPitchDegree","FlightRollDegree","FlightYawDegree","FlightPitchDegree","GpsLatitude","GpsLongitude","AbsoluteAltitude","RtkFlag","LRFTargetDistance","LRFTargetLat","LRFTargetLon","LRFTargetAlt"} and availability.get(f,0)>0,"notes":"missing values are unavailable"} for f in FIELDS}
 result={"batches":batches,"rules":{"missing":"unavailable","intrinsics_required_for_absolute_3d":True,"extrinsics_required_for_cross_camera_3d":True}}
 args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); print("wrote",args.output)
if __name__=="__main__": main()
