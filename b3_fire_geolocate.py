from pathlib import Path
import json
import os
import csv
import math
import numpy as np

ROOT = Path(os.environ.get('B3_AUDIT_ROOT', r'D:\课题\_dji_preview'))
rows = list(csv.DictReader(open(ROOT / 'b3_telemetry.csv', encoding='utf-8-sig')))
poses = {r['drone'].split('_')[0]: r for r in rows}
LAT0, LON0 = 31.2897, 120.4727

def basis(yaw, pitch):
    y, p = map(math.radians, (yaw, pitch))
    d = np.array([math.cos(p)*math.sin(y), math.cos(p)*math.cos(y), math.sin(p)])
    r = np.array([math.cos(y), -math.sin(y), 0.0])
    return d, r, np.cross(r, d)

def ray(drone, xy):
    a = poses[drone]
    c = np.array([(float(a['longitude'])-LON0)*95194,
                  (float(a['latitude'])-LAT0)*111186,
                  float(a['abs_alt'])])
    d, r, u = basis(float(a['gb_yaw']), float(a['gb_pitch']))
    fx = 1280 * float(a['focal_len']) / 24
    x, y = xy
    v = d + (x-960)/fx*r - (y-540)/fx*u
    return c, v/np.linalg.norm(v)

def ground(drone, xy, z=52.5):
    c, v = ray(drone, xy)
    return c + (z-c[2])/v[2]*v

def geod(p):
    return LAT0+p[1]/111186, LON0+p[0]/95194, p[2]

def intersect_many(rays):
    A=np.zeros((3,3)); b=np.zeros(3)
    for c,v in rays:
        M=np.eye(3)-np.outer(v,v)
        A+=M; b+=M@c
    p=np.linalg.solve(A,b)
    return p,[float(np.linalg.norm(np.cross(p-c,v))) for c,v in rays]

marks = {
    'B3_northwest_fire': {
        '无人机02': (1395, 895),
        '无人机04': (205, 855),
        '无人机09': (375, 420),
    },
    'B3_southeast_fire': {
        '无人机02': (370, 265),
        '无人机04': (1750, 780),
        '无人机09': (1575, 640),
    },
}
refs = {'B3_F1': (31.2897849, 120.4727221),
        'B3_F2': (31.2896853, 120.47275315)}
results=[]
for name, m in marks.items():
    print(name)
    pts=[]; rays=[]; views=[]
    for drone,xy in m.items():
        p=ground(drone,xy)
        pts.append(p)
        rays.append(ray(drone,xy))
        views.append({'drone':drone,'x_px':xy[0],'y_px':xy[1],
                      'ground_latitude':geod(p)[0], 'ground_longitude':geod(p)[1]})
        print(drone,xy,geod(p))
    med=np.median(np.array(pts),axis=0)
    spread=max(np.linalg.norm(p[:2]-med[:2]) for p in pts)
    tri,res=intersect_many(rays)
    print('MEDIAN',geod(med),'MAX_SPREAD',spread)
    print('TRIANGULATED',geod(tri),'RAY_RESIDUALS',res)
    result={'point_id':name,'latitude_estimate':geod(med)[0],
            'longitude_estimate':geod(med)[1], 'ground_altitude_assumed_m':52.5,
            'max_horizontal_view_deviation_m':spread,
            'triangulated_latitude':geod(tri)[0],
            'triangulated_longitude':geod(tri)[1],
            'triangulated_altitude_unverified_m':geod(tri)[2],
            'ray_residuals_m':res,'views':views,
            'method':'nominal_intrinsics_ground_plane_multiview',
            'status':'provisional_visual_geolocation_not_surveyed_truth'}
    for label,(lat,lon) in refs.items():
        q=np.array([(lon-LON0)*95194,(lat-LAT0)*111186])
        dist=float(np.linalg.norm(q-med[:2]))
        result['distance_to_'+label+'_lrf_m']=dist
        print('TO',label,dist)
    results.append(result)
out=Path(os.environ.get('B3_AUDIT_OUT',str(ROOT/'b3_fire_geolocation.json')))
out.write_text(json.dumps({'sites':results,'input_telemetry':str(ROOT/'b3_telemetry.csv')},ensure_ascii=False,indent=2),encoding='utf-8')
print('OUTPUT',out)
