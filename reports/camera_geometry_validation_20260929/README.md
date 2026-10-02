# 无人机 V 视频相机几何校验实验（2026-09-29）

结论见 final_report.md（原资料引用）：B3 静态背景可检出名义几何的系统性不一致，但本轮没有得到可跨批次、跨火点接受的固定相机校正。M0 已与 2026-09-28 十组结果逐组数值复核；M1/M2 是冻结后转用的诊断候选，不作为新的正式定位器。

## 数据与分割

- B3 原始 V/S 与已有 COLMAP 模型在远程服务器只读。`extract_background_server.py` 提取 B1–B4 相机参数、每个 t3/t5/t7 图对应的字幕；`extract_tracks_server.py` 导出已有 COLMAP 的特征轨迹，不读火焰标注或激光点。
- B3 的 t3/t5 背景特征用于拟合；t7 背景像素用于时间留出检验。其他批次 B1/B2/B4 的 t7 是跨场景检验。`background_fit.py` 优化全局 yaw/pitch 零偏，再加一个全局焦距比例；每个背景点的三维位置仅由 t3/t5 射线三角化。GPS 和逐帧云台值保持固定。
- `evaluate_localization.py` 冻结参数，重新运行十组已有火点观测，包括 B1、B2、B3 南及 B3 北/B4 东西；未用火点或 LRF 拟合。M0 逐组断言与原 `localization_results.csv` 水平坐标一致。
- `reproduce_b3_server.py` 以原 B3 COLMAP 模型复算 C1/C2/C4 的 1.41/0.71/1.13 m 历史诊断，并额外读标称偏移处的字幕；`make_diagnostics.py` 汇总图表、zoom 与时序审计。

## 主要文件

| 文件 | 含义 |
|---|---|
| `model_comparison.csv` | M0–M5 决策表；M3–M5 未拟合的单元格留空 |
| `parameter_identifiability.csv`, `estimated_parameters.csv` | 参数判断与候选值；`accepted=no` 表示不能用作物理标定 |
| `calibration_observations.csv`, `validation_observations.csv` | 从 250 条候选中剔除 4 条人工可疑轨迹后，246 条 B3 轨迹的 1,205/602 个像素观测及分割 |
| `reprojection_results.csv` | B3 M0/M1/M2 逐观测重投影；`background_transfer_results.csv` 为跨批次汇总 |
| `localization_before_after.csv` | 十组火点 M0/M1/M2 全部重新交会、参考差、残差和留一视角位移 |
| `b3_071_reproduction.csv`, `b3_manual_frame_telemetry.csv`, `b3_subtitle_fire_transfer.csv` | 历史 0.71 m 复算、不同遥测来源核对及重读 S 后的冻结模型验证 |
| `input_manifest.csv`, `remote_input_manifest.csv` | 本地 SHA-256 与远程原始文件/重建清单 |
| `background_track_samples.jpg`, `manual_track_review.csv` | 自动匹配样本的人工物理合理性检查；8 条中 2 条阴影、2 条物理点不清，均已从拟合剔除 |

## 复算顺序

在有原始数据、COLMAP 模型和 `pycolmap/scipy/ffmpeg` 的原服务器运行前三个 `*_server.py` 脚本，复制 `/tmp/camera_geometry_20260929/` 的 CSV 到本目录；随后运行 `background_fit.py`、`transfer_eval.py`（服务器 Python 环境），复制输出；本地运行 `evaluate_localization.py`、`make_diagnostics.py`。脚本顶部记录输入路径。`transfer_eval.py` 导入 `background_fit.py` 时会重新做同一种受限拟合。随机抽样种子已固定。旧结果及原始视频未覆盖。

## 验证边界

背景轨迹关联取自包含 t7 和 B3 手工火点帧的既有自由 SfM 重建。t7 像素不进入本次受限参数优化或三角化，却参与了轨迹关联与旧 SfM，故时间留出不是全流程封闭盲测。历史 C2 的火点手工帧也在原 SfM 中。JPEG 的真实 PTS 未逐帧追认，跨机时钟未标定；字幕 GPS 高度基准未核实。参考位置是堆址级有条件对照，B3 北/B4 东西无绝对参考。
