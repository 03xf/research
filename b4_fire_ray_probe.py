from pathlib import Path
import csv, math
import numpy as np

f1_lat=31.28948135
f1_lon=120.47280755
rows=list(csv.DictReader(open(r'D:\课题\_dji_preview\b4_105410_telemetry.csv',encoding='utf-8-sig')))
by_drone={r['drone'].split('_')[0]:r for r in rows}

def enu(lat,lon,z):return np.array([(lon-f1_lon)*95194.0,(lat-f1_lat)*111186.0,z],dtype=float)
def geod(p):return f1_lat+p[1]/111186.0,f1_lon+p[0]/95194.0,p[2]
def basis(yaw,pitch):
    y=math.radians(yaw);p=math.radians(pitch)
    d=np.array([math.cos(p)*math.sin(y),math.cos(p)*math.cos(y),math.sin(p)])
    r=np.array([math.cos(y),-math.sin(y),0.0])
    u=np.cross(r,d)
    return d,r,u
def camera(drone):
    a=by_drone[drone]
    c=enu(float(a['latitude']),float(a['longitude']),float(a['abs_alt']))
    d,r,u=basis(float(a['gb_yaw']),float(a['gb_pitch']))
    fx=1280*float(a['focal_len'])/24.0
    return c,d,r,u,fx
def ray(drone,x,y):
    c,d,r,u,fx=camera(drone)
    v=d+(x-960)/fx*r-(y-540)/fx*u
    return c,v/np.linalg.norm(v)
def ground(drone,x,y,z=52.5):
    c,v=ray(drone,x,y)
    return c+(z-c[2])/v[2]*v
def project(drone,p):
    c,d,r,u,fx=camera(drone)
    v=p-c
    return np.array([960+fx*np.dot(v,r)/np.dot(v,d),540-fx*np.dot(v,u)/np.dot(v,d)])
def intersect(a,b):
    c1,v1=a;c2,v2=b
    A=np.array([v1,-v2]).T
    t=np.linalg.lstsq(A,c2-c1,rcond=None)[0]
    p1=c1+t[0]*v1;p2=c2+t[1]*v2
    return (p1+p2)/2,np.linalg.norm(p1-p2)
def intersect_many(rays):
    A=np.zeros((3,3));b=np.zeros(3)
    for c,v in rays:
        M=np.eye(3)-np.outer(v,v)
        A+=M;b+=M@c
    p=np.linalg.solve(A,b)
    return p,[float(np.linalg.norm(np.cross(p-c,v))) for c,v in rays]

marks={'near_road':{'无人机08':(1510,360),'无人机09':(1640,395),'无人机02':(250,225)},'near_tree':{'无人机08':(170,815),'无人机09':(420,855),'无人机02':(1670,745)}}
for target, m in marks.items():
    print('\n',target)
    for drone,(x,y) in m.items():
        p=ground(drone,x,y)
        print(drone,'ground',tuple(round(v,3) for v in p),'WGS84',geod(p))
    two=list(m.items())[:2]
    p,sep=intersect(ray(two[0][0],*two[0][1]),ray(two[1][0],*two[1][1]))
    print('triangulated',tuple(round(v,3) for v in p),'WGS84',geod(p),'ray_gap_m',round(sep,3))
    p3,res=intersect_many([ray(drone,*xy) for drone,xy in m.items()])
    print('triangulated_three',tuple(round(v,3) for v in p3),'WGS84',geod(p3),'ray_residuals_m',[round(v,2) for v in res])
    for drone in ('无人机02','无人机01','无人机05'):
        print('project',drone,tuple(round(v) for v in project(drone,p)))
    pts=np.array([ground(drone,*xy) for drone,xy in m.items()])
    med=np.median(pts,axis=0)
    print('ground_median',tuple(round(v,3) for v in med),'WGS84',geod(med))
    for drone in by_drone:
        xy=project(drone,med)
        if -100<xy[0]<2020 and -100<xy[1]<1180:
            print('project_median',drone,tuple(round(v) for v in xy))
