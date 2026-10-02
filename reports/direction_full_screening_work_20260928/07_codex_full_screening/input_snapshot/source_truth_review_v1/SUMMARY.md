# 火源真值复核摘要

复核任务：50 对；已保存：50 对；缺失：0 对。
格式错误：0 条；可进入跟踪真值处理：是。

## 总体统计

- 火源状态：{'active_fire': 32, 'hot_background': 8, 'residual_heat': 10}
- V/T 火源关系：{'same_source': 42, 'unknown': 8}
- 热像背景：{'none': 42, 'hot_background': 8}
- V 标注点：74 个；T 标注点：72 个。

## 解释

`same_source` 是人工确认的同一物理火源关系；`unknown` 不作为正确或错误关联。`residual_heat` 表示明火熄灭后的局部余热，`hot_background` 表示高温但不属于燃烧源的背景。

下一步可用这批标注评估轨迹覆盖、V/T 同源关系和图像源点误差；不把未确认关系强行计入准确率。
