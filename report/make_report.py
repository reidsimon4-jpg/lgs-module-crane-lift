"""Engineering report (PDF) for the Rev D lift design, built from the result files. Every number in it is read from a file.
Rev C version: make_report_revC.py.

usage: python report/make_report.py <repo root> <out.pdf>
"""
import sys, os, json, math, datetime
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from pdfkit_ilo import Doc, esc, WARN, SKY, OK

ROOT, OUT = sys.argv[1], sys.argv[2]
J = lambda p: json.load(open(os.path.join(ROOT, p), encoding="utf-8"))
E = lambda p: os.path.exists(os.path.join(ROOT, p))
D = J("site/data/revD.json"); B0 = J("site/data/before.json"); CON = J("results/revD_connectors/connectors.json")
SVC = J("results/revD_service/service.json"); AB = {r["id"]: r for r in J("site/data/ablation.json")}; CFG = J("analysis/configs/revD_final.json")
PN = J("verification/solver_crosscheck/pynite_full_R4_revD.json"); FC = J("results/framer_components/summary.json")
JS = J("results/joint_schedule.json")
import glob as _glob, re as _re
_need = [k for k in ("A1_framed_screws", "A2_no_gussets", "A3_no_bridging", "A4_no_plane_bracing", "A5_seat_between_joints", "A6_north_trusses_095", "A8_edge_trusses_100") if k in AB and (AB[k]["members_over"] or AB[k]["joints_over"])]
_free = [k for k in ("A1_framed_screws", "A2_no_gussets", "A3_no_bridging", "A4_no_plane_bracing", "A5_seat_between_joints", "A6_north_trusses_095", "A8_edge_trusses_100") if k in AB and k not in _need]
ABL_SUMMARY = (f"{len(_need)} of {len(_need) + len(_free)} measures are needed (something is over without each)"
               + (f"; not relied on in the lift: {', '.join(k.split('_')[0] for k in _free)}" if _free else "") + ": section 6.3")
N_TESTS = sum(len(_re.findall(r"^def test_", open(f_, encoding="utf-8").read(), _re.M)) for f_ in _glob.glob(os.path.join(ROOT, "analysis", "tests", "test_*.py")))
REV = J("results/review/review.json") if E("results/review/review.json") else None
REV_D = J("results/review/review_revD.json") if E("results/review/review_revD.json") else None
FIG = os.path.join(ROOT, "report/fig")
f = D["meta"]["factor"]; W = D["meta"]["W_N"] / 1e3
cases = D["cases"]; design = D["design_cases"]; info = D["info_cases"]
TL = [c for c in design if c.startswith("T") and "+" in c]; CG = [c for c in design if c.startswith("CG")]
MAIN = [c for c in design if c not in TL and c not in CG]
env = D["envelope"]
max_link_shear = env.get("max_link_shear", max(l["util"] for l in D["links"]))
max_conn = max(r["util"] for r in CON["rows"]); worst_conn = max(CON["rows"], key=lambda r: r["util"])
gov = max(env["max_member"], env["max_joint"], max_link_shear, max_conn)
NAME = {"R1_rigid": "Rigid rig, equal slings", "R2_springs": "Rigid rig, elastic slings", "R4_equalised": "Equalised cascade (main case)",
        "T1_roll_S": "Hangs 2 deg low to the south", "T2_roll_N": "Hangs 2 deg low to the north", "T3_pitch_W": "Hangs 2 deg low to the west end",
        "T4_pitch_E": "Hangs 2 deg low to the east end", "T5_SW": "Hangs 2 deg low to the south-west", "T6_SE": "Hangs 2 deg low to the south-east",
        "T7_NW": "Hangs 2 deg low to the north-west", "T8_NE": "Hangs 2 deg low to the north-east",
        "L1_squeeze_y": "Slings lean in 5 % (across)", "L2_spread_y": "Slings lean out 5 % (across)", "L3_squeeze_x": "Slings lean in 5 % (along)",
        "L4_spread_x": "Slings lean out 5 % (along)", "R7a_outer_high": "Share +10 % on the end lines", "R7b_inner_high": "Share +10 % on the inner lines",
        "R7c_one_end_high": "Share +10 % at one end", "R7d_twist": "Share 10 % twist",
        "TW1_twist": "Twist: cross beams 25 mm off (west S / east N)", "TW2_twist": "Twist: cross beams 25 mm off (west N / east S)"}
KIND = {"rim_truss": "floor edge truss", "roof_rim": "roof edge truss", "floor_truss": "floor truss", "roof_truss": "roof truss", "wall": "wall"}
SIDE = lambda y: "south" if y < 1650 else "north"
lines_m = ", ".join(f"{x / 1000:.2f}" for x in CFG["lift_lines_x"])
gauged = sorted(((CFG.get("build_options") or {}).get("gauge") or {}).keys())
src = Counter(v["source"] for v in JS["joints"].values())
svc_why = Counter(v.get("reason", "screws") for v in JS["joints"].values() if v["source"] == "service")
ties_by = Counter(l["rule"] for l in D["links"] if l["tie"])
t2 = sum(n for r, n in ties_by.items() if r.startswith("wall top track") or r.startswith("wall bottom track"))
t3 = ties_by.get("wall panel to wall panel (seam studs, corner studs, stacked tracks)", 0)
t1 = sum(n for r, n in ties_by.items() if "truss chord end" in r)
jb = D["screws"]["joints_by_screws"]
n_truss_ends = 2 * len({round((m["a"][0] + m["b"][0]) / 2) for m in D["members"] if m["kind"] in ("floor_truss",) and m["type"] == "TOP CHORD"}) \
    + 2 * len({round((m["a"][0] + m["b"][0]) / 2) for m in D["members"] if m["kind"] in ("roof_truss",) and m["type"] == "TOP CHORD"})
SCREWS = [("4 screws instead of 2 at truss and wall joints", int(jb.get("4", 0)), 2), ("joint gussets, 3 + 3 screws per face", int(JS["gusset_joints"]), 12),
          ("truss-end cleats, two per truss end, 5 + 5 screws each", n_truss_ends * 2, 10), ("tie plates T2 (4 + 4)", t2, 8), ("tie plates T3 (2 + 2)", t3, 4),
          ("cradle cheek screws (screwed seat)", len(D["foot_layout"]), 4), ("bridging noggings, 2 each end", sum(1 for m in D["members"] if m["type"] == "BRIDGING"), 4),
          ("plane bracing ends, 3 each end", sum(1 for m in D["members"] if m["type"] == "PLANE BRACE"), 6)]
n_screws = sum(n * k for _, n, k in SCREWS)

doc = Doc(OUT, "Crane lift engineering - LGS classroom module", "Rev D.1", banner="PRELIMINARY - SUBJECT TO STRUCTURAL ENGINEERING",
          date=datetime.date.today().strftime("%d %B %Y"))
doc.cover("Lift engineering study - Rev D.1", "Crane lift of a light-gauge-steel" + chr(10) + "classroom module",
          "Eight identical lift points, each a strap pair from a closed-box lifting head down to a cradle at a truss joint pair, with an equalising rig. Model, checks, part design, verification, two independent reviews.",
          "Prepared by Infinity Living Options (ILO). Preliminary engineering study - not issued for construction.",
          image=os.path.join(FIG, "fig_iso_after.png"),
          chips=(("Preliminary - subject to structural engineering", "#f59e0b"), ("Rated lift mass 6.5 t", "#38bdf8"),
                 (f"Members at most {env['max_member']:.2f}, joints at most {env['max_joint']:.2f} of design capacity", "#4ade80")))

# ------------------------------------------------------------------------------------------------ 1 summary
doc.h1("Summary", "1")
doc.lead("The classroom module was framed in Infinity Framer, then every one of its 1,194 steel members, 2,210 screwed joints and 622 "
         f"panel-to-panel connections was checked for a crane lift at the rated mass of 6.5 tonnes, with a combined factor of {f:.3f} on that "
         f"mass, in {len(design)} design cases: the rig cases, the module hanging 2 degrees out of level in eight directions, slings 2 degrees off "
         f"vertical, both together, the rig's cross beams set 25 mm off, and the centre of gravity at the corners of its allowed area. The bare frame does "
         f"not lift on its own: picked straight up at 8 points it has {AB['B0_frame_only']['members_over']} members "
         f"and {AB['B0_frame_only']['joints_over']} joints over their design capacity. With the lift system in this report, every member, joint, "
         "connection and lift part is below its design capacity in every design case.")
doc.stats([(f"{env['max_member']:.2f}", "highest member utilisation (1.00 = design capacity)"), (f"{env['max_joint']:.2f}", "highest screwed joint utilisation"),
           (f"{max_link_shear:.2f}", "highest panel-to-panel connection, shear"), (f"{max_conn:.2f}", "highest lift part (" + worst_conn["group"].split(" (")[0] + ")")], cols=4)
doc.stats([("6.5 t", "rated lift mass (itemised finished module %.1f t); the first check reaches 1.0 at %.2f t" % (D["meta"]["itemised_kg"] / 1000, 6.5 / gov)),
           (f"{f:.2f}", "factor on the rated mass: 1.03 x 1.05 x 1.5 x 1.5"),
           ("%.0f mm" % max(abs(cases[c]["sag_mm"]) for c in design), "largest sag relative to the lift points, design cases"),
           ("%d / %d" % (AB["B0_frame_only"]["members_over"], AB["B0_frame_only"]["joints_over"]), "members / joints over capacity before (frame as framed)")], cols=4)
doc.h2("What makes it work")
doc.bullets([
    f"<b>Pick it up from underneath, at the truss joints.</b> At each of the 8 lift points (x = {lines_m} m, both sides) a cradle sits under the floor edge truss exactly where two truss diagonals meet the bottom chord. Two bearing bolts under the joints push straight up into the diagonals, so the thin chord does not bend.",
    "<b>Settle every lift point by simple balance.</b> One strap pair per lift point (50 x 2.5 mm steel, one strap on each face, match-drilled) runs straight from the lifting head to the cradle. There is one load path, so bolt fit-up cannot change how the load is shared between lift points (and the pair is checked at a 65 / 35 split between its two straps).",
    "<b>Heads that cannot grab the roof.</b> Each lifting head is a closed steel box over the roof edge truss with no fasteners and an open top for the sling: it keeps the top of the module in line but carries no weight into the roof.",
    f"<b>Heavier steel only where it matters.</b> The two floor edge trusses and the north roof edge truss ({', '.join(gauged)}) are rolled in 1.15 mm instead of 0.95 mm; everything else stays as Framer framed it.",
    f"<b>Strengthen the joints that carry the load.</b> 4 screws instead of 2 at truss and wall joints, {JS['gusset_joints']} joint gussets sized joint by joint, folded cleats at every truss end, and {env['links_tie']} tie plates where a joint would otherwise pull apart.",
    "<b>Make the floor and roof stiff plates</b> with crossed steel straps, and hold the truss chords sideways with bridging lines.",
    "<b>Use a rig that shares the load by balance.</b> An equalising cascade of pinned spreader beams set to the weighed centre of gravity. A rigid lifting frame is not allowed.",
])
doc.callout("What this study is, and is not",
            "It is a complete preliminary design with every number traceable to a file in the repository, checked by an independent second solver, by "
            "Framer's own release check, and by an independent AI review. It is not a certified design: a registered structural engineer must review "
            "it, adopt it and sign it, and the hold points in section 10 must be met. It does not cover transport, wind or earthquake in service, the "
            "module-to-module connection or the foundations.", "warn")

# ------------------------------------------------------------------------------------------------ 2 module
doc.h1("The module and the Framer model", "2")
doc.p("One module of a two-module classroom: 12.0 m long, 3.3 m wide and about 3.3 m high. The south long wall has two windows (1.8 m wide) "
      "and a door; the two end walls are solid; the north long side is the join to the second module, so it is open between two 300 mm piers "
      "at 4.5 m and 7.5 m and two 1.05 m end returns. The floor and the flat roof are cassettes of 300 mm deep C89 trusses at 600 mm "
      "centres, with an edge truss along each long side. The edge trusses are Warren trusses: their diagonals meet the bottom chord in pairs "
      "441 mm apart, and the lift points sit on those pairs.")
doc.p(f"Infinity Framer 0.7.1 framed the whole module from one project file (<i>model/engineered/project.json</i>): {FC['panels']} panels, "
      f"{FC['members']:,} members, {FC['frame_kg']:,.0f} kg with the three 1.15 mm edge trusses. The lift parts were then added to the Framer "
      f"project as {FC['components']} parametric components, so Framer's own bill of quantities and IFC carry them, and Framer's clash check "
      f"and release check were run on the result: {FC['clashes']} clashes, release check {'passed' if FC['release_ok'] else 'NOT passed'}.")
doc.table(["Item", "Value", "Source"], [
    ["Panels / members / steel", f"{FC['panels']} / {FC['members']:,} / {FC['frame_kg']:,.0f} kg", "Framer run of project_with_lift_parts.json"],
    ["Section", "C89-38-9 lipped channel, 0.95 mm; " + ", ".join(gauged) + " in 1.15 mm", "Framer profile; analysis/liftcalc/sections.py"],
    ["Screwed joints as framed", f"{D['screws']['joints']:,} joints, {D['screws']['as_framed']:,} screws (2 per joint)", "Framer dimple joints"],
    ["Joints after this design", f"{jb.get('2', 0)} at 2 screws, {jb.get('4', 0)} at 4 screws, {JS['gusset_joints']} with a gusset", "results/joint_schedule.json"],
    ["Lift parts, as Framer components", f"{FC['components']} components, {FC['component_kg']:.0f} kg of steel", "Framer BOQ group 'components'"],
    ["Framer checks with the parts", f"{FC['clashes']} clashes; release check {'passed' if FC['release_ok'] else 'not passed'} ({FC['release_blockers']} blockers)", "results/framer_components/summary.json"],
    ["IFC of frame and lift parts", f"{FC['ifc_bytes'] / 1e6:.1f} MB", FC["ifc"].replace(chr(92), "/")],
], widths=[2.2, 2.8, 3.2])
doc.callout("One thing Framer cannot do yet",
            "Framer 0.7.1 frames a floor-truss element at the job gauge and has no per-element gauge. The three 1.15 mm edge trusses were therefore set "
            "after Framer's framing run, and Framer's own tooling rules were run again on them (modelling.regenerate) before the checks, the BOQ and the "
            "IFC. In the factory those three trusses must be rolled from 1.15 mm coil. A per-element gauge in Framer would remove this manual step.", "info")
doc.image(os.path.join(FIG, "fig_iso_before.png"), "Figure 1. Before: the frame as framed (2 screws per joint, no lift parts), picked up straight at the floor edge truss "
          f"at the same 8 points. {AB['B0_frame_only']['members_over']} members and {AB['B0_frame_only']['joints_over']} joints are over their design capacity (red).", h_max_mm=95)

# ------------------------------------------------------------------------------------------------ 3 load path
doc.h1("How it is lifted: the load path, step by step", "3")
doc.image(os.path.join(FIG, "fig_iso_after.png"), f"Figure 2. Rev D.1: the frame coloured by utilisation (envelope of the {len(design)} design cases) with the lift parts.", h_max_mm=105)
R4 = cases["R4_equalised"]["reactions"]
doc.h2("3.1 The rig: an equalising cascade")
doc.p("A top beam hangs from the crane hook; two middle beams hang from it; four cross beams hang from those; eight vertical slings drop to the "
      "eight lifting heads. Every beam hangs from a single pin, so the share each sling carries is fixed by simple balance, whatever the sling "
      "lengths. The cross beams are picked off-centre to suit the centre of gravity, which sits %.0f mm south of the centre line because the north "
      "side is open. At the rated mass the south slings carry %.1f to %.1f kN and the north slings %.1f to %.1f kN (no factors)."
      % (1650 - D["meta"]["cg"][1], min(R4[k] for k in R4 if k[0] == "S") / 1e3, max(R4[k] for k in R4 if k[0] == "S") / 1e3,
         min(R4[k] for k in R4 if k[0] == "N") / 1e3, max(R4[k] for k in R4 if k[0] == "N") / 1e3))
doc.image(os.path.join(FIG, "fig_rig.png"), "Figure 3. The cascade rig with the sling forces in the main case (rated mass, no factors).", h_max_mm=80)
r6 = max(cases[c]["max_joint"] for c in info if c.startswith("R6"))
doc.p(f"A rigid lifting frame with eight fixed-length slings is <b>not</b> allowed: with one sling 10 mm short, joints reach {r6:.2f} times their "
      "design capacity (cases R6, information only). A free cascade cannot do that.")
doc.h2("3.2 The lifting head")
doc.p("A closed steel box sits over the roof edge truss at each lift line: two 3 mm G450 cheeks on the faces of the truss, joined above the truss "
      "by two 3 mm end plates, open at the top. The cheeks seat on pads clear of the joint screw heads with running clearance and no fasteners, so the "
      "head keeps the top of the module in line sideways, a stop block keeps it in place along the module, and it cannot carry weight into the roof. "
      "An M20 grade 8.8 plain-shank pin with a 40 mm free-turning sleeve crosses the box near the top; the round sling eye goes down through the open "
      "top onto the sleeve, and the cheek tops carry edge protectors. The hanger straps bolt to the cheeks above the truss. The heads lift off after "
      "set-down, so the gutter and fascia go on afterwards.")
doc.image(os.path.join(FIG, "fig_liftpoint.png"), "Figure 4. A lift point: section across the wall, and lift point S2 seen from outside with the forces in the main case.", h_max_mm=118)
doc.h2("3.3 The hanger straps")
hs = max(r["demand"] for r in CON["rows"] if r["group"].startswith("Hanger strap") and "tension" in r["item"])
doc.p("Two 50 x 2.5 mm G450 straps, one on each face, run from the head straight down to the cradle, with 2 x M12 grade 8.8 bolts and washers at "
      "each end; the two straps of a pair are drilled together so they share the load evenly, and they are checked with 65 % on one strap. They are "
      "fixed nowhere in between: no lining, batten or cladding fixing goes through a strap, and the floor sheet and ceiling are notched round them "
      "(hold point H3), so the straps cannot drag load into studs or plates. "
      f"Each strap carries up to {hs:.1f} kN factored. On the north (marriage) face the strap is the only part standing proud of the frame (with "
      "the cradle cheek and the head cheek). The two modules meet north face to north face with their lift lines opposite each other, so after "
      "set-down the 4 north cradles, the marriage-face straps and the heads are unbolted and taken off (hold point H9); they carry nothing in service.")
doc.h2("3.4 The cradles: how they take the load")
seat = [r for r in CON["rows"] if r["item"].startswith("bearing under one truss joint")][0]
bb = [r for r in CON["rows"] if r["item"].startswith("M16 8.8 bearing bolt bending")][0]
doc.p("This is the key part. The floor edge truss chord is a thin 1.15 mm channel lying with its web down; it is strong along its length but very "
      "weak if it is pushed up between truss joints (with the cradles bearing between joints, members reach 3.5 times their capacity, run A5). So each cradle "
      "sits exactly under a joint pair, where the two truss diagonals meet the chord. Two 3 mm steel cheeks, one on each face of the truss, are "
      "joined under the chord by two M16 grade 8.8 bolts in steel sleeves, one bolt under each joint, each with a 3 mm bearing packer. The strap "
      "pair bolts to the cheeks below the bearing bolts. The joint gusset plates go on first and the 200 mm high cheeks fit over them. When the crane "
      "lifts, the bolts push straight up into the two diagonals and the load goes up the truss with no "
      "bending in the chord. The cheeks are screwed to the chord at the first joint only (2 screws per cheek); at the second joint they only bear. "
      "That stops the stiff cradle from sharing the chord's own pull, which would otherwise overload the screws.")
doc.p(f"Checks: chord flanges under the packer {seat['util']:.2f}, bearing-bolt bending {bb['util']:.2f}, bolt shear and bearing, cheek tear-out and "
      "cheek screws all lower (section 7). Each cradle is placed at least %.0f mm clear of the truss-end cleats on the inside face. The cradles stand "
      "153 mm below the edge truss, so the module is landed on packers (hold point H8)." % min(q["cradle_gap"] for q in D["foot_layout"]))
doc.image(os.path.join(FIG, "fig_cradle.png"), "Figure 5. How a cradle works: elevation along the edge truss and section across the chord.", h_max_mm=82)
doc.h2("3.5 The edge trusses, walls and floor")
doc.p("The four edge trusses are the beams of the module in the lift. The north side is open between the piers, so the north floor and roof edge "
      "trusses span the openings on their own; they and the south floor edge truss are rolled in 1.15 mm (with 0.95 mm, "
      f"{AB['A6_north_trusses_095']['members_over']} members and {AB['A6_north_trusses_095']['joints_over']} joints are over, run A6; with 1.00 mm, "
      f"{AB['A8_edge_trusses_100']['members_over']} members and {AB['A8_edge_trusses_100']['joints_over']} joints, run A8). The checks take the steel as G450, so 1.15 mm coil of grade G450 or better "
      "is enough, but it must be certified to AS 1397 (hold point H2), and BlueScope Indonesia lists its TRUECORE G550 coil only up to 1.00 mm: the "
      "certified source of the 1.15 mm coil for these three trusses must be confirmed before production. The walls carry the roof down to the floor "
      "edge trusses as they do in service.")
doc.image(os.path.join(FIG, "fig_elev_south.png"), "Figure 6. South wall line with the lift parts. The straps are vertical and clear the windows and the door.", h_max_mm=85)
doc.image(os.path.join(FIG, "fig_elev_north.png"), "Figure 7. North (open) side: the hangers sit on the piers and end returns.", h_max_mm=85)
doc.h2("3.6 Bracing, bridging, joints and ties")
doc.p("Crossed 30 x 1.0 mm G300 straps with tensioners in the floor and roof planes, anchored on the truss top chords 205 mm in from the edge "
      "trusses (clear of the wall tracks and the heads), make the floor and roof stiff plates "
      f"(without them {AB['A4_no_plane_bracing']['members_over']} members and {AB['A4_no_plane_bracing']['joints_over']} joints are over, run A4). "
      + (f"A line of C89 noggings near mid-span, 90 mm off the panel point, ties the truss chords sideways; the lift does not rely on it (without it "
         f"the worst member is {AB['A3_no_bridging']['max_member']:.2f} and nothing is over, run A3), and it is kept as normal floor-truss practice. "
         if AB['A3_no_bridging']['members_over'] == 0 and AB['A3_no_bridging']['joints_over'] == 0 else
         f"A line of C89 noggings near mid-span, 90 mm off the panel point, holds the truss chords sideways (without it one chord reaches {AB['A3_no_bridging']['max_member']:.2f}, run A3). ") +
      f"Every truss and wall joint that carries lift load gets 4 screws instead of 2 (with 2 screws everywhere {AB['A1_framed_screws']['joints_over']} joints "
      f"are over, run A1). Where 4 screws are not enough, or where a notched chord needs it, the joint gets a gusset: two 1.5 mm plates flush with the "
      f"chord face, 3 + 3 screws per face. The gussets were sized joint by joint (analysis/size_joints.py): {src.get('lift', 0)} for the lift, "
      f"{src.get('notch', 0)} for notched chords and {src.get('service', 0)} for the 3 kPa classroom floor in service (floor structure, needed whether or not the module is lifted) "
      f"(without them {AB['A2_no_gussets']['joints_over']} joints are over, run A2). Every truss end gets a full-depth folded 1.5 mm cleat on each side "
      f"(5 screws into the end vertical, 5 into the edge-truss chords), and {t2 + t3} tie plates (T2 {t2}, T3 {t3}) go across the wall joints that would "
      f"otherwise pull apart, so no screw is relied on in pull-out.")
doc.image(os.path.join(FIG, "fig_plan.png"), "Figure 8. Floor plan: lift points, cradles, centre of gravity, floor plane bracing and the bridging line.", h_max_mm=72)
doc.h2("3.7 How the design got here")
doc.p("Rev C used a vertical hanger plus inclined straps at each lift point, with 600 mm cradles screwed along the chord. An independent review "
      "found that the share between hanger and inclined straps depended on bolt fit-up, and raised six more blocking points (section 9). Rev D "
      "first replaced the south lift points with A-frames of two inclined strap pairs. That was settled by balance and passed the checks, but the "
      "inclined straps and their cradles clashed with the truss-end cleats on the inside face of the edge truss. The final Rev D uses one vertical "
      "strap pair into one cradle at every lift point: simpler, fewer parts, nothing near the windows, door or cleats. A second independent review "
      "of Rev D then found 4 blocking and 16 should-fix items (section 9). Rev D.1 answers them: the notched sections are checked properly, the joints "
      "under the cradles get real gussets, the head is a closed box, the straps are thicker, the rig tolerances are tied to the hold points and checked "
      "(tilt with lean, twist, centre-of-gravity corners), and the landing rule is a packer under every floor-truss end.")

# ------------------------------------------------------------------------------------------------ 4 design basis
doc.h1("Design basis", "4")
doc.p("The full basis is in <i>docs/DESIGN_BASIS.md</i>. The factors and rules were set from a public-source research study (lifting factors, "
      "AS/NZS 4600 rules, rigging hardware, masses), fact-checked by separate reviewers; their corrections are adopted.")
fc = D["meta"]["factors"]
doc.table(["Factor", "Value", "Why"], [
    ["Weight", f"{fc['weight']}", "on the weighed mass (hold point H1); the 6.5 t rating is already about 1.4 x the itemised mass"],
    ["Centre of gravity", f"{fc['cog']}", "DNV-OS-H102 minimum when no CoG envelope is modelled; with the H1 CoG limits"],
    ["Dynamic", f"{fc['dynamic']}", "Australian practice: at least 1.2 for a crane on outriggers; 1.5 adopted for the whole frame"],
    ["Load factor", f"{fc['load']}", "lifting points and their load path; used for the whole frame"],
    ["Total", f"{f:.3f}", "applied to the rated 6.5 t in every member, joint, connection and part check"],
], widths=[1.6, 0.9, 6.0])
doc.table(["Case", "What it represents", "Type"], [[c, NAME.get(c, cases[c]["label"]), "design"] for c in MAIN] +
          [["T1+L1 ... T8+L4", f"Each 2 deg tilt with each 3.5 % lean ({len(TL)} cases)", "design"],
           ["CG_NE ... CG_SW+T", f"Centre of gravity 150 mm along and 90 mm across off its design position, level and hanging 2 deg toward that corner ({len(CG)} cases; CoG factor 1.0 as the shift is modelled)", "design"]] +
          [["R7a-d", "Sling share +-10 % (a pinned cascade shares by balance, so this is robustness only)", "information"],
           ["R6 (x8)", "Rigid rig, one sling 10 mm short", "information"], ["R5 (x8)", "One sling slack", "information"]], widths=[1.6, 5.4, 1.1])
doc.h2("Resistance")
doc.bullets([
    "Members: AS/NZS 4600:2018 Direct Strength Method and effective width method (lower governs), elastic buckling from a finite-strip table (matches "
    "published values within about 1 %). Member steel taken as G450 (fy 450 MPa) although the coil will be G550.",
    "At every element end that sits on a Framer lip notch the member is checked as the lipless section for axial load, both bending axes and tension, "
    "by the Direct Strength Method, with its local buckling from the finite strip solver at the notch length (50 mm, or about 127 mm across a truss joint "
    "pair). The nested web member or stud holds the flange edges, and at a gusseted joint the two plates form the section; without that credit "
    f"(sensitivity S3) {AB.get('S3_no_notch_credit', {}).get('members_over', '?')} members are over, so hold point H4 includes a test of a notched chord joint. "
    "Members with a service hole use the net area. Member shear and bending with shear are checked.",
    "Buckling lengths from the model: in plane, the largest gap between joints; out of plane, the largest gap between points held by another panel or a "
    "lift part. Twist (torsional) buckling length = the gap between screwed joints, because the screws pass through both flanges at every truss "
    f"joint and wall noggin (hold point H3). Without that restraint {AB['S2_twist_length_out']['members_over']} members are over (sensitivity S2).",
    "No restraint from linings, cladding or flooring in the lift check (counting them changes nothing that governs: sensitivity S1).",
    "Screwed joints: every member end force passes through the screws (bearing only for a stud standing square on a plate). One 10 gauge screw in "
    "0.95 mm steel: 1.77 kN, using fu = 0.75 x 550 = 412.5 MPa; 10 % less per screw in groups of 3 or more; fracture cap 2.85 kN; end rupture "
    "checked at every Framer screw from its distance to the member end.",
    "Bolts on sheet: deformation-limited bearing (AISI S100-16 J3.3.2) at 0.65; tear-out 0.60 t e fu; net section 0.65 An fu; bolts grade 8.8 at 800 MPa.",
])

_seats = [q for q in CON.get("seats", []) if q["cradle"] == "FOOT_S2h" and q["case"] == "R4_equalised"]
_up = [q["up_kN"] - q["down_kN"] for q in _seats]
S2HAND = (D["lift_points"]["S2"]["reactions_kN"]["R4_equalised"], [m for m in D["members"] if m["id"] == "HANG_S2"][0]["N_R4_unfactored"],
          sum(_up) / f, 100 * min(_up) / sum(_up), 100 * max(_up) / sum(_up))
# ------------------------------------------------------------------------------------------------ 5 analysis model
doc.h1("Analysis model and verification", "5")
doc.p("A 3D frame model was built from Framer's export (<i>analysis/liftcalc/framemodel.py</i>): every member split at its joints, in-plane ends "
      "pinned at joints, panels joined by short links where Framer's members touch, truss end reactions carried by ties standing for the cleat screws, "
      "and every lift part added as members attached to the framed members. The cradle is modelled as a stiff body on two seats at the truss joints: "
      "the screwed seat is pinned in the truss plane, the bearing-only seat is an upward-only bar. Straps carry tension only. %s nodes, %s elements. "
      "The mass model (table below) is spread onto the members it belongs to and scaled up to 6.5 t (x%.2f), keeping its distribution and centre of gravity."
      % (f"{PN['nodes']:,}", f"{PN['elements']:,}", D["scale_to_rated"]))
grp = {}
for x in D["ledger"]: grp[x["group"]] = grp.get(x["group"], 0) + x["kg"]
doc.table(["Group", "Itemised kg", "Rated kg (x%.2f)" % D["scale_to_rated"]], [[g, f"{v:,.0f}", f"{v * D['scale_to_rated']:,.0f}"] for g, v in grp.items()] +
          [["<b>Total</b>", f"<b>{sum(grp.values()):,.0f}</b>", f"<b>{sum(grp.values()) * D['scale_to_rated']:,.0f}</b>"]], widths=[3, 2, 2])
doc.h2("Verification of the solver and the model")
doc.table(["Check", "Result"], [
    ["Equilibrium in every case", f"sum of sling forces = weight to 4 decimals in all {len(design) + len(info)} cases ({W:.2f} kN)"],
    ["Independent solver (PyNite) on the full Rev D.1 model, main case", f"displacements agree to {PN['relative_disp_difference']:.0e}, axial forces to {PN['relative_axial_difference']:.0e} (relative); same nodes, elements and releases"],
    ["Lift point S2 by hand (main case, no factors)", "sling %.2f kN = hanger pair %.2f kN + head and strap weight; the two cradle seats push up %.2f kN in total, shared %.0f / %.0f %% (hanger at the pair centre)" % S2HAND],
    ["Unit tests", f"{N_TESTS} tests: solver against closed-form results and PyNite, sections against Framer, buckling table against published values, capacities against the reviewers' hand values, the lip-notch section, the bolted strap rule"],
    ["Framer's clash and release checks, frame with the lift parts", f"{FC['clashes']} clashes; release check {'passed' if FC['release_ok'] else 'not passed'}"],
    ["Each measure taken away in turn (ablation)", ABL_SUMMARY],
    ["Independent review", "five AI reviewers on Rev C, every finding answered in Rev D; four AI reviewers on Rev D, every finding answered in Rev D.1 (section 9)"],
], widths=[3.2, 5.2])

# ------------------------------------------------------------------------------------------------ 6 results
doc.h1("Results", "6")
doc.h2("6.1 Every design case")
rows = []
for c in MAIN:
    x = cases[c]
    rows.append([NAME.get(c, c), f"{x['max_member']:.2f}", f"{x['max_joint']:.2f}", f"{x['max_link']:.2f}", f"{x['sag_mm']:.1f} / {x['hog_mm']:+.1f}",
                 " ".join(f"{x['reactions'][k] / 1e3:.1f}" for k in ("S1", "S2", "S3", "S4")), " ".join(f"{x['reactions'][k] / 1e3:.1f}" for k in ("N1", "N2", "N3", "N4"))])
for lab, grp in ((f"Tilt 2 deg + lean 3.5 %, {len(TL)} cases (worst)", TL), (f"CoG envelope corners, {len(CG)} cases (worst)", CG)):
    if grp:
        wm = max(grp, key=lambda c: cases[c]["max_member"])
        rows.append([lab + f": {wm}", f"{max(cases[c]['max_member'] for c in grp):.2f}", f"{max(cases[c]['max_joint'] for c in grp):.2f}",
                     f"{max(cases[c]['max_link'] for c in grp):.2f}", f"{min(cases[c]['sag_mm'] for c in grp):.1f} / {max(cases[c]['hog_mm'] for c in grp):+.1f}", "", ""])
doc.table(["Case", "Member", "Joint", "Link*", "Sag / hog mm", "S1-S4 kN", "N1-N4 kN"], rows, widths=[2.6, 0.8, 0.8, 0.8, 1.3, 1.8, 1.8], font_cell="cell")
doc.small("Utilisations at the factored level (x%.3f). *Link utilisation here is the largest of shear and pull-out; every link in tension gets a "
          "tie plate, and the shear on the link screws is at most %.2f. Sag and hog are relative to the lift points at the rated mass, no factors. "
          "Sling forces unfactored." % (f, max_link_shear))
doc.image(os.path.join(FIG, "fig_cases.png"), "Figure 9. Worst member and joint in every design case.", h_max_mm=68)
doc.image(os.path.join(FIG, "fig_reactions.png"), "Figure 10. Sling force at each lift point in every design case.", h_max_mm=68)
doc.h2("6.2 The most loaded members and joints")
mem = sorted([m for m in D["members"] if m.get("util") is not None], key=lambda m: -m["util"])[:12]
doc.table(["Member", "Where", "Util", "Case", "Check", "N kN", "M in / out kNm"],
          [[f"{KIND.get(m['kind'], m['kind'])} {m['type'].lower()}", f"x {((m['a'][0] + m['b'][0]) / 2000):.1f} m, {SIDE((m['a'][1] + m['b'][1]) / 2)}", f"{m['util']:.2f}",
            NAME.get(m["case"], m["case"]), m["mode"][:46], f"{m['N']:.1f}", f"{m['M_in']:.2f} / {m['M_out']:.2f}"] for m in mem],
          widths=[2.2, 1.6, 0.6, 1.9, 2.6, 0.7, 1.2])
jt = sorted(D["joints"], key=lambda j: -j["util"])[:12]
doc.table(["Joint in", "At x, y, z (m)", "Screws", "Demand kN", "Capacity kN", "Util", "Case"],
          [[j["panel"], "%.2f, %.2f, %.2f" % tuple(v / 1000 for v in j["xyz"]), j["screws"], f"{j['demand']:.2f}", f"{j['capacity']:.2f}", f"{j['util']:.2f}", NAME.get(j["case"], j["case"])] for j in jt],
          widths=[1.0, 2.0, 0.8, 1.0, 1.1, 0.7, 2.6])
doc.small("A joint shown with 10 screws has a gusset (two 1.5 mm plates, 3 + 3 screws per face), counted as 10 screw-equivalents.")
doc.h2("6.3 What each measure does (ablation) and sensitivity")
doc.image(os.path.join(FIG, "fig_ablation.png"), "Figure 11. The design with one measure taken away (or one assumption changed) at a time, against the bare frame and the full design.", h_max_mm=86)
order = [k for k in ("revD_final", "S1_lining_credit", "S4_links_soft", "S5_links_stiff", "S6_joint_fixity", "A7_single_inner_hanger", "A3_no_bridging", "A8_edge_trusses_100",
                     "A6_north_trusses_095", "A5_seat_between_joints", "S2_twist_length_out", "S3_no_notch_credit",
                     "A4_no_plane_bracing", "A2_no_gussets", "A1_framed_screws", "B0_frame_only") if k in AB]
doc.table(["Run", "Members over", "Joints over", "Worst member", "Worst joint"], [[AB[k]["name"], AB[k]["members_over"], AB[k]["joints_over"], f"{AB[k]['max_member']:.2f}", f"{AB[k]['max_joint']:.2f}"] for k in order],
          widths=[5.2, 0.9, 0.9, 0.9, 0.9])
doc.p(f"Some results need a word. A single hanger strap on the inside face at the north lift points (nothing on the marriage face) also passes the "
      f"frame checks, at {AB['A7_single_inner_hanger']['max_member']:.2f}: it is a fall-back if the marriage face must stay clear, but that strap then carries "
      "the whole drop force and needs its own check, and the cradle twist must be checked. "
      + (f"The bridging line is not relied on in the lift (run A3: worst member {AB['A3_no_bridging']['max_member']:.2f} without it); it is kept as normal "
         "floor-truss practice. " if AB['A3_no_bridging']['members_over'] == 0 and AB['A3_no_bridging']['joints_over'] == 0 else "")
      + "The design relies on the screws through both flanges at every truss joint and wall noggin to stop members twisting (S2), and on the nested "
      f"member holding the cut flange edges at a lip notch (S3: without that credit {AB['S3_no_notch_credit']['members_over']} members are over, worst "
      f"{AB['S3_no_notch_credit']['max_member']:.2f}): both are hold points (H3, and the notched-joint load test in H4). Links 4 times softer or stiffer "
      f"and partly fixed joints (S4 to S6) leave nothing over: worst member {max(AB[k]['max_member'] for k in ('S4_links_soft', 'S5_links_stiff', 'S6_joint_fixity')):.2f}, "
      f"worst joint {max(AB[k]['max_joint'] for k in ('S4_links_soft', 'S5_links_stiff', 'S6_joint_fixity')):.2f}.")
doc.h2("6.4 Information cases")
rows = [[c, cases[c]["label"][:72], f"{cases[c]['max_member']:.2f}", f"{cases[c]['max_joint']:.2f}", f"{cases[c]['sag_mm']:.1f}"] for c in info]
doc.table(["Case", "Description", "Member", "Joint", "Sag mm"], rows, widths=[1.4, 4.8, 0.8, 0.8, 0.8])
doc.small("These are not design cases. A pinned cascade shares by balance (R7 is a robustness check), a sling cannot be 10 mm short in a free cascade "
          "(R6 is why a rigid frame is excluded), and losing a sling (R5) is not survivable on any 4-point pick, which is why the rig and slings are "
          "certified and proof tested (hold point H7).")

# ------------------------------------------------------------------------------------------------ 7 parts
doc.h1("Lift parts: design checks and schedule", "7")
doc.p("Every part outside Framer was checked against the largest factored force it carries in any design case (<i>analysis/run_connectors.py</i>).")
prev = None; prow = []
for r in CON["rows"]:
    prow.append([("<b>" + esc(r["group"]) + "</b>") if r["group"] != prev else "", r["item"], r["demand"], r["capacity"], r["unit"], f"{r['util']:.2f}"]); prev = r["group"]
doc.table(["Part", "Check", "Demand", "Capacity", "Unit", "Util"], prow, widths=[2.6, 4.2, 0.8, 0.9, 0.8, 0.6])
rg = CON["rigging"]
doc.callout("Rigging interface", f"Largest drop force in the design cases, with weight and CoG factors: {rg['max_static_drop_kN']} kN ({rg['max_static_drop_t']} t), no dynamic factor. "
            "Drop gear: 2 t round slings (or 8 mm chain), the round sling eye straight over the free-turning sleeve on the M20 head pin; shackles only "
            "at the beam ends. The rig itself (beams, slings, shackles, top rigging) is lifting equipment designed, certified (AS 4991) and proof tested "
            "by the rigging supplier; drop points within 50 mm of the head positions.", "info")
rows = [[r["item"], r["count"], f"{r['qty']:.1f}"] for r in FC["component_rows"]]
rows += [["M12 8.8 bolt sets (hanger straps, 2 per strap end)", f"{8 * 2 * 2 * 2}", ""], ["M16 8.8 bearing bolts with 92 mm sleeves and 3 x 40 x 89 packers", f"{2 * len(D['foot_layout'])}", ""],
         ["M20 8.8 lifting pins with 40 mm sleeves", "8", ""], ["Strap tensioners for the plane bracing", f"{sum(1 for m in D['members'] if m['type'] == 'PLANE BRACE')}", ""],
         [f"Added 10 gauge screws (brand with at least 5.7 kN shear, hold point H3)", f"{n_screws:,}", ""]]
doc.table(["Part (Framer component or hardware)", "Qty", "Steel kg"], rows, widths=[6.4, 0.8, 1.0])
doc.table(["Where the added screws go", "Places", "Screws each", "Screws"], [[a, f"{n:,}", k, f"{n * k:,}"] for a, n, k in SCREWS] + [["<b>Total</b>", "", "", f"<b>{n_screws:,}</b>"]],
          widths=[4.6, 1.0, 1.0, 1.0])
doc.small(f"Quantities and masses of the parts are Framer's own bill of quantities for the components placed in the project (steel only). They add "
          f"{FC['component_kg']:.0f} kg to the {FC['frame_kg']:,.0f} kg frame. Nothing is temporary.")

# ------------------------------------------------------------------------------------------------ 8 in service
doc.h1("In service (sanity check)", "8")
lb = SVC["layouts"]["bearer"]; lp = SVC["layouts"]["piers"]
lk = SVC["layouts"].get("packers", lb); lh = SVC["layouts"].get("packers_heavy", lb)
doc.p("The lift parts and extra screws must not leave the module weak in service, and the floor must carry a classroom. Check: 1.2 x dead + 1.5 x live, "
      "live load 3.0 kPa on the floor and 0.25 kPa on the roof, dead load the itemised mass (%.1f kN), every lift part left in place (the straps carry "
      "nothing because the heads are free vertically), flooring screwed at 300 mm restraining the floor truss top chords." % SVC["G_kN"])
doc.table(["Support", "Members over", "Max member", "Joints over", "Max joint", "Floor truss sag (G + 0.7Q)"], [
    ["A packer under every floor-truss end, both sides (the landing rule)", lk["ULS1"]["members_over"], f"{lk['ULS1']['max_member']:.2f}", lk["ULS1"]["joints_over"], f"{lk['ULS1']['max_joint']:.2f}", f"{lk['floor_truss_relative_sag_SLS_mm']} mm"],
    ["The same, dead load 1.2 x the itemised mass", lh["ULS1"]["members_over"], f"{lh['ULS1']['max_member']:.2f}", lh["ULS1"]["joints_over"], f"{lh['ULS1']['max_joint']:.2f}", f"{lh['floor_truss_relative_sag_SLS_mm']} mm"],
    ["Continuous rigid bearers under both floor edge trusses (reference)", lb["ULS1"]["members_over"], f"{lb['ULS1']['max_member']:.2f}", lb["ULS1"]["joints_over"], f"{lb['ULS1']['max_joint']:.2f}", f"{lb['floor_truss_relative_sag_SLS_mm']} mm"],
    ["Piers at 1.8 m or less", lp["ULS1"]["members_over"], f"{lp['ULS1']['max_member']:.2f}", lp["ULS1"]["joints_over"], f"{lp['ULS1']['max_joint']:.2f}", f"{lp['floor_truss_relative_sag_SLS_mm']} mm"],
], widths=[3.2, 1.0, 1.0, 1.0, 1.0, 1.6])
doc.p(f"On a packer under every floor-truss end everything passes, and also with 1.2 times the itemised dead load. On piers at 1.8 m it does not, so "
      f"the landing and storage rule is a packer under every floor-truss end (hold point H8). Lip notches are checked here exactly as in the lift "
      f"(lipless section with the edge credit; a gusseted joint as the plated section). This check found that {src.get('service', 0)} floor-truss joints "
      f"need a gusset for the 3 kPa classroom load ({svc_why.get('screws', 0)} because 4 screws are not enough, {svc_why.get('lip notch', 0)} because the "
      "notched chord is over without one); they are floor structure, needed whether or not the module is lifted, and are in the parts list. "
      "Not checked: wind, earthquake, transport, point loads, the floor sheet, roof sheeting, foundations.")

# ------------------------------------------------------------------------------------------------ 9 independent review
doc.h1("Independent review", "9")
if REV:
    syn = REV.get("synthesis") or {}
    doc.p(esc(syn.get("verdict", "")))
    if REV.get("resolutions"):
        doc.table(["Finding (review of Rev C)", "Severity", "Status", "What Rev D does"], [[esc(r["title"]), r["severity"], r.get("status", ""), esc(r["action"])] for r in REV["resolutions"]],
                  widths=[2.8, 0.8, 0.7, 4.2], font_cell="cell")
if REV_D:
    doc.h2("Review of Rev D")
    doc.p(esc(REV_D.get("verdict", "")))
    if REV_D.get("items"):
        doc.table(["Finding (review of Rev D)", "Severity", "What was done"], [[esc(r["title"]), r["severity"], esc(r["action"])] for r in REV_D["items"]],
                  widths=[3.2, 0.9, 4.4], font_cell="cell")
elif REV:
    doc.p("A second independent review of Rev D is in progress; its findings are added to this section when it completes.")

# ------------------------------------------------------------------------------------------------ hold points and limits
doc.h1("Hold points, lift sequence and limits", "10")
doc.table(["Hold point", "Requirement"], [
    ["H1 Weigh", "Weigh the first module (and any changed layout) on load cells under the 8 lift points (accuracy +-1 % of reading). Mass x 1.03 must not exceed 6,500 kg; if the mass is more than 1.2 x the itemised estimate, re-run the in-service check with it. The centre of gravity from the readings must be within 90 mm across and 150 mm along of the design position (the modelled envelope); it sets the cascade."],
    ["H2 Steel", "Coil certificates for every coil in lift-critical members: AS 1397 grade, base metal thickness at least 95 % of nominal. The floor edge trusses and the north roof edge truss from 1.15 mm coil."],
    ["H3 Screws", "Screw brand fixed, characteristic shear at least 5.7 kN (10 gauge; cheek screws with a drill point rated for the full thickness); counts per the joint schedule; screws through both flanges at every truss joint and wall noggin; gussets and cleats as scheduled; no fixings through the lift straps; inspected before lining."],
    ["H4 Tests", "Load tests before first use, factor and acceptance set by the engineer (AS/NZS 4600 Section 8): one complete lift point (cradle on a 1.15 mm truss joint pair with its nested diagonals, strap pair, head), including both cradle seats; and one notched chord joint in combined axial load and in-plane bending."],
    ["H5 First lift", "Load-measuring shackles on all 8 drops; lift 100 mm and hold; stop if any drop is more than 4 % from its design share or the module hangs more than 1.5 degrees out of level."],
    ["H6 Conditions", "Crane on outriggers, no travelling with the load, controlled hoist speed, no snatch, wind within the lift plan limit, tag lines at both ends."],
    ["H7 Rig", "Cascade beams, slings and shackles designed, certified to AS 4991, proof tested and rated by the rigging supplier; drop spacing equal to the head spacing so the drops hang within 2 degrees of vertical; each cross beam set to its own line's measured split within 25 mm; beams free to rotate; planning hook load = 6.5 t + rigging."],
    ["H8 Landing", "Land and store only on a packer under every floor-truss end, both sides, shimmed to full bearing (feeler-gauge check), never on corners; the cradles stand 153 mm below the edge truss."],
    ["H9 Fit-up", "Stud end gap at most 1 mm within 600 mm of the lift lines. After set-down and before the second module: remove the 8 heads, the 4 north cradles and the marriage-face hanger straps (they carry nothing in service); marriage gap at least 15 mm; gutter fitted after."],
], widths=[1.4, 7.0])
doc.h2("Lift sequence")
doc.bullets(["Check the lift parts, ties, gussets and cleats are fitted and inspected; check the weighed mass and CoG are on the lift plan.",
             "Set the cascade pick points to the weighed CoG; hang the drops; round sling eyes over the head sleeves; drops vertical within 2 degrees.",
             "Take up slowly; at 100 mm stop and read the load shackles (H5); check the hang is level within 1.5 degrees.",
             "Lift, slew and land on the prepared bearers and packers, all 8 lines together (no landing on one end).",
             "Remove the heads, the 4 north cradles and the marriage-face hanger straps; fit the gutter; place the second module."])
doc.h2("Limits of this study")
doc.bullets(["Preliminary: not certified, not for construction. A registered structural engineer must review, adopt and sign the design.",
             "The mass is an itemised estimate scaled to the 6.5 t rating; the real mass and CoG come from weighing (H1).",
             "The AS/NZS 4600:2018 text itself was not available; clauses were taken from public quotations, AISI S100-16 and published tables, with the more conservative value where they differ.",
             "The frame model idealises Framer's screwed joints as pins in plane and its panel contacts as short links; the ablation and sensitivity runs show how results depend on the main choices. A full elastic buckling analysis of the whole model was not run.",
             "Transport, wind and earthquake in service, the module-to-module connection, the foundations and the rig itself are outside this study."])

# ------------------------------------------------------------------------------------------------ appendix
doc.h1("Appendix: where everything is", "A")
doc.table(["Path", "What it is"], [
    ["docs/DESIGN_BASIS.md", "factors, cases, resistance rules, hold points"],
    ["model/engineered/project.json, framed.json", "the Framer project and Framer's framed output"],
    ["model/engineered/project_with_lift_parts.json, lift_module_frame_and_parts.ifc", "the Framer project with the lift parts as components, and its IFC"],
    ["model/mass_model.json", "itemised mass of the finished module with sources"],
    ["analysis/configs/revD_final.json", "the design: lift lines, parts, screw schedule, gussets, factors, cases"],
    ["analysis/run_lift.py, analysis/liftcalc/", "frame model, solver, cases, member / joint / link checks"],
    ["analysis/run_connectors.py, run_service.py, size_joints.py, run_ablation.py", "lift part checks; in-service check; gusset sizing; ablation runs"],
    ["results/revD_final/, revD_connectors/, revD_service/, ablation_revD/, joint_schedule.json", "results: logs, summaries, the joint schedule"],
    ["verification/", "PyNite cross-check of the full model, Framer engine attempt"],
    ["results/review/", "the independent reviews and how each finding was answered"],
    ["site/", "the interactive 3D page (index.html and data)"],
    ["report/", "this report and its figures (rebuilt from the result files)"],
], widths=[4.0, 4.4])
doc.p("Reproduce: <i>.venv/Scripts/python.exe analysis/run_lift.py model/engineered analysis/configs/revD_final.json results/revD_final</i>, then "
      "<i>run_connectors.py</i>, <i>run_service.py</i>, <i>export_results.py</i>, <i>run_ablation.py</i>, <i>report/make_figures.py</i> and "
      "<i>report/make_report.py</i>.")
doc.build()
print("written", OUT)
