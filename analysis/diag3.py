import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_lift as RL
import numpy as np
cfg = json.load(open(sys.argv[2], encoding="utf-8")); cfg["slack_cases"] = False
r = RL.run(sys.argv[1], cfg, None, quiet=True)
B = r["B"]; M = B.model; f = r["factor"]
want = sys.argv[3]
case = [c for c in r["cases"] if c["id"] == sys.argv[4]][0]
F = case["_res"]["end_forces"] * f
m = [m for m in B.members.values() if m["panel"] == want.split(":")[0] and m["type"] == want.split(":")[1]][0]
rows = []
for e in m["elements"]:
    el = M.el[e]
    xi, xj = M.xyz[el["i"]], M.xyz[el["j"]]
    rows.append((abs(F[e][5]), abs(F[e][11]), F[e][6], xi[0], xj[0], abs(F[e][4]), abs(F[e][10])))
rows.sort(reverse=True)
for x in rows[:6]: print("Mout i %.3f j %.3f kNm  N %.1f kN  x %.0f..%.0f  Min %.3f %.3f" % (x[0]/1e6, x[1]/1e6, x[2]/1e3, x[3], x[4], x[5]/1e6, x[6]/1e6))
print("tags on member:", [(round(s), t) for s, t in m.get("tags", []) if t in ("LINK", "ATTACH")][:40])
