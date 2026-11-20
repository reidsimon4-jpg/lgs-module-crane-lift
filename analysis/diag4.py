import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_lift as RL
import numpy as np
cfg = json.load(open(sys.argv[2], encoding="utf-8")); cfg["slack_cases"] = False; cfg["sling_tolerance_mm"] = 0
r = RL.run(sys.argv[1], cfg, None, quiet=True)
B = r["B"]; M = B.model; f = r["factor"]
for cid in ("R4_equalised", "L1_squeeze_y"):
    case = [c for c in r["cases"] if c["id"] == cid][0]
    F = case["_res"]["end_forces"] * f; u = case["_res"]["u"]
    for pn in ("NFT25", "NFT24"):
        m = [m for m in B.members.values() if m["panel"] == pn and m["type"] == "TOP CHORD"][0]
        print(cid, pn, "nrm", m["nrm"], "elements", len(m["elements"]))
        for e in m["elements"]:
            el = M.el[e]; xi = M.xyz[el["i"]][0]
            if 4100 < xi < 4900:
                k, T, L, dof = M._ke[e]
                print("   x %.0f-%.0f  N %.1f  Vy' %.2f Vz' %.2f  Mz'(out) %.3f/%.3f  My'(in) %.3f/%.3f kNm | uy_i %.2f mm rx %.4f rz_i %.5f" % (
                    xi, M.xyz[el["j"]][0], F[e][6]/1e3, F[e][1]/1e3, F[e][2]/1e3, F[e][5]/1e6, F[e][11]/1e6, F[e][4]/1e6, F[e][10]/1e6,
                    u[el["i"], 1], u[el["i"], 3], u[el["i"], 5]))
                print("      local axes:", np.round(T[:3, :3], 3).tolist())
                break
