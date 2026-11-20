"""Design checks of every lift part outside Infinity Framer, with the factored forces taken from the lift model.

usage: python analysis/run_connectors.py <model folder> <config.json> <results folder>

Writes connectors.json and connectors.md (one row per check: demand, capacity, unit, utilisation, rule). Written for the
Rev D layout (A-frame strap pairs on the south side, single vertical hangers on the inside face on the north side,
U-cradles in bearing under the floor edge truss, saddle heads with no fasteners). The Rev C version is
run_connectors_revC.py.
"""
from __future__ import annotations
import sys, os, json, math
from collections import defaultdict
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_lift as RL  # noqa: E402
from liftcalc import connectors as K, liftcase as LC, as4600 as C  # noqa: E402

kN = 1e3


def node_forces_from(B, res, member_ids, factor):
    """Force that a group of (added) members puts on each node they touch, global x y z, factored. Returns {node: vec}."""
    M = B.model
    F = res["end_forces"] * factor
    out = defaultdict(lambda: np.zeros(3))
    for mid in member_ids:
        for e in B.members[mid].get("elements") or []:
            k, T, L, dof = M._ke[e]
            R = T[:3, :3]
            for end, nd in ((0, M.el[e]["i"]), (1, M.el[e]["j"])):
                out[nd] -= R.T @ F[e][6 * end: 6 * end + 3]
    return out


def web_crippling_c(t, fy, d1, r, lb, webs=2, C_=13.0, CR=0.23, CN=0.14, Ch=0.01, phi=0.90):
    """Web crippling of a C section under a one-flange interior load, unfastened (AS/NZS 4600 cl 3.3.6 form with the
    single-web C coefficients of AISI S100-16 Table G5-2), per web, times the number of webs that carry the load."""
    Pw = C_ * t * t * fy * (1 - CR * math.sqrt(r / t)) * (1 + CN * math.sqrt(lb / t)) * (1 - Ch * math.sqrt(d1 / t))
    return phi * Pw * webs


def main():
    model_dir, cfg_path, out_dir = sys.argv[1:4]
    cfg = json.load(open(cfg_path, encoding="utf-8")); cfg["slack_cases"] = False
    r = RL.run(model_dir, cfg, None, quiet=True)
    B = r["B"]; M = B.model; f = r["factor"]
    design = [c for c in r["cases"] if c.get("design", True)]
    env = r["env_a"]
    rows = []

    def row(group, item, demand, capacity, rule, note="", unit="kN"):
        u = demand / capacity if capacity > 0 else float("inf")
        sc = {"kN": kN, "N.mm/mm": 1.0, "N.m": 1.0}[unit]
        rows.append(dict(group=group, item=item, demand=round(demand / sc, 2), capacity=round(capacity / sc, 2), unit=unit, util=round(u, 2), rule=rule, note=note))

    def env_of(pred, key):
        vals = [v[key] for k, v in env.items() if pred(k, v)]
        return max(vals) if vals else 0.0

    one_09 = K.screw_shear(0.95, 0.95, K.FRAME_CONN_FU, K.FRAME_CONN_FU)[1]
    # ---------------------------------------------------------------- 1 straps
    south_pair = env_of(lambda k, v: v["type"] == "V-STRAP", "N_max")
    if south_pair:
        T1 = south_pair / 2
        g = "A-frame strap pair, south (2 x 50 x 1.2 G450)"
        row(g, "strap tension per strap (gross yield / net section at a 14 mm hole)", T1, K.strap_tension(50.0, 1.2, K.G450, hole=14.0)[0], "0.90 Ag fy ; 0.65 An fu")
        row(g, "2 x M12 each end, bearing on the 1.2 mm strap", T1, 2 * K.bolt_bearing(12, 1.2, 480.0), "AISI J3.3.2 deformation-limited, phi 0.65")
        row(g, "tear-out: end bolt e = 30 mm, inner bolt clear distance 40 - 7 = 33 mm", T1, K.bolt_tearout(30.0, 1.2, 480.0) + K.bolt_tearout(33.0, 1.2, 480.0), "0.60 t e fu")
        row(g, "M12 8.8 bolt shear, single plane, threads included", T1 / 2, K.bolt_shear(12), "0.8 x 0.62 x 800 x Ac")
    hang = env_of(lambda k, v: v["type"] == "STRAP", "N_max")
    inner = set(cfg.get("inner_face_sides", []))
    split = cfg.get("strap_split", 0.65)                           # fit-up: the two straps of a pair share at worst 65 / 35
    ts = cfg.get("hanger_strap_t", 2.5)
    if hang and "N" not in inner:
        T1h = split * hang
        g = f"Hanger strap pair (2 x 50 x {ts:g} G450, one on each face, match-drilled; checked at a {split * 100:.0f} / {100 - split * 100:.0f} split)"
        row(g, "strap tension, the more loaded strap (gross yield / bolted thin-sheet net section at a 14 mm hole)", T1h,
            K.strap_tension_bolted(50.0, ts, K.G450, 12.0, 14.0)[0], "0.90 Ag fy ; 0.55 (0.1 + 3d/s) An fu (AS/NZS 4600 5.3.3 form, single shear, washers)")
        row(g, "2 x M12 each end, bearing on the strap", T1h, 2 * K.bolt_bearing(12, ts, 480.0), "AISI J3.3.2 deformation-limited, phi 0.65")
        row(g, "tear-out: end bolt e = 30 mm, inner bolt clear distance 40 - 7 = 33 mm", T1h, K.bolt_tearout(30.0, ts, 480.0) + K.bolt_tearout(33.0, ts, 480.0), "0.60 t e fu")
        row(g, "M12 8.8 bolt shear, single plane, threads included", T1h / 2, K.bolt_shear(12), "0.8 x 0.62 x 800 x Ac")
    elif hang:
        g = "Hanger strap, north, inside face only (1 x 50 x 3.0 G450)"
        row(g, "strap tension (gross yield / net section at a 14 mm hole)", hang, K.strap_tension(50.0, 3.0, K.G450, hole=14.0)[0], "0.90 Ag fy ; 0.65 An fu")
        row(g, "2 x M12 each end, bearing on the 3.0 mm strap", hang, 2 * K.bolt_bearing(12, 3.0, 480.0), "AISI J3.3.2, phi 0.65")
        row(g, "tear-out: end bolt e = 30 mm, inner bolt 33 mm", hang, K.bolt_tearout(30.0, 3.0, 480.0) + K.bolt_tearout(33.0, 3.0, 480.0), "0.60 t e fu")
        row(g, "M12 8.8 bolt shear, single plane", hang / 2, K.bolt_shear(12), "0.8 x 0.62 x 800 x Ac")
    # ---------------------------------------------------------------- 2 cradles: two bearing seats at the truss joint pair
    groups = defaultdict(list)
    for mid, m in B.members.items():
        if m.get("added") and m.get("cradle"): groups[m["cradle"]].append(mid)
    framed = {nd for mm in B.members.values() if not mm.get("added") for _, nd in (mm.get("nodes") or [])}
    worst = dict(c=(0.0, ""), t=(0.0, ""), scr=(0.0, ""), y=(0.0, ""))
    seat_log = []
    for cid, mids in groups.items():
        seats = [x for x in mids if B.members[x]["type"] == "CRADLE SEAT"]
        for case in design:
            for sid in seats:
                for nd, v in node_forces_from(B, case["_res"], [sid], f).items():
                    if nd not in framed: continue
                    tag = f"{cid} seat at x {M.xyz[nd][0]:.0f}, {case['id']}"
                    up, down = max(0.0, float(v[2])), max(0.0, -float(v[2]))
                    t_ch = B.members[B.members[sid]["attached_to"]["b"]]["t"]           # the chord the seat bears on
                    cap_c = web_crippling_c(t_ch, 450.0, 36.0, 2.0, 40.0, webs=2)
                    if up / cap_c > worst.get("cu", (0.0, ""))[0]: worst["cu"] = (up / cap_c, tag, up, cap_c, t_ch)
                    scr = math.hypot(float(v[0]), down)                  # along-truss shear and any uplift: cheek screws
                    if up > worst["c"][0]: worst["c"] = (up, tag)
                    if down > worst["t"][0]: worst["t"] = (down, tag)
                    if scr > worst["scr"][0]: worst["scr"] = (scr, tag)
                    if abs(v[1]) > worst["y"][0]: worst["y"] = (abs(float(v[1])), tag)
                    seat_log.append(dict(cradle=cid, seat=sid, x=round(M.xyz[nd][0], 1), case=case["id"], up_kN=round(up / kN, 2), down_kN=round(down / kN, 2),
                                         along_kN=round(float(v[0]) / kN, 2), across_kN=round(float(v[1]) / kN, 2)))
    if groups:
        g = "Cradle (two 3 mm G450 cheeks 120 x 200 over the joint gusset plates, joined under the chord by 2 x M16 8.8 bearing bolts with 92 mm sleeves, one under each truss joint; screwed at the first joint, bearing only at the second)"
        Pc = worst["c"][0]
        cu = worst["cu"]
        row(g, f"bearing under one truss joint on a 3 x 40 x 89 packer: crippling of the chord's two flanges ({cu[4]:.2f} mm chord; worst: {cu[1]})", cu[2],
            cu[3], "AS/NZS 4600 3.3.6 form (AISI G5 C, interior one-flange, unfastened), phi 0.90",
            "formula outside its test basis here (the chord's own flanges are the crippling webs): UNVERIFIED until the seat test of hold point H4")
        span = cfg.get("cradle_inside", 92.0)
        Mb = Pc * span / 4.0                                             # packer load taken as a point load at mid-span (conservative)
        row(g, f"M16 8.8 bearing bolt bending between the cheeks ({span:.0f} mm span), packer load as a point load at mid-span", Mb / 1e3,
            0.90 * 640.0 * 16.0 ** 3 / 6.0 / 1e3, "plain shank in the bending zone, phi 0.90 fy Zp (fy 640 MPa)", unit="N.m")
        row(g, "M16 8.8 bearing bolt shear at each cheek (2 planes share the seat load)", Pc / 2, K.bolt_shear(16), "0.8 x 0.62 x 800 x Ac")
        row(g, "M16 bearing bolt on the 3 mm cheek (each cheek takes half)", Pc / 2, K.bolt_bearing(16, 3.0, 480.0), "AISI J3.3.2, phi 0.65")
        row(g, "tear-out of the cheek below the bearing bolt, e = 25 mm", Pc / 2, K.bolt_tearout(25.0, 3.0, 480.0), "0.60 t e fu")
        row(g, f"cheek screws at the screwed seat, 2 per cheek: along-truss shear with any uplift (worst: {worst['scr'][1]})", worst["scr"][0],
            K.screw_shear(3.0, 0.95, 480.0, K.FRAME_CONN_FU, n=4)[0], "AS/NZS 4600 5.4.2.4, taken in a 0.95 mm chord at 412.5 MPa (the edge trusses are 1.15), group 0.90")
        Ts = max(south_pair / 2, split * hang if "N" not in inner else hang)
        row(g, "strap bolts below the bearing bolts: 2 x M12 per strap, bearing on the 3 mm cheek", Ts, 2 * K.bolt_bearing(12, 3.0, 480.0), "AISI J3.3.2, phi 0.65")
        row(g, "tear-out of the cheek below the lower strap bolt, e = 30 mm", Ts, K.bolt_tearout(30.0, 3.0, 480.0), "0.60 t e fu")
        row(g, f"sideways force at one seat, carried by a cheek bearing on the chord flange over the 120 mm cheek (worst: {worst['y'][1]})", worst["y"][0],
            0.90 * 450.0 * 0.95 * 120.0 * 0.5, "half the flange yield in bearing over the cheek length (local), phi 0.90",
            "information: small once both faces carry straps")
    # ---------------------------------------------------------------- 3 lifting heads: closed box (two cheeks + two end plates), open top
    head_max = 0.0
    for case in design:
        for k, v in case["_info"]["reactions"].items(): head_max = max(head_max, abs(v))
    P = head_max * f
    lean = cfg.get("lean_fraction", 0.035)
    side = lean * P
    Pres = math.hypot(P, side)
    g = "Lifting head (closed box: two 3 mm G450 cheeks 120 x 480 joined by two 3 mm end plates, open top; M20 8.8 pin with a 40 mm sleeve)"
    row(g, "M20 8.8 lifting pin, double shear", Pres, K.bolt_shear(20, planes=2), "0.8 x 0.62 x 800 x Ac, 2 planes")
    span_pin = 98.0
    row(g, f"M20 pin bending between the cheeks ({span_pin:.0f} mm), sling on the sleeve taken as a point load at mid-span", Pres * span_pin / 4.0,
        0.90 * 640.0 * 20.0 ** 3 / 6.0, "plain shank, phi 0.90 fy Zp (fy 640 MPa)", unit="N.m")
    row(g, "pin bearing on the two 3 mm cheeks (the straps bolt to the cheeks separately)", Pres, 2 * K.bolt_bearing(20, 3.0, 480.0), "AISI J3.3.2, phi 0.65")
    row(g, "tear-out above the pin, e = 45 mm, 2 cheeks of 3 mm", Pres, 2 * K.bolt_tearout(45.0, 3.0, 480.0), "0.60 t e fu")
    row(g, "strap bolts at the head: 2 x M12 per strap, bearing on the 3 mm cheek", max(south_pair / 2, split * hang if "N" not in inner else hang), 2 * K.bolt_bearing(12, 3.0, 480.0), "AISI J3.3.2, phi 0.65")
    gv = env_of(lambda k, v: v["type"] == "GUIDE", "V")
    gl = max([max(abs(v["N_max"]), abs(v["N_min"]), v["V"]) for v in env.values() if v["type"] == "GUIDE LINK"] or [0.0])
    bear = 1.6 * max(gv, gl)
    row(g, "head bearing on the roof edge truss top chord (no fasteners; stop block along the module): 1.6 x the guide force (lever to the bottom chord), web crippling over a 40 mm pad", bear,
        web_crippling_c(0.95, 450.0, 87.0, 2.0, 40.0, webs=1), "AS/NZS 4600 3.3.6 form, one web")
    Zbox = (2 * (120.0 * 3.0) * 50.5 ** 2 + 2 * (3.0 * 101.0 ** 3 / 12.0)) / 52.0
    row(g, f"sideways load at the pin ({lean * 100:.1f} % of the sling force, the 2 deg drop limit), closed box as a cantilever 170 mm above the truss", side * 170.0 / 1e3,
        0.90 * 450.0 * Zbox / 1e3, "box of two cheeks and two end plates, phi 0.90 fy Z", unit="N.m")
    # ---------------------------------------------------------------- 4 cleats, ties, gussets, chord plates
    tie_max = defaultdict(float)
    for i, v in r["env_l"].items():
        if v["tie"]: tie_max[v["rule"]] = max(tie_max[v["rule"]], v["N_max"])
    ncl = int((cfg.get("link_screws") or {}).get("truss end vertical screwed to the rim (end reaction)", 4))
    cleat = K.screw_shear(1.5, 0.95, 480.0, K.FRAME_CONN_FU, n=ncl)[0]
    t1 = max([tie_max.get(k, 0.0) for k in ("floor truss chord end to floor rim chord", "roof truss chord end to roof rim chord")] + [0.0])
    ter = max([v["util_shear"] * ncl * one_09 * K.GROUP for v in r["env_l"].values() if v["rule"].startswith("truss end vertical")] or [0.0])
    g = f"Truss-end cleat (folded 1.5 mm G450 angle, full depth 280 mm, each side of every truss end; {ncl} screws into the end vertical, {ncl} into the edge-truss chords: 3 bottom, 2 top)"
    row(g, "chord pull at the truss end, through the cleat leg screws in shear", t1, cleat, f"{ncl} screws per leg in shear, group 0.90")
    row(g, "end reaction through the end vertical (per tie of the model)", ter, cleat, f"{ncl} screws per leg in shear, group 0.90")
    t2 = max([tie_max.get(k, 0.0) for k in ("wall top track under roof rim / end roof truss", "wall bottom track on floor rim / end floor truss")] + [0.0])
    t3 = tie_max.get("wall panel to wall panel (seam studs, corner studs, stacked tracks)", 0.0)
    row("Tie T2 (40 x 1.0 G300 strap on the side faces of the track and edge truss, 4 + 4 screws)", "wall plate to edge truss tension", t2,
        min(K.screw_shear(1.0, 0.95, 340.0, K.FRAME_CONN_FU, n=4)[0], K.strap_tension(40.0, 1.0, K.G300, hole=5.0)[0]), "screws in shear, group 0.90; strap net section")
    row("Tie T3 (30 x 0.8 G300 strap across a wall seam, 2 + 2 screws)", "seam stud pull-apart", t3,
        min(K.screw_shear(0.8, 0.95, 340.0, K.FRAME_CONN_FU, n=2)[0], K.strap_tension(30.0, 0.8, K.G300, hole=5.0)[0]), "screws in shear; strap net section")
    jg = max([v["demand"] for v in r["env_j"].values() if v["fasteners"] >= 10] or [0.0])
    row("Joint gusset (1.5 mm G450 plate each face, 3 + 3 screws per face)", "largest gusseted joint force against the plate pair (100 mm wide) in tension", jg,
        2 * K.strap_tension(100.0, 1.5, K.G450, hole=5.0)[0], "0.90 Ag fy / 0.65 An fu", "the screws are in the joint check (10 screw-equivalents)")
    cp = [k for k, v in r["env_m"].items() if B.members[k].get("built_up")]
    if cp:
        Nb = max(abs(r["env_m"][k]["N"]) for k in cp)
        row("Chord flat bar (3 x 89 G450 under the north edge-truss bottom chords, screwed at 100 mm)", "screws that tie bar and chord: shear flow from the bar's share of the chord force over a 400 mm panel",
            Nb * (267.0 / 437.0) / 4.0, K.screw_shear(3.0, 0.95, 480.0, K.FRAME_CONN_FU, n=4)[0], "4 screws per 400 mm panel in shear (100 mm pitch)",
            "the member check treats the plated chord as a doubled chord")
    # ---------------------------------------------------------------- 5 bracing and bridging
    pbs = [v for v in env.values() if v["type"] == "PLANE BRACE"]
    if pbs:
        T_pb = 2 * max(max(v["N_max"] for v in pbs), -min(v["N_min"] for v in pbs))
        row("Plane bracing (30 x 1.0 G300 strap, tensioner)", "strap tension (tension diagonal carries both halves)", T_pb, K.strap_tension(30.0, 1.0, K.G300, hole=5.0)[0], "0.90 Ag fy ; 0.65 An fu")
        row("Plane bracing (30 x 1.0 G300 strap, tensioner)", "end fixing: 3 screws into the edge truss chord", T_pb, K.screw_shear(1.0, 0.95, 340.0, K.FRAME_CONN_FU, n=3)[0], "screws in shear, group 0.90")
    brs = [v for v in env.values() if v["type"] == "BRIDGING"]
    if brs:
        nb = max(max(v["N_max"] for v in brs), -min(v["N_min"] for v in brs))
        row("Bridging (C89 0.95 noggings at truss mid-span, floor and roof)", "largest nogging force (from the model), 2 screws each end", nb,
            K.screw_shear(0.95, 0.95, K.FRAME_CONN_FU, K.FRAME_CONN_FU, n=2)[0], "screws in shear")
    # ---------------------------------------------------------------- 6 stud bearing on the track over the edge truss
    stud_c = 0.0
    for k, v in r["env_m"].items():
        mm = B.members[k]
        if mm["kind"] == "wall" and mm["type"] in ("STUD", "KING STUD", "JAMB", "POST") and v["N"] < 0: stud_c = max(stud_c, -v["N"])
    row("Stud bearing on the bottom track over the floor edge truss", "largest stud compression in the design cases (studs seated, end gap at most 1 mm: hold point)", stud_c,
        web_crippling_c(0.95, 450.0, 36.0, 2.0, 38.0, webs=2), "AS/NZS 4600 3.3.6 form, the chord's two flanges")
    # ---------------------------------------------------------------- rigging interface
    static = head_max * cfg["factors"]["weight"] * cfg["factors"]["cog"]
    rig = dict(max_static_drop_kN=round(static / kN, 2), max_static_drop_t=round(static / 9.80665 / 1000, 2),
               note="largest drop force in the design cases x weight 1.03 x CoG 1.05 (no dynamic factor): drop gear WLL at least this. "
                    "Interface: round sling eye down through the open top of the head box onto the free-turning 40 mm sleeve on the M20 pin, "
                    "cheek tops fitted with edge protectors; shackles only at the beam ends. The rig (beams, slings, shackles) is lifting "
                    "equipment: designed, certified to AS 4991, proof tested and rated; drops within 2 deg of vertical.")
    out = dict(config=cfg.get("name"), factor=f, rows=rows, rigging=rig, seats=seat_log if groups else [])
    os.makedirs(out_dir, exist_ok=True)
    json.dump(out, open(os.path.join(out_dir, "connectors.json"), "w"), indent=1)
    md = ["| Part | Check | Demand | Capacity | Unit | Util | Rule |", "|---|---|---|---|---|---|---|"]
    for x in rows:
        md.append(f"| {x['group']} | {x['item']} | {x['demand']} | {x['capacity']} | {x['unit']} | {x['util']} | {x['rule']} |")
    open(os.path.join(out_dir, "connectors.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    for x in rows:
        flag = "  <-- OVER" if x["util"] > 1.0 else ""
        print(f"{x['util']:5.2f}  {x['demand']:8.2f} / {x['capacity']:8.2f} {x['unit']:7s} {x['group'][:44]:44s} {x['item'][:80]}{flag}")
    print("rigging:", rig)


if __name__ == "__main__":
    main()
