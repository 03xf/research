from pathlib import Path
import cv2
import numpy as np

base=Path(r'D:\课题\_dji_preview')
def read(path):return cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_COLOR)
src=read(base/'confirm2_0008_V.jpg')
assert src is not None
sift=cv2.SIFT_create(nfeatures=8000)
def features(im):
    g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    return sift.detectAndCompute(g,None)
kp1,des1=features(src)
for name in ['DJI_20260908112209_0004_V.JPG','DJI_20260908112332_0007_V.JPG']:
    dst=read(base/name)
    scale=0.5
    dstsmall=cv2.resize(dst,None,fx=scale,fy=scale)
    kp2,des2=features(dstsmall)
    pairs=cv2.BFMatcher().knnMatch(des1,des2,k=2)
    good=[a for a,b in pairs if a.distance<0.90*b.distance]
    print('candidate_matches',name,len(good))
    if len(good)<4:continue
    p1=np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1,1,2)
    p2=np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1,1,2)
    H,mask=cv2.findHomography(p1,p2,cv2.RANSAC,5.0)
    print(name,'kp',len(kp1),len(kp2),'good',len(good),'inliers',int(mask.sum()) if mask is not None else 0)
    if H is None:continue
    H[0,:]/=scale; H[1,:]/=scale
    pts=np.array([[[155,805]],[[1610,365]],[[1060,610]]],dtype=np.float32)
    out=cv2.perspectiveTransform(pts,H).reshape(-1,2)
    print('points leftfire rightfire centerbrush',out)
    vis=cv2.resize(dst,(2016,1512))
    for label,(x,y),color in zip(['leftfire','rightfire','centerbrush'],out,[(0,0,255),(0,255,255),(255,0,0)]):
        xx,yy=round(x/2),round(y/2)
        cv2.circle(vis,(xx,yy),18,color,4)
        cv2.putText(vis,label,(xx+20,yy),cv2.FONT_HERSHEY_SIMPLEX,0.8,color,2)
    ok,data=cv2.imencode('.jpg',vis)
    if ok:data.tofile(base/(name+'.registered.jpg'))
