from pathlib import Path
import glob, runpy
import cv2, numpy as np

ns=runpy.run_path(r'D:\课题\b4_fire_ray_probe.py')
project=ns['project'];by_drone=ns['by_drone']
points={'road_fire':np.array([-4.678,-78.062,52.5]),'tree_fire':np.array([-30.318,-72.834,52.5])}
base=Path(r'D:\课题\_dji_preview')
canvas=np.full((3*386,3*640,3),255,np.uint8)
for i,drone in enumerate(by_drone):
    match=glob.glob(str(base/(drone+'*_105410.jpg')))
    if not match:continue
    im=cv2.imdecode(np.fromfile(match[0],dtype=np.uint8),cv2.IMREAD_COLOR)
    for label,p in points.items():
        x,y=project(drone,p)
        if -100<x<2020 and -100<y<1180:
            color=(0,0,255) if label=='road_fire' else (255,255,0)
            cv2.circle(im,(round(x),round(y)),35,color,6)
            cv2.putText(im,label,(round(x)+35,round(y)),cv2.FONT_HERSHEY_SIMPLEX,1.1,color,3)
    thumb=cv2.resize(im,(640,360))
    xx=i%3*640;yy=i//3*386
    canvas[yy+26:yy+386,xx:xx+640]=thumb
    cv2.putText(canvas,'D'+drone[3:5],(xx+8,yy+20),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,0),2)
ok,data=cv2.imencode('.jpg',canvas)
if ok:data.tofile(base/'b4_fire_geo_projection_check.jpg')
