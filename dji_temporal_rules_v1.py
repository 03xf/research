"""Deterministic online temporal state for frozen V/T tracked detections."""
from collections import deque


class TemporalFilter:
    def __init__(self, sensor, hold_s=0.6):
        self.sensor = sensor
        self.hold_s = hold_s
        self.state = {}
        self.frame_index = -1

    def update(self, pts_s, detections):
        self.frame_index += 1
        desired = 'flame' if self.sensor == 'V' else 'hotspot'
        current = {}
        for d in detections:
            if d.get('class_name') != desired:
                continue
            tid = d.get('track_id')
            if tid:
                if tid in current:
                    raise ValueError('duplicate track in frame: '+tid)
                current[tid] = d
        output = []
        for tid, d in current.items():
            st = self.state.setdefault(tid, {'seen':deque(maxlen=3),'last_frame':-1,'last_pts':None,'last_detection':None,'stable':False})
            if st['last_pts'] is not None and pts_s-st['last_pts']>self.hold_s:
                st['seen'].clear()
                st['stable']=False
            st['seen'].append(True)
            st['last_frame']=self.frame_index; st['last_pts']=pts_s; st['last_detection']=d
            if sum(st['seen'])>=2: st['stable']=True
            output.append({'track_id':tid,'sensor':self.sensor,'class_name':desired,
                           'state':'stable_candidate' if st['stable'] else 'unconfirmed',
                           'bbox_xyxy_px':d['bbox_xyxy_px'],'confidence':d.get('confidence'),
                           'source_point_image_normalized':d.get('source_point_image_normalized'),
                           'predicted_hold':False})
        for tid, st in list(self.state.items()):
            if tid in current: continue
            st['seen'].append(False)
            age = pts_s-st['last_pts'] if st['last_pts'] is not None else float('inf')
            if st['stable'] and 0 <= age <= self.hold_s:
                d=st['last_detection']
                output.append({'track_id':tid,'sensor':self.sensor,'class_name':desired,
                               'state':'predicted_hold','bbox_xyxy_px':d['bbox_xyxy_px'],
                               'confidence':d.get('confidence'),
                               'source_point_image_normalized':d.get('source_point_image_normalized'),
                               'predicted_hold':True,'hold_age_s':age})
            if age>max(3.0,self.hold_s*3): del self.state[tid]
        return output
