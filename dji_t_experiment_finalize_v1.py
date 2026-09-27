"""Close the B4 T review experiment after frozen development selection."""
import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    work = root / "thermal_background_v1"
    policy_path = work / "selection_policy_v1.json"
    freeze_path = work / "review_frozen_v1.json"
    selection_path = work / "development_selection_v1.json"
    status_path = root / "status_current.json"
    report_path = work / "REPORT_20260925.md"
    result_path = work / "experiment_summary_v1.json"
    if report_path.exists() or result_path.exists():
        raise FileExistsError("T report already exists")
    policy, freeze, selection = map(load, (policy_path, freeze_path, selection_path))
    if selection["policy_sha256"] != digest(policy_path) or selection["selected_mode"] is not None:
        raise ValueError("selection changed or requires further evaluation")
    if freeze["decisions_sha256"] != digest(work / "review_queue_frozen_v1/decisions.json"):
        raise ValueError("review snapshot changed")
    status = load(status_path)
    candidates = selection["candidates"]
    if {x["mode"] for x in candidates} != {"T1", "T2"} or any(x["eligible"] for x in candidates):
        raise ValueError("unexpected T candidate state")
    now = datetime.now(timezone.utc).isoformat()
    summary = {"schema_version": "dji_b4_thermal_experiment_summary_v1",
               "created_utc": now, "decision": "E2_T_remains_default",
               "new_confirmation_evaluation_done": False,
               "new_source_point_evaluation_done": False,
               "reason": "neither T1 nor T2 meets the predeclared development false-positive and coverage rule",
               "review": {"pairs": freeze["pair_count"], "usable": freeze["usable_count"],
                          "uncertain": freeze["uncertain_count"],
                          "new_source_negative_images": 0,
                          "decisions_sha256": freeze["decisions_sha256"]},
               "baseline": policy["baseline"], "candidates": candidates,
               "policy_sha256": digest(policy_path), "selection_sha256": digest(selection_path),
               "limits": ["all 32 newly reviewed pairs have source boxes; no new source-negative image was added",
                          "development set was historically exposed",
                          "the nine 50-pair no-truth detection frames are correlated and not nine independent physical false alarms"],
               "next_action": "retain E2 V/T and close B4 realtime display and localization capability reporting"}
    result_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    t1 = next(x for x in candidates if x["mode"] == "T1")
    t2 = next(x for x in candidates if x["mode"] == "T2")
    report_path.write_text(
        "# B4 T 路高温背景实验结果\n\n"
        f"更新时间：{now}\n\n"
        "32 对 B4 训练来源 V/T 画面已复核并冻结。全部画面都有火源或余热框，因此没有新增无火源负例。T1 仅修正 16 张既有 T 训练图；T2 在 T1 上增加 16 张新图。两组均从相同 YOLOv8n 初始化、以相同参数训练 100 轮。\n\n"
        "| 模型 | 开发阈值 | TP | FP | 无真值图误报数 | P | R | AP50 |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|\n"
        f"| E2 T | {policy['baseline']['threshold']:.2f} | {policy['baseline']['tp']} | {policy['baseline']['fp']} | {policy['baseline']['negative_false_positive_images']} | {policy['baseline']['P']:.3f} | {policy['baseline']['R']:.3f} | {policy['baseline']['AP50']:.3f} |\n"
        f"| T1 | {t1['threshold']:.2f} | {t1['tp']} | {t1['fp']} | {t1['negative_false_positive_images']} | {t1['P']:.3f} | {t1['R']:.3f} | {t1['AP50']:.3f} |\n"
        f"| T2 | {t2['threshold']:.2f} | {t2['tp']} | {t2['fp']} | {t2['negative_false_positive_images']} | {t2['P']:.3f} | {t2['R']:.3f} | {t2['AP50']:.3f} |\n\n"
        "T1 相比 E2 少 2 个 FP、少 1 个 TP；T2 多 7 个 TP、也多 5 个 FP。两组均未达到在读取结果前固定的至少减少 3 个 FP、最多损失 2 个 TP、且无真值图误报减少的共同条件。没有合格候选，因此停止种子复验和新确认集评估，网页默认继续使用 E2 T。\n\n"
        "既有 50 对真值中的 9 帧“无人工 T 火源点但仍有检测”多数来自同一连续热区，不是 9 个独立物理误报事件，也不能仅凭 V 无可见火焰断定为非火高温。本轮没有把这 50 对用于选模。\n\n"
        "结果与复现入口：`review_frozen_v1.json`、`datasets/T1`、`datasets/T2`、`runs/T1_T_960_s0`、`runs/T2_T_960_s0`、`evaluations/T1_T_960_s0`、`evaluations/T2_T_960_s0`、`selection_policy_v1.json`、`development_selection_v1.json`。\n",
        encoding="utf-8")
    history = root / "status_history"
    history.mkdir(exist_ok=True)
    backup = history / (digest(status_path) + ".json")
    if not backup.exists():
        shutil.copyfile(status_path, backup)
    status["updated_utc"] = now
    status["stage"] = "thermal_background_development_gate_failed"
    status["next_action"] = summary["next_action"]
    status["thermal_background_v1"] = {
        "status": "complete_no_deployable_candidate",
        "review_pairs": 32, "review_frozen_sha256": digest(freeze_path),
        "new_source_negative_images": 0,
        "T1_run_status": "complete", "T2_run_status": "complete",
        "selection_policy_sha256": digest(policy_path),
        "development_selection_sha256": digest(selection_path),
        "selected_mode": None,
        "E2_T_remains_default": True,
        "new_confirmation_evaluation_done": False,
        "new_source_point_evaluation_done": False,
        "report": str(report_path), "summary": str(result_path),
    }
    temp = status_path.with_suffix(".json.new")
    if temp.exists():
        raise FileExistsError(temp)
    temp.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, status_path)
    print(json.dumps({"stage": status["stage"], "report": str(report_path),
                      "status_archived": str(backup)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
