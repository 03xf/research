from pathlib import Path
import csv, json, math
import os

ROOT=Path(os.environ.get('COORD_ROOT', r'D:\课题\_dji_preview'))
OUT=ROOT/'fire_coordinate_inventory_v3.csv'

rows=[]
def add(point_id,batch,lat,lon,source,status,events='',spread='',notes=''):
    rows.append({'point_id':point_id,'batch_id':batch,'latitude':f'{lat:.10f}',
                 'longitude':f'{lon:.10f}','source':source,'status':status,
                 'independent_events':events,'spread_m':spread,'notes':notes})

add('B1_F1_LRF','B1',31.2891377000,120.4727498500,'XMP_LRFTarget_event_median','reference_confirmed','4','0.34','事后激光参考；不等同于燃烧中火焰中心')
add('B2_F1_LRF','B2',31.2894735000,120.4728031000,'XMP_LRFTarget_event_median','prefire_reference','1','0','放火前木柴堆；不作为燃烧期火焰真值')
add('B3_F1_LRF','B3',31.2897849000,120.4727221000,'XMP_LRFTarget_event_median','reference_confirmed','1','0','事后激光参考')
add('B3_F2_LRF','B3',31.2896853000,120.4727531500,'XMP_LRFTarget_event_median','reference_confirmed','2','0.47','事后激光参考；与南侧视频火堆约4.75 m')
add('B4_F1_LRF','B4',31.2894814000,120.4728076000,'XMP_LRFTarget_event_median','reference_confirmed','9','0.44','事后主炭化区激光参考')
add('B3_video_north_fire','B3',31.2899036006,120.4726785084,'nominal_camera_multiview_ground_plane','provisional_visual','3','2.26','2026-09-08 10:07 两处明火中的北侧；非LRF独立真值')
add('B3_video_south_fire','B3',31.2896677352,120.4727986134,'nominal_camera_multiview_ground_plane','provisional_visual','3','2.71','2026-09-08 10:07 两处明火中的南侧；与B3_F2约4.75 m')
add('B4_video_east_near_road','B4',31.2887792678,120.4727584031,'nominal_camera_multiview_ground_plane','provisional_visual','3','3.04','2026-09-08 10:54 两处正式视频明火之一；与B4_F1约78.21 m')
add('B4_video_west_near_tree','B4',31.2888262887,120.4724890680,'nominal_camera_multiview_ground_plane','provisional_visual','3','3.06','2026-09-08 10:54 两处正式视频明火之一；与B4_F1约78.90 m')
add('B4_F2_candidate_northwest_charred','B4',31.2897240930,120.4727676677,'postfire_image_ray_estimate','candidate_only','2','3.11','事后影像炭化斑候选；历史B4_F2无法唯一映射')
add('B4_F2_candidate_middle_gray','B4',31.2895964971,120.4727907382,'postfire_image_ray_estimate','candidate_only','1','0','单视角候选；不得作为定位真值')
add('B4_F2_candidate_south_charred','B4',31.2893640206,120.4728224004,'postfire_image_ray_estimate','candidate_only','3','0.80','事后影像另一炭化斑候选；历史B4_F2无法唯一映射')

with OUT.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
summary={'version':'fire_coordinate_inventory_v3','coordinate_count':len(rows),
         'lrf_reference_count':5,'video_visual_count':4,'postfire_candidates_count':3,
         'missing_coordinate_fields':0,
         'important_limit':'provisional_visual rows use nominal intrinsics and assumed ground plane; no Matrice 4T calibration available',
         'b4_f2':'historical label has no unique LRF event; three image candidates are retained separately'}
(ROOT/'fire_coordinate_inventory_v3.json').write_text(json.dumps({'summary':summary,'rows':rows},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
