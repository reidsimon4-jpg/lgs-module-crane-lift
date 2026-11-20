"""Figures for the engineering report, drawn from the exported results (site/data/*.json).

usage: python report/make_figures.py <repo root> <out folder>
"""
import sys, os, json, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, FancyArrowPatch, Circle
from mpl_toolkits.mplot3d.art3d import Line3DCollection

ROOT, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
D = json.load(open(os.path.join(ROOT, "site/data/revC.json")))
B0 = json.load(open(os.path.join(ROOT, "site/data/before.json")))
AB = json.load(open(os.path.join(ROOT, "site/data/ablation.json")))
proj = json.load(open(os.path.join(ROOT, "model/engineered/project.json")))
NAVY, SKY, INK, MUTED = "#14304f", "#2f7fc1", "#1d2733", "#7a8794"
PART = {"STRAP": "#e8731a", "V-STRAP": "#f2a33a", "CRADLE": "#3b4651", "STIRRUP": "#3b4651", "GUIDE": "#d4a400", "PLANE BRACE": "#2aa198"}
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 9, "axes.edgecolor": "#c9d1d9", "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED})


def ucol(u):
    if u is None: return "#b8c2cc"
    if u > 1.0: return "#d1242f"
    if u > 0.95: return "#f0663a"
    if u > 0.8: return "#e3a008"
    if u > 0.5: return "#3fa34d"
    return "#9fb3c8"


def iso(data, fname, title, parts=True):
    fig = plt.figure(figsize=(9.5, 5.2), dpi=200)
    ax = fig.add_subplot(111, projection="3d")
    segs, cols, lws = [], [], []
    for m in data["members"]:
        if m["added"]:
            if not parts or m["type"] in ("CRADLE",): continue
            c = "#c2185b" if m.get("temporary") else PART.get(m["type"], "#555")
            lw = 2.2 if m["type"] in ("STRAP", "V-STRAP", "GUIDE") else (1.6 if m["type"] == "STIRRUP" else 0.7)
        else:
            c = ucol(m.get("util")); lw = 0.6 if (m.get("util") or 0) < 0.8 else 1.4
        segs.append([np.array(m["a"]) / 1000, np.array(m["b"]) / 1000]); cols.append(c); lws.append(lw)
    ax.add_collection3d(Line3DCollection(segs, colors=cols, linewidths=lws))
    if parts:
        for k, p in data["lift_points"].items():
            x, y, z = np.array(p["xyz"]) / 1000
            ax.plot([x, x], [y, y], [z, z + 1.1], color="#6b7785", lw=1.0, ls="--")
            ax.text(x, y, z + 1.2, k, fontsize=7, color=INK, ha="center")
    ax.set_xlim(0, 12); ax.set_ylim(-4.35, 7.65); ax.set_zlim(-1.5, 5.0)
    ax.set_box_aspect((12, 12, 6.5)); ax.view_init(elev=18, azim=-58); ax.set_axis_off()
    ax.set_title(title, fontsize=10, color=INK, loc="left")
    from matplotlib.lines import Line2D
    leg = [Line2D([0], [0], color=c, lw=3, label=l) for c, l in (("#9fb3c8", "below 0.5"), ("#3fa34d", "0.5 - 0.8"), ("#e3a008", "0.8 - 0.95"),
                                                                 ("#f0663a", "0.95 - 1.0"), ("#d1242f", "over 1.0"))]
    if parts:
        leg += [Line2D([0], [0], color=PART["STRAP"], lw=3, label="hanger straps"), Line2D([0], [0], color=PART["V-STRAP"], lw=3, label="V-straps"),
                Line2D([0], [0], color="#c2185b", lw=3, label="temporary straps"), Line2D([0], [0], color=PART["GUIDE"], lw=3, label="lifting heads"),
                Line2D([0], [0], color=PART["STIRRUP"], lw=3, label="cradles / foot plates"), Line2D([0], [0], color=PART["PLANE BRACE"], lw=3, label="plane bracing")]
    ax.legend(handles=leg, loc="upper left", bbox_to_anchor=(0.0, 0.93), fontsize=7, frameon=False, ncol=1)
    fig.subplots_adjust(0, 0, 1, 1)
    fig.savefig(os.path.join(OUT, fname), bbox_inches="tight"); plt.close(fig)


iso(D, "fig_iso_after.png", "Rev C, engineered for the lift: utilisation of every member (envelope of the 11 design cases, factor 2.433)")
iso(B0, "fig_iso_before.png", "Before: the frame as framed, slings straight onto the floor edge truss (same 8 points, same factors)", parts=False)


def elevation(yline, fname, title, openings):
    fig, ax = plt.subplots(figsize=(10, 3.9), dpi=200)
    for m in D["members"]:
        if abs(m["a"][1] - yline) > 60 or abs(m["b"][1] - yline) > 60: continue
        xa, za, xb, zb = m["a"][0] / 1000, m["a"][2] / 1000, m["b"][0] / 1000, m["b"][2] / 1000
        if m["added"]:
            if m["type"] == "CRADLE": continue
            c = "#c2185b" if m.get("temporary") else PART.get(m["type"], "#555")
            ls = "--" if m.get("temporary") else "-"
            lw = 2.4 if m["type"] in ("STRAP", "V-STRAP") else 3.0
            ax.plot([xa, xb], [za, zb], color=c, lw=lw, ls=ls, solid_capstyle="butt", zorder=4)
        else:
            ax.plot([xa, xb], [za, zb], color=ucol(m.get("util")), lw=0.9, zorder=2)
    # cradle / foot plates as rectangles
    seen = set()
    for m in D["members"]:
        if m["type"] == "CRADLE" and m["id"].endswith("_B") and abs(m["a"][1] - yline) < 60:
            x0, x1 = m["a"][0] / 1000, m["b"][0] / 1000
            tmp = m.get("temporary")
            ax.add_patch(Rectangle((x0, -0.2795), x1 - x0, 0.259, fc=("#c2185b" if tmp else "#3b4651"), alpha=0.28, ec=("#c2185b" if tmp else "#3b4651"), lw=0.8, zorder=3))
    for (o0, w, sill, h, lab) in openings:
        ax.add_patch(Rectangle((o0 / 1000, sill / 1000), w / 1000, h / 1000, fc="#dbe9f6", ec=SKY, lw=0.8, zorder=1))
        ax.text((o0 + w / 2) / 1000, (sill + h / 2) / 1000, lab, ha="center", va="center", fontsize=7, color=SKY)
    for k, p in D["lift_points"].items():
        if abs(p["xyz"][1] - yline) > 60: continue
        x, z = p["xyz"][0] / 1000, p["xyz"][2] / 1000
        R = p["reactions_kN"]["R4_equalised"]
        ax.annotate("", xy=(x, z + 0.75), xytext=(x, z + 0.05), arrowprops=dict(arrowstyle="-|>", color=NAVY, lw=1.6))
        ax.text(x, z + 0.82, f"{k}\n{R:.1f} kN", ha="center", va="bottom", fontsize=7.5, color=NAVY)
    ax.set_xlim(-0.3, 12.3); ax.set_ylim(-0.55, 4.6); ax.set_aspect("equal")
    ax.set_xlabel("x along the module (m)"); ax.set_yticks([0, 1, 2, 3]); ax.set_ylabel("z (m)")
    ax.set_title(title, fontsize=10, color=INK, loc="left")
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    fig.savefig(os.path.join(OUT, fname), bbox_inches="tight"); plt.close(fig)


ops_s = []
for w in proj["walls"]:
    if w["id"] == "EW1":
        for o in w["openings"]:
            ops_s.append((o["offset"], o["width"], o["sill"], o["height"], o["kind"]))
elevation(44.5, "fig_elev_south.png", "South wall line (outside face view): members by utilisation, lift parts, sling forces in the main case (unfactored)", ops_s)
elevation(3255.5, "fig_elev_north.png", "North (open) side: posts at 4.5 and 7.5 m, end returns; dashed magenta = temporary straps across the openings",
          [(1050, 3300, 0, 2700, "opening"), (4650, 2700, 0, 2700, "opening"), (7650, 3300, 0, 2700, "opening")])


# ---- plan: floor trusses, bridging, plane bracing, lift points
fig, ax = plt.subplots(figsize=(10, 3.4), dpi=200)
for m in D["members"]:
    a, b = np.array(m["a"]) / 1000, np.array(m["b"]) / 1000
    if m["kind"] in ("floor_truss",) and m["type"] == "TOP CHORD":
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#9fb3c8", lw=1.0)
    if m["kind"] == "rim_truss" and m["type"] == "TOP CHORD":
        ax.plot([a[0], b[0]], [a[1], b[1]], color=INK, lw=2.0)
    if m["type"] == "PLANE BRACE" and m["id"].startswith("F"):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=PART["PLANE BRACE"], lw=1.2)
ax.plot([0.044, 11.956], [1.65, 1.65], color="#7b3fa0", lw=2.0, ls=(0, (4, 2)), label="bridging line (noggings) at mid-span")
for k, p in D["lift_points"].items():
    ax.add_patch(Circle((p["xyz"][0] / 1000, p["xyz"][1] / 1000), 0.09, fc=NAVY, ec="white", lw=1, zorder=5))
    ax.text(p["xyz"][0] / 1000, p["xyz"][1] / 1000 + (0.22 if p["xyz"][1] > 1650 else -0.32), k, ha="center", fontsize=7.5, color=NAVY)
cg = D["meta"]["cg"]
ax.plot(cg[0] / 1000, cg[1] / 1000, marker="P", ms=9, color="#d1242f"); ax.text(cg[0] / 1000 + 0.15, cg[1] / 1000 - 0.25, "centre of gravity", fontsize=7.5, color="#d1242f")
ax.plot([], [], color=PART["PLANE BRACE"], lw=1.2, label="floor plane strap bracing (30 x 1.0)")
ax.plot([], [], color="#9fb3c8", lw=1.0, label="floor trusses at 600 mm")
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, fontsize=7.5, frameon=False)
ax.set_xlim(-0.2, 12.2); ax.set_ylim(-0.4, 3.7); ax.set_aspect("equal"); ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
ax.set_title("Floor plan: lift points, floor plane bracing and the bridging line (the roof plane has the same bracing)", fontsize=10, loc="left", color=INK)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.savefig(os.path.join(OUT, "fig_plan.png"), bbox_inches="tight"); plt.close(fig)


# ---- lift point detail: section across the wall and elevation
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 6.2), dpi=200, gridspec_kw=dict(width_ratios=[1, 1.6]))
def rect(ax, x, y, w, h, fc, ec="#333", lw=0.8, a=1.0, z=2):
    ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec=ec, lw=lw, alpha=a, zorder=z))
# section (y across, z up), mm
for ax_ in (a1,):
    rect(ax_, 0, -300, 89, 300, "#e8edf2")                      # floor rim truss envelope
    rect(ax_, 0, 0, 89, 2700, "#f4f6f8")                        # wall
    rect(ax_, 0, 2700, 89, 300, "#e8edf2")                      # roof rim
    rect(ax_, -2.5, -302.5, 94, 2.5, "#3b4651", z=4)            # cradle base
    rect(ax_, -2.5, -302.5, 2.5, 300, "#3b4651", z=4); rect(ax_, 89, -302.5, 2.5, 300, "#3b4651", z=4)   # cheeks
    rect(ax_, -4.0, -250, 1.5, 3400, PART["STRAP"], ec=PART["STRAP"], z=5); rect(ax_, 92.5, -250, 1.5, 3400, PART["STRAP"], ec=PART["STRAP"], z=5)
    rect(ax_, -7, 2720, 3, 430, PART["GUIDE"], ec="#8a6d00", z=6); rect(ax_, 93, 2720, 3, 430, PART["GUIDE"], ec="#8a6d00", z=6)
    rect(ax_, -7, 3150, 103, 3, PART["GUIDE"], ec="#8a6d00", z=6)
    ax_.add_patch(Circle((44.5, 3100), 10, fc="#555", ec="black", zorder=7)); ax_.add_patch(Circle((44.5, 3100), 16.5, fc="none", ec="#555", lw=1.2, zorder=7))
    ax_.annotate("", xy=(44.5, 3600), xytext=(44.5, 3120), arrowprops=dict(arrowstyle="-|>", color=NAVY, lw=1.5))
    notes = [(3500, "sling to the cascade (vertical, within 2 deg)"), (3100, "M20 lifting pin + sleeve, shackle bow over the sleeve"),
             (2850, "lifting head: folded 3 mm box over the roof edge truss,\nvertical slots - holds sideways, carries no weight"),
             (1400, "hanger strap 50 x 1.5 on each face\n(fixings through slots only)"), (-150, "cradle: folded 2.5 mm U wrapping under\nthe floor edge truss, screwed to both chords")]
    for z, t in notes:
        ax_.annotate(t, xy=(100, z), xytext=(260, z), fontsize=7, va="center", arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
    ax_.set_xlim(-150, 1400); ax_.set_ylim(-450, 3750); ax_.set_aspect("equal"); ax_.set_axis_off()
    ax_.set_title("Section through a lift point (across the wall)", fontsize=9.5, loc="left", color=INK)
# elevation x-z around S2
x0 = 4500
rect(a2, x0 - 1500, -300, 3000, 300, "#e8edf2"); rect(a2, x0 - 1500, 2700, 3000, 300, "#e8edf2")
for xs in np.arange(x0 - 1500, x0 + 1501, 600): rect(a2, xs - 20, 0, 41, 2700, "#dfe5ea", ec="#9aa5b1", lw=0.4)
rect(a2, x0 - 300, -302.5, 600, 302.5, "#3b4651", a=0.35, z=4)
for xf in (x0 - 840, x0 + 840): rect(a2, xf - 300, -300, 600, 300, "#3b4651", a=0.22, z=4)
a2.plot([x0, x0], [-280, 3150], color=PART["STRAP"], lw=3, zorder=5)
for xf in (x0 - 840, x0 + 840): a2.plot([xf, x0], [-280, 3150], color=PART["V-STRAP"], lw=2.4, zorder=5)
rect(a2, x0 - 60, 2720, 120, 430, PART["GUIDE"], ec="#8a6d00", z=6)
a2.annotate("", xy=(x0, 3700), xytext=(x0, 3180), arrowprops=dict(arrowstyle="-|>", color=NAVY, lw=1.5))
R = D["lift_points"]["S2"]["reactions_kN"]["R4_equalised"]
hs = [m for m in D["members"] if m["id"] == "HANG_S2"][0]; vs = [m for m in D["members"] if m["id"].startswith("VSTR_S2")]
a2.text(x0 + 60, 3600, f"sling {R:.1f} kN", fontsize=8, color=NAVY)
a2.text(x0 + 40, 1500, f"hanger pair\n{hs['N_R4_unfactored']:.1f} kN", fontsize=7.5, color=PART["STRAP"])
for v in vs:
    xm = (v["a"][0] + v["b"][0]) / 2 - 120
    a2.text(xm, 900 if v["a"][0] < x0 else 700, f"V-strap pair\n{v['N_R4_unfactored']:.1f} kN", fontsize=7.5, color="#b26b00", ha="center")
a2.text(x0, -430, "cradle 600 long", ha="center", fontsize=7.5); a2.text(x0 - 840, -430, "foot plate", ha="center", fontsize=7.5); a2.text(x0 + 840, -430, "foot plate", ha="center", fontsize=7.5)
a2.set_xlim(x0 - 1600, x0 + 1600); a2.set_ylim(-500, 3800); a2.set_aspect("equal"); a2.set_axis_off()
a2.set_title("Lift point S2 seen from outside (south wall): forces in the main case, unfactored", fontsize=9.5, loc="left", color=INK)
fig.savefig(os.path.join(OUT, "fig_liftpoint.png"), bbox_inches="tight"); plt.close(fig)


# ---- rig schematic
fig, ax = plt.subplots(figsize=(10, 4.2), dpi=200)
xs = [0.9, 4.5, 7.5, 11.1]
R4 = D["cases"]["R4_equalised"]["reactions"]
ax.add_patch(Rectangle((0, 0), 12, 3.3, fc="#eef2f6", ec="#9aa5b1"))
ax.text(6, 1.65, "module (seen from the side)", ha="center", va="center", color=MUTED, fontsize=8)
zc, zm, zt, zh = 4.9, 6.2, 7.4, 8.6
for i, x in enumerate(xs):
    ax.plot([x, x], [3.45, zc], color="#555", lw=1.2)
    s, n = R4[f"S{i + 1}"] / 1e3, R4[f"N{i + 1}"] / 1e3
    ax.text(x + 0.08, 4.1, f"S{i + 1} {s:.1f}\nN{i + 1} {n:.1f} kN", fontsize=7, color=NAVY)
    ax.add_patch(Rectangle((x - 0.35, zc), 0.7, 0.12, fc="#7b8794"))
ax.text(0.05, zc + 0.2, "4 cross beams (span 3.21 m, picked at the CoG across)", fontsize=7, color=INK)
for (xa, xb) in ((0.9, 4.5), (7.5, 11.1)):
    ax.plot([xa, (xa + xb) / 2], [zc + 0.12, zm], color="#555", lw=1.0); ax.plot([xb, (xa + xb) / 2], [zc + 0.12, zm], color="#555", lw=1.0)
    ax.add_patch(Rectangle(((xa + xb) / 2 - 0.9, zm), 1.8, 0.12, fc="#7b8794"))
ax.text(0.05, zm + 0.2, "2 middle beams", fontsize=7, color=INK)
for xm in (2.7, 9.3): ax.plot([xm, 6.0], [zm + 0.12, zt], color="#555", lw=1.0)
ax.add_patch(Rectangle((6.0 - 3.6, zt), 7.2, 0.12, fc="#7b8794")); ax.text(2.0, zt + 0.2, "top beam (pick point set to the weighed CoG)", fontsize=7, color=INK)
ax.plot([6.0, 6.0], [zt + 0.12, zh], color="#555", lw=1.2); ax.add_patch(Circle((6.0, zh + 0.12), 0.12, fc="#555"))
ax.text(6.2, zh, f"hook: {D['meta']['W_N'] / 1e3:.1f} kN module (6.5 t rated) + rigging", fontsize=7.5, color=INK)
ax.set_xlim(-0.3, 12.3); ax.set_ylim(-0.2, 9.2); ax.set_aspect("equal"); ax.set_axis_off()
ax.set_title("Rig: equalising pinned-beam cascade. Every beam hangs from one pin, so each drop's share is fixed by statics, not by sling length", fontsize=9.5, loc="left", color=INK)
fig.savefig(os.path.join(OUT, "fig_rig.png"), bbox_inches="tight"); plt.close(fig)


# ---- ablation chart
names = {"revC_design": "Rev C design", "B0_frame_only": "Before (as framed)", "A1_no_vstraps": "no V-straps", "A2_no_temp_north": "no temporary north straps",
         "A3_two_screws": "2 screws per joint", "A4_no_bridging": "no bridging", "A5_point_cradles": "point stirrups, no cradle plates",
         "A6_no_plane_bracing": "no floor / roof bracing", "S1_lining_credit": "linings counted (sensitivity)"}
order = ["revC_design", "S1_lining_credit", "A4_no_bridging", "A5_point_cradles", "A2_no_temp_north", "A6_no_plane_bracing", "A1_no_vstraps", "A3_two_screws", "B0_frame_only"]
rows = {r["id"]: r for r in AB}
fig, ax = plt.subplots(figsize=(10, 3.6), dpi=200)
yy = np.arange(len(order))
mo = [rows[k]["members_over"] for k in order]; jo = [rows[k]["joints_over"] for k in order]
ax.barh(yy - 0.18, mo, height=0.34, color="#d1242f", label="members over capacity")
ax.barh(yy + 0.18, jo, height=0.34, color="#e3a008", label="screwed joints over capacity")
for i, (a, b) in enumerate(zip(mo, jo)):
    ax.text(a + 2, i - 0.18, str(a), va="center", fontsize=7); ax.text(b + 2, i + 0.18, str(b), va="center", fontsize=7)
ax.set_yticks(yy); ax.set_yticklabels([names[k] for k in order]); ax.invert_yaxis()
ax.set_xlabel("count over 1.0 (envelope of the design cases, factor 2.433)"); ax.legend(frameon=False, fontsize=8, loc="lower right")
ax.set_title("What each measure does: the design with one measure taken away at a time", fontsize=10, loc="left", color=INK)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.savefig(os.path.join(OUT, "fig_ablation.png"), bbox_inches="tight"); plt.close(fig)


# ---- reactions per design case
cases = [c for c in D["cases"] if D["cases"][c]["design"]]
pts = ["S1", "S2", "S3", "S4", "N1", "N2", "N3", "N4"]
fig, ax = plt.subplots(figsize=(10, 3.4), dpi=200)
w = 0.8 / len(cases)
cmap = plt.get_cmap("tab20")
for i, c in enumerate(cases):
    vals = [D["cases"][c]["reactions"].get(p, 0) / 1e3 for p in pts]
    ax.bar(np.arange(8) + (i - len(cases) / 2) * w + w / 2, vals, width=w, color=cmap(i), label=c)
ax.set_xticks(np.arange(8)); ax.set_xticklabels(pts); ax.set_ylabel("sling force, unfactored (kN)")
ax.legend(ncol=5, fontsize=6.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12))
ax.set_title("Sling force at each lift point in every design case (rated 6.5 t, no factors)", fontsize=10, loc="left", color=INK)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.savefig(os.path.join(OUT, "fig_reactions.png"), bbox_inches="tight"); plt.close(fig)
print("figures written to", OUT)
