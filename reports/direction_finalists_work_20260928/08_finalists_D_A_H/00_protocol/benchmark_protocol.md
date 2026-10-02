# 第二阶段共享基准协议

日期：2026-09-28。原始数据只读；新增结果仅写入 `08_finalists_D_A_H`。第一阶段 `07_codex_full_screening` 的原始人工记录、冻结检测器和几何结果作为继承证据，未改写。

## 抽样和真值

`01_shared_benchmark/finalist_benchmark.csv` 共 147 行：旧人工复核的 50 个时刻展开为 82 条源点/状态行，另有 6 条 B3 三机同案人工点与 accepted LRF 对应，以及 59 个新 V/T 时刻。旧 50 时刻集中在 B3 一段、B4 四段短片；展开行数绝非 82 个独立事件。新时刻来自 B1/B2/B4 七条 UAV 视频，固定 PTS 分层抽样，逐项查看 t−3、t、t+3 秒的 V/T 接触图。新复核：明火 25、余热 3、uncertain 31、非火热背景 0。B2 新余热与旧 B4 余热是两个批次/燃烧事件；第二个可信非火热背景事件没有找到。

`review_queue.csv` 保留 59 个候选及视觉判断；`contact_sheets/` 保留各时刻的六帧图。抽样在检测器打分前冻结，但不是原始视频的无偏随机样本。冻结 V/T 检测器随后对中心帧及 T 的 ±3 秒运行；其权重曾接触开发数据，因此这里是诊断，不能宣称真正独立泛化。

## 拆分和评价单元

继承 `candidate_event_split_v3_strict.csv`：B1+B2 train 候选 1643、B3 dev 候选 726、共享 session 排除 32；这 2401 个候选都未人工确认为同源。这里不把它们当训练/测试真值。所有结果按物理燃烧事件与 batch 汇总，不把连续帧、同一火址的重复 UAV/时间算作独立事件。B4 新时刻与旧 B4 短片同属一批多火事件。

## 坐标和参考

旧人工点从归一化坐标换算到 V 1920×1080、T 1280×1024 像素。新接触图是缩略图，故未从图上臆测精确 source point；相应坐标留空。视频遥测、焦距、相机模式没有逐时刻可靠提取，字段留空，不能误认为零。旧人工点不自动关联 LRF；只有经过同案验证的 B3/几何结果使用 accepted LRF。B2 F1 是放火前木柴堆址，不算燃烧期火点真值。B4 F2 无独立 LRF 坐标。

## 可复现性

`scripts/build_review_sheets.py` 生成图与初始候选，`scripts/assemble_benchmark.py` 冻结标签，`scripts/score_new_review.py` 运行冻结检测器，`scripts/score_anchor.py` 和 `scripts/score_b3_anchor_downstream.py` 做 A 实验，`scripts/score_h_noise.py` 做 H 条件噪声实验，`scripts/analyze_finalists.py` 汇总。长任务日志在 `logs/`。缺失的同案输入保持缺失，不做替代拼接。


另对 B1/B2 其余 UAV 的四个稀疏 PTS 进行 detector-driven 热像补漏预筛，30 个候选全部视觉复核为热框在既有燃烧堆址，未发现独立非火热背景。这 30 个是在检测后选出的对象类型核查，不进入 59 时刻的 D 性能表；记录见 extra_hot_prescreen_review.csv。
