"""Preliminary 2D study that fixed the lift-line positions (run before the 3D model existed).

Each long side of the module is treated as a beam along the 12 m length carrying that side's share of the weight.
Compares the concept's post lines with the adopted lines, for a rigid lifting frame (natural reactions) and for an
equalising rig (all four line forces equal). Loads are PRELIMINARY service loads scaled to the rated lift mass.
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "analysis"))
from liftcalc.beam2d import solve, summary

L = 12.0
RATED_KN = 6.5 * 9.80665                      # rated lift mass 6.5 t
# preliminary service line loads (kN/m) and end-wall point loads (kN) per side, before scaling
south = {"w": 2.20, "P_end": 1.38}
north = {"w": 1.80, "P_end": 1.38}
raw_total = (south["w"] + north["w"]) * L + 2 * (south["P_end"] + north["P_end"])
k = RATED_KN / raw_total
layouts = {"concept post lines": [0.25, 4.13, 7.98, 11.80], "L/8 lines": [1.5, 4.5, 7.5, 10.5], "adopted 1.2/4.2/7.8/10.8": [1.2, 4.2, 7.8, 10.8]}
out = {"rated_kN": RATED_KN, "scale": k, "cases": []}
print(f"rated {RATED_KN:.1f} kN, preliminary itemised {raw_total:.1f} kN, scale {k:.3f}")
for side, ld in (("south", south), ("north", north)):
    w, P = ld["w"] * k, ld["P_end"] * k
    for name, xs in layouts.items():
        nat = solve(L, 1e4, xs, w_segments=[(0, L, w)], points=[(0.0, P), (L, P)])
        tot = w * L + 2 * P
        eq = solve(L, 1e4, [], w_segments=[(0, L, w)], points=[(0.0, P), (L, P)], prescribed={x: tot / 4 for x in xs})
        sn, se = summary(nat), summary(eq)
        Rn = list(nat["reactions"].values())
        print(f"{side:5s} | {name:26s} | natural R = {[round(r,2) for r in Rn]} kN  M +{sn['M_sag']:.2f}/{sn['M_hog']:.2f}  V {sn['V_max']:.2f}"
              f" | equal F = {tot/4:.2f}  M +{se['M_sag']:.2f}/{se['M_hog']:.2f} kNm  V {se['V_max']:.2f} kN")
        out["cases"].append({"side": side, "layout": name, "lines": xs, "w": w, "P_end": P, "natural": sn, "equal": se})
json.dump(out, open(os.path.join(os.path.dirname(__file__), "prelim_lines_study.json"), "w"), indent=1)
