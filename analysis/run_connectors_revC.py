"""Design checks of every lift part outside Infinity Framer, with the factored forces taken from the lift model.

usage: python analysis/run_connectors.py <model folder> <config.json> <results folder>

Writes connectors.json and connectors.md (one row per check: demand, capacity, utilisation, rule).
"""
from __future__ import annotations
import sys, os, json, math
from collections import defaultdict
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_lift as RL  # noqa: E402
from liftcalc import connectors as K, liftcase as LC  # noqa: E402

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
                f_loc = F[e][6 * end: 6 * end + 3]
                out[nd] -= R.T @ f_loc                      # the member pushes the node with minus its end action
    return out


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

    def env_type(t, key):
        vals = [v[key] for v in env.values() if v["type"] == t]
        return max(vals) if vals else 0.0

    # ---------------------------------------------------------------- 1 hanger straps (pair, one each face)
    T_pair = env_type("STRAP", "N_max"); T1 = T_pair / 2
    cap, det = K.strap_tension(50.0, 1.5, K.G450, hole=14.0)
    row("Hanger strap HS (2 x 50 x 1.5 G450)", "strap tension per strap (gross yield / net section at M12 hole)", T1, cap, "0.90 Ag fy ; 0.65 An fu")
    row("Hanger strap HS (2 x 50 x 1.5 G450)", "2 x M12 bolts each end, bearing on the 1.5 mm strap", T1, 2 * K.bolt_bearing(12, 1.5, 480.0), "AISI J3.3.2 deformation-limited, phi 0.65")
    row("Hanger strap HS (2 x 50 x 1.5 G450)", "end tear-out, 2 bolts, e = 30 mm, pitch 40 mm", T1, K.bolt_tearout(30.0, 1.5, 480.0) + K.bolt_tearout(40.0, 1.5, 480.0), "0.60 t e fu")
    row("Hanger strap HS (2 x 50 x 1.5 G450)", "M12 8.8 bolt shear, single plane, threads included", T1 / 2, K.bolt_shear(12), "0.8 x 0.62 x 800 x Ac")
    # ---------------------------------------------------------------- 2 inclined straps
    V_pair = env_type("V-STRAP", "N_max"); V1 = V_pair / 2
    cap, det = K.strap_tension(50.0, 1.2, K.G450, hole=14.0)
    row("Inclined strap VS (2 x 50 x 1.2 G450)", "strap tension per strap", V1, cap, "0.90 Ag fy ; 0.65 An fu")
    row("Inclined strap VS (2 x 50 x 1.2 G450)", "2 x M12 bolts each end, bearing on the 1.2 mm strap", V1, 2 * K.bolt_bearing(12, 1.2, 480.0), "AISI J3.3.2, phi 0.65")
    row("Inclined strap VS (2 x 50 x 1.2 G450)", "end tear-out, 2 bolts, e = 30 / 40 mm", V1, K.bolt_tearout(30.0, 1.2, 480.0) + K.bolt_tearout(40.0, 1.2, 480.0), "0.60 t e fu")

    # ---------------------------------------------------------------- 3 cradles and foot plates: screws into the rim chords
    one_scr = K.screw_shear(2.5, 0.95, 480.0, K.FRAME_CONN_FU)[1]
    groups = defaultdict(list)
    for mid, m in B.members.items():
        if m.get("added") and m.get("cradle"): groups[m["cradle"]].append(mid)
    framed_node_set = {nd for y, mm in B.members.items() if not mm.get("added") for _, nd in (mm.get("nodes") or [])}
    worst = {"cradle": dict(local=0.0, total=0.0), "foot": dict(local=0.0, total=0.0)}
    for cid, mids in groups.items():
        kind = "foot" if cid.startswith("VFOOT") else "cradle"
        xs = B.members[cid]["a"][0]
        strap_ids = [x for x, mm in B.members.items() if mm.get("added") and mm["type"] in ("STRAP", "V-STRAP") and
                     abs(mm["a"][0] - xs) < 1.0 and abs(mm["a"][1] - B.members[cid]["a"][1]) < 1.0]
        nodes = {nd for x in mids for _, nd in (B.members[x].get("nodes") or [])} & framed_node_set
        for case in design:
            nf = node_forces_from(B, case["_res"], mids + strap_ids, f)
            loc = tot = 0.0
            for nd in nodes:
                vv = nf[nd].copy()
                if kind == "cradle" and M.xyz[nd][2] < -200 and vv[2] > 0: vv[2] = 0.0     # upward on the bottom chord: bearing on the folded base
                mag = float(np.linalg.norm(vv)); tot += mag
                if abs(M.xyz[nd][0] - xs) <= 150.0: loc += mag
            worst[kind]["local"] = max(worst[kind]["local"], loc); worst[kind]["total"] = max(worst[kind]["total"], tot)
    pitch = cfg.get("cradle_screw_pitch", 100.0)
    st_per_chord = int(round(2 * cfg.get("cradle_half", 300.0) / pitch)) + 1
    n_total = st_per_chord * 2 * 2 * 2                    # stations x 2 chords x 2 faces x 2 screws
    n_local = 3 * 2 * 2 * 2                               # the 3 stations within 150 mm of the strap bolts, both chords, both faces
    for kind, lab in (("cradle", "Cradle FC (2.5 mm G450 folded U, 600 long)"), ("foot", "Foot plate FP (2.0 mm G450 pair, 600 long)")):
        row(lab, f"screws within 150 mm of the strap bolts ({n_local} screws: 3 stations x 2 chords x 2 faces x 2)", worst[kind]["local"],
            K.screw_shear(2.0, 0.95, 480.0, K.FRAME_CONN_FU, n=n_local)[0], "AS/NZS 4600 5.4.2.4 in the 0.95 mm chord at 412.5 MPa, group 0.90",
            "upward force on the cradle base goes in bearing" if kind == "cradle" else "no bearing assumed: everything through screws")
        row(lab, f"all screws of the plate pair ({n_total} screws at {pitch:.0f} mm, 2 per face per chord)", worst[kind]["total"],
            K.screw_shear(2.0, 0.95, 480.0, K.FRAME_CONN_FU, n=n_total)[0], "as above")
    # ---------------------------------------------------------------- 4 cradle base bearing under the floor rim chord
    w = T_pair / 600.0                                    # N/mm along the cradle
    Mstrip = w * 89.0 / 8.0
    row("Cradle FC (2.5 mm G450 folded U)", "base fold bending under the rim bottom chord (89 mm span between cheeks, per mm of length)", Mstrip, K.plate_bending_strip(2.5),
        "elastic plate strip, phi 0.90 fy t^2/6", unit="N.mm/mm")
    row("Cradle FC (2.5 mm G450 folded U)", "2 x M12 bolts each strap, bearing on the 2.5 mm cheek", T1, 2 * K.bolt_bearing(12, 2.5, 480.0), "AISI J3.3.2, phi 0.65")

    # ---------------------------------------------------------------- 5 lifting head
    head_max = 0.0
    for case in design:
        for k, v in case["_info"]["reactions"].items(): head_max = max(head_max, abs(v))
    P = head_max * f
    side = 0.105 * P                                      # sideways at the lug: 6 degree drop tolerance (rigging check)
    Pres = math.hypot(P, side)
    row("Lifting head LH (3 mm G450 box, M20 pin)", "M20 8.8 lifting pin, double shear", Pres, K.bolt_shear(20, planes=2), "0.8 x 0.62 x 800 x Ac, 2 planes")
    row("Lifting head LH (3 mm G450 box, M20 pin)", "pin bearing on 2 cheeks of 3 mm + 2 straps of 1.5 mm", Pres,
        2 * (K.bolt_bearing(20, 3.0, 480.0) + K.bolt_bearing(20, 1.5, 480.0)), "AISI J3.3.2, phi 0.65")
    row("Lifting head LH (3 mm G450 box, M20 pin)", "tear-out above the pin, e = 45 mm, 2 cheeks of 3 mm", Pres, 2 * K.bolt_tearout(45.0, 3.0, 480.0), "0.60 t e fu")
    gv = env_type("GUIDE", "V"); gm = env_type("GUIDE", "M")
    # the head box is screwed to the roof rim through vertical slots over the 259 mm between the chords: couple + shear
    F_scr = gv / 2 + gm / 259.0
    row("Lifting head LH (3 mm G450 box, M20 pin)", "bolts to the roof rim (sideways / along the module): 2 x M12 at each chord, bearing in the 0.95 mm chord pair",
        F_scr, 2 * K.bolt_bearing(12, 0.95, K.FRAME_CONN_FU) * 2, "AISI J3.3.2 at 412.5 MPa", "vertical slots: no vertical load into the roof rim")
    row("Lifting head LH (3 mm G450 box, M20 pin)", "sideways load on the head (10.5 % of the sling force) carried by the box, cantilever 170 mm",
        side * 170.0 / 1e3, 0.90 * 450.0 * 2 * (89.0 * 3.0 ** 2 / 6 + 3.0 * 89.0 ** 2 / 6) / 1e3, "box section of two 3 mm cheeks + flanges, phi 0.90 fy Z",
        unit="N.m")

    # ---------------------------------------------------------------- 6 ties where a frame joint would otherwise pull on screws
    tie_max = defaultdict(float)
    for i, v in r["env_l"].items():
        if v["tie"]: tie_max[v["rule"]] = max(tie_max[v["rule"]], v["N_max"])
    t1 = max([tie_max.get(k, 0.0) for k in ("floor truss chord end to floor rim chord", "roof truss chord end to roof rim chord")] + [0.0])
    t2 = max([tie_max.get(k, 0.0) for k in ("wall top track under roof rim / end roof truss", "wall bottom track on floor rim / end floor truss")] + [0.0])
    t3 = tie_max.get("wall panel to wall panel (seam studs, corner studs, stacked tracks)", 0.0)
    row("Tie T1 (40 x 1.0 G300 flat plate over the chord joint, 2 + 2 screws)", "truss chord to rim chord tension", t1, min(K.screw_shear(1.0, 0.95, 340.0, K.FRAME_CONN_FU, n=2)[0],
        K.strap_tension(40.0, 1.0, K.G300, hole=5.0)[0]), "screws in shear; strap net section")
    row("Tie T2 (30 x 0.8 G300 strap, 2 + 2 screws)", "wall plate to rim tension", t2, min(K.screw_shear(0.8, 0.95, 340.0, K.FRAME_CONN_FU, n=2)[0],
        K.strap_tension(30.0, 0.8, K.G300, hole=5.0)[0]), "screws in shear; strap net section")
    row("Tie T3 (30 x 0.8 G300 strap across a wall seam, 2 + 2 screws)", "seam stud pull-apart", t3, min(K.screw_shear(0.8, 0.95, 340.0, K.FRAME_CONN_FU, n=2)[0],
        K.strap_tension(30.0, 0.8, K.G300, hole=5.0)[0]), "screws in shear; strap net section")

    # ---------------------------------------------------------------- 7 plane bracing and bridging
    pb = max(env_type("PLANE BRACE", "N_max"), -min(v["N_min"] for v in env.values() if v["type"] == "PLANE BRACE"))
    T_pb = 2 * pb                                          # tension-only pair modelled as half area both ways
    row("Plane bracing PB (30 x 1.0 G300 strap, tensioner)", "strap tension (tension diagonal carries both halves)", T_pb, K.strap_tension(30.0, 1.0, K.G300, hole=5.0)[0], "0.90 Ag fy ; 0.65 An fu")
    row("Plane bracing PB (30 x 1.0 G300 strap, tensioner)", "end fixing: 3 screws into the rim chord", T_pb, K.screw_shear(1.0, 0.95, 340.0, K.FRAME_CONN_FU, n=3)[0], "screws in shear, group 0.90")
    ftc = max((v["N"] for k, v in r["env_m"].items() if B.members[k]["kind"] == "floor_truss" and B.members[k]["type"] == "TOP CHORD"), key=abs)
    n_tr = len({B.members[k]["panel"] for k in r["env_m"] if B.members[k]["kind"] == "floor_truss"})
    restr = 0.025 * abs(ftc)
    row("Bridging BR (C89 0.95 noggings at floor truss mid-span)", "restraint force at one truss (2.5 % of its top chord compression), 2 screws", restr,
        K.screw_shear(0.95, 0.95, K.FRAME_CONN_FU, K.FRAME_CONN_FU, n=2)[0], "screws in shear")
    row("Bridging BR (C89 0.95 noggings at floor truss mid-span)", f"accumulated restraint of all {n_tr} trusses at one end anchor (anchors at both ends), 6 screws", restr * n_tr,
        K.screw_shear(0.95, 0.95, K.FRAME_CONN_FU, K.FRAME_CONN_FU, n=6)[0], "screws in shear, group 0.90", "conservative: all trusses in phase, taken by one anchor")

    # ---------------------------------------------------------------- rigging interface (static, unfactored by DAF)
    static = head_max * cfg["factors"]["weight"] * cfg["factors"]["cog"]
    rig = dict(max_static_drop_kN=round(static / kN, 2), max_static_drop_t=round(static / 9.80665 / 1000, 2),
               note="largest drop force in the design cases (10 % skew included) x weight 1.03 x CoG 1.05; drop gear WLL to be at least this, "
                    "recommended 2 t round slings with 3.25 t bow shackles over the sleeved M20 head pin")
    out = dict(config=cfg.get("name"), factor=f, rows=rows, rigging=rig)
    os.makedirs(out_dir, exist_ok=True)
    json.dump(out, open(os.path.join(out_dir, "connectors.json"), "w"), indent=1)
    md = ["| Part | Check | Demand | Capacity | Unit | Util | Rule |", "|---|---|---|---|---|---|---|"]
    for x in rows:
        md.append(f"| {x['group']} | {x['item']} | {x['demand']} | {x['capacity']} | {x['unit']} | {x['util']} | {x['rule']} |")
    open(os.path.join(out_dir, "connectors.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    for x in rows:
        flag = "  <-- OVER" if x["util"] > 1.0 else ""
        print(f"{x['util']:5.2f}  {x['demand']:7.2f} / {x['capacity']:7.2f} {x['unit']:7s} {x['group'][:40]:40s} {x['item'][:84]}{flag}")
    print("rigging:", rig)


if __name__ == "__main__":
    main()
