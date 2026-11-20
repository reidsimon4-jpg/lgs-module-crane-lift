import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_lift as RL
import numpy as np
cfg = json.load(open(sys.argv[2], encoding="utf-8"))
cfg["slack_cases"] = False; cfg["sling_tolerance_mm"] = 0; cfg["k_sling_N_per_mm"] = 0; cfg["tilt_deg"] = 0; cfg["sideways_fraction"] = 0
for k, v in json.loads(sys.argv[3] if len(sys.argv) > 3 else "{}").items(): cfg[k] = v
r = RL.run(sys.argv[1], cfg, None, quiet=True)
B = r["B"]; M = B.model
for cid in ("R4_equalised", "R7d_twist"):
    c = [c for c in r["cases"] if c["id"] == cid][0]
    mc = sorted(c["_mc"].items(), key=lambda kv: -kv[1]["util"])[:6]
    print(cid, "slack:", c["_info"]["slack_straps"][:12])
    for mid, v in mc:
        m = B.members[mid]; e = v["element"]; el = M.el[e]
        print(f"   M {m['panel']:6s} {m['type']:14s} {m['kind']:11s} util {v['util']:.2f} x {M.xyz[el['i']][0]:.0f}..{M.xyz[el['j']][0]:.0f} y {M.xyz[el['i']][1]:.0f} z {M.xyz[el['i']][2]:.0f} N {v['N']/1e3:.1f} Min {v['M_in']/1e6:.3f} Mout {v['M_out']/1e6:.3f} | {v['mode'][:40]}")
    jc = sorted(c["_jc"].items(), key=lambda kv: -kv[1]["util"])[:6]
    for jid, v in jc:
        mm = B.members[v["member"]] if v["member"] else {"type": "?", "kind": "?"}
        print(f"   J {v['panel']:6s} {mm['type']:14s} util {v['util']:.2f} at {[round(t) for t in M.xyz[v['node']]]} demand {v['demand']/1e3:.2f} cap {v['capacity']/1e3:.2f}")
    u = c["_res"]["u"]
    i = int(np.argmax(np.abs(u[:, 2]))); print("   max |dz| node", [round(t) for t in M.xyz[i]], round(u[i, 2], 1))
