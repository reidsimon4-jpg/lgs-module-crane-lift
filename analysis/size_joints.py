"""Size the joint upgrades joint by joint: which truss and wall joints need a gusset, and which are fine with 4 screws.

usage: python analysis/size_joints.py [config] [--limit 0.90]

Runs the design cases with every joint at its 4-screw (or framed) count and no gussets, takes each joint's worst demand
over the design cases, and lists the joints whose 4-screw utilisation is above the limit (default 0.90, a 10 % margin).
Those joints get a gusset (two 1.5 mm plates, 3 + 3 screws per face; counted as 10 screw-equivalents in the joint check).
Writes the list into the config as "gusset_joints" (Framer joint ids, stable for this framed model) and a schedule to
results/joint_schedule.json. The in-service check (continuous bearers) is added as a second load set.
"""
from __future__ import annotations
import sys, os, json, copy, argparse, contextlib, io
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run_lift as RL  # noqa: E402
from liftcalc import liftcase as LC, as4600 as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("config", nargs="?", default=os.path.join(HERE, "configs", "revD_final.json"))
    ap.add_argument("--limit", type=float, default=0.90)
    a = ap.parse_args()
    cfg0 = json.load(open(a.config, encoding="utf-8"))
    cfg = copy.deepcopy(cfg0)
    cfg["joint_rules"] = [r for r in cfg.get("joint_rules", []) if r.get("n", 0) < 10]
    cfg.pop("gusset_joints", None); cfg["only_design"] = True
    with contextlib.redirect_stdout(io.StringIO()):
        r = RL.run(os.path.join(ROOT, "model", "engineered"), cfg, None)
    B = r["B"]; M = B.model
    need = {}
    for jid, v in r["env_j"].items():
        if v["util"] > a.limit:
            need[jid] = dict(util_4=round(v["util"], 2), demand_kN=round(v["demand"] / 1e3, 2), case=v["case"], panel=v["panel"],
                             member=B.members[v["member"]]["type"], xyz=[round(float(c), 1) for c in M.xyz[v["node"]]], source="lift", reason="screws")
    # in service on continuous bearers (1.2 G + 1.5 Q): the same joints at 4 screws
    import run_service as RS
    svc = RS.service_joint_demands(cfg)
    for jid, v in svc.items():
        if v["util"] > a.limit and jid not in need:
            need[jid] = dict(util_4=round(v["util"], 2), demand_kN=round(v["demand"] / 1e3, 2), case="service ULS on packers", panel=v["panel"],
                             member=B.members[v["member"]]["type"] if v.get("member") else "", xyz=[round(float(c), 1) for c in M.xyz[v["node"]]], source="service", reason="screws")
    # members that still fail at a lip notch without a gusset - in the lift cases, or in service on the packers (hold point H8)
    # at 1.0 and 1.2 x the dead load (hold point H1) - get gussets at the joints of that notch zone; re-run until nothing changes.
    # A gusset added for an in-service case is a floor-structure gusset (source "service", reason "lip notch").
    from liftcalc import notch as NT
    for it in range(6):
        cfg2 = copy.deepcopy(cfg); cfg2["gusset_joints"] = sorted(need)
        with contextlib.redirect_stdout(io.StringIO()):
            r2 = RL.run(os.path.join(ROOT, "model", "engineered"), cfg2, None)
            Bs, svc2 = RS.service_checks(cfg2)
        rows = [(r2["B"], mid, v, v["case"], "notch") for mid, v in r2["env_m"].items()]
        for lay, chk in svc2.items():
            for c, (mc, jc, lk) in chk.items():
                rows += [(Bs, mid, v, f"service {c} on {lay}", "service") for mid, v in mc.items()]
        added = 0
        for Bx, mid, v, case, src in rows:
            if v["util"] <= 1.0 or "lip-notch" not in v.get("mode", ""): continue
            m = Bx.members[mid]
            for z0, z1, a_n in NT.notch_zones(m):
                for p_, j_ in m.get("joints") or []:
                    if z0 - 10.0 <= p_ <= z1 + 10.0 and j_ not in need:
                        need[j_] = dict(util_4=None, demand_kN=None, case=case, panel=m["panel"], member=m["type"], reason="lip notch",
                                        xyz=[round(float(c), 1) for c in Bx.model.xyz[Bx.joints[j_]["node"]]], source=src); added += 1
        svc_over = sum(1 for chk in svc2.values() for mc, jc, lk in chk.values() for v in mc.values() if v["util"] > 1)
        svc_j_over = sum(1 for chk in svc2.values() for mc, jc, lk in chk.values() for v in jc.values() if v["util"] > 1)
        print(f"notch pass {it + 1}: lift members over {sum(1 for v in r2['env_m'].values() if v['util'] > 1)}, joints over "
              f"{sum(1 for v in r2['env_j'].values() if v['util'] > 1)}; service members over {svc_over}, joints over {svc_j_over}; gussets added {added}")
        if not added: break
    cfg0["joint_rules"] = [r for r in cfg0.get("joint_rules", []) if r.get("n", 0) < 10]
    cfg0["gusset_joints"] = sorted(need)
    json.dump(cfg0, open(a.config, "w", encoding="utf-8"), indent=1)
    sched = dict(limit=a.limit, gusset_joints=len(need), by_panel={}, joints=need)
    for v in need.values(): sched["by_panel"][v["panel"]] = sched["by_panel"].get(v["panel"], 0) + 1
    json.dump(sched, open(os.path.join(ROOT, "results", "joint_schedule.json"), "w", encoding="utf-8"), indent=1)
    print(f"joints needing a gusset (4-screw utilisation > {a.limit}): {len(need)}")
    print("by panel:", dict(sorted(sched["by_panel"].items(), key=lambda kv: -kv[1])))
    for jid, v in sorted(need.items(), key=lambda kv: -(kv[1]["util_4"] or 0))[:15]:
        print(f"  {v['panel']:6s} {v['member']:14s} at {v['xyz']}  4-screw util {v['util_4']}  ({v['demand_kN']} kN, {v['case']})")


if __name__ == "__main__":
    main()
