# 标签定义

- `active_fire`：V 时序上下文能看到明确当前火焰；单独热亮斑不能构成明火真值。
- `residual_heat`：既有燃烧堆址，±3 秒无可见火焰/烟且 T 仍持续明显发热。微小红炭、烟雾或遮挡使当前燃烧状态不明时标 `uncertain`。
- `hot_background`：与燃烧堆址无关的热目标，需要 V/T 与场景上下文独立确认；本轮没有把疑似热路面自动定真值。
- `uncertain`：当前燃烧、余热、遮挡或多源混合无法可靠区分；排除于 D 有标签分母。
- `V_source_visible`、`T_source_visible`：只记可见或不确定；不凭检测框或热亮区补造地面接触点。
- `physical_source_id`：须有人为可追溯的跨 UAV 物理身份。B4 可确认每个画面内两处固定火址，但跨 UAV 对应未独立确定，字段留空。
- `truth_origin`：`existing_manual` 为第一阶段人工复核，`new_manual_review` 为本轮接触图视觉复核，`derived` 仅为算法或坐标换算，`unknown` 不作为真值。
- `reference_type`：accepted LRF 火点、事前堆址、候选 LRF、无参考分开记录；不按 batch 给每帧自动挂 LRF。
