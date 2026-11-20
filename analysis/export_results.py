"""Export one lift design run for the 3D page and the report.

usage: python analysis/export_results.py <model folder> <config.json> <out folder> [--before <config.json>]

Writes <out>/model3d.json: every member (framed and added) with its geometry, envelope utilisation and governing case,
per-case utilisation for the main cases, the lift points with their sling forces, the joints and links that matter,
the deflected shape of the main case, and the forces in every added part.
"""
from __future__ import annotations
import sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_lift as RL  # noqa: E402

MAIN_CASES = ["R4_equalised", "R1_rigid", "T1_roll_S", "T2_roll_N", "T5_SW", "T6_SE", "L1_squeeze_y", "L3_squeeze_x", "TW1_twist",
              "T1+L4", "T2+L4", "CG_NW+T", "CG_SE+T", "R7d_twist"]


def r3(v):
    return [round(float(x), 1) for x in v]


def export(model_dir, cfg, out_dir, label):
    r = RL.run(model_dir, cfg, None, quiet=True)
    B = r["B"]; M = B.model; f = r["factor"]
    cases = {c["id"]: c for c in r["cases"]}
    main = [c for c in MAIN_CASES if c in cases]
    base = "R4_equalised" if "R4_equalised" in cases else r["cases"][0]["id"]
    members = []
    for mid, m in B.members.items():
        env = r["env_m"].get(mid)
        row = dict(id=mid, panel=m["panel"], kind=m["kind"], type=m["type"], a=r3(m["a"]), b=r3(m["b"]), t=m.get("t", 0.0),
                   added=bool(m.get("added")), role=m.get("role", ""), profile=m.get("profile", ""), in_model=bool(m.get("elements")),
                   nrm=[round(float(v), 3) for v in m["nrm"]], temporary=bool(m.get("temporary")), wall=m.get("wall"))
        if env:
            row.update(util=round(env["util"], 3), case=env["case"], mode=env["mode"], N=round(env["N"] / 1e3, 2),
                       M_in=round(env["M_in"] / 1e6, 3), M_out=round(env["M_out"] / 1e6, 3), L_in=round(env["L_in"]), L_out=round(env["L_out"]))
            row["util_by_case"] = {c: round(cases[c]["_mc"][mid]["util"], 3) for c in main if mid in cases[c]["_mc"]}
        if m.get("added") and mid in r["env_a"]:
            a = r["env_a"][mid]
            row.update(N_max=round(a["N_max"] / 1e3, 2), N_min=round(a["N_min"] / 1e3, 2), V=round(a["V"] / 1e3, 2), Mmax=round(a["M"] / 1e6, 3))
            if m.get("elements"):
                # unfactored axial force in the main case (for the load-path view)
                F = cases[base]["_res"]["end_forces"]
                row["N_R4_unfactored"] = round(float(np.mean([F[e][6] for e in m["elements"]])) / 1e3, 2)
        if m.get("elements"):
            u = cases[base]["_res"]["u"]
            n0 = M.el[m["elements"][0]]["i"]; n1 = M.el[m["elements"][-1]]["j"]
            row["d_a"] = [round(float(x), 2) for x in u[n0, :3]]; row["d_b"] = [round(float(x), 2) for x in u[n1, :3]]
        members.append(row)
    joints = []
    for jid, v in r["env_j"].items():
        if v["util"] < 0.5: continue
        joints.append(dict(id=jid, xyz=r3(M.xyz[v["node"]]), util=round(v["util"], 3), demand=round(v["demand"] / 1e3, 2), capacity=round(v["capacity"] / 1e3, 2),
                           screws=v["fasteners"], member=v["member"], panel=v["panel"], case=v["case"]))
    links = []
    for i, v in r["env_l"].items():
        lk = B.links[i]
        links.append(dict(a=r3(M.xyz[lk["na"]]), b=r3(M.xyz[lk["nb"]]), rule=lk["rule"], util=round(v["util_shear"], 3), tie=bool(v["tie"]),
                          N_max=round(v["N_max"] / 1e3, 2)))
    pts = {}
    for k, nd in r["pts"].items():
        pts[k] = dict(xyz=r3(M.xyz[nd]), reactions_kN={c: round(cases[c]["_info"]["reactions"].get(k, 0.0) / 1e3, 2) for c in cases})
    ex = r.get("extra_fasteners", {})
    final = {jid: j["fasteners"] + max(0, ex.get(jid, 0)) for jid, j in B.joints.items()}
    gus = [jid for jid, n in final.items() if n >= 10]
    screws = dict(joints=len(B.joints), as_framed=sum(j["fasteners"] for j in B.joints.values()), extra=sum(max(0, v) for v in ex.values()),
                  joints_upgraded=sum(1 for v in ex.values() if v > 0),
                  joints_by_screws={str(k): sum(1 for n in final.values() if n == k) for k in sorted(set(final.values()))},
                  gusseted_joints=len(gus),
                  note="a joint at 10 is a gusset: two 1.5 mm plates, 3 + 3 screws per face, plus the framed screws")
    sched_p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "joint_schedule.json")
    sched_ = json.load(open(sched_p, encoding="utf-8"))["joints"] if os.path.exists(sched_p) else {}
    gussets = [dict(xyz=r3(M.xyz[B.joints[jid]["node"]]), panel=B.joints[jid]["panel"], nrm=[round(float(v), 3) for v in B.members[B.joints[jid]["members"][0]]["nrm"]],
                    source=sched_.get(jid, {}).get("source", "lift"), reason=sched_.get(jid, {}).get("reason", "screws")) for jid in gus]
    ledger = [dict(item=x["item"], group=x["group"], kg=round(x["kg"], 1), note=x.get("note", "")) for x in r["led"]["ledger"]]
    out = dict(label=label, config=cfg.get("name"), meta=r["out"]["meta"], screws=screws, ledger=ledger, scale_to_rated=r["led"]["factor_to_rated"], envelope={k: v for k, v in r["out"]["envelope"].items() if k != "added"},
               cases={c: {k: v for k, v in r["out"]["cases"][c].items()} for c in r["out"]["cases"]}, main_cases=main,
               members=members, joints=joints, links=links, lift_points=pts, foot_layout=r["out"].get("foot_layout", []), gussets=gussets,
               design_cases=[c["id"] for c in r["cases"] if c.get("design", True)], info_cases=[c["id"] for c in r["cases"] if not c.get("design", True)])
    os.makedirs(out_dir, exist_ok=True)
    json.dump(out, open(os.path.join(out_dir, "model3d.json"), "w"), separators=(",", ":"))
    return out


if __name__ == "__main__":
    model_dir, cfg_path, out_dir = sys.argv[1:4]
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    o = export(model_dir, cfg, out_dir, os.path.basename(cfg_path))
    print("members", len(o["members"]), "joints>0.5", len(o["joints"]), "links", len(o["links"]), "size kB",
          round(os.path.getsize(os.path.join(out_dir, "model3d.json")) / 1024))
