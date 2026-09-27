#!/usr/bin/env python3
"""Group LRF records by target coordinate before computing errors."""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean


def dist(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-dir", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    batches = {}
    for path in sorted(args.audit_dir.glob("B*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        groups = defaultdict(list)
        for item in data.get("images", {}).get("files", []):
            try:
                lat, lon, alt = float(item["LRFTargetLat"]), float(item["LRFTargetLon"]), float(item["LRFTargetAlt"])
            except (KeyError, TypeError, ValueError):
                continue
            key = (round(lat, 7), round(lon, 7), round(alt, 3))
            groups[key].append({"source": item.get("source"), "lat": lat, "lon": lon, "alt": alt})
        output_groups = []
        for key, rows in sorted(groups.items()):
            lat, lon, alt = key
            horiz = [dist(lat, lon, row["lat"], row["lon"]) for row in rows]
            vert = [row["alt"] - alt for row in rows]
            output_groups.append({"reference": {"lat": lat, "lon": lon, "alt": alt}, "count": len(rows), "mean_horizontal_spread_m": mean(horiz) if horiz else None, "max_horizontal_spread_m": max(horiz, default=None), "rmse_3d_spread_m": math.sqrt(mean([h*h+v*v for h, v in zip(horiz, vert)])) if rows else None, "observations": rows})
        batches[path.stem] = {"group_count": len(output_groups), "groups": output_groups, "interpretation": "coordinate spread within each LRF target group; not flame-center error"}
    payload = {"schema_version": "dji_lrf_grouped_v1", "batches": batches}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({b: v["group_count"] for b, v in batches.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
