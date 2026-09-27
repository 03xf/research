#!/usr/bin/env python3
"""Quantify within-session LRF spread without inventing target identities."""
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/localization")
source = root / "lrf_capture_groups_round12.json"
target = root / "lrf_session_dispersion_v1.json"
if target.exists():
    raise SystemExit("output exists; refusing to overwrite")
groups = json.loads(source.read_text(encoding="utf-8"))["capture_groups"]


def error(a, b):
    r1, r2 = map(math.radians, (a["latitude"], b["latitude"]))
    dlat, dlon = r2 - r1, math.radians(b["longitude"] - a["longitude"])
    h = math.sin(dlat / 2) ** 2 + math.cos(r1) * math.cos(r2) * math.sin(dlon / 2) ** 2
    horizontal = 2 * 6371008.8 * math.asin(min(1, math.sqrt(h)))
    return horizontal, math.hypot(horizontal, a["altitude"] - b["altitude"])


sessions = defaultdict(list)
for group in groups:
    if group["batch_id"] not in {"B1", "B3"}:
        continue
    refs = group["lrf_reference_by_sensor"]
    selected = refs.get("T") or refs.get("V")
    sessions[(group["batch_id"], group["session_id"])].append({"capture_key": group["capture_key"], "drone_id": group["drone_id"], "representative_sensor": "T" if refs.get("T") else "V", "coordinate": selected})

rows = []
for (batch, session), captures in sorted(sessions.items()):
    distances = [error(a["coordinate"], b["coordinate"])[0] for a, b in combinations(captures, 2)]
    rows.append({"batch_id": batch, "session_id": session, "capture_group_count": len(captures), "pairwise_horizontal_min_m": min(distances) if distances else None, "pairwise_horizontal_median_m": statistics.median(distances) if distances else None, "pairwise_horizontal_max_m": max(distances) if distances else None, "captures": captures, "physical_target_identity": "unverified"})

doc = {"schema_version": "dji_lrf_session_dispersion_v1", "generated_utc": datetime.now(timezone.utc).isoformat(), "source": str(source), "sessions": rows, "interpretation": "Dispersion between LRF photo capture groups is not positioning error; groups may target different physical objects, so B1/B3 must not be averaged as one reference point."}
target.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps([{k: row[k] for k in ("batch_id", "session_id", "capture_group_count", "pairwise_horizontal_max_m")} for row in rows]))
