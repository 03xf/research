"""Reproduce the existing B1-B3 multiview geolocation estimates and diagnostics.

Inputs are existing local review artifacts copied from the server audit. This
script does not read or modify source videos. Pixel marks and telemetry remain
nominal/provisional; Monte Carlo results are sensitivity tests, not confidence
intervals.
"""
from __future__ import annotations

import csv
import itertools
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "_dji_preview"
OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)
ORIGIN_LAT, ORIGIN_LON = 31.2897, 120.4727
METERS_PER_DEG_LAT = 111_186.0
METERS_PER_DEG_LON = 95_194.0
GROUND_Z_ASSUMPTION_M = 52.5
RNG_SEED = 20260927
MONTE_CARLO_N = 2000

REFERENCES = {
    "B1_F1": (31.2891377, 120.47274985, "post-fire LRF; correspondence high probability"),
    "B2_F1": (31.2894735, 120.47280310, "pre-fire wood pile LRF; same physical site"),
    "B3_N": (31.2897849, 120.47272210, "B3_F1; north correspondence user-confirmed"),
    "B3_S": (31.2896853, 120.47275315, "B3_F2; south correspondence user-confirmed"),
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def to_enu(lat: float, lon: float) -> np.ndarray:
    return np.array([(lon - ORIGIN_LON) * METERS_PER_DEG_LON,
                     (lat - ORIGIN_LAT) * METERS_PER_DEG_LAT], dtype=float)


def from_local(point: np.ndarray) -> tuple[float, float, float]:
    return (ORIGIN_LAT + point[1] / METERS_PER_DEG_LAT,
            ORIGIN_LON + point[0] / METERS_PER_DEG_LON,
            float(point[2]))


def pose_ray(row: dict, xy: tuple[float, float], *, focal_scale: float = 1.0,
             yaw_delta_deg: float = 0.0, pitch_delta_deg: float = 0.0,
             pixel_delta: tuple[float, float] = (0.0, 0.0)) -> tuple[np.ndarray, np.ndarray]:
    """Approximate camera ray using the project's legacy focal-length convention."""
    center = np.array([(float(row["longitude"]) - ORIGIN_LON) * METERS_PER_DEG_LON,
                       (float(row["latitude"]) - ORIGIN_LAT) * METERS_PER_DEG_LAT,
                       float(row["abs_alt"])], dtype=float)
    yaw, pitch = map(math.radians, (float(row["gb_yaw"]) + yaw_delta_deg,
                                    float(row["gb_pitch"]) + pitch_delta_deg))
    forward = np.array([math.cos(pitch) * math.sin(yaw),
                        math.cos(pitch) * math.cos(yaw), math.sin(pitch)])
    right = np.array([math.cos(yaw), -math.sin(yaw), 0.0])
    up = np.cross(right, forward)
    # This is the legacy assumed model: 35-mm-equivalent focal length, 36-mm
    # sensor width represented by 1280*F/24. The camera calibration is unknown.
    focal_px = 1280.0 * float(row["focal_len"]) / 24.0 * focal_scale
    x = float(xy[0]) + pixel_delta[0]
    y = float(xy[1]) + pixel_delta[1]
    direction = forward + (x - 960.0) / focal_px * right - (y - 540.0) / focal_px * up
    return center, direction / np.linalg.norm(direction)


def intersect(rays: list[tuple[np.ndarray, np.ndarray]]) -> tuple[np.ndarray, list[float], float]:
    a = np.zeros((3, 3), dtype=float)
    b = np.zeros(3, dtype=float)
    for center, direction in rays:
        projector = np.eye(3) - np.outer(direction, direction)
        a += projector
        b += projector @ center
    point = np.linalg.lstsq(a, b, rcond=None)[0]
    residuals = [float(np.linalg.norm(np.cross(point - c, d))) for c, d in rays]
    return point, residuals, float(np.linalg.cond(a))


def plane_hit(ray: tuple[np.ndarray, np.ndarray], z: float) -> np.ndarray:
    center, direction = ray
    if abs(direction[2]) < 1e-9:
        return np.array([np.nan, np.nan, np.nan])
    return center + ((z - center[2]) / direction[2]) * direction


def h_error(point: np.ndarray, ref: tuple[float, float, str]) -> float:
    return float(np.linalg.norm(point[:2] - to_enu(ref[0], ref[1])))


def distance_between_latlon(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    a = to_enu(a_lat, a_lon)
    b = to_enu(b_lat, b_lon)
    return float(np.linalg.norm(a - b))


def b3_identity_diagnostic(results: list[dict]) -> dict:
    """Compare user-confirmed B3 identity with the alternative swapped mapping."""
    by_id = {r["site_id"]: r for r in results}
    north, south = by_id["B3_N"], by_id["B3_S"]
    ref_n, ref_s = REFERENCES["B3_N"], REFERENCES["B3_S"]
    north_to_north = distance_between_latlon(north["triangulated_lat"], north["triangulated_lon"], ref_n[0], ref_n[1])
    south_to_south = distance_between_latlon(south["triangulated_lat"], south["triangulated_lon"], ref_s[0], ref_s[1])
    north_to_south = distance_between_latlon(north["triangulated_lat"], north["triangulated_lon"], ref_s[0], ref_s[1])
    south_to_north = distance_between_latlon(south["triangulated_lat"], south["triangulated_lon"], ref_n[0], ref_n[1])
    return {
        "identity_source": "scope_v5_and_user_confirmation: F1=north, F2=south",
        "confirmed_mapping": {"B3_N_estimate_to_B3_F1_reference_m": north_to_north,
                              "B3_S_estimate_to_B3_F2_reference_m": south_to_south,
                              "sum_of_two_horizontal_differences_m": north_to_north + south_to_south},
        "swapped_mapping_diagnostic_only": {"B3_N_estimate_to_B3_F2_reference_m": north_to_south,
                                            "B3_S_estimate_to_B3_F1_reference_m": south_to_north,
                                            "sum_of_two_horizontal_differences_m": north_to_south + south_to_north},
        "interpretation": "The user-confirmed identity is retained. The swapped calculation is only a consistency check and does not override the physical identity decision."
    }


def make_observations() -> list[dict]:
    site_doc = read_json(DATA / "six_fire_video_sites_v1.json")
    b3_doc = read_json(DATA / "b3_fire_geolocation.json")
    sites = {s["site_id"]: s for s in site_doc["sites"]}
    telemetry = {}
    for batch in ("b1", "b2", "b3"):
        with (DATA / f"{batch}_telemetry.csv").open(encoding="utf-8-sig", newline="") as f:
            telemetry[batch.upper()] = list(csv.DictReader(f))

    observations = []
    for site_id, ref_id in (("B1_video_fire", "B1_F1"), ("B2_video_fire", "B2_F1")):
        site = sites[site_id]
        by_drone = {r["drone"].split("_")[0]: r for r in telemetry[site["batch_id"]]}
        views = []
        for view in site["views"]:
            drone = view["drone"]
            views.append({"drone": drone, "xy": (float(view["x_px"]), float(view["y_px"])),
                          "telemetry": by_drone[drone], "frame": view["source_frame"],
                          "offset_s": by_drone[drone]["offset_s"]})
        observations.append({"site_id": ref_id, "source": "existing manual ground-contact marks",
                             "views": views, "reference": REFERENCES[ref_id]})

    by_drone_b3 = {r["drone"].split("_")[0]: r for r in telemetry["B3"]}
    for old_name, site_id, ref_id in (("B3_northwest_fire", "B3_N_video", "B3_N"),
                                      ("B3_southeast_fire", "B3_S_video", "B3_S")):
        old = next(s for s in b3_doc["sites"] if s["point_id"] == old_name)
        views = []
        for view in old["views"]:
            drone = view["drone"]
            row = by_drone_b3[drone]
            frame_matches = list(DATA.glob(f"{drone}_*{row['session']}_frame.jpg"))
            views.append({"drone": drone, "xy": (float(view["x_px"]), float(view["y_px"])),
                          "telemetry": row, "frame": frame_matches[0].name if frame_matches else "",
                          "offset_s": row["offset_s"]})
        observations.append({"site_id": ref_id, "source": "existing B3 manual marks; physical identity from scope v5",
                             "views": views, "reference": REFERENCES[ref_id]})
    return observations


def run_self_checks() -> dict:
    # Synthetic rays point toward one known 3D point; solution must recover it.
    target = np.array([10.0, 20.0, 30.0])
    centers = [np.array([-20., 0., 60.]), np.array([35., 5., 70.]), np.array([0., 50., 55.])]
    rays = [(c, (target - c) / np.linalg.norm(target - c)) for c in centers]
    got, residuals, _ = intersect(rays)
    err = float(np.linalg.norm(got - target))
    assert err < 1e-8 and max(residuals) < 1e-8
    return {"synthetic_3d_intersection_pass": True, "recovered_point_error_m": err,
            "max_ray_residual_m": max(residuals)}


def analyze_site(obs: dict) -> tuple[dict, list[dict], list[dict]]:
    base_rays = [pose_ray(v["telemetry"], v["xy"]) for v in obs["views"]]
    point, residuals, condition = intersect(base_rays)
    ground_hits = [plane_hit(r, GROUND_Z_ASSUMPTION_M) for r in base_rays]
    plane_median = np.median(np.array(ground_hits), axis=0)
    ref = obs["reference"]
    row = {
        "site_id": obs["site_id"], "reference_status": ref[2],
        "view_count": len(obs["views"]), "triangulated_lat": from_local(point)[0],
        "triangulated_lon": from_local(point)[1], "triangulated_alt_m_unverified": point[2],
        "triangulated_horizontal_reference_error_m": h_error(point, ref),
        "ray_residuals_m": residuals, "median_ray_residual_m": float(np.median(residuals)),
        "max_ray_residual_m": max(residuals), "intersection_condition_number": condition,
        "assumed_plane_z_m": GROUND_Z_ASSUMPTION_M,
        "plane_median_lat": from_local(plane_median)[0], "plane_median_lon": from_local(plane_median)[1],
        "plane_horizontal_reference_error_m": h_error(plane_median, ref),
        "plane_view_spread_m": max(float(np.linalg.norm(g[:2] - plane_median[:2])) for g in ground_hits),
        "views": []
    }
    for v, ray, ground in zip(obs["views"], base_rays, ground_hits):
        row["views"].append({"drone": v["drone"], "offset_s": float(v["offset_s"]),
                              "xy_px": list(v["xy"]), "frame": v["frame"],
                              "ground_projection_lat": from_local(ground)[0],
                              "ground_projection_lon": from_local(ground)[1],
                              "depth_to_intersection_m": float(np.dot(point - ray[0], ray[1]))})
    pair_rows = []
    for indices in itertools.combinations(range(len(obs["views"])), 2):
        sub = [base_rays[i] for i in indices]
        p, r, cond = intersect(sub)
        cosang = float(np.clip(np.dot(sub[0][1], sub[1][1]), -1.0, 1.0))
        angle = math.degrees(math.acos(abs(cosang)))
        pair_rows.append({"site_id": obs["site_id"], "view_1": obs["views"][indices[0]]["drone"],
                          "view_2": obs["views"][indices[1]]["drone"],
                          "parallax_angle_deg_acute": angle,
                          "horizontal_reference_error_m": h_error(p, ref),
                          "triangulated_altitude_m_unverified": float(p[2]),
                          "max_ray_residual_m": max(r), "condition_number": cond})

    rng = np.random.default_rng(RNG_SEED + sum(ord(c) for c in obs["site_id"]))
    scenarios = [("pixel_sigma_1px", 1, 0, 0), ("pixel_sigma_3px", 3, 0, 0),
                 ("pixel_sigma_5px", 5, 0, 0), ("pixel_sigma_10px", 10, 0, 0),
                 ("angle_sigma_0p1deg", 0, 0.1, 0), ("angle_sigma_0p5deg", 0, 0.5, 0),
                 ("angle_sigma_1deg", 0, 1.0, 0), ("focal_sigma_1pct", 0, 0, 0.01),
                 ("focal_sigma_5pct", 0, 0, 0.05), ("focal_sigma_10pct", 0, 0, 0.10),
                 ("combined_3px_0p5deg_5pct", 3, 0.5, 0.05)]
    sensitivity = []
    for name, pixel_sigma, angle_sigma, focal_sigma in scenarios:
        shifts, ref_errors = [], []
        for _ in range(MONTE_CARLO_N):
            scale = max(0.1, 1.0 + rng.normal(0, focal_sigma)) if focal_sigma else 1.0
            perturbed = []
            for v in obs["views"]:
                px = (rng.normal(0, pixel_sigma), rng.normal(0, pixel_sigma)) if pixel_sigma else (0., 0.)
                dy = rng.normal(0, angle_sigma) if angle_sigma else 0.
                dp = rng.normal(0, angle_sigma) if angle_sigma else 0.
                perturbed.append(pose_ray(v["telemetry"], v["xy"], focal_scale=scale,
                                          yaw_delta_deg=dy, pitch_delta_deg=dp, pixel_delta=px))
            p, _, _ = intersect(perturbed)
            shifts.append(float(np.linalg.norm(p[:2] - point[:2])))
            ref_errors.append(h_error(p, ref))
        sensitivity.append({"site_id": obs["site_id"], "scenario": name, "draws": MONTE_CARLO_N,
                            "horizontal_shift_p50_m": float(np.quantile(shifts, .5)),
                            "horizontal_shift_p95_m": float(np.quantile(shifts, .95)),
                            "reference_error_p50_m": float(np.quantile(ref_errors, .5)),
                            "reference_error_p95_m": float(np.quantile(ref_errors, .95))})
    return row, pair_rows, sensitivity


def draw_overlays(observations: list[dict]) -> list[str]:
    out_dir = OUT / "point_overlays"
    out_dir.mkdir(exist_ok=True)
    written = []
    for obs in observations:
        for idx, view in enumerate(obs["views"], 1):
            if not view["frame"]:
                continue
            path = DATA / view["frame"]
            if not path.exists():
                continue
            image = Image.open(path).convert("RGB")
            draw = ImageDraw.Draw(image)
            x, y = view["xy"]
            draw.ellipse((x - 12, y - 12, x + 12, y + 12), outline=(255, 0, 0), width=4)
            draw.line((x - 20, y, x + 20, y), fill=(255, 0, 0), width=3)
            draw.line((x, y - 20, x, y + 20), fill=(255, 0, 0), width=3)
            draw.rectangle((10, 10, 520, 58), fill=(0, 0, 0))
            draw.text((20, 20), f"{obs['site_id']} | {view['drone']} | px=({x:.0f},{y:.0f})", fill=(255, 255, 0))
            dest = out_dir / f"{obs['site_id']}_{idx}_{view['drone']}.jpg"
            image.save(dest, quality=94)
            written.append(str(dest.relative_to(OUT)))
    return written


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    observations = make_observations()
    results, pairs, sensitivity = [], [], []
    for obs in observations:
        row, pair_rows, sens = analyze_site(obs)
        results.append(row)
        pairs.extend(pair_rows)
        sensitivity.extend(sens)
    b3_identity = b3_identity_diagnostic(results)
    overlays = draw_overlays(observations)
    checks = run_self_checks()
    result_doc = {
        "schema_version": "localization_feasibility_execution_v1",
        "input_scope": "B1-B3; four linked locations (B1 and B3 north/south fire references, plus B2 pre-fire pile reference); one existing multiview snapshot per location",
        "algorithm": "least-squares closest point to camera rays; no ground-elevation input",
        "camera_model": "legacy nominal focal conversion fx=1280*focal_len/24; principal point=(960,540); not calibrated",
        "monte_carlo": {"seed": RNG_SEED, "draws_per_scenario": MONTE_CARLO_N,
                        "interpretation": "sensitivity only; perturbation ranges are analyst-selected, not measured sensor distributions"},
        "self_checks": checks,
        "b3_identity_diagnostic": b3_identity,
        "reference_error_summary": {
            "fire_linked_sites": ["B1_F1", "B3_N", "B3_S"],
            "fire_linked_site_count": 3,
            "fire_linked_horizontal_error_median": float(np.median([r["triangulated_horizontal_reference_error_m"] for r in results if r["site_id"] != "B2_F1"])),
            "fire_linked_horizontal_error_max": max(r["triangulated_horizontal_reference_error_m"] for r in results if r["site_id"] != "B2_F1"),
            "B2_prefire_site_difference_m": next(r["triangulated_horizontal_reference_error_m"] for r in results if r["site_id"] == "B2_F1"),
            "warning": "B2 is a pre-fire pile reference and is excluded from the fire-linked error summary."
        },
        "sites": results,
        "pairwise": pairs,
        "sensitivity": sensitivity,
        "point_overlays": overlays,
        "limits": ["B1/B2 coordinates are existing one-snapshot manual marks; B3 uses existing three-view marks.",
                   "B1-B3 temporal stability is not measured by this execution.",
                   "LRF targets are limited reference points; B1 is post-fire and B2 is pre-fire.",
                   "No per-camera intrinsic/distortion or camera-gimbal/body extrinsic calibration was available.",
                   "Absolute altitude datum compatibility is unverified; triangulated z is diagnostic only.",
                   "A small ray residual measures mutual ray consistency, not absolute position accuracy."]}
    (OUT / "localization_results.json").write_text(json.dumps(result_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    flat_results = [{k: v for k, v in row.items() if k != "views" and k != "ray_residuals_m"} for row in results]
    write_csv(OUT / "site_results.csv", flat_results)
    write_csv(OUT / "pairwise_results.csv", pairs)
    write_csv(OUT / "sensitivity_results.csv", sensitivity)
    write_csv(OUT / "b3_identity_diagnostic.csv", [
        {"mapping": "user_confirmed_F1_north_F2_south",
         "north_estimate_to_north_F1_reference_m": b3_identity["confirmed_mapping"]["B3_N_estimate_to_B3_F1_reference_m"],
         "south_estimate_to_south_F2_reference_m": b3_identity["confirmed_mapping"]["B3_S_estimate_to_B3_F2_reference_m"],
         "sum_horizontal_difference_m": b3_identity["confirmed_mapping"]["sum_of_two_horizontal_differences_m"]},
        {"mapping": "swapped_diagnostic_only",
         "north_estimate_to_south_F2_reference_m": b3_identity["swapped_mapping_diagnostic_only"]["B3_N_estimate_to_B3_F2_reference_m"],
         "south_estimate_to_north_F1_reference_m": b3_identity["swapped_mapping_diagnostic_only"]["B3_S_estimate_to_B3_F1_reference_m"],
         "sum_horizontal_difference_m": b3_identity["swapped_mapping_diagnostic_only"]["sum_of_two_horizontal_differences_m"]},
    ])
    lines = [
        "# 苏州多机火源定位可行性执行结果 v2", "",
        "本报告复用了现有 B1/B2/B3 人工像素点、逐帧字幕遥测和 LRF 对应表，并重新运行不输入地面高度的三维多视线交会。原始服务器数据未改动。", "",
        "## 执行范围", "",
        "- 纳入四处关联位置：B1 单火点、B2 点火前木柴堆参考、B3 北/南两个火点；B4 按既有范围排除。B2 单列为点火前参考，不计入火点参考误差汇总。",
        "- 四处关联位置各使用已有一组三机像素点，共 12 条观测；其中 B2 仅为点火前木柴堆参考，不纳入火点误差统计；未新增人工标注。",
        "- B1/B2 使用现存 `six_fire_video_sites_v1.json` 点位；B3 使用现存三视角点位，并按 scope v5 将西北组映射到北侧、东南组映射到南侧。",
        "- 主结果为三维射线最小二乘交会，不输入目标地面高程。假设地面高程 52.5 m 的平面投影只列作对照。", "",
        "## 定位结果", "",
        "| 火点 | 无地面高度交会与参考水平差 | 最大射线残差 | 52.5 m 平面参考差 | 判断 |",
        "|---|---:|---:|---:|---|"
    ]
    labels = {"B1_F1": "B1 单火点", "B2_F1": "B2 单火点", "B3_N": "B3 北侧", "B3_S": "B3 南侧"}
    for r in results:
        lines.append(f"| {labels[r['site_id']]} | {r['triangulated_horizontal_reference_error_m']:.2f} m | {r['max_ray_residual_m']:.2f} m | {r['plane_horizontal_reference_error_m']:.2f} m | {r['reference_status']} |")
    fire_linked = [r for r in results if r["site_id"] != "B2_F1"]
    b2_result = next(r for r in results if r["site_id"] == "B2_F1")
    lines += ["", "三处火点关联参考（B1、B3 北、B3 南）的水平差中位数 **%.2f m**，最大 **%.2f m**；B2 点火前木柴堆参考另列，差 **%.2f m**，不并入火点误差统计。统计单位是位置，不是视线或重复帧。" % (float(np.median([r['triangulated_horizontal_reference_error_m'] for r in fire_linked])), max(r['triangulated_horizontal_reference_error_m'] for r in fire_linked), b2_result['triangulated_horizontal_reference_error_m']),
              "", "### B3 身份映射核对", "",
              "按用户确认的 F1=北、F2=南，北/南交会点与各自参考的水平差分别为 **%.2f m / %.2f m**，两点差值和为 **%.2f m**。仅作身份一致性诊断的对调映射，其对应差分别为 **%.2f m / %.2f m**，两点差值和为 **%.2f m**。因此报告保留用户确认的物理身份；该几何比较不构成新的身份真值，也不能解释北侧约 13 m 的误差来源。" % (
                  b3_identity["confirmed_mapping"]["B3_N_estimate_to_B3_F1_reference_m"],
                  b3_identity["confirmed_mapping"]["B3_S_estimate_to_B3_F2_reference_m"],
                  b3_identity["confirmed_mapping"]["sum_of_two_horizontal_differences_m"],
                  b3_identity["swapped_mapping_diagnostic_only"]["B3_N_estimate_to_B3_F2_reference_m"],
                  b3_identity["swapped_mapping_diagnostic_only"]["B3_S_estimate_to_B3_F1_reference_m"],
                  b3_identity["swapped_mapping_diagnostic_only"]["sum_of_two_horizontal_differences_m"]),
              "", "## 结果解释", "",
              "B1 和 B3 南侧的火点关联参考差约为 1.44 m、3.29 m；B3 北侧约 13.28 m，是明显异常点。B2 另有约 2.22 m 的点火前堆址差，不是燃烧期真值。四处结果的最大射线残差约 %.2f m，但 B3 北侧仍偏离参考点约 %.2f m，直接说明射线彼此接近不能证明绝对坐标准确。" % (max(r['max_ray_residual_m'] for r in results), next(r['triangulated_horizontal_reference_error_m'] for r in results if r['site_id']=='B3_N')),
              "", "三维交会与假设高程平面结果不同：B1 从约 %.2f m 变为 %.2f m，B2 从约 %.2f m 变为 %.2f m。该对照表明预设地面高度会改变估计，但本轮没有验证字幕绝对高度与目标高程使用同一基准；估计的三维高度只能视作几何诊断值。" % (next(r['plane_horizontal_reference_error_m'] for r in results if r['site_id']=='B1_F1'), next(r['triangulated_horizontal_reference_error_m'] for r in results if r['site_id']=='B1_F1'), next(r['plane_horizontal_reference_error_m'] for r in results if r['site_id']=='B2_F1'), next(r['triangulated_horizontal_reference_error_m'] for r in results if r['site_id']=='B2_F1')),
              "", "B1 的激光记录是事后炭化堆参考，B2 是点火前木柴堆参考；它们并不等同于燃烧过程中每一帧的火焰中心真值。B3 北侧偏差需要核查点位映射、火堆接地点定义、焦距/姿态模型和 LR​​F 对应坐标，不能直接归因于某一个因素。", "",
              "## 机位几何与敏感性", "",
              "每组机位的视线夹角、条件数及双机组合误差见 `pairwise_results.csv`。B2 的无人机06/07 夹角约 19.02°，该双机组合差约 10.96 m；B3 北侧三种双机组合差均约 12.54–13.87 m，暂不能把偏差归因于单架无人机。像素取点、焦距和角度误差按指定范围分别进行 2,000 次扰动，结果见 `sensitivity_results.csv`。这些扰动幅度是诊断假设，不是该机型已测出的误差分布，不能解释为置信区间。", "",
              "当前射线实现只将云台 yaw/pitch 与名义焦距代入近似模型，没有把机体 roll/pitch/yaw、云台 roll、相机—云台/机体外参和镜头畸变组成经标定的完整姿态链。遥测中有部分姿态字段，不等于变换约定和外参已经验证；绝对坐标偏差可能来自像素点、相机参数、姿态/坐标基准或参考点物理定义。", "",
              "## 能否继续做定位", "",
              "结论是**可以继续做定位研究，但目前只能作为有边界的可行性课题**。按三处火点关联参考统计，水平差中位数为 %.2f m、最大 %.2f m；B3 北侧仍有约 13 m 偏差。四个关联位置只有一个时刻的三机观测，且一个参考为点火前木柴堆，不足以宣称稳定精度或跨场景泛化。现有资料支持复现多机几何、定位误差归因和有限参考点验证。" % (float(np.median([r['triangulated_horizontal_reference_error_m'] for r in fire_linked])), max(r['triangulated_horizontal_reference_error_m'] for r in fire_linked)), "",
              "下一步最有研究价值的技术切口是定位质量判别：利用交会夹角、射线残差、姿态/焦距敏感性识别何时坐标可靠，并对 B3 北侧这类情况拒绝输出或提示需要校准。若人工点之间本身不一致，先改善源点标注；若人工点仍出现大参考差，核心工作应放在几何参数与误差建模。", "",
              "## 计划完成度与边界", "",
              "本次已完成文件核对、旧结果重算、无地面高度三维交会、平面基线对照、机位组合检查、参数敏感性计算、正确性自检和结果报告。由于现有材料只提供每处一个多机快照，本次没有声称完成每处 10 个时刻的独立人工标注，也没有声称验证了跨时间定位稳定性。自动火源点、双人标注一致性和新相机标定仍未完成。完整计划的分阶段状态见 `完整计划执行核验.md`。", "",
              "## 产物", "",
              "- `localization_results.json`：完整输入点、参数、逐火点坐标、误差和敏感性结果。",
              "- `site_results.csv`、`pairwise_results.csv`、`sensitivity_results.csv`：便于复查的表格。",
              "- `b3_identity_diagnostic.csv`：用户确认映射与对调映射的参考差对照。",
              "- `point_overlays/`：每条已有像素点的图像叠加预览。",
              "- `run_localization_audit.py`：从现有本地审计材料重跑全部计算。", ""]
    (OUT / "定位可行性执行报告.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"report": str(OUT / "定位可行性执行报告.md"), "sites": flat_results,
                      "pairs": len(pairs), "sensitivity_rows": len(sensitivity),
                      "overlays": len(overlays), "self_checks": checks}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
