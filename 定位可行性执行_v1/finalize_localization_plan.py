"""Freeze inputs and assemble the full-plan closeout for the DJI localization work."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "_dji_preview"
OUT = Path(__file__).resolve().parent
SNAPSHOT = OUT / "input_snapshot"
CANDIDATE = ROOT / "b1_b3_candidate_dataset_v1"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def freeze_inputs() -> dict:
    SNAPSHOT.mkdir(parents=True, exist_ok=True)
    sources = {
        "fixed_fire_points.csv": DATA / "fixed_fire_points_server_snapshot.csv",
        "fixed_fire_observations.csv": DATA / "fixed_fire_observations.csv",
        "fixed_fire_point_summary.json": DATA / "fixed_fire_point_summary_server_snapshot.json",
    }
    frozen = []
    for name, source in sources.items():
        dest = SNAPSHOT / name
        shutil.copy2(source, dest)
        frozen.append({"file": name, "source": str(source), "snapshot": str(dest),
                       "sha256": sha256(dest), "bytes": dest.stat().st_size})
    return {"created_local_date": "2026-09-27", "source_files": frozen,
            "statement": "Read-only copies for this execution; originals on the source server were not modified."}


def candidate_split_audit() -> dict:
    manifest = json.loads((CANDIDATE / "dataset_manifest.json").read_text(encoding="utf-8"))
    rows = [json.loads(x) for x in (CANDIDATE / "candidate_frames.jsonl").read_text(encoding="utf-8").splitlines() if x]
    split_by_group = {g["group_key"]: g["split"] for g in manifest["groups"]}
    sessions: dict[str, set[str]] = defaultdict(set)
    prefixes: dict[str, set[str]] = defaultdict(set)
    groups_by_batch_split: Counter = Counter()
    frame_counts: Counter = Counter()
    event_group_counts: Counter = Counter()
    for g in manifest["groups"]:
        split = g["split"]
        sessions[g["session"]].add(split)
        prefixes[g["recording_prefix"]].add(split)
        groups_by_batch_split[(g["batch"], split)] += 1
        event_group_counts[(g["batch"], "event_dev_B3" if g["batch"] == "B3" else "event_train_B1_B2")] += 1
    for r in rows:
        frame_counts[(r["batch"], r["split"])] += 1
    session_overlap = sorted(k for k, v in sessions.items() if len(v) > 1)
    prefix_overlap = sorted(k for k, v in prefixes.items() if len(v) > 1)
    # A conservative development split that holds out the complete B3 fire event.
    # This is a split proposal only; the candidate labels are still unreviewed.
    split_rows = []
    for r in rows:
        event_split = "event_dev_B3" if r["batch"] == "B3" else "event_train_B1_B2"
        split_rows.append({"candidate_id": r["candidate_id"], "batch": r["batch"],
                           "group_key": r["group_key"], "session": r["session"],
                           "recording_prefix": r["recording_prefix"],
                           "existing_split": r["split"], "event_split_v2": event_split,
                           "label_status": r.get("review_status", "candidate_unreviewed")})
    write_csv(OUT / "candidate_event_split_v2.csv", split_rows)
    return {
        "manifest_status": manifest.get("status"), "candidate_frames": len(rows),
        "groups": len(manifest["groups"]), "existing_group_split": dict(Counter(g["split"] for g in manifest["groups"])),
        "existing_candidate_frame_split": dict(Counter(r["split"] for r in rows)),
        "existing_train_dev_session_overlap_count": len(session_overlap),
        "existing_train_dev_session_overlap": session_overlap,
        "existing_train_dev_recording_prefix_overlap_count": len(prefix_overlap),
        "existing_train_dev_recording_prefix_overlap": prefix_overlap,
        "event_split_v2": {
            "rule": "B1+B2 train; all B3 synchronized video groups dev; split by fire batch/event",
            "groups_by_batch_event_split": {f"{b}/{s}": n for (b, s), n in event_group_counts.items()},
            "existing_candidate_frames_by_batch_split": {f"{b}/{s}": n for (b, s), n in frame_counts.items()},
            "candidate_frame_assignment_counts": dict(Counter(r["event_split_v2"] for r in split_rows)),
            "label_status": "candidate_unreviewed; do not train or score until manual review",
            "file": str(OUT / "candidate_event_split_v2.csv")
        },
        "limitation": "Only three recording batches/fire events exist in B1-B3; this is an event-held-out diagnostic, not evidence of broad cross-site generalization."
    }


def association_table() -> list[dict]:
    sites = {r["site_id"]: r for r in read_csv(OUT / "site_results.csv")}
    rows = [
        ("B1_F1", "B1_F1_LRF", "事后激光参考；高概率对应", "post-fire reference; high-probability match", "yes"),
        ("B2_F1", "B2_F1_LRF", "点火前木柴堆；非燃烧期真值", "pre-fire wood-pile reference; not fire ground truth", "no"),
        ("B3_N", "B3_F1_LRF", "用户确认 F1=北侧", "user-confirmed F1=north", "yes"),
        ("B3_S", "B3_F2_LRF", "用户确认 F2=南侧", "user-confirmed F2=south", "yes"),
    ]
    output = []
    for site_id, ref_id, status, status_en, eligible in rows:
        s = sites[site_id]
        output.append({
            "video_site_id": site_id, "lrf_reference_id": ref_id,
            "identity_status": status, "identity_status_en": status_en,
            "lrf_latitude": s["reference_status"],
            "provisional_visual_latitude": s["triangulated_lat"],
            "provisional_visual_longitude": s["triangulated_lon"],
            "horizontal_difference_m": s["triangulated_horizontal_reference_error_m"],
            "reference_error_eligible": eligible,
            "coordinate_source": "visual_prediction_provisional (uncalibrated nominal geometry)",
            "absolute_wgs84_claim": "no",
            "note": "Coordinates are candidates only; B2 is excluded from fire-linked error summary." if site_id == "B2_F1" else "LRF is a limited horizontal reference; do not infer verified altitude accuracy."
        })
    # Replace the display-only value above with the actual reference coordinate using the frozen scope table.
    scope = {r["fire_point_id"]: r for r in read_csv(DATA / "fire_point_analysis_scope_v5.csv")}
    ref_ids = {"B1_F1": "B1_F1_video", "B2_F1": "B2_F1_video", "B3_N": "B3_N_video", "B3_S": "B3_S_video"}
    for r in output:
        s = scope[ref_ids[r["video_site_id"]]]
        r["lrf_latitude"] = s["latitude"]
        r["lrf_longitude"] = s["longitude"]
    write_csv(OUT / "fire_source_association_v2.csv", output)
    return output


def main() -> None:
    freeze = freeze_inputs()
    observations = read_csv(SNAPSHOT / "fixed_fire_observations.csv")
    valid = [r for r in observations if r["observation_valid"].strip().lower() == "true"]
    invalid = [r for r in observations if r["observation_valid"].strip().lower() != "true"]
    match_status = Counter(r["target_match_status"] for r in observations)
    b1_outliers = [r for r in observations if r["batch_id"] == "B1" and r["target_match_status"] == "outlier_removed"]
    valid_by_id = dict(Counter(f"{r['batch_id']}_{r['fire_id']}" for r in valid))
    fixed_points = read_csv(SNAPSHOT / "fixed_fire_points.csv")
    ref_events = read_csv(DATA / "lrf_reference_event_centers.csv")
    split = candidate_split_audit()
    associations = association_table()
    results_json = json.loads((OUT / "localization_results.json").read_text(encoding="utf-8"))
    result_summary = results_json["reference_error_summary"]
    pair_rows = read_csv(OUT / "pairwise_results.csv")
    poor_pair = next(r for r in pair_rows if r["site_id"] == "B2_F1" and r["view_1"] == "无人机06" and r["view_2"] == "无人机07")
    north_pairs = [float(r["horizontal_reference_error_m"]) for r in pair_rows if r["site_id"] == "B3_N"]
    freeze_doc = {
        "schema_version": "dji_localization_plan_execution_v2",
        "date": "2026-09-27",
        "frozen_inputs": freeze,
        "reference_audit": {
            "fixed_point_records": len(fixed_points), "observation_rows": len(observations),
            "valid_observations": len(valid), "excluded_observations": len(invalid),
            "target_match_status_counts": dict(match_status),
            "valid_observations_by_lrf_batch_point": valid_by_id,
            "B1_outlier_removed_rows": len(b1_outliers),
            "B1_outlier_distance_min_m": min(float(r["target_match_distance_m"]) for r in b1_outliers),
            "B1_outlier_distance_max_m": max(float(r["target_match_distance_m"]) for r in b1_outliers),
            "event_center_rows": len(ref_events),
            "B1_independent_LRF_events": 4, "B2_independent_LRF_events": 1,
            "B3_F1_independent_LRF_events": 1, "B3_F2_independent_LRF_events": 2,
            "B4_F1_independent_LRF_events": 9, "B4_F2_independent_LRF_events": 0,
            "b3_F1_F2_reference_separation_m": 11.4618061404,
            "B4_F2_independent_reference_found": False
        },
        "candidate_data_split_audit": split,
        "geometric_results": result_summary,
        "pairwise_diagnostics": {
            "B2_uav06_uav07_parallax_angle_deg": float(poor_pair["parallax_angle_deg_acute"]),
            "B2_uav06_uav07_horizontal_reference_difference_m": float(poor_pair["horizontal_reference_error_m"]),
            "B3_north_pairwise_difference_min_m": min(north_pairs),
            "B3_north_pairwise_difference_max_m": max(north_pairs)
        },
        "source_associations": associations,
        "training_history_summary": {
            "V_C1_training_images": 404, "V_C1_development_images": 61,
            "V_C1_seed0_development": {"precision": 0.655, "recall": 0.792, "AP50": 0.723, "threshold": 0.21},
            "V_C1_seed1_development": {"precision": 0.737, "recall": 0.583, "AP50": 0.612},
            "V_C1_seed2_development": {"precision": 0.643, "recall": 0.750, "AP50": 0.683},
            "V_C1_confirmation_194_pairs": {"precision": 0.384, "recall": 0.358, "AP50": 0.241, "gate": "failed; history-exposed confirmation set"},
            "V_C1_point_pairs": {"all": "35/52 vs E2 33/52", "B4": "17/32 vs E2 18/32", "decision": "do not deploy"},
            "T_T1_dev": {"precision": 0.611, "recall": 0.753, "AP50": 0.799, "FP": 35, "gate": "failed predeclared FP<=34 condition"},
            "T_T2_dev": {"precision": 0.600, "recall": 0.863, "AP50": 0.804, "FP": 42, "gate": "failed predeclared FP<=34 condition"},
            "deployed_model": "frozen E2 V/T; no candidate met the predeclared replacement gate"
        }
    }
    (OUT / "execution_manifest.json").write_text(json.dumps(freeze_doc, ensure_ascii=False, indent=2), encoding="utf-8")

    report = f'''# DJI 火点定位计划执行核验与结果（2026-09-27）

## 执行范围

本次按《DJI 后续火点定位实验计划》复核已完成实验、补做输入冻结与候选数据划分审计，并对已有三机像素点重跑不输入地面高程的射线交会。服务器原始视频和历史训练结果只读；新快照与派生产物保存在本地 `{OUT.name}`，另有同名服务器执行归档目录。

## 结果先看

- 四处关联位置分别是 B1 单火点、B2 点火前木柴堆参考、B3 北/南火点。B2 不是燃烧期真值，因此火点关联参考统计只看 B1 与 B3 两点，共 **3 个位置**。
- 三个火点关联参考的水平差中位数 **{result_summary['fire_linked_horizontal_error_median']:.2f} m**，最大 **{result_summary['fire_linked_horizontal_error_max']:.2f} m**。B1 为 **1.44 m**，B3 南侧为 **3.29 m**，B3 北侧为 **13.28 m**。这些差值来自名义相机模型与有限 LRF 参考，不是稳定精度估计。
- B2 与点火前木柴堆参考相差 **{result_summary['B2_prefire_site_difference_m']:.2f} m**，只作同址/几何诊断，不计入火点误差汇总。
- B3 按用户确认的 F1=北、F2=南；对调的两点差值和为 **39.15 m**，当前确认映射的两点差值和为 **16.58 m**。对调结果仅是几何一致性检查，保留用户的物理身份裁决。
- B3 北侧任一双机组合与参考的差都在 **{min(north_pairs):.2f}–{max(north_pairs):.2f} m**；B2 无人机06/07 夹角 **{float(poor_pair['parallax_angle_deg_acute']):.2f}°** 的双机组合差 **{float(poor_pair['horizontal_reference_error_m']):.2f} m**。B3 北侧不是删掉一架飞机就能消除的单机异常。
- 交会最大视线残差只有约 **{max(float(r['max_ray_residual_m']) for r in read_csv(OUT / 'site_results.csv')):.2f} m**，但 B3 北侧对参考差 **13.28 m**。因此仅用射线互相靠近作为定位可信度是不够的。

## 按原计划逐阶段核验

| 阶段 | 完成情况 | 证据与结论 |
|---|---|---|
| A 参考坐标整理 | 已完成并重新冻结 | 三份坐标源文件已作 SHA256 快照；核对 **{len(observations)} 条**照片记录，**{len(valid)} 条候选有效、{len(invalid)} 条排除**。其中 32 条被旧筛选接受、4 条 B1 行标为离群剔除（距旧中心约 {min(float(r['target_match_distance_m']) for r in b1_outliers):.2f}–{max(float(r['target_match_distance_m']) for r in b1_outliers):.2f} m）。B1 4 次、B2 1 次、B3 F1 1 次、B3 F2 2 次、B4 F1 9 次独立 LRF 事件；没有找到 B4 F2 独立坐标。B3 F1/F2 参考点相距 11.46 m。 |
| B 精简检测任务与数据检查 | 部分完成；新候选集尚不能训练 | 历史 V 单类与 T 单类数据/评估已存在；但新 B1–B3 候选集共 2,401 对仍为未复核候选。原按录像组切分有 **{len(split['existing_train_dev_session_overlap'])} 个 session** 跨 train/dev、**{len(split['existing_train_dev_recording_prefix_overlap'])} 个同步录制前缀**跨集。已生成 `candidate_event_split_v2.csv`，将整批 B3 留作事件级 dev、B1/B2 作 train；标签仍未人工审核，不得训练或报告准确率。 |
| C 检测对照与替换门槛 | 历史对照已完成；没有可替换模型 | V 单类 C1 开发集达到 P/R/AP50 门槛，但三种子差异较大；固定阈值在历史暴露的 194 对上只有 P=.384、R=.358、AP50=.241。火源点对照总体 35/52 对 E2 的 33/52，B4 主体 17/32 低于 E2 的 18/32，故不部署。T1/T2 开发结果分别为 P/R/AP50=.611/.753/.799、.600/.863/.804，但误报数 35/42 未满足预定 ≤34 规则；两者均不进入确认测试。默认 E2 V/T 保持不变。 |
| D 地面源点与同目标关联 | 部分完成 | 现有 12 个像素标注已做叠加核查，覆盖四处位置各三视角；另有历史 50 对源点复核资料，其中 10 对属于 B3。B3 双火画面曾把两个源点都记为 F1，不能直接作为跨火点 ID 真值。现有标注不是每处多时刻序列标注，不能评价持续身份稳定性；新 2,401 对候选也没有火焰/热点真值。 |
| E 固定坐标关联与候选位置输出 | 已完成有限关联 | 输出 `fire_source_association_v2.csv`，只纳入 B1、B2、B3 四个位置并标明参考语义。B1 为高概率事后对应，B2 为点火前参考，B3 F1/F2 的北/南身份按用户确认。B4 不纳入；所有视觉坐标都标 `visual_prediction_provisional`，不是校准后的 WGS84 预测精度。 |

## 定位试算和模型边界

主试算对三架无人机各一条像素射线求最小二乘最近点，**不使用地面高程**。像素内参沿用 `fx=1280*focal_len/24`、主点 `(960,540)` 的名义近似；方向目前只使用云台 yaw/pitch。它没有包含经校验的机体姿态—云台—相机完整旋转链、相机内参/畸变及相机外参。现有字幕虽然能读到部分机体/云台字段，字段不等于标定结果。

52.5 m 平面交点仅作基线对照。射线交会估出的 Z 和 LRF 原始高度基准均未验证。2,000 次敏感性扰动使用人为给定的像素、角度和焦距误差范围，不是设备实测误差、置信区间或外场重复性结论。程序合成射线自检恢复目标误差约 `2.9e-14 m`，只验证线性求解实现。

## 对论文方向的判断

数据支持把定位作为**有限参考点上的误差诊断/可信度门控探索**；目前不支持宣称已经解决稳定火源持续识别与绝对定位。最有证据的现象是：小视线残差并不排除约 13 m 的绝对偏差，而且 B3 北侧偏差跨双机组合存在。可发展的论文问题是利用几何条件、交会残差、姿态/焦距扰动和可用多机数量来判断何时输出坐标、何时拒绝输出。要把它做成可靠 EI 论文主线，还需要在多个独立火点或采集批次上获得重复时刻的人工源点与独立坐标参考；当前三个可用于火点关联的参考位置远不足以训练/验证通用置信阈值。

## 产物

- `定位可行性执行报告.md`：交会计算、误差表、身份检查、双机几何、敏感性和局限。
- `execution_manifest.json`：冻结输入 SHA256、原始坐标统计、切分审计和模型历史结果。
- `site_results.csv`、`pairwise_results.csv`、`sensitivity_results.csv`、`b3_identity_diagnostic.csv`。
- `fire_source_association_v2.csv`：火点身份、参考坐标、候选视觉坐标与来源状态。
- `candidate_event_split_v2.csv`：2,401 对候选按整批次留出的新切分清单；没有改动标签或原图。
- `point_overlays/` 与 `point_overlays_montage.jpg`：12 个既有标注点的视图核验。
- `run_localization_audit.py`、`finalize_localization_plan.py`：重现实验与本次审计脚本。
'''
    (OUT / "完整计划执行核验.md").write_text(report, encoding="utf-8")
    print(json.dumps({"execution_manifest": str(OUT / "execution_manifest.json"),
                      "report": str(OUT / "完整计划执行核验.md"),
                      "candidate_event_split": split["event_split_v2"],
                      "session_overlap": split["existing_train_dev_session_overlap_count"],
                      "recording_prefix_overlap": split["existing_train_dev_recording_prefix_overlap_count"],
                      "reference_rows": len(associations)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
