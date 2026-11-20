import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_lift as RL
from collections import defaultdict
cfg = json.load(open(sys.argv[2], encoding="utf-8"))
r = RL.run(sys.argv[1], cfg, None, quiet=True)
B = r["B"]; M = B.model
print("factor", r["factor"])
grp = defaultdict(list)
for jid, v in r["env_j"].items():
    if v["member"] is None: continue
    m = B.members[v["member"]]
    grp[(m["panel"], m["kind"])].append((M.xyz[v["node"]][0], M.xyz[v["node"]][1], v["util"], v["demand"], v["case"], m["type"]))
print("panel kind  y  n_over  max  | util of worst joint per 600 mm of x")
for (pn, kind), lst in sorted(grp.items(), key=lambda kv: -max(x[2] for x in kv[1])):
    over = [x for x in lst if x[2] > 1.0]
    if not over: continue
    xs = [x[0] for x in lst]; ys = [x[1] for x in lst]
    span_x = max(xs) - min(xs) > 1000
    bins = defaultdict(float)
    for x in lst:
        key = int((x[0] if span_x else x[1]) // 600)
        bins[key] = max(bins[key], x[2])
    print(f"{pn:7s} {kind:11s} y={sum(ys)/len(ys):6.0f} x={sum(xs)/len(xs):6.0f} over {len(over):3d} max {max(x[2] for x in lst):.2f} | " + " ".join(f"{bins[k]:.1f}" for k in sorted(bins)))
