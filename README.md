# 无人机可见光微小明火检测与多视角火点定位

本仓库发布可见光图片、原标签、数据来源、历史划分、实验结果与报告，供第三方判断数据规模、标签质量、事件独立性和已有方法的实际表现。整理日期：2026-10-02。

## 数据规模与下载

| 内容 | 实际数量 |
|---|---:|
| 唯一可见光图像内容 | 1959 |
| 图片来源/历史使用记录 | 4616 |
| 历史数据版本 | 14 |
| 可见光训练运行结果 | 18 |
| 未标注候选补充图 | 600 |
| 连续帧 | 5 段，共 750 帧 |
| 仓库内原尺寸浏览图 | 102 |
| 原可见光视频来源清单 | 68 条 |

这些是文件/使用记录数量，不能当作独立火灾事件数量。候选图、连续帧、训练图可能有内容重叠，不相加计算唯一图像数。

- [完整可见光图片、标签、清单和连续帧数据包](https://github.com/03xf/research/releases/download/visible-data-20261002/visible_data_20261002.tar.gz)；约 1129.9 MiB。
- [E2 可见光单独数据包](https://github.com/03xf/research/releases/download/dataset-e2-20260928/dji_e2_visible_20261002.tar.gz)；404 张训练图、61 张验证图。
- [数据包大小与 SHA256](manifests/release_assets.csv)。完整包解压后为 `data/images/`、`data/labels/`、`manifests/` 和 `results/sequences/`。

## 从哪里开始看

| 目的 | 入口 |
|---|---|
| 浏览图片与标签 | [data](data/README.md)、[浏览图索引](manifests/browsable_samples.csv) |
| 查原文件与标签版本 | [图片来源表](manifests/image_sources.csv)、[历史划分](manifests/historical_splits.csv) |
| 查微小明火规模 | [统计说明](results/data_audit/README.md)、[尺寸统计](results/data_audit/bbox_size_definitions.csv)、[分组规模](results/data_audit/group_counts.csv) |
| 查重复与划分风险 | [历史划分检查](results/data_audit/split_leakage.csv) |
| 查检测实验 | [实验索引](results/detection/experiment_index.csv)、[历史检测输出](results/detection) |
| 查视频时序 | [序列清单](manifests/sequence_summary.csv)、[逐帧 PTS](manifests/sequences.csv)、[历史预测](results/sequences) |
| 查定位输入与结果 | [定位资料](results/localization)、[物理事件与参考](manifests/physical_fires.csv) |
| 查当前研究判断 | [课题主文档](reports/课题主文档.md)、[发布边界](reports/PUBLICATION_STATUS.md)、[研究报告](reports) |

## 数据与结果的使用边界

E1/E2 的 `0=smoke、1=flame`；明火专用数据的 `0=flame`。每张图片的类别解释、数据版本和标签文件记录在来源表，标签没有被重新编号。不同历史标签版本分别保存，模型预测单独保存，不当作人工 GT。

E2 的 335 张旧训练图片未逐图复核；validation 有历史实验暴露。空标签不能自动证明无火，未标注图片不计为负样本。历史训练索引中的指标来自最大日志验证 mAP50–95 所在 epoch，未冒充冻结模型的独立测试成绩；专门的确认集和失败结果另见原评估报告。

连续帧保留解码 PTS，但没有完整逐帧人工 GT，因此当前不能直接声称能够可靠计算全部时序检测指标。候选抽帧和部分历史图片仅有请求时间/帧号；未核实精确 PTS 的地方留空并注明。GPS/姿态只在已有同通道核查证据时绑定，未知字段不猜测。

B1/B2/B3_S 只有条件参考；B3 F1 不作为 B3_N 真值；所谓 B4 F1 与 B2 同址，不作为 B4_E/B4_W 真值。定位观测与旧报告可供审计，不代表六处火点都有可靠同时刻绝对真值。

## 未上传内容与复现限制

完整原视频、热成像图片/视频/标签、模型权重、训练与推理代码、临时脚本、调试页面、缓存、第三方论文全文均不在当前版本。原视频通过相对路径、录像名和校验值对应；`@raw` 为原始数据根目录，`@trial`、`@recovery`、`@workspace` 是来源位置代号，不公开账号、服务器地址和个人本地路径。

保留训练参数、权重 hash、原结果日志与失败报告，便于审计已有实验；此版本没有代码、权重与完整原视频，不能独立重训或完整复现全部实验。Huaian 只上传研究核查报告，烟雾原图不混入明火训练数据。

Git 旧提交历史保留，已从当前版本清理的文件仍可能在旧提交中访问。旧报告的撤回结论以最新主文档为准。
