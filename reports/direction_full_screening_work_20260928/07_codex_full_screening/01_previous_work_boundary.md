# 两篇毕业论文与本研究边界

依据 `input_snapshot/赵迪的毕业论文第四版.txt` 和 `input_snapshot/徐瑞擎毕业论文终版论文(1).txt` 的摘要、目录及方法章节；源 PDF 位于本地 `@workspace/reference_papers/`。

| 论文 | 已做工作 | 可继承的资源 | 不能作为新论文主贡献的直接重复 |
|---|---|---|---|
| 赵迪（2025） | 部分卷积轻量烟雾检测；师生蒸馏与改进 SSDA-YOLO 域适应；动态烟雾特征过滤、烟源预测、ORB-SLAM2 和三角测距；Matrice100/Jetson Nano 原型 | 旧烟雾标签、权重、分割与域适应基线、定位代码和评估经验 | 简单换 YOLO 模块、再做同类烟雾域适应、普通单目 ORB-SLAM 烟雾定位 |
| 徐瑞擎（2026） | LFSNet 轻量烟雾检测；多功能教师、课程伪标签、记忆库对齐、FreeControl 增强；MK-UNet 分割、优化 ORB-SLAM2、多帧约束烟源定位；无人机软件验证 | 烟雾跨域基线、分割/轨迹方法及部署流程 | 再做普通 teacher-student 烟雾检测或多帧烟源 SLAM 定位 |

本次苏州数据提出不同的物理对象：**正在燃烧的地面火源**。两篇旧论文面向烟雾及烟源区域，不能把其烟源位置自动当成火焰接地点，也不能以其中的烟雾检测提升证明火源定位提升。

外部先例同样形成边界：2024 年 IEEE TIE 的 [Early Wildfire Detection and Distance Estimation Using Aerial Visible-Infrared Images](https://ieeexplore.ieee.org/document/10520273/) 已把可见光/红外配准、SLAM 与火点测距集成为系统。因此“RGB-T + SLAM + 三角化”的组合本身不构成新颖性。真正待验证的是非配准多模态下的物理火源观测、明火/余热拒识、跨机同源判别和**独立 LRF 水平误差**。

可继承而需隔离的代码和数据：旧烟雾 `datasets_yolo`、`results`、`weights` 仅作基线并重新划分；苏州候选 V/T 表仅作抽样框；人工 `source_truth_review_v1` 用于明火点/状态评估；现有 `localization_v2`、`direction_screen_20260928`、`direction_research_20260928` 用于几何消融及原始脚本复核。`input_provenance.json` 记录本次实际使用的快照。
