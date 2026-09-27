#!/usr/bin/env python3
"""Emit explicit gates for the long-running DJI experiment."""
import argparse
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    summaries = {b: read(args.results / "summary" / f"{b}.json") for b in ("B1", "B2", "B3", "B4")}
    manifest = read(args.results / "annotation_manifest.json")
    quality = read(args.results / "detection_quality.json")
    matrix = read(args.results / "parameter_matrix.json") or {}
    calibration_available = False
    for batch in matrix.get("batches", {}).values():
        focal = batch.get("CalibratedFocalLength", {})
        if focal.get("available_count", 0) > 0:
            calibration_available = True
    labels_ready = False
    if manifest:
        labels_ready = any(obs.get("annotation", {}).get("annotation_quality") in {"clear", "weak"} and (obs.get("annotation", {}).get("visible_labels") or obs.get("annotation", {}).get("thermal_labels")) for obs in manifest.get("observations", []))
    gates = {
        "coarse_inference_complete": all(summaries.values()),
        "annotation_candidates_ready": bool(manifest and manifest.get("summary", {}).get("observation_count", 0) > 0),
        "manual_labels_ready": labels_ready,
        "dji_adaptation_allowed": bool(labels_ready and all(summaries.values())),
        "absolute_3d_localization_allowed": calibration_available,
        "quality_report_available": bool(quality),
        "current_localization_mode": "absolute_3d" if calibration_available else "degraded_relative_lrf",
        "blocking_reasons": []
    }
    if not gates["coarse_inference_complete"]:
        gates["blocking_reasons"].append("B1-B4粗采样尚未全部完成")
    if not gates["manual_labels_ready"]:
        gates["blocking_reasons"].append("候选观测尚未完成人工标注")
    if not gates["absolute_3d_localization_allowed"]:
        gates["blocking_reasons"].append("DJI文件中未发现可用标定焦距/光心，保持降级定位")
    payload = {"schema_version": "dji_stage_gate_v1", "gates": gates}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(gates, ensure_ascii=False))


if __name__ == "__main__":
    main()
