# 多视角定位验证结果

主结论和十节实验汇报：validation_summary.md（原资料引用）。

本目录是独立新结果。`run_validation.py` 复用旧脚本的名义相机射线与无高度约束三维最小二乘，严格把旧三机“地面接触”标注与新增“火焰根部代理”分层；全部原始输入只读。`observations.csv` 为 54 条观测，`rays.csv` 为射线/逐线残差，`localization_results.csv` 为 10 组全视角解，`view_subset_results.csv` 为 1,024 组穷举组合，`pixel_sensitivity.csv` 为 ±1/2/5 px 等效条件扰动，`diagnostics/` 含时间、方向、假设参数、Level B 既有背景修正和图表。`input_manifest.csv` 记录输入路径与 SHA-256。

计算环境：Windows Python、NumPy、Matplotlib。服务器 PTS 探测环境：`@server_home/.conda/envs/colmap_exp/bin/python` 与 FFprobe 4.3.1。镜头与高度基准尚未实测，所有经纬度是局部平面近似的名义几何解。B3 北、B4 东西没有可用绝对参考；勿把旧 B3 F1 或 B4 F1 用于它们的精度评分。
