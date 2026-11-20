"""Second solver check of the full lift model: the same nodes, elements, end releases, supports and loads, solved by PyNite
(an independent open-source frame solver), compared with the project solver (analysis/liftcalc/fea3d.py).

usage: python verification/solver_crosscheck/pynite_full.py <model folder> <config.json> <case id> <out.json>

Local axes: each PyNite member is given the roll angle that puts its local y axis on the project solver's local y axis
(checked member by member after the angle is set). Releases: an end fixity factor of 0 becomes a PyNite release.
"""
from __future__ import annotations
import sys, os, json, math, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "analysis"))
import run_lift as RL  # noqa: E402
from Pynite import FEModel3D  # noqa: E402
import Pynite.PhysMember as _PM  # noqa: E402

# PyNite splits a member wherever another node lies on its line. The project model already defines every element between
# its own two nodes (cradle plates share nodes with the chords they lie on), so the split is turned off: each PyNite
# member is exactly one project element.
_orig_descritize = _PM.PhysMember.descritize


def _descritize_no_split(self):
    saved = self.model.nodes
    self.model.nodes = {self.i_node.name: self.i_node, self.j_node.name: self.j_node}
    try:
        _orig_descritize(self)
    finally:
        self.model.nodes = saved


_PM.PhysMember.descritize = _descritize_no_split


def main():
    model_dir, cfg_path, case_id, out_path = sys.argv[1:5]
    cfg = json.load(open(cfg_path, encoding="utf-8")); cfg["slack_cases"] = False; cfg["sling_tolerance_mm"] = 0
    r = RL.run(model_dir, cfg, None, quiet=True)
    B = r["B"]; M = B.model
    case = [c for c in r["cases"] if c["id"] == case_id][0]
    slack = set(case["_info"].get("slack_straps", []))
    # rebuild the exact support and load state of the case
    res_ref, info = RL.solve_case(B, r["pts"], case)
    lc = "C_" + case_id
    slack_el = {e for mid in slack for e in B.members[mid]["elements"]}
    for e in slack_el: M.el[e]["A_save"] = M.el[e]["A"]; M.el[e]["A"] = 1e-6
    if hasattr(M, "K"): del M.K
    res_ref = M.solve([lc])[lc]
    t0 = time.time()
    pn = FEModel3D()
    E = 200000.0; G = E / 2.6
    pn.add_material("steel", E, G, 0.3, 7.85e-9)
    for i, (x, y, z) in enumerate(M.xyz):
        pn.add_node(f"N{i}", x, y, z)
    sections = {}
    worst_axis = 0.0
    for k, e in enumerate(M.el):
        key = (round(e["A"], 6), round(e["Iy"], 4), round(e["Iz"], 4), round(e["J"], 4))
        if key not in sections:
            sections[key] = f"S{len(sections)}"
            pn.add_section(sections[key], e["A"], e["Iy"], e["Iz"], e["J"])
        name = f"E{k}"
        pn.add_member(name, f"N{e['i']}", f"N{e['j']}", "steel", sections[key])
        mem = pn.members[name]
        # project solver local axes
        kloc, T, L, dof = M._ke[k]
        ey = T[1, :3]
        Tp = mem.T()[:3, :3]
        yp, zp = Tp[1], Tp[2]
        ang = math.degrees(math.atan2(float(np.dot(ey, zp)), float(np.dot(ey, yp))))
        mem.rotation = ang
        Tp2 = mem.T()[:3, :3]
        if float(np.dot(Tp2[1], ey)) < 0.999:
            mem.rotation = -ang
            Tp2 = mem.T()[:3, :3]
        worst_axis = max(worst_axis, 1.0 - float(np.dot(Tp2[1], ey)))
        rel = dict(Ryi=e["ry"][0] < 0.5, Ryj=e["ry"][1] < 0.5, Rzi=e["rz"][0] < 0.5, Rzj=e["rz"][1] < 0.5, Rxj=bool(e["tr"]))
        if any(rel.values()):
            pn.def_releases(name, **rel)
    for nd, dofs in M.fixed.items():
        d = [i in dofs for i in range(6)]
        pn.def_support(f"N{nd}", *d)
    for (nd, d, kspring) in M.nspring:
        pn.def_support_spring(f"N{nd}", ["DX", "DY", "DZ", "RX", "RY", "RZ"][d], kspring)
    for (nd, d), v in M.loads[lc].items():
        if abs(v) > 0:
            pn.add_node_load(f"N{nd}", ["FX", "FY", "FZ", "MX", "MY", "MZ"][d], float(v), "L")
    pn.add_load_combo("C", {"L": 1.0})
    pn.analyze_linear(check_stability=False, check_statics=False, sparse=True)
    t_pn = time.time() - t0
    u_ref = res_ref["u"]
    u_pn = np.array([[pn.nodes[f"N{i}"].DX["C"], pn.nodes[f"N{i}"].DY["C"], pn.nodes[f"N{i}"].DZ["C"]] for i in range(len(M.xyz))])
    du = np.abs(u_ref[:, :3] - u_pn).max(); umax = np.abs(u_ref[:, :3]).max()
    N_ref = res_ref["end_forces"][:, 6]
    N_pn = np.array([-pn.members[f"E{k}"].axial(0.0, "C") for k in range(len(M.el))])     # PyNite: compression positive
    ok = np.array([k not in slack_el for k in range(len(M.el))])
    dN = np.abs(N_ref - N_pn)[ok]; Nmax = np.abs(N_ref[ok]).max()
    # reactions at the holds
    R_ref = {nd: res_ref["reactions"][nd] for nd in M.fixed}
    R_pn = {nd: [pn.nodes[f"N{nd}"].RxnFX["C"], pn.nodes[f"N{nd}"].RxnFY["C"], pn.nodes[f"N{nd}"].RxnFZ["C"]] for nd in M.fixed}
    dR = max(abs(R_ref[nd][i] - R_pn[nd][i]) for nd in M.fixed for i in range(3))
    # members of interest: hanger straps, inclined straps, worst framed members
    sample = {}
    for mid in [x for x in B.members if B.members[x]["type"] in ("STRAP", "V-STRAP")][:30]:
        es = B.members[mid]["elements"]
        sample[mid] = dict(ref_kN=round(float(np.mean(N_ref[es])) / 1e3, 3), pynite_kN=round(float(np.mean(N_pn[es])) / 1e3, 3))
    out = dict(case=case_id, nodes=len(M.xyz), elements=len(M.el), pynite_seconds=round(t_pn, 1), worst_local_axis_misfit=worst_axis,
               max_disp_ref_mm=round(float(umax), 4), max_disp_difference_mm=float(du), relative_disp_difference=float(du / umax),
               max_axial_ref_kN=round(float(Nmax) / 1e3, 3), max_axial_difference_kN=float(dN.max() / 1e3), relative_axial_difference=float(dN.max() / Nmax),
               max_reaction_difference_N=float(dR), slack_straps=sorted(slack), sample_axial=sample)
    json.dump(out, open(out_path, "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "sample_axial"}, indent=1))
    for k, v in list(sample.items())[:8]: print(" ", k, v)


if __name__ == "__main__":
    main()
