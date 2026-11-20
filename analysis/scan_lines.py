import sys, json, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_lift as RL
base = json.load(open(sys.argv[2], encoding="utf-8")); base["slack_cases"] = False; base["sling_tolerance_mm"] = 0; base["sideways_fraction"] = 0
for lines in json.loads(sys.argv[3]):
    cfg = copy.deepcopy(base); cfg["lift_lines_x"] = lines
    xs = sorted(set([0, 12000] + lines))
    for d in ("floor_diaphragm", "roof_diaphragm"): cfg[d]["x_stations"] = xs
    r = RL.run(sys.argv[1], cfg, None, quiet=True)
    o = r["out"]["cases"]
    R1 = o["R1_rigid"]["reactions"]
    print(lines, "R1:", " ".join(f"{k}:{v/1e3:.1f}" for k, v in R1.items()), "| R1 jnt max %.2f over %d | R4 jnt max %.2f over %d hog %.1f sag %.1f" % (
        o["R1_rigid"]["max_joint"], o["R1_rigid"]["joints_over"], o["R4_equalised"]["max_joint"], o["R4_equalised"]["joints_over"], o["R4_equalised"]["hog_mm"], o["R4_equalised"]["sag_mm"]))
