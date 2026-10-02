# 数据与协议审计

执行记录：`audit_snapshot.py`、`strict_split.py`、`L_smoke_domain/experiment.py`。复制输入的来源和 SHA256 见 `input_provenance.json`。原始视频、既有实验和第一阶段目录均未改写。

## 苏州 V/T 与遥测

原清单有 285 条，其中正式视频 103 条；S 视频可提供逐帧 telemetry。候选表有 2401 对（B1 709、B2 966、B3 726）、42 个组、26 个 session，**2401 条全是 `candidate_unreviewed`**。视频候选不等于 V/T 同源真值，也不等于火源标注。

原 v2 把 B1+B2 的 1675 条作为训练候选，把 B3 的 726 条作为开发候选。虽然 `group_key` 没有交叉，B2/B3 仍共享两个 session：`DJI_202609080945_004` 与 `DJI_202609080946_003`。本次输出 `candidate_event_split_v3_strict.csv`：训练候选 1643、开发候选 726、排除共享 session 的 B2 候选 32；训练/开发 session 交集为 0。这只是更严格的划分协议，尚无逐图合格标签，且 B2/B3 地点背景可能相似。

## 人工火源与独立定位参考

人工复核 50 个时刻，集中在 5 段短片（B3 一段、B4 四段）；明火 32、余热 10、非火热背景 8。同源确认 42，未知 8。V/T 手工点数分别为 74/72；其中用于本次明火同源逐点实验的是 52 对。状态与片段强相关，余热仅见于一段片段，不能把逐帧随机划分当状态泛化测试。

LRF 文件有 52 张照片、去重后 27 个 observation。`observation_valid=true` 为 19 个，其中 `target_match_status=accepted` 仅 17 个；8 个无效排除、2 个有效但离群剔除。17 个 accepted 分别是 B1 F1 4、B2 F1 1、B3 F1 1、B3 F2 2、B4 F1 9。B2 是**放火前木柴堆址**，不计明火真值。B4 F2 没有独立 LRF 坐标。多次观测同一物理点不得当作多个独立测试火点；高程基准和 LRF 与真实地面燃烧点的物理偏差尚未独立确定。LRF 仅用于评估，不进入算法输出。

## 旧烟雾协议

`L_smoke_domain/results.json` 重新做文件级 SHA256：`target/images/val` 与 `target/images/test` 各 45 张，**45/45 内容相同**；两者各有 10/45 与 `target/images/train` 内容相同；`Detection/train/images` 的 3150 张与 `target/images/train` 同名且逐张内容相同。旧 YOLO `val0` 对 train 的精确去重脚本另外排除了 44 张。该去重只解决字节完全相同的图片，尚未建立视频/事件独立划分。原跨域目录的训练/验证/测试指标不应进入论文主结论。

## 使用约束

地面燃烧源点、火焰尖端、火焰框、烟中心、热像热点、余热、非火热物、激光命中点分别保留语义。所有定位图表只报告经纬度对应的水平参考差；未验证地面高度或相机模式光轴时不宣称三维精度。
