import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_lift as RL
import numpy as np
cfg = json.load(open(sys.argv[2], encoding="utf-8")); cfg["slack_cases"] = False; cfg["sling_tolerance_mm"] = 0
r = RL.run(sys.argv[1], cfg, None, quiet=True)
B = r["B"]; M = B.model; f = r["factor"]
top = sorted(r["env_m"].items(), key=lambda kv: -kv[1]["util"])[:8]
for mid, v in top:
    m = B.members[mid]; e = v["element"]; el = M.el[e]
    print(f'{m["panel"]:6s} {m["type"]:13s} util {v["util"]:.2f} [{v["case"]}] element x {M.xyz[el["i"]][0]:.0f}..{M.xyz[el["j"]][0]:.0f} z {M.xyz[el["i"]][2]:.0f} N {v["N"]/1e3:.1f} Min {v["M_in"]/1e6:.3f} | phiNc {v["phiNc"]/1e3:.1f} phiMy {v["phiMy"]/1e6:.3f}')
