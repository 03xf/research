"""Validate and summarize the completed source-truth review queue."""

from __future__ import annotations

import argparse
import collections
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True, help="source_truth_review_v1 directory")
    args = ap.parse_args()
    root = args.root
    queue = json.loads((root / "queue.json").read_text(encoding="utf-8"))
    decisions = json.loads((root / "decisions.json").read_text(encoding="utf-8")).get("decisions", {})
    tasks = {row["task_id"]: row for row in queue["tasks"]}
    missing = sorted(set(tasks) - set(decisions))
    extra = sorted(set(decisions) - set(tasks))
    errors = []
    clip_summary = collections.defaultdict(lambda: collections.Counter())
    all_counts = {name: collections.Counter() for name in ("source_state", "tv_relation", "thermal_background", "frame_status")}
    point_counts = collections.Counter()
    for task_id, decision in decisions.items():
        if task_id not in tasks:
            continue
        clip = tasks[task_id]["clip_id"]
        for field in all_counts:
            value = decision.get(field)
            all_counts[field][value] += 1
            clip_summary[clip][f"{field}:{value}"] += 1
        for sensor in ("V", "T"):
            points = decision.get(sensor, {}).get("points", [])
            point_counts[sensor] += len(points)
            for point in points:
                if len(point) != 3 or not isinstance(point[2], str) or not point[2].strip():
                    errors.append(f"{task_id}:{sensor}:invalid_point")
                elif not (0 <= float(point[0]) <= 1 and 0 <= float(point[1]) <= 1):
                    errors.append(f"{task_id}:{sensor}:point_out_of_bounds")
    summary = {
        "schema_version": "dji_source_truth_summary_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "queue": str(root / "queue.json"),
        "decisions": str(root / "decisions.json"),
        "task_count": len(tasks),
        "decision_count": len(decisions),
        "missing_task_count": len(missing),
        "extra_decision_count": len(extra),
        "validation_errors": errors,
        "counts": {field: dict(counter) for field, counter in all_counts.items()},
        "point_counts": dict(point_counts),
        "clip_counts": {clip: dict(counter) for clip, counter in sorted(clip_summary.items())},
        "ready_for_tracking_truth": not missing and not extra and not errors,
        "interpretation": {
            "same_source": "manual physical-source correspondence confirmation",
            "unknown": "not used as a correct or incorrect correspondence",
            "residual_heat": "localized post-extinguishing heat; not active flame",
            "hot_background": "thermal bright non-burning background; no source point",
        },
    }
    (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 火源真值复核摘要",
        "",
        f"复核任务：{len(tasks)} 对；已保存：{len(decisions)} 对；缺失：{len(missing)} 对。",
        f"格式错误：{len(errors)} 条；可进入跟踪真值处理：{'是' if summary['ready_for_tracking_truth'] else '否'}。",
        "",
        "## 总体统计",
        "",
        f"- 火源状态：{dict(all_counts['source_state'])}",
        f"- V/T 火源关系：{dict(all_counts['tv_relation'])}",
        f"- 热像背景：{dict(all_counts['thermal_background'])}",
        f"- V 标注点：{point_counts['V']} 个；T 标注点：{point_counts['T']} 个。",
        "",
        "## 解释",
        "",
        "`same_source` 是人工确认的同一物理火源关系；`unknown` 不作为正确或错误关联。`residual_heat` 表示明火熄灭后的局部余热，`hot_background` 表示高温但不属于燃烧源的背景。",
        "",
        "下一步可用这批标注评估轨迹覆盖、V/T 同源关系和图像源点误差；不把未确认关系强行计入准确率。",
    ]
    (root / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"summary": str(root / "summary.json"), "report": str(root / "SUMMARY.md"), "ready": summary["ready_for_tracking_truth"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
