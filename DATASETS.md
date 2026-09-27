# 数据集说明

## E2 V/T 历史训练数据

- 下载：[E2 图像、YOLO 标签与 manifest](https://github.com/03xf/research/releases/tag/dataset-e2-20260928)
- 文件：`dji_e2_dataset_review_applied_v1_20260928.tar.gz`
- 大小：393,448,253 字节；SHA256：`38615b1cb86a290bf103de51343d1b1103c2d83e5821eb6c768f31cf0a263f6b`
- 来源：服务器 `recovery_v1/dataset_review_applied_v1`，与仓库 `模型权重/` 中冻结的 E2 V/T 权重对应。
- 内容：V train 404 张、validation 61 张；T train 433 张、validation 66 张，共 964 张图像及相应 YOLO 标签。另有 `manifest.json` 和 `review_decisions_snapshot.json`。
- 使用边界：750 张旧训练正例仍是历史标签，未经逐图复核；validation 也有历史实验暴露。可用于重现和诊断 E2，不能当最终独立测试集。标签语义和错误修正见主文档及审计记录。

解压后目录为 `dataset_review_applied_v1/{V,T}/{images,labels}/{train,validation}`。训练前应读取 `manifest.json` 核对来源、切分和人工复核状态。

## B1–B3 视频抽帧候选

仓库内的 `b1_b3_candidate_dataset_v1/` 保存 2,401 对 V/T 候选帧的完整索引和 53 组录像来源；`样本/候选抽帧/` 提供 36 对可核验 SHA256 的真实抽帧。其余 2,365 对图像仍在服务器。**全部 2,401 对均处于候选状态，尚未确认为训练标签。** 现有 train/dev 录像组切分也不能代表跨燃烧事件的独立测试。

## 原始视频与旧烟雾数据

苏州原始素材约 166 GiB，未纳入 Git 仓库或本次 Release；源文件与 SHA256 清单见 `_tmp_train_audit/`。旧烟雾数据存在同内容副本及切分重复，当前也没有发布为可直接训练的数据集。
