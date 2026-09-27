from pathlib import Path
import csv, json, math
import numpy as np

ROOT=Path(r'D:\课题\_dji_preview')
obs={r['name']:r for r in csv.DictReader(open(ROOT/'fixed_fire_observations.csv',encoding='utf-8-sig'))
     if r['batch_id']=='B4' and r['channel']=='ZoomCamera'}

def basis(yaw,pitch):
    y,p=map(math.radians,(yaw,pitch))
    f=np.array([math.cos(p)*math.sin(y),math.cos(p)*math.cos(y),math.sin(p)])
    r=np.array([math.cos(y),-math.sin(y),0])
    return f,r,np.cross(r,f)

LAT0,LON0=31.28948,120.47280
def to_enu(lat,lon):return np.array([(lon-LON0)*95194,(lat-LAT0)*111186])
def to_geod(xy):return LAT0+xy[1]/111186,LON0+xy[0]/95194

def pixel_ground(rec,x,y):
    c=np.array([*to_enu(float(rec['GpsLatitude']),float(rec['GpsLongitude'])),float(rec['AbsoluteAltitude'])])
    f,r,u=basis(float(rec['GimbalYawDegree']),float(rec['GimbalPitchDegree']))
    fx=2688.0
    v=f+(x-2016)/fx*r-(y-1512)/fx*u
    z=float(rec['AbsoluteAltitude'])-float(rec['RelativeAltitude'])
    return (c+(z-c[2])/v[2]*v)[:2]

marks={
 'northwest_charred_patch':[
    ('DJI_20260908112209_0004_V.JPG',145,1990),
    ('DJI_20260908112300_0005_V.JPG',1190,870),
 ],
 'middle_gray_brush_patch':[
    ('DJI_20260908112321_0006_V.JPG',785,1560),
 ],
 'south_charred_patch':[
    ('DJI_20260908112332_0007_V.JPG',2060,280),
    ('DJI_20260908112338_0008_V.JPG',1930,165),
    ('DJI_20260908112321_0006_V.JPG',3390,1390),
 ],
}
out=[]
for name,measurements in marks.items():
    pts=[];views=[]
    print(name)
    for filename,x,y in measurements:
        rec=obs[filename]
        p=pixel_ground(rec,x,y)
        center=pixel_ground(rec,2016,1512)
        laser=to_enu(float(rec['LRFTargetLat']),float(rec['LRFTargetLon']))
        correction=laser-center
        adj=p+correction
        pts.append(adj)
        views.append({'image':filename,'x_px':x,'y_px':y,
                      'raw_latitude':to_geod(p)[0],'raw_longitude':to_geod(p)[1],
                      'laser_center_correction_m':float(np.linalg.norm(correction)),
                      'adjusted_latitude':to_geod(adj)[0],
                      'adjusted_longitude':to_geod(adj)[1]})
        print(filename,to_geod(adj),'correction',np.linalg.norm(correction))
    med=np.median(np.array(pts),axis=0)
    spread=max(np.linalg.norm(p-med) for p in pts)
    ref=to_enu(31.2894814,120.4728076)
    item={'point_id':name,'latitude_estimate':to_geod(med)[0],
          'longitude_estimate':to_geod(med)[1],
          'max_horizontal_view_deviation_m':float(spread),
          'distance_to_B4_F1_lrf_m':float(np.linalg.norm(med-ref)),
          'status':'approximate_ground_patch_not_lrf_measurement',
          'views':views}
    out.append(item)
    print('MEDIAN',to_geod(med),'SPREAD',spread,'TO F1',np.linalg.norm(med-ref))
(ROOT/'b4_postfire_patches.json').write_text(json.dumps({'patches':out},ensure_ascii=False,indent=2),encoding='utf-8')
