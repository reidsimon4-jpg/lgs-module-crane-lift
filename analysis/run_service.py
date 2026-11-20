"""In-service gravity check of the lift-engineered module (a sanity check, not the full in-service design).

usage: python analysis/run_service.py <model folder> <config.json> <results folder>

Same frame model and added parts as the lift run. Loads: G = the itemised finished mass (no rating up), Q = floor live load
on the floor trusses and roof live load on the roof trusses. Combination 1.2 G + 1.5 Q (AS/NZS 1170.0), and 1.35 G.
Supports (two layouts, both reported):
  piers  - the module on piers under both floor rims at no more than 1.8 m: the 8 lift cradles, the 4 corners and 6 more;
  bearer - the module on continuous bearers under both floor rims (every rim bottom-chord node held vertically).
In service the floor truss top chords are restrained by the structural flooring screwed at 300 mm (normal floor design
practice; the lift check takes no credit for it). Rev D has no temporary parts: every lift part stays (the straps carry
nothing in service because the lifting heads are free vertically).
Not covered: wind, earthquake, point loads on the floor, the floor sheet, the roof sheeting and the foundations.
"""
from __future__ import annotations
import sys, os, json, copy
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_lift as RL  # noqa: E402
from liftcalc import framemodel as F, masses as MS, liftcase as LC, as4600 as C  # noqa: E402

G_ACC = 9.80665


def live_load(B, case, kind, q_kPa, x_extent):
    """Area live load (kPa) on the top chords of the trusses of one kind, by tributary width (as masses.spread_area)."""
    mm = {"area_items": {"roof": [], "ceiling": [], "floor": [], "wall": []}, "lumps": [], "extents": {"x": x_extent}}
    key = "floor" if kind == "floor_truss" else "roof"
    mm["area_items"][key] = [{"name": "live", "kg_m2": q_kPa * 1000.0 / G_ACC}]
    # use the mass spreader on a scratch load case, then copy only the area part
    M = B.model
    before = dict(M.loads.get(case, {}))
    tmp = "_tmp_" + case
    M.loads[tmp] = {}
    led = MS.apply(B, dict(mm, rated_lift_mass_kg=None), {"walls": []}, case=tmp)
    # MS.apply also books the steel frame: remove it by subtracting a steel-only run
    steel = "_steel_" + case
    M.loads[steel] = {}
    MS.apply(B, {"area_items": {"roof": [], "ceiling": [], "floor": [], "wall": []}, "lumps": [], "extents": {"x": x_extent}}, {"walls": []}, case=steel)
    out = dict(before)
    for k, v in M.loads[tmp].items():
        out[k] = out.get(k, 0.0) + v - M.loads[steel].get(k, 0.0)
    M.loads[case] = out
    del M.loads[tmp], M.loads[steel]
    return led


def service_joint_demands(cfg, model_dir=None):
    """Joint check of the in-service ULS case (1.2 G + 1.5 Q) on continuous bearers, with the config's joint screws.
    Returns {joint id: joint check row} (used by size_joints.py to size the gussets)."""
    model_dir = model_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model", "engineered")
    B, M, rimBC, piers, sv, led = build(cfg, model_dir)
    M.fixed.clear(); M.nspring = []
    for nd in rimBC: M.fix(nd, [2])
    M.fix(rimBC[0], [0, 1]); M.fix(rimBC[-1], [1])
    if hasattr(M, "K"): del M.K
    res = M.solve(["ULS1"])
    return LC.check_joints(B, res["ULS1"], C.CONN_LOW, extra_fasteners=RL.extra_fasteners(B, cfg))


def build(cfg, model_dir):
    sv = cfg.get("service", {"floor_live_kPa": 3.0, "roof_live_kPa": 0.25})
    snap = F.load_snapshot(os.path.join(model_dir, "framed.json")); proj = json.load(open(os.path.join(model_dir, "project.json"), encoding="utf-8"))
    cfg = copy.deepcopy(cfg)
    cfg["v_legs"] = [lg for lg in cfg.get("v_legs", []) if not lg.get("temporary")]
    B = F.build(snap, options=cfg.get("build_options"), additions={"members": RL.lift_additions(cfg, proj, snap)})
    M = B.model
    mm = MS.load_mass_model(os.path.join(os.path.dirname(model_dir.rstrip("/\\")), "mass_model.json"))
    mm["rated_lift_mass_kg"] = None
    led = MS.apply(B, mm, proj, case="G")
    M.loads["Q"] = {}
    live_load(B, "Q", "floor_truss", sv["floor_live_kPa"], [0, 12000])
    live_load(B, "Q", "roof_truss", sv["roof_live_kPa"], [0, 12000])
    M.loads["ULS1"] = {k: 1.2 * M.loads["G"].get(k, 0.0) + 1.5 * M.loads["Q"].get(k, 0.0) for k in set(M.loads["G"]) | set(M.loads["Q"])}
    M.loads["ULS2"] = {k: 1.35 * v for k, v in M.loads["G"].items()}
    M.loads["SLS"] = {k: M.loads["G"].get(k, 0.0) + 0.7 * M.loads["Q"].get(k, 0.0) for k in set(M.loads["G"]) | set(M.loads["Q"])}
    rimBC = sorted({nd for m in B.members.values() if m["kind"] == "rim_truss" and m["type"] == "BOTTOM CHORD" for _, nd in (m.get("nodes") or [])})
    xyz = np.array(M.xyz)
    piers = []
    for y in cfg["rim_y"].values():
        for x in sorted(set(list(cfg["lift_lines_x"]) + [30.0, 11970.0] + list(sv.get("extra_pier_x", [2700.0, 6000.0, 9300.0])))):
            piers.append(min(rimBC, key=lambda n: (xyz[n][0] - x) ** 2 + (xyz[n][1] - y) ** 2))
    return B, M, rimBC, piers, sv, led


def main():
    model_dir, cfg_path, out_dir = sys.argv[1:4]
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    sv = cfg.get("service", {"floor_live_kPa": 3.0, "roof_live_kPa": 0.25})
    snap = F.load_snapshot(os.path.join(model_dir, "framed.json")); proj = json.load(open(os.path.join(model_dir, "project.json"), encoding="utf-8"))
    cfg = copy.deepcopy(cfg)
    cfg["v_legs"] = [lg for lg in cfg.get("v_legs", []) if not lg.get("temporary")]   # the temporary lift straps are gone in service
    B = F.build(snap, options=cfg.get("build_options"), additions={"members": RL.lift_additions(cfg, proj, snap)})
    M = B.model
    mm = MS.load_mass_model(os.path.join(os.path.dirname(model_dir.rstrip("/\\")), "mass_model.json"))
    mm["rated_lift_mass_kg"] = None                                      # in service: the itemised mass as it is
    led = MS.apply(B, mm, proj, case="G")
    M.loads["Q"] = {}
    live_load(B, "Q", "floor_truss", sv["floor_live_kPa"], [0, 12000])
    live_load(B, "Q", "roof_truss", sv["roof_live_kPa"], [0, 12000])
    Wg = LC.total_vertical_load(M, "G"); Wq = LC.total_vertical_load(M, "Q")
    print(f"G = {Wg / 1e3:.1f} kN ({led['itemised_kg']:.0f} kg), Q = {Wq / 1e3:.1f} kN (floor {sv['floor_live_kPa']} kPa, roof {sv['roof_live_kPa']} kPa)")
    M.loads["ULS1"] = {k: 1.2 * M.loads["G"].get(k, 0.0) + 1.5 * M.loads["Q"].get(k, 0.0) for k in set(M.loads["G"]) | set(M.loads["Q"])}
    M.loads["ULS2"] = {k: 1.35 * v for k, v in M.loads["G"].items()}
    M.loads["SLS"] = {k: M.loads["G"].get(k, 0.0) + 0.7 * M.loads["Q"].get(k, 0.0) for k in set(M.loads["G"]) | set(M.loads["Q"])}
    rimBC = sorted({nd for m in B.members.values() if m["kind"] == "rim_truss" and m["type"] == "BOTTOM CHORD" for _, nd in (m.get("nodes") or [])})
    xyz = np.array(M.xyz)
    piers = []
    for y in cfg["rim_y"].values():
        for x in sorted(set(list(cfg["lift_lines_x"]) + [30.0, 11970.0] + list(sv.get("extra_pier_x", [2700.0, 6000.0, 9300.0])))):
            piers.append(min(rimBC, key=lambda n: (xyz[n][0] - x) ** 2 + (xyz[n][1] - y) ** 2))
    steel = getattr(C, cfg.get("steel", "G450"))
    extra = RL.extra_fasteners(B, cfg)
    out = {"G_kN": Wg / 1e3, "Q_kN": Wq / 1e3, "itemised_kg": led["itemised_kg"], "layouts": {}}
    for layout, nodes in (("piers", piers), ("bearer", rimBC)):
        M.fixed.clear(); M.nspring = []
        for nd in nodes: M.fix(nd, [2])
        M.fix(nodes[0], [0, 1]); M.fix(nodes[-1], [1])
        if hasattr(M, "K"): del M.K
        res = M.solve(["ULS1", "ULS2", "SLS"])
        row = {}
        for c in ("ULS1", "ULS2"):
            rs = dict(cfg.get("restraint_lines") or {}); rs.update(sv.get("restraint_lines", {"floor_truss|TOP CHORD": 300.0}))   # flooring screwed at 300 mm
            mc = LC.check_members(B, res[c], steel, lining=False, restraint=rs)
            jc = LC.check_joints(B, res[c], C.CONN_LOW, extra_fasteners=extra)
            lk = LC.check_links(B, res[c], C.CONN_LOW, screws_by_rule=cfg.get("link_screws"))
            wm = sorted(mc.items(), key=lambda kv: -kv[1]["util"])[:6]; wj = sorted(jc.items(), key=lambda kv: -kv[1]["util"])[:6]
            row[c] = dict(members_over=sum(1 for v in mc.values() if v["util"] > 1), joints_over=sum(1 for v in jc.values() if v["util"] > 1),
                          links_over_shear=sum(1 for v in lk if v["util_shear"] > 1), max_member=max(v["util"] for v in mc.values()),
                          max_joint=max(v["util"] for v in jc.values()), max_link_shear=max(v["util_shear"] for v in lk),
                          worst_members=[(B.members[k]["panel"], B.members[k]["type"], round(v["util"], 2), v["mode"][:40]) for k, v in wm],
                          worst_joints=[(v["panel"], B.members[v["member"]]["type"] if v["member"] else "", round(v["util"], 2), round(v["demand"] / 1e3, 2)) for k, v in wj])
        u = res["SLS"]["u"]
        ft = [m for m in B.members.values() if m["kind"] == "floor_truss" and m["type"] == "TOP CHORD" and m.get("nodes")]
        sag = 0.0
        for m in ft:
            nds = [nd for _, nd in m["nodes"]]
            ends = (u[nds[0], 2] + u[nds[-1], 2]) / 2
            sag = min(sag, min(u[n, 2] for n in nds) - ends)
        row["floor_truss_relative_sag_SLS_mm"] = round(float(sag), 1)
        row["max_settlement_mm"] = round(float(u[:, 2].min()), 1)
        out["layouts"][layout] = row
        print(f"--- {layout}: ULS 1.2G+1.5Q members>1 {row['ULS1']['members_over']} (max {row['ULS1']['max_member']:.2f}) joints>1 {row['ULS1']['joints_over']} (max {row['ULS1']['max_joint']:.2f}) "
              f"links>1 {row['ULS1']['links_over_shear']} (max {row['ULS1']['max_link_shear']:.2f}) | 1.35G max member {row['ULS2']['max_member']:.2f} joint {row['ULS2']['max_joint']:.2f} | "
              f"floor truss sag (G+0.7Q) {row['floor_truss_relative_sag_SLS_mm']} mm")
        for w in row["ULS1"]["worst_members"][:4]: print("     member", w)
        for w in row["ULS1"]["worst_joints"][:4]: print("     joint ", w)
    os.makedirs(out_dir, exist_ok=True)
    json.dump(out, open(os.path.join(out_dir, "service.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
