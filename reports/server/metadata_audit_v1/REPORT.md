# DJI 输入能力审计 v1

生成时间：2026-09-25T06:36:54.962322+00:00

## 已从现有文件解析到的内容

- 视频遥测字段：abs_alt, drone, dzoom_ratio, file, focal_len, frame, gb_pitch, gb_yaw, latitude, longitude, offset_s, rel_alt, session
- LRF 观测：52 条，候选配对 25 组，未配对 2 条。
- 视频 seek 抽查：33/33 对成功读取，报告中位时间差 0.009966666666667151 s，最大时间差 0.029566666666651146 s。
- 可用于降级实时输出：帧号、视频偏移、飞机位置、高度、云台 yaw/pitch、名义焦距和变焦比例。

## 仍然缺失

- V_focal_length
- V_principal_point
- V_distortion
- T_focal_length
- T_principal_point
- T_distortion
- camera_to_gimbal_extrinsics
- gimbal_to_body_extrinsics
- T_V_extrinsics
- timestamp_alignment

这些缺项阻止绝对视觉 WGS84 定位，但不阻止先做图像平面检测、跟踪、时间配对和候选结果展示。

## 少量火源真值标注任务

建议抽取 8 个 30 秒片段、5 Hz 成对 V/T 图像。每对只标：地面火源接触点或源区域、片段内稳定 fire_id、V/T 是否同源，以及热像高温非燃烧背景。可选 unknown；不要求重新复核 214 张图，也不要求标烟雾框。

## 实时输出建议

服务器两张 RTX 3090 分别处理 V/T 流，网页显示双流、检测框、track_id、候选点、坐标来源、FPS、延迟和丢帧数，同时保存 JSONL、CSV 和带框视频。

## 结论

Current files support image-plane tracking, telemetry-aware candidate projection and temporal V/T pairing. Absolute WGS84 visual localization remains unavailable until per-camera calibration, extrinsics and verified time alignment are present.
