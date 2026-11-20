import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_lift as RL
import numpy as np
cfg = json.load(open(sys.argv[2], encoding="utf-8")); cfg["slack_cases"] = False; cfg["sling_tolerance_mm"] = 0
r = RL.run(sys.argv[1], cfg, None, quiet=True)
B = r["B"]; M = B.model; f = r["factor"]
case = [c for c in r["cases"] if c["id"] == "R4_equalised"][0]
res = case["_res"]; u = res["u"]; F = res["end_forces"] * f
names = list(r["pts"]); z0 = np.mean([u[r["pts"][k], 2] for k in names])
used = sorted({nd for m in B.members.values() if not m.get("added") for _, nd in (m.get("nodes") or [])})
order = sorted(used, key=lambda n: u[n, 2])
print("lowest nodes (dz rel heads, unfactored):")
for n in order[:6]: print("  ", [round(v) for v in M.xyz[n]], round(u[n, 2] - z0, 1))
print("heads dz:", {k: round(u[r["pts"][k], 2] - z0, 2) for k in names})
for pn in sys.argv[3:]:
    print("panel", pn, "factored member forces, R4")
    rows = []
    for m in B.members.values():
        if m["panel"] != pn or not m.get("elements"): continue
        N = [F[e][6] for e in m["elements"]]
        xm = (m["a"] + m["b"]) / 2
        rows.append((xm[0], xm[1], xm[2], m["type"], min(N), max(N), m["L"]))
    rows.sort()
    for t in ("WEB", "TOP CHORD", "BOTTOM CHORD"):
        sel = [x for x in rows if x[3] == t]
        print("  ", t, len(sel), " ".join(f"{x[0]:.0f}:{(x[4] if abs(x[4]) > abs(x[5]) else x[5]) / 1e3:.1f}" for x in sel)[:1500])
    # dz along bottom chord
    bc = [m for m in B.members.values() if m["panel"] == pn and m["type"] == "BOTTOM CHORD"]
    pts = sorted({(round(M.xyz[nd][0]), round(u[nd, 2] - z0, 1)) for m in bc for _, nd in m["nodes"]})
    print("   dz along bottom chord:", " ".join(f"{x}:{d}" for x, d in pts[::3])[:900])
print("--- floor trusses: midspan dz, end link info")
import collections
pan = collections.defaultdict(list)
for m in B.members.values():
    if m["kind"] in ("floor_truss", "roof_truss") and m.get("nodes"): pan[m["panel"]].append(m)
linked = collections.Counter()
for lk in B.links:
    linked[B.members[lk["a"]]["panel"]] += 1; linked[B.members[lk["b"]]["panel"]] += 1
for pn, ms in sorted(pan.items(), key=lambda kv: (kv[1][0]["kind"], kv[1][0]["a"][0])):
    nds = {nd for m in ms for _, nd in m["nodes"]}
    dz = [u[n, 2] - z0 for n in nds]
    print(f"  {pn:6s} {ms[0]['kind']:11s} x={np.mean([M.xyz[n][0] for n in nds]):7.0f} members {len(ms):3d} nodes {len(nds):3d} links {linked[pn]:2d} dz min {min(dz):6.1f} max {max(dz):6.1f} load kg {sum(r['led']['node_kg'].get(int(n), 0) for n in nds):6.0f}")
