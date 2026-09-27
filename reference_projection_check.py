from pathlib import Path
import csv, math, re
import cv2,numpy as np

base=Path(r'D:\课题\_dji_preview')
refs={
 'b1':{'B1_F1':(31.28913770,120.47274985)},
 'b2':{'B2_F1':(31.28947350,120.47280310)},
 'b3':{'B3_F1':(31.28978490,120.47272210),'B3_F2':(31.28968530,120.47275315)},
}
colors=[(0,0,255),(255,255,0)]
for batch,points in refs.items():
    rows=list(csv.DictReader(open(base/(batch+'_telemetry.csv'),encoding='utf-8-sig')))
    cols=3;rr=(len(rows)+2)//3
    sheet=np.full((rr*386,cols*640,3),255,np.uint8)
    for i,row in enumerate(rows):
        name=Path(row['frame']).name
        local=base/name
        im=cv2.imdecode(np.fromfile(local,dtype=np.uint8),cv2.IMREAD_COLOR)
        if im is None:continue
        lat=float(row['latitude']);lon=float(row['longitude']);z=float(row['abs_alt'])
        yaw=math.radians(float(row['gb_yaw']));pitch=math.radians(float(row['gb_pitch']))
        d=np.array([math.cos(pitch)*math.sin(yaw),math.cos(pitch)*math.cos(yaw),math.sin(pitch)])
        r=np.array([math.cos(yaw),-math.sin(yaw),0.0]);u=np.cross(r,d)
        fx=1280*float(row['focal_len'])/24
        for j,(label,(plat,plon)) in enumerate(points.items()):
            v=np.array([(plon-lon)*95194,(plat-lat)*111186,52.5-z])
            forward=float(v@d)
            if forward<=0:continue
            x=960+fx*float(v@r)/forward;y=540-fx*float(v@u)/forward
            if -100<x<2020 and -100<y<1180:
                cv2.circle(im,(round(x),round(y)),35,colors[j],6)
                cv2.putText(im,label,(round(x)+20,round(y)),cv2.FONT_HERSHEY_SIMPLEX,1.1,colors[j],3)
        thumb=cv2.resize(im,(640,360))
        xx=i%3*640;yy=i//3*386
        sheet[yy+26:yy+386,xx:xx+640]=thumb
        drone=re.search(r'无人机(\d+)',row['drone']).group(1)
        cv2.putText(sheet,'D'+drone,(xx+5,yy+20),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,0),2)
    ok,data=cv2.imencode('.jpg',sheet)
    if ok:data.tofile(base/(batch+'_ref_projection.jpg'))
