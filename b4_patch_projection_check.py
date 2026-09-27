from pathlib import Path
import csv, math
import cv2, numpy as np

ROOT=Path(r'D:\课题\_dji_preview')
rows={r['name']:r for r in csv.DictReader(open(ROOT/'fixed_fire_observations.csv',encoding='utf-8-sig'))
      if r['batch_id']=='B4' and r['channel']=='ZoomCamera'}
LAT0,LON0=31.28948,120.47280
points={'P_0006_left':(31.289596497,120.472790738),
        'P_0007_top':(31.289364448,120.472813997),
        'P_0005_left':(31.289696974,120.472775865),
        'P_0005_right':(31.289300866,120.472838381)}
names=['DJI_20260908112209_0004_V.JPG','DJI_20260908112300_0005_V.JPG','DJI_20260908112321_0006_V.JPG',
       'DJI_20260908112332_0007_V.JPG','DJI_20260908112338_0008_V.JPG']
colors=[(0,0,255),(255,255,0),(0,255,0),(255,0,255)]
sheet=np.full((2*780,3*1008,3),255,np.uint8)
for i,name in enumerate(names):
    rec=rows[name]
    c=np.array([(float(rec['GpsLongitude'])-LON0)*95194,
                (float(rec['GpsLatitude'])-LAT0)*111186,
                float(rec['AbsoluteAltitude'])])
    y,p=map(math.radians,(float(rec['GimbalYawDegree']),float(rec['GimbalPitchDegree'])))
    d=np.array([math.cos(p)*math.sin(y),math.cos(p)*math.cos(y),math.sin(p)])
    r=np.array([math.cos(y),-math.sin(y),0]);u=np.cross(r,d)
    z=float(rec['AbsoluteAltitude'])-float(rec['RelativeAltitude'])
    v0=d; center=c+(z-c[2])/v0[2]*v0
    laser=np.array([(float(rec['LRFTargetLon'])-LON0)*95194,
                    (float(rec['LRFTargetLat'])-LAT0)*111186,z])
    correction=laser-center
    im=cv2.imdecode(np.fromfile(ROOT/name,dtype=np.uint8),cv2.IMREAD_COLOR)
    for (label,(lat,lon)),color in zip(points.items(),colors):
        point=np.array([(lon-LON0)*95194,(lat-LAT0)*111186,z])-correction
        v=point-c;fw=float(v@d)
        x=2016+2688*float(v@r)/fw;y=1512-2688*float(v@u)/fw
        if 0<x<4032 and 0<y<3024:
            cv2.circle(im,(round(x),round(y)),55,color,10)
            cv2.putText(im,label,(round(x)+20,round(y)-20),cv2.FONT_HERSHEY_SIMPLEX,2,color,5)
    small=cv2.resize(im,(1008,756))
    xx=i%3*1008;yy=i//3*780
    sheet[yy+24:yy+780,xx:xx+1008]=small
    cv2.putText(sheet,name,(xx+10,yy+20),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,0,0),2)
cv2.imencode('.jpg',sheet)[1].tofile(ROOT/'b4_patch_projection.jpg')
