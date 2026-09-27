"""One-to-one source-point diagnostics for frozen E2 tracking outputs.

Writes a new v2 result. The earlier exploratory report is retained verbatim.
"""
import argparse
import collections
import json
import math
from pathlib import Path


def matched(points, detections, width, height):
    edges = []
    for pi, point in enumerate(points):
        px, py = float(point[0]) * width, float(point[1]) * height
        for di, det in enumerate(detections):
            x1, y1, x2, y2 = det['bbox_xyxy_px']
            if x1 <= px <= x2 and y1 <= py <= y2:
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                edges.append((math.hypot((px-cx)/width, (py-cy)/height), pi, di))
    used_p, used_d, pairs = set(), set(), []
    for _, pi, di in sorted(edges):
        if pi not in used_p and di not in used_d:
            used_p.add(pi); used_d.add(di); pairs.append((pi, di))
    return pairs


def evaluate(root):
    truth = root/'source_truth_review_v1'
    queue = json.loads((truth/'queue.json').read_text(encoding='utf-8'))
    decisions = json.loads((truth/'decisions.json').read_text(encoding='utf-8'))['decisions']
    rows, totals, by_clip, by_fire, by_state = [], collections.Counter(), collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for task in queue['tasks']:
        choice = decisions.get(task['task_id'])
        if not choice:
            raise ValueError('missing decision '+task['task_id'])
        state, clip = choice['source_state'], task['clip_id']
        if choice['frame_status'] != 'usable':
            continue
        result = {'task_id':task['task_id'],'clip_id':clip,'source_state':state,'tv_relation':choice['tv_relation'],'sensors':{}}
        for sensor in ('V','T'):
            frame = Path(task['visible_frame' if sensor=='V' else 'thermal_frame'])
            track_path = root/'tracking_v2'/(clip+'_E2_s0')/sensor/'detections.json'
            tracks = json.loads(track_path.read_text(encoding='utf-8'))['rows']
            track_row = next((x for x in tracks if x['frame_file']==frame.name),None)
            if track_row is None:
                raise ValueError('missing tracking frame '+str(frame))
            import cv2
            im = cv2.imread(str(frame)); height,width=im.shape[:2]
            class_name = 'flame' if sensor=='V' else 'hotspot'
            ds = [x for x in track_row['detections'] if x['class_name']==class_name]
            all_points = choice[sensor]['points']
            # A V ground-contact mark in a residual-heat frame is not a visible flame target.
            eligible = state=='active_fire' if sensor=='V' else state in ('active_fire','residual_heat')
            ps = all_points if eligible else []
            pairs = matched(ps,ds,width,height)
            item = {'eligible_truth_points':len(ps),'ignored_context_points':len(all_points)-len(ps),
                    'matched_points':len(pairs),'missed_points':len(ps)-len(pairs),
                    'detections':len(ds),'unmatched_detections':len(ds)-len(pairs),
                    'matched_track_ids':[ds[di]['track_id'] for _,di in pairs]}
            result['sensors'][sensor]=item
            for prefix,counter in (('',totals),(clip+':',by_clip[clip]),(state+':',by_state[state])):
                counter[sensor+'_truth']+=len(ps); counter[sensor+'_matched']+=len(pairs); counter[sensor+'_missed']+=len(ps)-len(pairs)
                counter[sensor+'_detections']+=len(ds)
                if not ps and ds: counter[sensor+'_negative_frame_with_detection']+=1
            for pi,di in pairs:
                by_fire[clip+':'+ps[pi][2]][sensor+'_matched']+=1
            for pi,p in enumerate(ps):
                by_fire[clip+':'+p[2]][sensor+'_truth']+=1
        if choice['tv_relation']=='same_source':
            totals['same_source_pairs']+=1
            if result['sensors']['V']['matched_points'] and result['sensors']['T']['matched_points']:
                totals['same_source_both_detected_pairs']+=1
        rows.append(result)
    return {'schema_version':'dji_source_truth_eval_v2','method':'point-inside-box; greedy one-to-one normalized-center distance; active V flame only; T active and residual heat',
            'task_count':len(rows),'totals':dict(totals),'by_clip':{k:dict(v) for k,v in by_clip.items()},
            'by_state':{k:dict(v) for k,v in by_state.items()},'by_fire':{k:dict(v) for k,v in by_fire.items()},'rows':rows,
            'limits':'Same 50 reviewed pairs used for diagnostics. Point coverage is not detector AP, tracking ID accuracy, or geographic accuracy.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    out=a.root/'source_truth_review_v1'/'evaluation_v2.json'
    if out.exists():raise FileExistsError(out)
    result=evaluate(a.root);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'totals':result['totals']},ensure_ascii=False))
