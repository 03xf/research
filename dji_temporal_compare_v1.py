"""Apply frozen temporal rules to existing E2 tracks and compare with 50 source-truth pairs."""
import argparse
import collections
import json
from pathlib import Path

from dji_temporal_rules_v1 import TemporalFilter
from dji_source_truth_eval_v2 import matched


def main(root, output=None):
    out=output or root/'source_truth_review_v1'/'temporal_comparison_v1.json'
    if out.exists():raise FileExistsError(out)
    truth=root/'source_truth_review_v1'
    tasks=json.loads((truth/'queue.json').read_text(encoding='utf-8'))['tasks']
    decisions=json.loads((truth/'decisions.json').read_text(encoding='utf-8'))['decisions']
    cache={}
    for clip in sorted({x['clip_id'] for x in tasks}):
        cache[clip]={}
        for sensor in ('V','T'):
            p=root/'tracking_v2'/(clip+'_E2_s0')/sensor/'detections.json'
            frames=json.loads(p.read_text(encoding='utf-8'))['rows']
            f=TemporalFilter(sensor)
            cache[clip][sensor]={row['frame_file']:{'raw':row['detections'],
                'processed':f.update(row['decoded_pts_s'],row['detections'])} for row in frames}
    totals={mode:collections.Counter() for mode in ('raw','stable','stable_plus_hold')}
    by_state={mode:collections.defaultdict(collections.Counter) for mode in totals}
    by_clip={mode:collections.defaultdict(collections.Counter) for mode in totals}
    rows=[]
    import cv2
    for task in tasks:
        choice=decisions[task['task_id']];clip=task['clip_id'];state=choice['source_state']
        record={'task_id':task['task_id'],'clip_id':clip,'source_state':state,'sensors':{}}
        for sensor,key in (('V','visible_frame'),('T','thermal_frame')):
            path=Path(task[key]);im=cv2.imread(str(path));h,w=im.shape[:2]
            data=cache[clip][sensor][path.name]
            eligible=state=='active_fire' if sensor=='V' else state in ('active_fire','residual_heat')
            points=choice[sensor]['points'] if eligible else []
            record['sensors'][sensor]={}
            for mode in totals:
                if mode=='raw':
                    detections=[d for d in data['raw'] if d['class_name']==('flame' if sensor=='V' else 'hotspot')]
                elif mode=='stable':
                    detections=[d for d in data['processed'] if d['state']=='stable_candidate']
                else:
                    detections=[d for d in data['processed'] if d['state'] in ('stable_candidate','predicted_hold')]
                pairs=matched(points,detections,w,h)
                entry={'truth':len(points),'matched':len(pairs),'detections':len(detections),
                       'negative_frame_with_detection':int(not points and bool(detections)),
                       'held_matches':sum(detections[di].get('predicted_hold',False) for _,di in pairs)}
                record['sensors'][sensor][mode]=entry
                for counter in (totals[mode],by_state[mode][state],by_clip[mode][clip]):
                    for field,value in entry.items():counter[sensor+'_'+field]+=value
        rows.append(record)
    result={'schema_version':'dji_temporal_comparison_v1','rules':{'stable':'at least two detections in last 3 processed frames, same track ID',
            'hold':'last stable bbox displayed for at most 0.6s; explicitly predicted, never counted as new detection'},
            'totals':{k:dict(v) for k,v in totals.items()},
            'by_state':{k:{s:dict(c) for s,c in v.items()} for k,v in by_state.items()},
            'by_clip':{k:{s:dict(c) for s,c in v.items()} for k,v in by_clip.items()},
            'rows':rows,'limits':'Same reviewed 50 pairs; exploratory in-sample diagnostics only.'}
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'totals':result['totals']},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path)
    args=p.parse_args();main(args.root,args.output)
