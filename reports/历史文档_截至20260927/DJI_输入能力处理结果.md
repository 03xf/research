# DJI 输入能力处理结果

更新时间：2026-09-25。

## 已完成

- 读取并核对服务器已有 Matrice 4T 标定审计、LRF 时间配对审计、视频 seek 抽查和视频遥测表。
- 已确认可解析字段：飞机经纬度、相对/绝对高度、云台 yaw/pitch、名义焦距、变焦比例、帧号、视频偏移、LRF 目标坐标和部分时间配对信息。
- 已确认 52 条 LRF 观测、25 组候选 T/V 配对、2 条未配对观测。
- 已确认视频 seek 抽查 33/33 对成功读取，报告中位时间差约 9.97 ms，最大约 29.57 ms。
- 已确认缺少：V/T 逐相机内参、畸变、相机到云台/机体外参、T/V 外参和可验证的统一时间偏移/漂移模型。

## 处理边界

缺失的 Matrice 4T 标定、外参和统一时间模型已确认无法从现有数据补出，后续不再把它们列为待提供内容。流程固定为图像平面检测、轨迹跟踪、时间配对、遥测伴随输出、已有 LRF 坐标查表关联和候选位置展示。绝对 WGS84 视觉定位保持 `unavailable`，不使用 H20T 参数或产品名义焦距替代。

## 少量火源真值标注页面

已从现有 B3/B4 连续片段均匀抽取 50 对 V/T 帧，覆盖 5 个代表性片段。页面只要求：

- 点击地面火源接触点或热点候选点；
- 填写片段内稳定 `fire_id`；
- 选择 V/T 是否同一火源；
- 标记热像高温非燃烧背景；
- 不确定时选择 `unknown`。

不要求重新复核 214 张图片，也不要求标注烟雾框。

页面地址：`http://127.0.0.1:18782/`

服务器输出：

- `@recovery/metadata_audit_v1/audit.json`
- `@recovery/metadata_audit_v1/REPORT.md`
- `@recovery/source_truth_review_v1/queue.json`
- `@recovery/source_truth_review_v1/decisions.json`

## 复现脚本

- dji_input_capability_audit.py（原资料引用）
- dji_source_truth_prepare.py（原资料引用）
- dji_source_truth_review_server.py（原资料引用）
