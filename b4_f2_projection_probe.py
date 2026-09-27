import csv
import math
from pathlib import Path

rows=list(csv.DictReader(open(r'D:\课题\_dji_preview\fixed_fire_observations.csv',encoding='utf-8-sig')))
f1_lat=31.28948135
f1_lon=120.47280755
alt={1:(69.219,52.7),2:(69.410,52.5),3:(76.041,52.4),4:(85.899,52.5),5:(78.634,52.8),6:(73.658,52.1),7:(71.198,52.2),8:(69.198,52.3),9:(64.113,52.6)}

def enu(lat,lon,z):
    north=(lat-f1_lat)*111186.0
    east=(lon-f1_lon)*95194.0
    return (east,north,z)
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def basis(yaw,pitch):
    y=math.radians(yaw); p=math.radians(pitch)
    d=(math.cos(p)*math.sin(y),math.cos(p)*math.cos(y),math.sin(p))
    r=(math.cos(y),-math.sin(y),0)
    u=(r[1]*d[2]-r[2]*d[1],r[2]*d[0]-r[0]*d[2],r[0]*d[1]-r[1]*d[0])
    return d,r,u
def pixel(p,cam,yaw,pitch,f=2795):
    d,r,u=basis(yaw,pitch)
    v=sub(p,cam); a=dot(v,d)
    return (2016+f*dot(v,r)/a,1512-f*dot(v,u)/a,a)
def intersect(x,y,cam,yaw,pitch,z,f=2795):
    d,r,u=basis(yaw,pitch)
    ray=tuple(d[j]+(x-2016)/f*r[j]-(y-1512)/f*u[j] for j in range(3))
    t=(z-cam[2])/ray[2]
    return tuple(cam[j]+t*ray[j] for j in range(3))
cams={}
for i in range(1,10):
    ri=[x for x in rows if x['batch_id']=='B4' and x['observation_id'].endswith(f'_{i:04d}') and x['channel']=='InfraredCamera'][0]
    cam=enu(float(ri['GpsLatitude']),float(ri['GpsLongitude']),alt[i][0])
    tgt=enu(f1_lat,f1_lon,alt[i][1])
    cams[i]=(cam,float(ri['GimbalYawDegree']),float(ri['GimbalPitchDegree']))
    print(i, 'cam_xy',tuple(round(v,2) for v in cam[:2]), 'yaw',ri['GimbalYawDegree'],'pitch',ri['GimbalPitchDegree'], 'f1_pixel',tuple(round(v,1) for v in pixel(tgt,cam,float(ri['GimbalYawDegree']),float(ri['GimbalPitchDegree']))))
print('probe_f2')
c,y,p=cams[7]
f2=intersect(2100,200,c,y,p,52.2)
print('f2_enu',tuple(round(v,3) for v in f2),'lat',f1_lat+f2[1]/111186.0,'lon',f1_lon+f2[0]/95194.0)
for i,(c,y,p) in cams.items():
    print(i,tuple(round(v) for v in pixel(f2,c,y,p)[:2]))
print('probe_f2_from_4')
c,y,p=cams[4]
f2b=intersect(3800,1050,c,y,p,52.5)
print('f2_enu',tuple(round(v,3) for v in f2b),'lat',f1_lat+f2b[1]/111186.0,'lon',f1_lon+f2b[0]/95194.0)
for i,(c,y,p) in cams.items():
    print(i,tuple(round(v) for v in pixel(f2b,c,y,p)[:2]))
