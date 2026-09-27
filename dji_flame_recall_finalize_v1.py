"""Finalize the B4 flame recall experiment from immutable server artifacts.

This script runs on the server. It never overwrites an existing result; it
archives the current status first and writes a new status plus a concise
failure-attribution report.
"""

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def archive(path: Path, history: Path):
    if not path.exists():
        return None
    history.mkdir(parents=True, exist_ok=True)
    target = history / (sha256(path) + ".json")
    if not target.exists():
        shutil.copyfile(path, target)
    return str(target)


def metric(result):
    c = result["classes"][0]
    return {
        "threshold": c["work_threshold"],
        "precision": c["work_metrics"]["precision"],
        "recall": c["work_metrics"]["recall"],
        "ap50": c["ap50"],
        "gate_passed": c["gate_passed"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    work = root / "flame_recall_v1"
    status_path = root / "status_current.json"
    now = datetime.now(timezone.utc).isoformat()

    freeze_path = work / "candidate_freeze_v1.json"
    confirmation_path = work / "evaluations/confirmation_C1_V_flame_s0/result.json"
    point_path = work / "evaluations/point_C1_V_flame_s0/result.json"
    if not all(p.exists() for p in (freeze_path, confirmation_path, point_path)):
        raise FileNotFoundError("candidate freeze, confirmation, or point result is missing")
    freeze = load(freeze_path)
    confirmation = load(confirmation_path)
    point = load(point_path)
    if freeze["mode"] != "C1" or freeze["deployment_seed"] != 0:
        raise ValueError("unexpected frozen candidate")
    if confirmation["threshold"] != freeze["threshold"]:
        raise ValueError("confirmation threshold does not match freeze")
    if confirmation["weights_sha256"] != freeze["weights_sha256"]:
        raise ValueError("confirmation weights do not match freeze")
    if point["baseline_E2_tracked"]["B4"] != "18/32":
        raise ValueError("unexpected E2 B4 point baseline")

    c1_metrics = {str(seed): metric(load(work / f"evaluations/C1_V_flame_960_s{seed}/result.json"))
                  for seed in (0, 1, 2)}
    c2 = metric(load(work / "evaluations/C2_V_flame_960_s0/result.json"))
    c3 = metric(load(work / "evaluations/C3_V_flame_960_s0/result.json"))
    confirmation_metrics = {
        "precision": confirmation["work_metrics"]["precision"],
        "recall": confirmation["work_metrics"]["recall"],
        "ap50": confirmation["AP50"],
        "gate_passed": confirmation["gate_passed"],
        "tp": confirmation["work_metrics"]["tp"],
        "fp": confirmation["work_metrics"]["fp"],
        "fn": confirmation["work_metrics"]["fn"],
        "by_session": confirmation["by_session"],
    }
    point_summary = {
        "overall": "35/52",
        "B4": "17/32",
        "E2_overall": "33/52",
        "E2_B4": "18/32",
        "raw": point["totals"],
        "by_batch": point["by_batch"],
    }

    report = {
        "schema_version": "dji_b4_flame_recall_failure_attribution_v1",
        "created_utc": now,
        "decision": "C1_not_deployed_E2_remains_default",
        "scope": "B4-priority visible flame recall; exploratory because confirmation and point cohorts were historically exposed",
        "frozen_candidate": {
            "mode": freeze["mode"],
            "seed": freeze["deployment_seed"],
            "threshold": freeze["threshold"],
            "weights": freeze["weights"],
            "weights_sha256": freeze["weights_sha256"],
        },
        "development": {
            "C1_seeds": c1_metrics,
            "C2_seed0": c2,
            "C3_seed0": c3,
            "selection_rule": "seed-0 predeclared for confirmation; no confirmation tuning",
        },
        "confirmation": confirmation_metrics,
        "fire_source_points": point_summary,
        "evidence_based_findings": [
            "C1 improved the exposed development recall over E2, but the fixed threshold candidate failed the one-time confirmation gate.",
            "C1 B4 fire-source matching decreased from E2 18/32 to 17/32; overall 35/52 versus 33/52 was driven by B3.",
            "C2 and C3 seed-0 development recall were 0.625 and did not meet the R>=0.70 gate.",
        ],
        "possible_contributors_not_proven": [
            "confirmation sessions contain smaller or different-view flames than the exposed development split",
            "335 historical positive V training images remain without full-image independent review",
            "the added 23 frames come from one mostly fixed viewpoint and do not add independent scene coverage",
        ],
        "limits": [
            "confirmation sessions were historically exposed and are not a strict blind test",
            "absolute visual WGS84 localization remains unavailable without Matrice 4T calibration",
            "B4 F2 retains three candidate coordinates and no unique LRF truth",
        ],
        "artifacts": {
            "candidate_freeze": str(freeze_path),
            "confirmation_result": str(confirmation_path),
            "point_result": str(point_path),
        },
    }
    report_path = work / "FAILURE_ATTRIBUTION_20260925.md"
    json_path = work / "failure_attribution_v1.json"
    report_path.write_text(
        "# B4 优先 V 明火漏检实验：失败归因\n\n"
        f"更新时间：{now}\n\n"
        "## 结论\n\n"
        "C1 不替换 E2。网页和实时原型继续使用冻结 E2 V 模型；C1 仅保留为可复现实验版本。\n\n"
        "## 证据\n\n"
        f"- C1 确认集：P={confirmation_metrics['precision']:.3f}，R={confirmation_metrics['recall']:.3f}，AP50={confirmation_metrics['ap50']:.3f}，未通过。\n"
        f"- 火源点：C1 总体 {point_summary['overall']}，B4 {point_summary['B4']}；E2 基线总体 {point_summary['E2_overall']}，B4 {point_summary['E2_B4']}。\n"
        f"- C2 seed 0：R={c2['recall']:.3f}；C3 seed 0：R={c3['recall']:.3f}，两者均未通过开发召回门槛。\n\n"
        "## 原因判断\n\n"
        "已证实的是候选在确认集和 B4 火源点对照中不满足部署条件。小目标、视角分布差异、历史训练标签未逐图复核和新增帧场景单一是待验证的可能因素，不能由本轮结果单独证明。\n\n"
        "## 后续边界\n\n"
        "E2、T 模型、跟踪和定位规则保持不变；不在确认集调阈值，不覆盖历史结果。下一步由用户决定是否启动新的独立场景 V 数据实验，或进入实时展示和定位报告收尾。\n",
        encoding="utf-8",
    )
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status = load(status_path)
    archived = archive(status_path, root / "status_history")
    status.update({
        "updated_utc": now,
        "stage": "flame_recall_candidate_confirmation_failed",
        "next_action": "Keep E2 as the default V model; discuss whether to start a new independent-scene V experiment or close with realtime/localization reporting.",
        "absolute_visual_localization": "unavailable",
        "flame_recall_v1": {
            "focus": "B4 V flame misses",
            "review_complete": True,
            "review_queue_count": 40,
            "review_decision_count": 40,
            "frozen_candidate": "C1 seed 0",
            "candidate_threshold": freeze["threshold"],
            "candidate_weights_sha256": freeze["weights_sha256"],
            "new_confirmation_evaluation_done": True,
            "confirmation_result": str(confirmation_path),
            "confirmation_metrics": confirmation_metrics,
            "confirmation_gate_passed": False,
            "point_result": str(point_path),
            "point_summary": point_summary,
            "C2_train_status": "complete",
            "C3_train_status": "complete",
            "C2_development": c2,
            "C3_development": c3,
            "deployment_decision": "E2_remains_default",
            "failure_attribution_report": str(report_path),
            "failure_attribution_json": str(json_path),
            "historical_V_train_labels_unreviewed": 335,
        },
        "status_history_archived": archived,
    })
    temp = status_path.with_suffix(".json.new")
    temp.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, status_path)
    print(json.dumps({"stage": status["stage"], "report": str(report_path), "archived": archived}, ensure_ascii=False))


if __name__ == "__main__":
    main()
