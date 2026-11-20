"""Figures for the Rev D engineering report, drawn from the exported results (site/data/*.json). Rev C: make_figures_revC.py.

usage: python report/make_figures.py <repo root> <out folder>
"""
import sys, os, json, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle
from mpl_toolkits.mplot3d.art3d import Line3DCollection
from matplotlib.lines import Line2D

ROOT, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
D = json.load(open(os.path.join(ROOT, "site/data/revD.json")))
B0 = json.load(open(os.path.join(ROOT, "site/data/before.json")))
AB = json.load(open(os.path.join(ROOT, "site/data/ablation.json")))
CFG = json.load(open(os.path.join(ROOT, "analysis/configs/revD_final.json")))
proj = json.load(open(os.path.join(ROOT, "model/engineered/project.json")))
NAVY, SKY, INK, MUTED = "#14304f", "#2f7fc1", "#1d2733", "#7a8794"
PART = {"STRAP": "#e8731a", "V-STRAP": "#f2a33a", "CRADLE": "#3b4651", "CRADLE SEAT": "#3b4651", "GUIDE": "#d4a400",
        "PLANE BRACE": "#2aa198", "BRIDGING": "#7b3fa0"}
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 9, "axes.edgecolor": "#c9d1d9", "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED})
FEET = D["foot_layout"]
GAUGED = set((CFG.get("build_options") or {}).get("gauge") or {})
NDES = len(D["design_cases"])


def ucol(u):
    if u is None: return "#b8c2cc"
    if u > 1.0: return "#d1242f"
    if u > 0.95: return "#f0663a"
    if u > 0.8: return "#e3a008"
    if u > 0.5: return "#3fa34d"
    return "#9fb3c8"


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), bbox_inches="tight"); plt.close(fig)


def spines(ax):
    for s in ("top", "right"): ax.spines[s].set_visible(False)


# ------------------------------------------------------------------------------------------------ 3D views
def iso(data, fname, title, parts=True):
    fig = plt.figure(figsize=(9.5, 5.2), dpi=200)
    ax = fig.add_subplot(111, projection="3d")
    segs, cols, lws = [], [], []
    for m in data["members"]:
        if m["added"]:
            if not parts or m["type"] in ("CRADLE", "CRADLE SEAT"): continue
            c = PART.get(m["type"], "#555")
            lw = 2.2 if m["type"] in ("STRAP", "V-STRAP", "GUIDE") else 0.8
        else:
            c = ucol(m.get("util")); lw = 0.6 if (m.get("util") or 0) < 0.8 else 1.4
            if parts and m["panel"] in GAUGED: lw = max(lw, 1.1)
        segs.append([np.array(m["a"]) / 1000, np.array(m["b"]) / 1000]); cols.append(c); lws.append(lw)
    ax.add_collection3d(Line3DCollection(segs, colors=cols, linewidths=lws))
    if parts:
        for f in data.get("foot_layout", []):
            y = CFG["rim_y"][f["side"]] / 1000
            x0, x1 = f["cradle"][0] / 1000, f["cradle"][1] / 1000
            ax.plot([x0, x1, x1, x0, x0], [y] * 5, [-0.41, -0.41, -0.25, -0.25, -0.41], color=PART["CRADLE"], lw=1.6)
        for k, p in data["lift_points"].items():
            x, y, z = np.array(p["xyz"]) / 1000
            ax.plot([x, x], [y, y], [z, z + 1.1], color="#6b7785", lw=1.0, ls="--")
            ax.text(x, y, z + 1.2, k, fontsize=7, color=INK, ha="center")
    ax.set_xlim(0, 12); ax.set_ylim(-4.35, 7.65); ax.set_zlim(-1.5, 5.0)
    ax.set_box_aspect((12, 12, 6.5)); ax.view_init(elev=18, azim=-58); ax.set_axis_off()
    ax.set_title(title, fontsize=10, color=INK, loc="left")
    leg = [Line2D([0], [0], color=c, lw=3, label=l) for c, l in (("#9fb3c8", "below 0.5"), ("#3fa34d", "0.5 - 0.8"), ("#e3a008", "0.8 - 0.95"),
                                                                 ("#f0663a", "0.95 - 1.0"), ("#d1242f", "over 1.0"))]
    if parts:
        leg += [Line2D([0], [0], color=PART["STRAP"], lw=3, label="hanger strap pairs (8)"),
                Line2D([0], [0], color=PART["GUIDE"], lw=3, label="lifting heads (closed box)"), Line2D([0], [0], color=PART["CRADLE"], lw=3, label="cradles at truss joint pairs"),
                Line2D([0], [0], color=PART["PLANE BRACE"], lw=3, label="floor / roof strap bracing"), Line2D([0], [0], color=PART["BRIDGING"], lw=3, label="bridging")]
    ax.legend(handles=leg, loc="upper left", bbox_to_anchor=(0.0, 0.93), fontsize=7, frameon=False, ncol=1)
    fig.subplots_adjust(0, 0, 1, 1)
    save(fig, fname)


iso(D, "fig_iso_after.png", f"Rev D.1, engineered for the lift: utilisation of every member (envelope of the {NDES} design cases, factor 2.433)")
iso(B0, "fig_iso_before.png", "Before: the frame as framed, slings straight onto the floor edge truss (same 8 points, same factors)", parts=False)


# ------------------------------------------------------------------------------------------------ elevations
def elevation(yline, fname, title, openings):
    fig, ax = plt.subplots(figsize=(10, 3.9), dpi=200)
    for m in D["members"]:
        if abs(m["a"][1] - yline) > 60 or abs(m["b"][1] - yline) > 60: continue
        xa, za, xb, zb = m["a"][0] / 1000, m["a"][2] / 1000, m["b"][0] / 1000, m["b"][2] / 1000
        if m["added"]:
            if m["type"] in ("CRADLE", "CRADLE SEAT"): continue
            ax.plot([xa, xb], [za, zb], color=PART.get(m["type"], "#555"), lw=2.4 if m["type"] in ("STRAP", "V-STRAP") else 3.0, solid_capstyle="butt", zorder=4)
        else:
            ax.plot([xa, xb], [za, zb], color=ucol(m.get("util")), lw=1.4 if m["panel"] in GAUGED else 0.9, zorder=2)
    for f in FEET:
        if abs(CFG["rim_y"][f["side"]] - yline) > 60: continue
        x0, x1 = f["cradle"][0] / 1000, f["cradle"][1] / 1000
        ax.add_patch(Rectangle((x0, -0.41), x1 - x0, 0.16, fc="#3b4651", alpha=0.55, ec="#3b4651", lw=0.8, zorder=5))
    for (o0, w, sill, h, lab) in openings:
        ax.add_patch(Rectangle((o0 / 1000, sill / 1000), w / 1000, h / 1000, fc="#dbe9f6", ec=SKY, lw=0.8, zorder=1))
        ax.text((o0 + w / 2) / 1000, (sill + h / 2) / 1000, lab, ha="center", va="center", fontsize=7, color=SKY)
    for k, p in D["lift_points"].items():
        if abs(p["xyz"][1] - yline) > 60: continue
        x, z = p["xyz"][0] / 1000, p["xyz"][2] / 1000
        R = p["reactions_kN"]["R4_equalised"]
        ax.annotate("", xy=(x, z + 0.75), xytext=(x, z + 0.05), arrowprops=dict(arrowstyle="-|>", color=NAVY, lw=1.6))
        ax.text(x, z + 0.82, f"{k}\n{R:.1f} kN", ha="center", va="bottom", fontsize=7.5, color=NAVY)
    ax.set_xlim(-0.3, 12.3); ax.set_ylim(-0.6, 4.6); ax.set_aspect("equal")
    ax.set_xlabel("x along the module (m)"); ax.set_yticks([0, 1, 2, 3]); ax.set_ylabel("z (m)")
    ax.set_title(title, fontsize=10, color=INK, loc="left"); spines(ax)
    save(fig, fname)


ops_s = [(o["offset"], o["width"], o["sill"], o["height"], o["kind"]) for w in proj["walls"] if w["id"] == "EW1" for o in w["openings"]]
elevation(44.5, "fig_elev_south.png", "South wall (outside view): members by utilisation, hanger strap pairs, cradles (dark), sling forces in the main case (unfactored)", ops_s)
elevation(3255.5, "fig_elev_north.png", "North (open marriage) side: piers at 4.5 and 7.5 m, end returns; vertical hanger strap pairs into cradles",
          [(1050, 3300, 0, 2700, "opening"), (4650, 2700, 0, 2700, "opening"), (7650, 3300, 0, 2700, "opening")])


# ------------------------------------------------------------------------------------------------ plan
fig, ax = plt.subplots(figsize=(10, 3.6), dpi=200)
for m in D["members"]:
    a, b = np.array(m["a"]) / 1000, np.array(m["b"]) / 1000
    if m["kind"] == "floor_truss" and m["type"] == "TOP CHORD":
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#9fb3c8", lw=1.0)
    if m["kind"] == "rim_truss" and m["type"] == "TOP CHORD":
        ax.plot([a[0], b[0]], [a[1], b[1]], color=INK, lw=2.6 if m["panel"] in GAUGED else 1.6)
    if m["type"] == "PLANE BRACE" and m["id"].startswith("F"):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=PART["PLANE BRACE"], lw=1.2)
    if m["type"] == "BRIDGING" and m["id"].startswith("FBR"):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=PART["BRIDGING"], lw=2.0)
for f in FEET:
    y = CFG["rim_y"][f["side"]] / 1000
    ax.add_patch(Rectangle((f["cradle"][0] / 1000, y - 0.06), 0.12, 0.12, fc="#3b4651", ec="white", lw=0.6, zorder=6))
for k, p in D["lift_points"].items():
    ax.add_patch(Circle((p["xyz"][0] / 1000, p["xyz"][1] / 1000), 0.09, fc=NAVY, ec="white", lw=1, zorder=7))
    ax.text(p["xyz"][0] / 1000, p["xyz"][1] / 1000 + (0.22 if p["xyz"][1] > 1650 else -0.34), k, ha="center", fontsize=7.5, color=NAVY)
cg = D["meta"]["cg"]
ax.plot(cg[0] / 1000, cg[1] / 1000, marker="P", ms=9, color="#d1242f"); ax.text(cg[0] / 1000 + 0.15, cg[1] / 1000 - 0.25, "centre of gravity", fontsize=7.5, color="#d1242f")
for lab, kw in (("floor plane strap bracing (30 x 1.0)", dict(color=PART["PLANE BRACE"], lw=1.2)), ("bridging line (C89 noggings)", dict(color=PART["BRIDGING"], lw=2.0)),
                ("floor trusses at 600 mm", dict(color="#9fb3c8", lw=1.0)), ("floor edge trusses, 1.15 mm", dict(color=INK, lw=2.6))):
    ax.plot([], [], label=lab, **kw)
ax.plot([], [], marker="s", ls="", color="#3b4651", label="cradles (feet)")
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, fontsize=7.5, frameon=False)
ax.set_xlim(-0.2, 12.2); ax.set_ylim(-0.45, 3.75); ax.set_aspect("equal"); ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
ax.set_title("Floor plan: lift points, feet, floor plane bracing and the bridging line (the roof plane has the same bracing)", fontsize=10, loc="left", color=INK)
spines(ax); save(fig, "fig_plan.png")


# ------------------------------------------------------------------------------------------------ lift point: section and elevation of S2
def rect(ax, x, y, w, h, fc, ec="#333", lw=0.8, a=1.0, z=2):
    ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec=ec, lw=lw, alpha=a, zorder=z))


fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 6.4), dpi=200, gridspec_kw=dict(width_ratios=[1, 1.75]))
rect(a1, 0, -297, 89, 297, "#e8edf2"); rect(a1, 0, 0, 89, 2700, "#f4f6f8"); rect(a1, 0, 2700, 89, 300, "#e8edf2")
rect(a1, -1.5, -297, 1.5, 100, "#9fb3c8", z=4); rect(a1, 89, -297, 1.5, 100, "#9fb3c8", z=4)             # gusset plates
rect(a1, -4.5, -450, 3, 200, "#3b4651", z=4); rect(a1, 90.5, -450, 3, 200, "#3b4651", z=4)               # cheeks over the gussets
rect(a1, -8, -320.5, 105, 16, "#555", z=5)                                                              # M16 bearing bolt
rect(a1, 0, -300, 89, 3, "#8b6f47", z=5)                                                                 # packer
rect(a1, -7.0, -420, 2.5, 3560, PART["STRAP"], ec=PART["STRAP"], z=6); rect(a1, 93.5, -420, 2.5, 3560, PART["STRAP"], ec=PART["STRAP"], z=6)
rect(a1, -10, 2700, 3, 480, PART["GUIDE"], ec="#8a6d00", z=6); rect(a1, 96, 2700, 3, 480, PART["GUIDE"], ec="#8a6d00", z=6)
rect(a1, -10, 3000, 109, 180, PART["GUIDE"], ec="#8a6d00", a=0.25, z=5)                                    # end plates above the truss (box)
a1.add_patch(Circle((44.5, 3150), 10, fc="#555", ec="black", zorder=7)); a1.add_patch(Circle((44.5, 3150), 20, fc="none", ec="#555", lw=1.2, zorder=7))
a1.annotate("", xy=(44.5, 3620), xytext=(44.5, 3125), arrowprops=dict(arrowstyle="-|>", color=NAVY, lw=1.5))
for z, t in [(3560, "sling from the cascade (drops within 2 deg of vertical)"), (3150, "M20 8.8 pin + 40 mm sleeve; round sling eye\ndown through the OPEN TOP onto the sleeve"),
             (2860, "lifting head: closed box (two 3 mm cheeks + two end\nplates above the truss), running clearance, NO\nfasteners - holds sideways, no weight into the roof"),
             (1400, "hanger strap pair, one on each face\n(50 x 2.5 G450, match-drilled), 2 x M12 each\nend; no fixings through it anywhere"),
             (-330, "cradle: 3 mm cheeks over the joint gusset plates;\nM16 bearing bolt + sleeve + packer under each\ntruss joint; strap bolts below")]:
    a1.annotate(t, xy=(100, z), xytext=(250, z), fontsize=6.8, va="center", arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
a1.set_xlim(-150, 1450); a1.set_ylim(-560, 3760); a1.set_aspect("equal"); a1.set_axis_off()
a1.set_title("Section through a lift point (across the wall)", fontsize=9.5, loc="left", color=INK)
x0 = D["lift_points"]["S2"]["xyz"][0]
rect(a2, x0 - 1600, -297, 3200, 297, "#eef2f6", ec="#c9d1d9"); rect(a2, x0 - 1600, 2700, 3200, 300, "#eef2f6", ec="#c9d1d9")
for m in D["members"]:
    if m["panel"] in ("NFT1",) and abs((m["a"][0] + m["b"][0]) / 2 - x0) < 1600:
        a2.plot([m["a"][0], m["b"][0]], [m["a"][2], m["b"][2]], color=ucol(m.get("util")), lw=1.4, zorder=3)
for xt in [x for x in sorted({round((m["a"][0] + m["b"][0]) / 2) for m in D["members"] if m["kind"] == "floor_truss" and m["type"] == "TOP CHORD"}) if abs(x - x0) < 1600]:
    rect(a2, xt - 44.5, -297, 89, 297, "#d7dee6", ec="#9aa5b1", lw=0.4, a=0.8, z=2)
for xs in np.arange(x0 - 1500, x0 + 1501, 600): rect(a2, xs - 20, 0, 41, 2700, "#e6ebf0", ec="#b4bfca", lw=0.4)
for f in FEET:
    if f["id"] == "FOOT_S2h":
        rect(a2, f["cradle"][0], -450, f["cradle"][1] - f["cradle"][0], 200, "#3b4651", a=0.5, z=5)
        for s_ in f["seats"]: a2.add_patch(Circle((s_, -312.5), 9, fc="#222", zorder=6))
        a2.plot([f["x_strap"], x0], [-420, 3150], color=PART["STRAP"], lw=3.0, zorder=6)
        v = [m for m in D["members"] if m["id"] == "HANG_S2"][0]
        a2.text(x0 + 60, 1300, f"hanger strap pair" + chr(10) + f"{v['N_R4_unfactored']:.1f} kN", fontsize=7.5, color="#b25a10")
        a2.text((f["cradle"][0] + f["cradle"][1]) / 2, -520, f"cradle {f['cradle'][1] - f['cradle'][0]:.0f} long at the truss joint pair" + chr(10) + f"{f['cradle_gap']:.0f} mm clear of the truss-end cleats", ha="center", va="top", fontsize=6.8)
rect(a2, x0 - 60, 2720, 120, 430, PART["GUIDE"], ec="#8a6d00", z=6)
a2.annotate("", xy=(x0, 3700), xytext=(x0, 3180), arrowprops=dict(arrowstyle="-|>", color=NAVY, lw=1.5))
a2.text(x0 + 70, 3600, f"sling {D['lift_points']['S2']['reactions_kN']['R4_equalised']:.1f} kN", fontsize=8, color=NAVY)
a2.set_xlim(x0 - 1650, x0 + 1650); a2.set_ylim(-800, 3800); a2.set_aspect("equal"); a2.set_axis_off()
a2.set_title("Lift point S2 seen from outside: the hanger lands on the truss joint pair under it (main case, unfactored)", fontsize=9.5, loc="left", color=INK)
save(fig, "fig_liftpoint.png")


# ------------------------------------------------------------------------------------------------ cradle close-up: how it works
f = [q for q in FEET if q["id"] == "FOOT_S2h"][0]
j1, j2 = f["seats"][0], f["seats"][-1]; xs = f["x_strap"]; c0, c1 = f["cradle"]
fig, (b1, b2) = plt.subplots(1, 2, figsize=(10.5, 4.3), dpi=200, gridspec_kw=dict(width_ratios=[1.7, 1]))
xl, xr = c0 - 210, c1 + 230
rect(b1, xl, -297, xr - xl, 38, "#cfd8e2", ec="#7b8794")                                 # bottom chord (web down, flanges up)
for m in D["members"]:
    if m["panel"] == "NFT1" and m["type"] == "WEB" and (abs(m["a"][0] - j1) < 40 or abs(m["a"][0] - j2) < 40):
        ax_, az, bx, bz = m["a"][0], m["a"][2], m["b"][0], m["b"][2]
        t = 230.0 / math.hypot(bx - ax_, bz - az)
        b1.plot([ax_, ax_ + (bx - ax_) * t], [az, az + (bz - az) * t], color="#7b8794", lw=9, solid_capstyle="butt", zorder=2, alpha=0.6)
xt = min([x for x in {round((m["a"][0] + m["b"][0]) / 2) for m in D["members"] if m["kind"] == "floor_truss" and m["type"] == "TOP CHORD"}], key=lambda x: abs(x - xs))
rect(b1, xt - 44.5, -297, 89, 297, "#e4e9ef", ec="#9aa5b1", lw=0.6, z=1); b1.text(xt, 30, "floor truss end\n(inside face)", ha="center", fontsize=6.5, color=MUTED)
for s_ in (j1, j2): rect(b1, s_ - 50, -297, 100, 100, "#9fb3c8", ec="#6e8296", lw=0.6, a=0.55, z=2)        # gusset plates (first)
rect(b1, c0, -450, c1 - c0, 200, "#3b4651", a=0.35, z=3)
for s in (j1, j2):
    rect(b1, s - 20, -300, 40, 3, "#8b6f47", z=5); b1.add_patch(Circle((s, -312.5), 12.5, fc="#999", ec="#333", zorder=5)); b1.add_patch(Circle((s, -312.5), 8, fc="#222", zorder=6))
    b1.annotate("", xy=(s, -296), xytext=(s, -352), arrowprops=dict(arrowstyle="-|>", color="#d1242f", lw=1.6), zorder=7)
for dx in (-14, 14): b1.add_patch(Circle((j1 + dx, -278), 2.4, fc="white", ec="#333", lw=0.6, zorder=6))
k = (D["lift_points"]["S2"]["xyz"][0] - xs) / 3540.0          # 0 for a vertical hanger
b1.plot([xs, xs + k * 500], [-420, 110], color=PART["STRAP"], lw=5, zorder=4, alpha=0.9)
for zb in (-410, -370): b1.add_patch(Circle((xs + k * (zb + 420), zb), 6, fc="#e8731a", ec="#333", zorder=6))
b1.annotate("", xy=(xs + k * 520 + 10, 140), xytext=(xs + k * 380 + 10, 0), arrowprops=dict(arrowstyle="-|>", color=NAVY, lw=1.6))
b1.text(xs + k * 520 + 25, 120, "hanger pull (to the head)", color=NAVY, fontsize=6.8, va="center")
b1.annotate("screwed seat\n(2 screws per cheek)", xy=(j1, -325), xytext=(j1 - 75, -500), ha="right", fontsize=6.6, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
b1.annotate("bearing-only seat\n(no screws)", xy=(j2, -325), xytext=(j2 + 75, -500), ha="left", fontsize=6.6, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
b1.text(c1 + 35, -120, "the two truss diagonals\nmeet the chord at this\njoint pair: each seat pushes\nstraight up into them,\nso the chord does not bend", ha="left", va="center", fontsize=6.8, color=INK)
cl = CFG.get("cleat_leg", 50.0); side_ = 1 if xs > xt else -1
cx = xt + side_ * 44.5 if side_ > 0 else xt - 44.5 - cl
rect(b1, cx, -270, cl, 200, "#c3ced9", ec="#8795a3", lw=0.6, z=2); b1.text(cx + cl / 2, -60, "cleat", ha="center", fontsize=6.3, color=MUTED)
ce = cx + cl if side_ > 0 else cx
b1.annotate("", xy=(ce, -215), xytext=(c0 if side_ > 0 else c1, -215), arrowprops=dict(arrowstyle="<->", color="#2f7fc1", lw=0.8), zorder=8)
b1.text((ce + (c0 if side_ > 0 else c1)) / 2, -205, f"{f['cradle_gap']:.0f} mm clear", ha="center", va="bottom", fontsize=6.5, color="#2f7fc1", zorder=8)
b1.set_xlim(xl, xr); b1.set_ylim(-600, 180); b1.set_aspect("equal"); b1.set_axis_off()
b1.set_title(f"Cradle {f['id'][5:]} (south, x {xs / 1000:.2f} m): elevation along the edge truss", fontsize=9.5, loc="left", color=INK)
# section across the chord
rect(b2, -44.5, -297, 89, 0.95 * 2, "#7b8794"); rect(b2, -44.5, -297, 1.9, 38, "#7b8794"); rect(b2, 42.6, -297, 1.9, 38, "#7b8794")
rect(b2, -44.5, -260, 9, 1.9, "#7b8794"); rect(b2, 35.5, -260, 9, 1.9, "#7b8794")
rect(b2, -46.0, -297, 1.5, 100, "#9fb3c8"); rect(b2, 44.5, -297, 1.5, 100, "#9fb3c8")
rect(b2, -49.0, -450, 3, 200, "#3b4651"); rect(b2, 46.0, -450, 3, 200, "#3b4651")
rect(b2, -44.5, -300, 89, 3, "#8b6f47"); rect(b2, -44.5, -325, 89, 25, "#bbb", ec="#555"); rect(b2, -56, -320.5, 112, 16, "#444", z=3)
rect(b2, -51.5, -425, 2.5, 425, PART["STRAP"], ec=PART["STRAP"]); rect(b2, 49.0, -425, 2.5, 425, PART["STRAP"], ec=PART["STRAP"])
for z, t in [(-278, "chord C89 (web down, flanges up)"), (-240, "1.5 mm gusset plate each face (fitted first)"), (-298.5, "3 mm packer"),
             (-312.5, "M16 8.8 bolt in a 92 mm sleeve"), (-400, "3 mm cheek each side over the gussets;\nhanger strap pair outside, bolted below")]:
    b2.annotate(t, xy=(50, z), xytext=(80, z), fontsize=6.5, va="center", arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.5))
b2.set_xlim(-70, 340); b2.set_ylim(-470, -120); b2.set_aspect("equal"); b2.set_axis_off()
b2.set_title("Section across the chord", fontsize=9.5, loc="left", color=INK)
save(fig, "fig_cradle.png")


# ------------------------------------------------------------------------------------------------ rig schematic
fig, ax = plt.subplots(figsize=(10, 4.2), dpi=200)
xs_ = [x / 1000 for x in CFG["lift_lines_x"]]
R4 = D["cases"]["R4_equalised"]["reactions"]
ax.add_patch(Rectangle((0, 0), 12, 3.3, fc="#eef2f6", ec="#9aa5b1"))
ax.text(6, 1.65, "module (seen from the side)", ha="center", va="center", color=MUTED, fontsize=8)
zc, zm, zt_, zh = 4.9, 6.2, 7.4, 8.6
for i, x in enumerate(xs_):
    ax.plot([x, x], [3.45, zc], color="#555", lw=1.2)
    ax.text(x + 0.08, 4.1, f"S{i + 1} {R4[f'S{i + 1}'] / 1e3:.1f}\nN{i + 1} {R4[f'N{i + 1}'] / 1e3:.1f} kN", fontsize=7, color=NAVY)
    ax.add_patch(Rectangle((x - 0.35, zc), 0.7, 0.12, fc="#7b8794"))
ax.text(0.05, zc + 0.2, "4 cross beams (span 3.21 m, picked at the CoG across)", fontsize=7, color=INK)
for (xa, xb) in ((xs_[0], xs_[1]), (xs_[2], xs_[3])):
    ax.plot([xa, (xa + xb) / 2], [zc + 0.12, zm], color="#555", lw=1.0); ax.plot([xb, (xa + xb) / 2], [zc + 0.12, zm], color="#555", lw=1.0)
    ax.add_patch(Rectangle(((xa + xb) / 2 - 0.9, zm), 1.8, 0.12, fc="#7b8794"))
ax.text(0.05, zm + 0.2, "2 middle beams", fontsize=7, color=INK)
for xm in ((xs_[0] + xs_[1]) / 2, (xs_[2] + xs_[3]) / 2): ax.plot([xm, 6.0], [zm + 0.12, zt_], color="#555", lw=1.0)
ax.add_patch(Rectangle((6.0 - 3.6, zt_), 7.2, 0.12, fc="#7b8794")); ax.text(2.0, zt_ + 0.2, "top beam (pick point set to the weighed CoG)", fontsize=7, color=INK)
ax.plot([6.0, 6.0], [zt_ + 0.12, zh], color="#555", lw=1.2); ax.add_patch(Circle((6.0, zh + 0.12), 0.12, fc="#555"))
ax.text(6.2, zh, f"hook: {D['meta']['W_N'] / 1e3:.1f} kN module (6.5 t rated) + rigging", fontsize=7.5, color=INK)
ax.set_xlim(-0.3, 12.3); ax.set_ylim(-0.2, 9.2); ax.set_aspect("equal"); ax.set_axis_off()
ax.set_title("Rig: equalising pinned-beam cascade. Every beam hangs from one pin, so each drop's share is fixed by balance, not by sling length", fontsize=9.5, loc="left", color=INK)
save(fig, "fig_rig.png")


# ------------------------------------------------------------------------------------------------ ablation chart
names = {"revD_final": "Rev D.1 design", "A1_framed_screws": "joints as framed (2 screws), no gussets", "A2_no_gussets": "4-screw joints, no gussets",
         "A3_no_bridging": "no bridging", "A4_no_plane_bracing": "no floor / roof strap bracing", "A5_seat_between_joints": "cradles between truss joints",
         "A6_north_trusses_095": "north edge trusses at 0.95 mm", "A8_edge_trusses_100": "edge trusses at 1.00 mm, not 1.15", "A7_single_inner_hanger": "one inside-face hanger (north)",
         "B0_frame_only": "Before (as framed, no lift parts)", "S1_lining_credit": "linings counted (sensitivity)", "S2_twist_length_out": "no twist restraint at joints (sensitivity)",
         "S3_no_notch_credit": "no credit at lip notches (sensitivity)", "S4_links_soft": "panel links 4 x softer (sensitivity)",
         "S5_links_stiff": "panel links 4 x stiffer (sensitivity)", "S6_joint_fixity": "joints partly fixed (sensitivity)"}
rows = {r["id"]: r for r in AB}
order = [k for k in ("revD_final", "S1_lining_credit", "S4_links_soft", "S5_links_stiff", "S6_joint_fixity", "A7_single_inner_hanger", "A3_no_bridging",
                     "A8_edge_trusses_100", "A6_north_trusses_095", "A5_seat_between_joints", "S2_twist_length_out", "S3_no_notch_credit", "A4_no_plane_bracing",
                     "A2_no_gussets", "A1_framed_screws", "B0_frame_only") if k in rows]
fig, ax = plt.subplots(figsize=(10, 5.2), dpi=200)
yy = np.arange(len(order))
mo = [rows[k]["members_over"] for k in order]; jo = [rows[k]["joints_over"] for k in order]
ax.barh(yy - 0.18, mo, height=0.34, color="#d1242f", label="members over capacity")
ax.barh(yy + 0.18, jo, height=0.34, color="#e3a008", label="screwed joints over capacity")
for i, k in enumerate(order):
    ax.text(mo[i] + 2, i - 0.18, f"{mo[i]}  (worst {rows[k]['max_member']:.2f})", va="center", fontsize=6.8)
    ax.text(jo[i] + 2, i + 0.18, f"{jo[i]}  (worst {rows[k]['max_joint']:.2f})", va="center", fontsize=6.8)
ax.set_yticks(yy); ax.set_yticklabels([names.get(k, k) for k in order]); ax.invert_yaxis()
ax.set_xscale("symlog", linthresh=10); ax.set_xlim(0, 2000)
ax.set_xlabel("count over 1.0 (envelope of the design cases, factor 2.433; log scale above 10)"); ax.legend(frameon=False, fontsize=8, loc="upper right")
ax.set_title("What each measure does: the design with one measure taken away (or one assumption changed) at a time", fontsize=10, loc="left", color=INK)
spines(ax); save(fig, "fig_ablation.png")


# ------------------------------------------------------------------------------------------------ utilisation by design case
allc = D["design_cases"]
TLc = [c for c in allc if c.startswith("T") and "+" in c]; CGc = [c for c in allc if c.startswith("CG")]
cases = [c for c in allc if c not in TLc and c not in CGc]
fig, ax = plt.subplots(figsize=(10, 3.4), dpi=200)
labels = [c.split("_")[0] for c in cases] + (["T+L (32)"] if TLc else []) + (["CoG (8)"] if CGc else [])
mm = [D["cases"][c]["max_member"] for c in cases] + ([max(D["cases"][c]["max_member"] for c in TLc)] if TLc else []) + ([max(D["cases"][c]["max_member"] for c in CGc)] if CGc else [])
jj = [D["cases"][c]["max_joint"] for c in cases] + ([max(D["cases"][c]["max_joint"] for c in TLc)] if TLc else []) + ([max(D["cases"][c]["max_joint"] for c in CGc)] if CGc else [])
xx = np.arange(len(labels))
ax.bar(xx - 0.2, mm, width=0.4, color=NAVY, label="worst member"); ax.bar(xx + 0.2, jj, width=0.4, color="#e3a008", label="worst screwed joint")
ax.axhline(1.0, color="#d1242f", lw=1.0, ls="--"); ax.text(len(cases) - 0.5, 1.01, "design capacity", color="#d1242f", fontsize=7, ha="right", va="bottom")
ax.set_xticks(xx); ax.set_xticklabels(labels, fontsize=7, rotation=0); ax.set_ylim(0, 1.15); ax.set_ylabel("utilisation (factored)")
ax.legend(frameon=False, fontsize=8, loc="lower left", ncol=2)
ax.set_title(f"Worst member and joint in each of the {len(allc)} design cases (R rig, T 2 deg tilt, L 3.5 % lean, TW twist, T+L and CoG families as their worst)", fontsize=9.5, loc="left", color=INK)
spines(ax); save(fig, "fig_cases.png")


# ------------------------------------------------------------------------------------------------ reactions per design case
pts = ["S1", "S2", "S3", "S4", "N1", "N2", "N3", "N4"]
cases = [c for c in cases if not c.startswith("TW")] + [c for c in cases if c.startswith("TW")] + CGc[:4]
fig, ax = plt.subplots(figsize=(10, 3.4), dpi=200)
w = 0.8 / len(cases); cmap = plt.get_cmap("tab20")
for i, c in enumerate(cases):
    vals = [D["cases"][c]["reactions"].get(p, 0) / 1e3 for p in pts]
    ax.bar(np.arange(8) + (i - len(cases) / 2) * w + w / 2, vals, width=w, color=cmap(i % 20), label=c)
ax.set_xticks(np.arange(8)); ax.set_xticklabels(pts); ax.set_ylabel("sling force, unfactored (kN)")
ax.legend(ncol=5, fontsize=6.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12))
ax.set_title("Sling force at each lift point in every design case (rated 6.5 t, no factors)", fontsize=10, loc="left", color=INK)
spines(ax); save(fig, "fig_reactions.png")
print("figures written to", OUT)
