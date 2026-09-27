"""Conservative per-frame source lookup for one audited B4 video scene.

This module never computes a new geographic coordinate. It links a visible
flame detection to an existing approximate scene point when the image position
agrees with human marks. A thermal match needs a recent visible match.
"""
import math


def _image_point(det, sensor, width, height):
    if sensor == 'V':
        return det.get('source_point_image_normalized')
    x1, y1, x2, y2 = det['bbox_xyxy_px']
    return [((x1+x2)/2)/width, ((y1+y2)/2)/height]


def associate(event, scene, recent_visible):
    """Mutate a frame event and return CSV-friendly position rows."""
    sensor = event['sensor']
    width, height = event['image_size_px']
    rows = []
    options = []
    stable_tracks = {t['track_id'] for t in event['tracks']
                     if t['state'] == 'stable_candidate' and t.get('track_id')}
    for index, det in enumerate(event['raw_detections']):
        point = _image_point(det, sensor, width, height)
        row = {
            'sensor': sensor, 'frame_seq': event['frame_seq'], 'pts_s': event['pts_s'],
            'detection_index': index, 'track_id': det.get('track_id'),
            'class_name': det['class_name'], 'confidence': det['confidence'],
            'image_x_normalized': point[0] if point else None,
            'image_y_normalized': point[1] if point else None,
            'image_point_semantics': 'flame_box_bottom_midpoint' if sensor == 'V' else 'hotspot_box_center_candidate',
            'point_id': None, 'point_name_zh': None, 'latitude': None, 'longitude': None,
            'coordinate_source': None, 'association_method': None,
            'association_status': 'unavailable', 'reason_zh': '画面不在已核对场景内' if scene is None else '未落入已核对火源区域',
        }
        rows.append(row)
        if scene is None or point is None:
            continue
        valid_pts = scene.get('valid_pts_s')
        if valid_pts and not (valid_pts[0] <= event['pts_s'] <= valid_pts[1]):
            row['reason_zh'] = '不在已核对的固定视角时间段'
            continue
        if scene.get('require_stable_track') and det.get('track_id') not in stable_tracks:
            row['reason_zh'] = '同一目标尚未连续检出'
            continue
        x1, y1, x2, y2 = det['bbox_xyxy_px']
        if (x2-x1)*(y2-y1)/(width*height) > (0.15 if sensor == 'V' else 0.12):
            row['reason_zh'] = '检测区域过大，不能确定具体火源'
            continue
        radius = scene['association_gate'][sensor+'_radius_normalized']
        for source in scene['sources']:
            anchor = source['anchors'][sensor]['point_normalized']
            distance = math.hypot(point[0]-anchor[0], point[1]-anchor[1])
            if distance <= radius:
                options.append((distance, -det['confidence'], index, source))
    taken_indices, taken_sources = set(), set()
    for distance, _, index, source in sorted(options, key=lambda x: (x[0], x[1])):
        source_id = source['point_id']
        if index in taken_indices or source_id in taken_sources:
            continue
        taken_indices.add(index)
        taken_sources.add(source_id)
        row = rows[index]
        row['point_id'] = source_id
        row['point_name_zh'] = source['name_zh']
        row['association_method'] = 'fixed_scene_anchor_to_lrf_lookup' if source['coordinate_status'] == 'reference_confirmed' else 'human_scene_anchor_lookup'
        row['anchor_distance_normalized'] = distance
        if sensor == 'T':
            visual_pts = recent_visible.get(source_id)
            if visual_pts is None or not (0 <= event['pts_s']-visual_pts <= scene['association_gate']['T_recent_V_seconds']):
                row['association_status'] = 'thermal_candidate_only'
                row['reason_zh'] = '仅有热像候选，缺少近期同区域明火'
                continue
        row['latitude'] = source['latitude']
        row['longitude'] = source['longitude']
        row['coordinate_source'] = source['coordinate_status']
        if source['coordinate_status'] == 'reference_confirmed':
            row['association_status'] = 'lrf_reference_lookup'
            row['reason_zh'] = '画面明火匹配固定火点区域；输出该火点已有的激光参考坐标'
        else:
            row['association_status'] = 'provisional_visual_lookup'
            row['reason_zh'] = '匹配已核对的画面火源区域；坐标是既有影像近似值'
        if sensor == 'V':
            recent_visible[source_id] = event['pts_s']
    for index, det in enumerate(event['raw_detections']):
        det['position'] = rows[index].copy()
    by_track = {r['track_id']: r for r in rows if r['track_id']}
    for track in event['tracks']:
        track['position'] = by_track.get(track.get('track_id'), {
            'association_status': 'unavailable', 'point_id': None,
            'latitude': None, 'longitude': None, 'reason_zh': '该帧没有可关联的检测框',
        })
        track['coordinate_status_zh'] = ('激光参考坐标' if track['position']['association_status'] == 'lrf_reference_lookup' else
                                          '影像近似坐标' if track['position']['association_status'] == 'provisional_visual_lookup'
                                          else '热像候选，位置未确定' if track['position']['association_status'] == 'thermal_candidate_only'
                                          else '位置未确定')
    event['positions'] = rows
    return rows
