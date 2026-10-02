# 更新方向判断

| 方向 | Current Evidence | Data Support After Annotation | Cross-event Evidence | Truth Quality | Method Headroom | Paper Feasibility |
| --- | --- | --- | --- | --- | --- | --- |
| H/R | B3/B4 留出身份间隔为正；2–5 支持可测 | 两独立多火点事件，五时刻固定堆址可追踪 | B3+B4；每事件仅一个精确点时刻 | 场景 ID 中等；同 Agent 复审；时钟未校准 | 相对拓扑、拒识、跨时刻身份 | 首选验证候选，尚需第二人和更多精确点 |
| D | 此前跨批互补信号，本轮未重训 | 四批 V/T 均有现场状态 | 既有证据跨批 | 状态标签仍弱 | 可做失败恢复对照 | 备选，不以本轮证明 |
| A | 留出火焰基部误差仍约百像素 | 多机看到同源但接地点为零 | 四批一时刻代理点 | A/O ground-contact Gold=0 | 相机标定及清晰接地点 | 第三候选；先补点 |
| O | 2→6 机误差有限下降 | 可形成弱几何候选 | 四批条件性曲线 | 不能作精确伪标签 | 不训练网络；先定标 | 暂缓 |
| F/G | B3_N 约14 m 系统偏差 | 有 S 遥测和少量 LRF | B1+B3 两个事件 | 绝对 Gold 很少且点语义不同 | 系统误差分解 | 暂缓绝对精度论文 |


Primary candidate: **H/R（相对多源关联）**。Backup: **D（既有跨批对照，不重训）**。Third: **A（先补 ground-contact 真值）**。Deferred: **O、F/G**。Rejected as a present claim: “6+ UAV 已产生可用的精确 ground-contact Silver-A 锚点”及“内部一致性证明绝对定位准确”。

本次排序是下一阶段验证次序，不是论文方向已通过的宣称。优先补 B3/B4 第二位独立审阅者、更多时刻的清晰源点、场景同步和相机标定，再检验 6+ 留出多源分类及 A/O 地面接触点误差。
