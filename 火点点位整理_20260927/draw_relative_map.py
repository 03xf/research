"""Draw a relative plan from the checked WGS84 coordinate inventory.

The EN conversion uses WGS84 local radii at B2. Across this ~130 m site,
this is a plotting approximation; it does not change source accuracy.
"""
from pathlib import Path
import csv
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

OUT = Path(__file__).resolve().parent
ORIGIN = (31.2894735, 120.4728031)  # B2 F1 LRF, lat/lon
VISUAL = {
    "B1": (31.289135169827922, 120.47276468042757, "三机交会；事后堆址"),
    "B2": (31.289492257070467, 120.47279523781181, "三机交会；点火前堆址"),
    "B3-N": (31.28989407954833, 120.47266545241642, "三机交会；无可信对应LRF"),
    "B3-S": (31.289663173674935, 120.47277613027067, "三机交会；F2候选对应"),
    "B4-E": (31.2887792678, 120.4727584031, "假设地面平面多视角近似"),
    "B4-W": (31.2888262887, 120.4724890680, "假设地面平面多视角近似"),
}
LRF = {
    "B1-LRF": (31.2891377, 120.47274985, "事后炭化堆；高概率对应B1"),
    "B2-LRF": (31.2894735, 120.4728031, "点火前木柴堆；与B4-F1同址"),
    "B3-F1": (31.2897849, 120.4727221, "疑似中间枝柴堆；不对应已证实北火"),
    "B3-F2": (31.2896853, 120.47275315, "南侧火点候选对应"),
    "B4-F1": (31.2894814, 120.4728076, "与B2同址；不是B4东/西火点"),
}

lat0 = math.radians(ORIGIN[0])
a = 6378137.0
e2 = 0.00669437999014
M = a * (1 - e2) / (1 - e2 * math.sin(lat0) ** 2) ** 1.5
N = a / math.sqrt(1 - e2 * math.sin(lat0) ** 2)
Y_PER_DEG = math.pi / 180 * M
X_PER_DEG = math.pi / 180 * N * math.cos(lat0)


def en(lat, lon):
    return ((lon - ORIGIN[1]) * X_PER_DEG, (lat - ORIGIN[0]) * Y_PER_DEG)


def distance(a, b):
    ax, ay = en(*a[:2])
    bx, by = en(*b[:2])
    return math.hypot(bx - ax, by - ay)


rows = []
for source, group in (("visual_provisional", VISUAL), ("LRF_record", LRF)):
    for name, (lat, lon, note) in group.items():
        east, north = en(lat, lon)
        rows.append({"point_id": name, "source": source, "latitude": f"{lat:.10f}",
                     "longitude": f"{lon:.10f}", "east_of_B2_m": f"{east:.2f}",
                     "north_of_B2_m": f"{north:.2f}", "interpretation": note})
with (OUT / "点位与相对坐标.csv").open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)

plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["svg.fonttype"] = "none"
fig, (ax, bx) = plt.subplots(1, 2, figsize=(15.8, 8.6), gridspec_kw={"width_ratios": [1.05, 1]})
fig.subplots_adjust(left=.075, right=.96, top=.84, bottom=.18, wspace=.27)
fig.suptitle("四批六处视频火点：相对点位", fontsize=19, fontweight="bold", y=.965)
fig.text(.5, .915, "B2 点火前 LRF 为原点 (0, 0)  ·  横轴向东 / 纵轴向北  ·  距离单位：米", ha="center", fontsize=11)


def base_axes(axes, title):
    axes.set_title(title, fontsize=14, pad=12, fontweight="bold")
    axes.set_xlabel("东向 E (m)")
    axes.set_ylabel("北向 N (m)")
    axes.grid(True, color="#dde3e9", linewidth=.7)
    axes.axhline(0, color="#a6b1ba", lw=.8)
    axes.axvline(0, color="#a6b1ba", lw=.8)
    axes.set_aspect("equal", adjustable="box")


base_axes(ax, "全场范围")
base_axes(bx, "B3 局部放大")
blue = "#1769aa"
green = "#27845d"
amber = "#d5891c"
gray = "#7d8893"

# Visual sites are hollow circles because all are provisional estimates.
for name, value in VISUAL.items():
    x, y = en(*value[:2])
    for target in (ax, bx) if name.startswith("B3") else (ax,):
        target.scatter(x, y, s=110, marker="o", facecolors="white", edgecolors=blue, linewidths=2.3, zorder=5)

# Physical LRF records use diamonds, with unresolved F1 in amber.
for name, value in LRF.items():
    x, y = en(*value[:2])
    color = amber if name == "B3-F1" else gray if name == "B4-F1" else green
    for target in (ax, bx) if name.startswith("B3") else (ax,):
        target.scatter(x, y, s=105 if name != "B4-F1" else 65, marker="D", color=color,
                       edgecolors="white", linewidths=.8, zorder=6)

# Draw only plausible associations. Do not connect B3-N to B3-F1.
for v, l in (("B1", "B1-LRF"), ("B2", "B2-LRF"), ("B3-S", "B3-F2")):
    x1, y1 = en(*VISUAL[v][:2])
    x2, y2 = en(*LRF[l][:2])
    for target in (ax, bx) if v.startswith("B3") else (ax,):
        target.plot([x1, x2], [y1, y2], color=green, lw=1.4, ls="--", alpha=.75, zorder=2)

labels_overall = {
    "B1": (5, -4, "B1 火点"), "B2": (6, 7, "B2 火点"),
    "B3-N": (-25, 5, "B3 北侧明火"), "B3-S": (6, -11, "B3 南侧明火"),
    "B4-E": (4, -2, "B4 东侧·路边"), "B4-W": (-27, 6, "B4 西侧·树边"),
}
for name, (dx, dy, label) in labels_overall.items():
    x, y = en(*VISUAL[name][:2])
    ax.annotate(label, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=10,
                ha="left" if dx >= 0 else "right", va="center", color="#18354a")
ax.annotate("F1 待定", en(*LRF["B3-F1"][:2]), xytext=(9, 2), textcoords="offset points", fontsize=9, color="#9a5812")
ax.annotate("B4-F1= B2 同址", en(*LRF["B4-F1"][:2]), xytext=(5, -14), textcoords="offset points", fontsize=8.5, color="#58646f")
ax.set_xlim(-38, 17)
ax.set_ylim(-89, 57)
ax.annotate("N ↑", xy=(.93, .96), xycoords="axes fraction", fontsize=13, fontweight="bold", ha="right")

detail_labels = {
    "B3-N": (-7, 9, "北侧明火\n无对应 LRF"),
    "B3-S": (13, -11, "南侧明火"),
}
for name, (dx, dy, label) in detail_labels.items():
    bx.annotate(label, en(*VISUAL[name][:2]), xytext=(dx, dy), textcoords="offset points", fontsize=10,
                ha="right" if dx < 0 else "left", va="center", color="#18354a")
bx.annotate("F1 疑似中间枝柴堆", en(*LRF["B3-F1"][:2]), xytext=(12, 1), textcoords="offset points",
            fontsize=9.5, color="#9a5812", va="center")
bx.annotate("F2 南侧候选", en(*LRF["B3-F2"][:2]), xytext=(-9, 9), textcoords="offset points",
            fontsize=9.5, color="#1d704c", ha="right")
bx.set_xlim(-22, 22)
bx.set_ylim(12, 56)
bx.annotate("N ↑", xy=(.95, .95), xycoords="axes fraction", fontsize=13, fontweight="bold", ha="right")
bx.text(.04, .04, f"北—南视觉点约 {distance(VISUAL['B3-N'], VISUAL['B3-S']):.1f} m\n"
                  f"F1 距北侧视觉点约 {distance(LRF['B3-F1'], VISUAL['B3-N']):.1f} m",
        transform=bx.transAxes, fontsize=9, color="#3a4854", va="bottom",
        bbox={"facecolor": "white", "edgecolor": "#d7dee4", "alpha": .95})

legend = [
    Line2D([0], [0], marker="o", linestyle="None", markerfacecolor="white", markeredgecolor=blue,
           markeredgewidth=2, markersize=9, label="视频火点：未标定影像估计"),
    Line2D([0], [0], marker="D", linestyle="None", markerfacecolor=green, markeredgecolor="white",
           markersize=9, label="LRF：有条件的参考/候选"),
    Line2D([0], [0], marker="D", linestyle="None", markerfacecolor=amber, markeredgecolor="white",
           markersize=9, label="B3 F1：对应对象待定"),
    Line2D([0], [0], marker="D", linestyle="None", markerfacecolor=gray, markeredgecolor="white",
           markersize=8, label="B4 F1：B2 同址复测"),
]
fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(.5, .07), ncol=2, frameon=False, fontsize=10)
fig.text(.5, .028, "点位按 WGS84 经纬度转换为 B2 附近局部东/北距离；图示位置不能替代实地测量。",
         ha="center", color="#53616d", fontsize=9)
fig.savefig(OUT / "火点相对点位图.png", dpi=220)
fig.savefig(OUT / "火点相对点位图.svg")
print(f"Saved {OUT / '火点相对点位图.png'}")
