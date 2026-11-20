import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_lift as RL
import numpy as np
cfg = json.load(open(sys.argv[2], encoding="utf-8")); cfg["slack_cases"] = False; cfg["sling_tolerance_mm"] = 0; cfg["k_sling_N_per_mm"] = 0; cfg["skew"] = 0
r = RL.run(sys.argv[1], cfg, None, quiet=True)
B = r["B"]; M = B.model
case = [c for c in r["cases"] if c["id"] == "L1_squeeze_y"][0]
u = case["_res"]["u"]
print("heads:", {k: [round(float(v), 2) for v in u[n, :3]] for k, n in r["pts"].items()})
xyz = np.array(M.xyz)
for lab, sel in (("floor rim S", (abs(xyz[:,1]-44.5)<60) & (xyz[:,2]<0)), ("floor rim N", (abs(xyz[:,1]-3255.5)<60) & (xyz[:,2]<0)),
                 ("roof rim S", (abs(xyz[:,1]-44.5)<60) & (xyz[:,2]>2700) & (xyz[:,2]<3000)), ("wall mid S", (abs(xyz[:,1]-44.5)<60) & (abs(xyz[:,2]-1350)<300))):
    idx = np.nonzero(sel)[0]
    if len(idx): print(f"{lab:12s} n={len(idx):4d} uy min {u[idx,1].min():8.2f} max {u[idx,1].max():8.2f}  uz min {u[idx,2].min():7.2f}")
# guide elements
for m in B.members.values():
    if m["type"] == "GUIDE":
        e = m["elements"][0]; el = M.el[e]
        print(m["id"], "nodes", el["i"], el["j"], "ry", el["ry"], "rz", el["rz"], "Iy", el["Iy"], "Iz", el["Iz"], "tr", el["tr"], "u_i", np.round(u[el["i"], :3], 2).tolist(), "u_j", np.round(u[el["j"], :3], 2).tolist())
