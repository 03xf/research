#!/usr/bin/env python3
"""Finalize long-running batch inference once the supervisor exits."""
import os
import subprocess
import time
from pathlib import Path

BASE = Path("/home/member/xmy/xmy")
RESULTS = BASE / "results/dji_all_batches"
PY = "/home/member/bin/python"
TOOLS = BASE / "code/tools"


def alive():
    out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True, check=False).stdout
    return "dji_run_batches_sequential.py" in out


def run(cmd, log):
    with log.open("a", encoding="utf-8") as fh:
        fh.write("$ " + " ".join(map(str, cmd)) + "\n")
        subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, check=False)


def main():
    log = RESULTS / "finalize_batches.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    while alive():
        time.sleep(60)
    summary_dir = RESULTS / "summary"
    summary_dir.mkdir(exist_ok=True)
    for batch in ("B1", "B2", "B3", "B4"):
        run([PY, str(TOOLS / "dji_detection_summary.py"), "--root", str(RESULTS / "inference" / batch), "--output", str(summary_dir / f"{batch}.json")], log)
    common = ["--inventory", str(RESULTS / "inventory.json"), "--sync-dir", str(RESULTS / "sync"), "--inference-root", str(RESULTS / "inference")]
    run([PY, str(TOOLS / "dji_annotation_manifest.py"), *common, "--output", str(RESULTS / "annotation_manifest.json")], log)
    run([PY, str(TOOLS / "dji_detection_quality.py"), *common, "--output", str(RESULTS / "detection_quality.json")], log)
    run([PY, str(TOOLS / "dji_batch_association.py"), *common, "--output", str(RESULTS / "tv_association.json")], log)
    run([PY, str(TOOLS / "dji_tv_tracking.py"), "--input", str(RESULTS / "tv_association.json"), "--output", str(RESULTS / "tv_tracking.json")], log)
    run([PY, str(TOOLS / "dji_stage_gate.py"), "--results", str(RESULTS), "--output", str(RESULTS / "stage_gate.json")], log)
    log.write_text(log.read_text(encoding="utf-8") + "finalized\n", encoding="utf-8")


if __name__ == "__main__":
    main()
