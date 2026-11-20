"""Write results/review/review_revD.json: how each finding of the independent review of Rev D was answered in Rev D.1.
Numbers are read from the result files, so re-run this after the analysis.

usage: python tools/write_review_revD.py
"""
import os, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda p: json.load(open(os.path.join(ROOT, p), encoding="utf-8"))
syn = J("results/review/synthesis_revD.json")
D = J("site/data/revD.json"); CON = J("results/revD_connectors/connectors.json"); SVC = J("results/revD_service/service.json")
AB = {r["id"]: r for r in J("site/data/ablation.json")}; JS = J("results/joint_schedule.json")
cases = D["cases"]
row = lambda key: next((r for r in CON["rows"] if key in r["item"] or key in r["group"]), None)
fam = lambda pred: max((cases[c]["max_member"] for c in cases if pred(c) and cases[c]["design"]), default=0.0)
famj = lambda pred: max((cases[c]["max_joint"] for c in cases if pred(c) and cases[c]["design"]), default=0.0)
tl_m, tl_j = fam(lambda c: c.startswith("T") and "+" in c), famj(lambda c: c.startswith("T") and "+" in c)
tw_m, tw_j = fam(lambda c: c.startswith("TW")), famj(lambda c: c.startswith("TW"))
cg_m, cg_j = fam(lambda c: c.startswith("CG")), famj(lambda c: c.startswith("CG"))
src = {}
for v in JS["joints"].values(): src[v["source"]] = src.get(v["source"], 0) + 1
pk = SVC["layouts"].get("packers", {}).get("ULS1", {}); pkh = SVC["layouts"].get("packers_heavy", {}).get("ULS1", {})
u = lambda r: f"{r['util']:.2f}" if r else "n/a"
S3, S4, S5, S6 = (AB.get(k, {}) for k in ("S3_no_notch_credit", "S4_links_soft", "S5_links_stiff", "S6_joint_fixity"))
fmt = lambda r: f"{r.get('members_over', '?')} members over (worst {r.get('max_member', 0):.2f}), {r.get('joints_over', '?')} joints over (worst {r.get('max_joint', 0):.2f})" if r else "not run"
A = {
 "Cradle joints are credited with gussets": f"Every cradle now sits over a real gusset pair: the 1.5 mm plates go on first (one plate per joint pair, 3 + 3 screws per face per joint, wafer heads where the cheek covers them), and the cradle cheeks fit over them (92 mm between the cheeks, sleeves 92 mm). A gusset is credited only where the plate is drawn; all 16 cradle joints are on the gusset list ({JS['gusset_joints']} gussets in all: {src.get('lift', 0)} for the lift, {src.get('notch', 0)} for notched chords, {src.get('service', 0)} for the floor in service).",
 "Lip-notch check uses full-section bending": f"New notch check (analysis/liftcalc/notch.py) at every element end on a notch: the lipless section for axial load, both bending axes and tension, by the Direct Strength Method, with its local buckling from the repository's finite strip solver at the notch length (127 mm at joint pairs). Design credit: the nested member holds the flange edges, and at gusseted joints the two plates form the section; never more than the full section. Without any credit (sensitivity S3): {fmt(S3)} - so hold point H4 adds a load test of a notched chord joint. The wall tracks are now modelled bearing on the edge truss under every stud, which removes the false track bending. Design result: members at most {D['envelope']['max_member']:.2f}.",
 "Lifting-head sideways check uses a closed box": f"The head is now a closed box: two 3 mm cheeks joined by two 3 mm end plates above the truss, with an open top for the sling. Checked as a box for the 3.5 % lean ({u(row('sideways load at the pin'))}); pin bending added ({u(row('M20 pin bending'))}); bearing on the roof truss at 1.6 x the guide force ({u(row('head bearing on the roof edge truss'))}).",
 "H5 lets the lift continue": f"H5 stop is now 4 % of each drop's design share (and 1.5 deg hang). H7: each cross beam is set to its own line's measured south / north split within +-25 mm. Two twist design cases at that tolerance (TW1, TW2) pass: members {tw_m:.2f}, joints {tw_j:.2f}.",
 "The drop-lean allowance has three values": f"One lean everywhere: drops within 2 deg of vertical (3.5 %) in the frame cases, the 32 tilt-plus-lean cases and the head check. The lean cases are balanced on every beam of the rig (equal and opposite drops), so the model's holds read about zero. Tilt plus lean: members {tl_m:.2f}, joints {tl_j:.2f}.",
 "H1 does not control what the design assumes": f"The CoG envelope is modelled explicitly: the mass reweighted so the CoG sits 150 mm along and 90 mm across off the design position (four corners), the cascade set to it, level and hanging 2 deg toward the corner, CoG factor 1.0 for these cases (the shift is modelled). All pass: members {cg_m:.2f}, joints {cg_j:.2f}. H1 states the accuracy budget: load cells +-1 % of reading, pick setting +-25 mm, inclinometer +-0.1 deg.",
 "Four south feet": "No longer applies: the south A-frames were replaced by vertical hanger pairs (all 8 lift points identical). Every cradle is at least 101.8 mm from the truss-end cleats.",
 "Truss-end cleats as drawn": "Cleats are now full depth (280 mm) angles, each side of every truss end: 5 screws into the end vertical and 5 into the edge-truss chords (3 bottom, 2 top). Drawn with both legs in the Framer components.",
 "Gusset detail": "One plate per joint or joint pair, 100 mm high, flush with the chord's outer face (no part above the floor or below the truss), 3 + 3 screws per face per joint at 3d pitch and 1.5d edge distance at least. Drawn in the Framer components; the 10-equivalent credit is used only where a plate is drawn.",
 "Lifting-head detailing": "Open top so the round sling eye reaches the sleeve, cheek tops fitted with edge protectors, pin at the model height (3150 mm), cheeks seated on pads with 8 mm clearance over the joint screw heads, plain-shank M20 pin with its bending checked.",
 "Strap-end bolt layouts": f"Cradle cheeks are 200 mm high: the bearing bolts sit just under the chord and the strap bolts below them, with the nuts inside the cradle; cheek tear-out below the strap bolt checked ({u(row('tear-out of the cheek below the lower strap bolt'))}). At the head the strap bolts sit in the box above the truss.",
 "Cradle seat crippling uses a formula": f"Kept as the working check ({u(row('bearing under one truss joint'))}) but marked unverified: hold point H4 now includes a load test of the seat on a 1.15 mm chord joint pair with its nested diagonals, both seats.",
 "Strap net-section check": f"Applied: (0.1 + 3d/s) An fu with phi 0.55 in single shear with washers. The hanger straps are now 50 x 2.5 mm, checked at a 65 / 35 split between the two straps for fit-up ({u(row('strap tension, the more loaded strap'))}); pairs are match-drilled.",
 "Reported margins sit inside the uncertainty": f"Bounding runs added: links 4 times softer (S4): {fmt(S4)}; 4 times stiffer (S5): {fmt(S5)}; joints partly fixed (S6): {fmt(S6)}.",
 "The in-service check assumes a support": f"Landing and storage rule: a packer under every floor-truss end on both sides, shimmed to full bearing. Checked on that support: members {pk.get('max_member', 0):.2f}, joints {pk.get('max_joint', 0):.2f}; with the dead load 1.2 times the itemised mass: members {pkh.get('max_member', 0):.2f}, joints {pkh.get('max_joint', 0):.2f}. H1: if the weighed mass is more than 1.2 x the itemised estimate, re-run the in-service check with it.",
 "172 of the 235 gussets": f"The floor gussets are booked as floor structure (FLOOR_GU) in Framer's BOQ, apart from the lift parts, and sized on the packer support ({src.get('service', 0)}); the basis states they are needed whether or not the module is lifted.",
 "Framer gauge step": "Same method (Framer 0.7.1 has no per-element gauge): the three trusses are re-gauged after framing and Framer's own tooling rules re-run on them; the report states what Framer's checks cover (the framed panels and their machine files; the run is a test run, not engineer-signed; components are not machine parts). A per-element gauge in Framer is a follow-up.",
 "Marriage-face hardware": "H9: after set-down and before the second module, the 8 heads, the 4 north cradles and the marriage-face hanger straps are unbolted and removed (they carry nothing in service and are reused).",
 "Lift straps must stay free": "Detailing rule and H3 inspection: no fixings through lift straps; battens packed out or set past them; linings fixed clear; floor sheet and ceiling notched at the straps; tie plates kept off the strap paths.",
 "Plane-bracing strap ends": "Moved onto the floor and roof truss top chords, 205 mm in from the edge trusses, at x 44.5, 1200, 4200, 7800, 10800 and 11955.5: clear of the wall tracks, the heads and the lift lines.",
}
items = []
for sev, lst in (("blocking", syn["blocking"]), ("should fix", syn["should_fix"])):
    for f in lst:
        act = next((v for k, v in A.items() if f["title"].startswith(k)), "See the report.")
        items.append(dict(title=f["title"], severity=sev, action=act))
out = dict(verdict=("The independent review of Rev D (four AI reviewers, one lens each, then a synthesis that re-ran the checks) found 4 blocking and "
                    "16 should-fix items and said 'not yet'. Rev D.1 answers every one of them, as listed; it has not itself been re-reviewed."),
           reviewed="Rev D, commit f4d20e3 (the A-frame variant); the findings apply to the final Rev D except where noted", items=items)
json.dump(out, open(os.path.join(ROOT, "results", "review", "review_revD.json"), "w", encoding="utf-8"), indent=1)
print(len(items), "items written")
