# DJI 火点确认与地面燃烧源定位：recovery_v1 结果

更新：2026-09-25。正式结果保存在服务器 `@recovery/`。本报告只陈述现有数据支持的结论。

## 1. 数据与实验链

- 先前 214 张训练/开发图像的复核决定已冻结，SHA256 为 `bb3b14e6aadb15cc80e6d8bae741d37fea0c6ff6b0c19037e91ddfbe9d6f21d2`。派生数据集 `dataset_review_applied_v1` 的 V/T 预检错误均为 0；另有 750 张训练正例仍沿用历史标签，未逐图复核。
- E0 历史 Round24/Round57 权重在修复的开发集上重评。E1（640）与 E2（960）各对 V/T 训练 seed 0、1、2，共 12 次受控正式训练；每组从同一 YOLOv8n 初始化权重开始，100 epochs。没有通过整图复核且符合新增场景条件的样本，E3 未执行。开发对照见 `comparison_seed0_seed1_seed2_v1.json`。
- 按预定开发集选择规则，冻结 E2 seed 0 模型。V 权重 SHA256 `16d161e21eb7d4dd0b12624d2bf8f6adcb8f115725ff5a3273f1181ca3006ff6`，烟雾阈值 0.41、火焰 0.37；T 权重 SHA256 `ee7566fe58336c21808d391907b37537f5a51baaef2f6286079bc88f4efdb2fa`，热点阈值 0.14。冻结记录为 `model_freeze_preconfirmation_v1.json`。确认集未用于选择模型或阈值。
- 两个预留 session 依据真实解码 PTS 每 10 秒成对抽取 194 对 V/T 图像（388 张），没有未配对样本。`DJI_202609081046_006` 为 86 对，`DJI_202609081036_005` 为 108 对。助手在成对浏览器逐对查看原图并保存 194 条完整决定；这不是独立人员盲审。冻结标签 `confirmation_10s_v2/decisions_frozen_v1.json` 的 SHA256 为 `9e11c2e06bbc5290e64c5fdc60f01b9840bb52e6b3293e2fee9ed63ca38072e5`，包含 116 个烟雾框、176 个火焰框、267 个热像热点框。历史 session 已暴露，因此确认评估不能称严格盲测。

## 2. 一次确认评估

评估采用同类别一对一 IoU 0.5 匹配，使用开发集冻结的工作阈值；P≥0.60、R≥0.70、AP50≥0.50 才算通过。完整结果和逐图预测分别在 `evaluations/confirmation_frozen_v1/result.json` 与 `predictions_V.json`、`predictions_T.json`。

| 类别 | 真值框 | 工作阈值 | P | R | AP50 | AP50–95 | 确认门槛 |
|---|---:|---:|---:|---:|---:|---:|---|
| V 烟雾 | 116 | 0.41 | 0.275 | 0.121 | 0.082 | 0.024 | 未通过 |
| V 火焰 | 176 | 0.37 | 0.571 | 0.250 | 0.314 | 0.097 | 未通过 |
| T 热点 | 267 | 0.14 | 0.475 | 0.566 | 0.519 | 0.259 | 未通过 |

V 烟雾的两 session 召回分别为 0.151、0.070；V 火焰为 0.508、0.113；T 热点为 0.490、0.613。热像在 29 张明确无热点图像中的 20 张产生了至少一次误检。开发集上 T 热点曾通过门槛，确认集失效；这与高温非燃烧背景及视角/场景变化相容，但现有实验不能单独量化每种原因。烟雾边缘和极小火焰的框位置差异也可能影响 IoU，仍需独立复核样本来衡量标注不确定性。**没有在确认集重新扫描阈值或补训。**

## 3. 视频跟踪

四段开发来源的连续片段，每段 30 秒、V/T 各 150 帧、5 Hz。V/T 时间配对仅是 PTS 接近，不证明同一物理目标。v1 默认 ByteTrack 的 `track_high_thresh=0.5`、`new_track_thresh=0.6`，热像四段合计没有一个轨迹；它与 0.14 的热像检测阈值不匹配。在开发片段上固定 `bytetrack_recovery_v1.yaml`（high/new 0.14，low 0.05），得到 `tracking_v2/` 下 8 个带 ID 视频，原 v1 输出保留。

| 开发片段 | V 轨迹/带 ID 检测 | T 轨迹/带 ID 检测 | T 无 ID 检测 |
|---|---:|---:|---:|
| visible_flame | 4 / 56 | 2 / 80 | 89 |
| paired_negative 候选 | 1 / 12 | 2 / 77 | 90 |
| visible_smoke_only | 2 / 142 | 2 / 158 | 0 |
| multiple_boxes | 4 / 207 | 8 / 170 | 27 |

v2 的 600 帧/传感器中，热像累计 485 个带 ID 检测、206 个无 ID 检测。带 ID 数增加仅证明跟踪器开始分配身份；`paired_negative` 候选片段仍有大量轨迹，显示误报可能变成持续轨迹。由于没有逐帧真实目标身份，ID 切换、断裂和覆盖率的真实性指标保持 `null`。每帧一框不能同时分给多个轨迹的程序检查已通过。视频已写盘，其中热像 `visible_flame` 视频由 ffprobe 确认可解码 150 帧。

## 4. 图像定位、T/V 对应与 LRF

`localization_confirmation_v1/image_localization_records.json` 包含每对原图、时间戳、检测框和图像候选点；`source_point_candidates.csv` 可直接筛选。176 个火焰框的下边中点被保存为 **图像空间候选点**，64 对无可见光火焰则不填点。该点并未经地面接触位置人工真值确认，不是已验证的地面燃烧源坐标。烟雾中心不作为源点；T 热点只保存候选区域。像素误差与归一化误差因缺少独立源点真值而不可评估。

194 对的 T/V 图像相差不超过 50 ms，只能作为时间候选。未找到可独立证明某个 V 点与某个 T 热点对应同一地面燃烧源的几何标定或逐目标真值，物理同目标确认数为 0，不把时间配对冒充同目标匹配。

`lrf/lrf_event_audit.json` 和 `lrf/lrf_review_rows.csv` 区分图片记录与拍摄/测距组。B4 为 18 条图片记录、11 个 capture group、7 个成对传感器组；四批总共 52 条图片记录、32 个 capture group。现有两个确认 session 没有对应的 LRF capture group。全部批次经独立核实属于同一地面燃烧源的 LRF 组数仍为 0，`lrf_review_rows` 中参考坐标只作元数据。历史 B4 约 0.398 m 平均水平差、0.492 m 三维 RMSE 是 LRF 对固定参考的内部离散统计，不能当作视觉定位误差。

Matrice 4T 的相机内参、畸变、相机至云台/机体外参、V/T 外参，以及激光落点与地面燃烧源的物理对应均不可用；不使用 H20T 参数或等效焦距替代。因此绝对视觉 WGS84 坐标为 `unavailable`，相关字段保持 `null`，没有填零或复用 LRF 参考坐标当预测。

## 5. 结论与交接

数据修复、受控实验、194 对自主复核、一次冻结确认评估、四段带 ID 视频和图像空间候选点已交付。**当前模型没有达到检测门槛；连续跟踪质量、跨模态物理对应和视觉绝对定位没有可验证的精度结论。** 本次对现有数据不再以确认集调参或反复训练。后续若要提升能力，需要新的独立场景/明确负例和地面燃烧源点真值；若要给出绝对视觉坐标，还必须补齐 Matrice 4T 标定与可靠几何/测距对应。

复现入口：服务器 `@server_home/bin/python`，脚本位于 `@project/code/tools/`。关键记录为 `status_current.json`、`dataset_review_applied_v1/manifest.json`、`comparison_seed0_seed1_seed2_v1.json`、`model_freeze_preconfirmation_v1.json`、`confirmation_10s_v2/manifest.json`、`confirmation_10s_v2/decisions_frozen_v1.json`、`evaluations/confirmation_frozen_v1/result.json`、`tracking_v2/*/manifest.json`、`localization_confirmation_v1/summary.json` 和 `lrf/lrf_event_audit.json`。所有历史数据和先前训练输出保留。
