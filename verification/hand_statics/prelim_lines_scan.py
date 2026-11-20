"""Scan symmetric lift-line layouts (a, b, 12-b, 12-a) on a 100 mm grid: worst bending moment per side over both rig
behaviours (rigid frame = natural reactions; equalising rig = four equal forces). Preliminary loads, rated mass."""
import sys, os, json, itertools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "analysis"))
from liftcalc.beam2d import solve, summary
L = 12.0; RATED_KN = 6.5 * 9.80665
sides = {"south": (2.20, 1.38), "north": (1.80, 1.38)}
raw = sum(w * L + 2 * P for w, P in sides.values()); k = RATED_KN / raw
rows = []
for a10 in range(6, 19):
    for b10 in range(34, 50):
        a, b = a10 / 10, b10 / 10
        xs = [a, b, L - b, L - a]; worstM = 0; worstV = 0; spread = 0
        for side, (w, P) in sides.items():
            w, P = w * k, P * k; tot = w * L + 2 * P
            nat = solve(L, 1e4, xs, w_segments=[(0, L, w)], points=[(0, P), (L, P)], n=480)
            eq = solve(L, 1e4, [], w_segments=[(0, L, w)], points=[(0, P), (L, P)], prescribed={x: tot / 4 for x in xs}, n=480)
            for r in (nat, eq):
                worstM = max(worstM, abs(r["M"]).max()); worstV = max(worstV, abs(r["V"]).max())
            R = list(nat["reactions"].values()); spread = max(spread, (max(R) - min(R)) / (tot / 4))
        rows.append((worstM, a, b, worstV, spread))
rows.sort()
print("best 12 layouts by worst |M| (kNm, service, either side, either rig):")
for m, a, b, v, s in rows[:12]:
    print(f"  a={a:.1f} b={b:.1f}  |M|max={m:.2f}  |V|max={v:.2f}  natural reaction spread={100*s:.0f}%")
for a, b in ((1.2, 4.2), (1.5, 4.5), (1.0, 4.0), (0.9, 4.2)):
    r = [x for x in rows if abs(x[1] - a) < 1e-9 and abs(x[2] - b) < 1e-9][0]
    print(f"check a={a} b={b}: |M|max={r[0]:.2f} |V|max={r[3]:.2f} spread={100*r[4]:.0f}%")
json.dump([dict(a=a, b=b, M=m, V=v, spread=s) for m, a, b, v, s in rows], open(os.path.join(os.path.dirname(__file__), "prelim_lines_scan.json"), "w"))
