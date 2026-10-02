# 2023–2026 相关研究与真实缺口

以下依据出版社/论文原始页面的摘要与方法说明，检索截至 2026-09-28；这些文献界定新颖性边界，不能代替系统综述或证明某问题“无人研究”。

## RGB-T

- [Li 等，IEEE TIE 2024：Early Wildfire Detection and Distance Estimation Using Aerial Visible-Infrared Images](https://ieeexplore.ieee.org/document/10520273/) 已把红外与可见光配准、SLAM、三角测距与 GPS 地理定位合并。因此简单 V/T fusion + SLAM 不是新贡献。
- [Kularatne 等，IEEE ETFA 2024：FireMan-UAV-RGBT](https://oulurepo.oulu.fi/handle/10024/52595) 已提供成对 RGB-T 视频和跨数据集检测基线。[Zhang 等，Remote Sensing 2025：RGBT-3M](https://www.mdpi.com/2072-4292/17/15/2593) 用 M-RIFT 对齐并做 RGB-T 火/烟检测。普通多模态检测框不能作为独占切口。
- [Qiu 等，IEEE TIM 2025：unregistered RGB-T saliency](https://ieeexplore.ieee.org/document/10947101/) 已在未注册模态上做特征交互/注册，[2025 unaligned RGB-T segmentation](https://ieeexplore.ieee.org/document/11073153/) 也研究粗到细特征对齐。C 若继续，需要报告**火源观测点**的跨 session 映射与定位收益，而不是通用配准分数。
- [Wang 等，Remote Sensing 2026：power-corridor RGB-T wildfire monitoring](https://www.mdpi.com/2072-4292/18/12/1869) 包括连续时序、热干扰负例和检测连续性。D/E 的新意只能放在明火/余热/非火热源状态与物理 source observation 的净收益，必须与时间连续性基线对照。

## Source anchor

- [Bai 等，2025 两阶段 UAV fire-source video analysis](https://arxiv.org/abs/2508.16739) 在 fire clip 上以改进 YOLOv8 定位火源，但其摘要指标侧重框检测与计算效率。本课题 A 若做论文，需明确人工**地面燃烧接触点**、不可见时的不确定性及下游 LRF 水平差；只提高框 mAP 不够。
- [NASA AMS 2026 multispectral active wildfire localization](https://arxiv.org/abs/2601.14475) 提供多光谱分割与火线定位；这也提醒“像素分割=地面燃烧源点”并非自动成立。本次检索未确认直接可比的多机地面燃烧点基准，需继续检索再写新颖性声明。

## Temporal and state

- 上述 [2026 power-corridor 工作](https://www.mdpi.com/2072-4292/18/12/1869) 已报告 temporal detection continuity 与热干扰；[FireMan-UAV-RGBT 2024](https://oulurepo.oulu.fi/handle/10024/52595) 已利用热像辅助 RGB 标注。仅加一个时序模块或热像分支不够。需要与热像误恢复、余热拒识和 source-point/localization 可用性绑定。

## Geometry and association

- [IEEE CASE 2024 UAV target geolocalization](https://ieeexplore.ieee.org/document/10711373/) 明确处理 UAV 定位不确定性；[Expert Systems with Applications 2025 三 UAV 视觉空间约束](https://www.sciencedirect.com/science/article/abs/pii/S0957417424028513) 已有多 UAV 三角化与不确定度实验。普通多射线交会或声称低残差本身没有新颖性。
- B1/B4 的 LRF 反例指向更具体的缺口：如何用 GPS/gimbal 绝对先验限制视觉修正、在外部参考下选择/拒绝定位，以及如何在 B3/B4 多火点中判定**同一物理源**。本批数据仅有四个明火参考位置，不能凭现有实验宣称这些问题已解决。

## Smoke

- 赵迪和徐瑞擎两篇校内论文已经覆盖轻量烟雾检测、跨域教师方法、烟源预测与 SLAM。2026 年 [边缘 RGB-T 火灾时序检测](https://www.mdpi.com/2072-4292/18/12/1869) 也覆盖小目标和连续性。因此 L/M 必须首先修复协议，并有新的独立研究问题，不能仅以面积分层召回差距立题。
