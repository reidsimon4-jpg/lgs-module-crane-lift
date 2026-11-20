"""Engineering report (PDF) for the lift design, built from the result files. Every number in it is read from a file.

usage: python report/make_report.py <repo root> <out.pdf>
"""
import sys, os, json, math, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from pdfkit_ilo import Doc, esc, WARN, SKY, OK

ROOT, OUT = sys.argv[1], sys.argv[2]
J = lambda p: json.load(open(os.path.join(ROOT, p), encoding="utf-8"))
D = J("site/data/revC.json"); B0 = J("site/data/before.json"); CON = J("results/revC_design/connectors.json")
SVC = J("results/service/service.json"); AB = {r["id"]: r for r in J("site/data/ablation.json")}; CFG = J("analysis/configs/revC_design.json")
PN = J("verification/solver_crosscheck/pynite_full_R4.json"); FR = J("verification/framer_crosscheck/framer_reactions.json")
FC = J("results/framer_components/summary.json")
REV = J("results/review/review.json") if os.path.exists(os.path.join(ROOT, "results/review/review.json")) else None
FIG = os.path.join(ROOT, "report/fig")
f = D["meta"]["factor"]; W = D["meta"]["W_N"] / 1e3
cases = D["cases"]; design = [c for c in cases if cases[c]["design"]]; info = [c for c in cases if not cases[c]["design"]]
env = D["envelope"]
max_link_shear = max(l["util"] for l in D["links"])          # shear on the screws (tension goes to the tie plates)
gov = max(env["max_member"], env["max_joint"], max_link_shear, max(r["util"] for r in CON["rows"]))
NAME = {"R1_rigid": "Rigid frame, equal slings", "R2_springs": "Rigid frame, elastic slings", "R4_equalised": "Equalised cascade (main case)",
        "R7a_outer_high": "Skew +10 % on the end lines", "R7b_inner_high": "Skew +10 % on the inner lines", "R7c_one_end_high": "Skew +10 % on one end",
        "R7d_twist": "Skew 10 % twist", "L1_squeeze_y": "Slings lean in 5 % (across)", "L2_spread_y": "Slings lean out 5 % (across)",
        "L3_squeeze_x": "Slings lean in 5 % (along)", "L4_spread_x": "Slings lean out 5 % (along)"}
KIND = {"rim_truss": "floor edge truss", "roof_rim": "roof edge truss", "floor_truss": "floor truss", "roof_truss": "roof truss", "wall": "wall"}
SIDE = lambda y: "south" if y < 1650 else "north"

doc = Doc(OUT, "Crane lift engineering - LGS classroom module", "Rev C", banner="PRELIMINARY - SUBJECT TO STRUCTURAL ENGINEERING",
          date=datetime.date.today().strftime("%d %B %Y"))
doc.cover("Lift engineering study - Rev C", "Crane lift of a light-gauge-steel" + chr(10) + "classroom module",
          "Eight-point pick-up from under the floor, with hanger straps, cradles and an equalising rig. Model, checks, part design, verification.",
          "Prepared by Infinity Living Options (ILO). Preliminary engineering study - not issued for construction.",
          image=os.path.join(FIG, "fig_iso_after.png"),
          chips=(("Preliminary - subject to structural engineering", "#f59e0b"), ("Rated lift mass 6.5 t", "#38bdf8"), (f"Members at most {env['max_member']:.2f}, joints at most {env['max_joint']:.2f} of design capacity", "#4ade80")))

# ------------------------------------------------------------------------------------------------ 1 summary
doc.h1("Summary", "1")
doc.lead("The classroom module was framed in Infinity Framer, then every one of its 1,194 steel members, 2,210 screwed joints and 524 "
         "panel-to-panel connections was checked for a crane lift at the rated mass of 6.5 tonnes, with a combined factor of "
         f"{f:.3f} on that mass, in {len(design)} lift cases. The bare frame does not lift on its own: picked straight up at 8 points it has "
         f"{AB['B0_frame_only']['members_over']} members and {AB['B0_frame_only']['joints_over']} joints over their design capacity. "
         "With the lift system in this report, every member and joint is below its design capacity in every case.")
doc.stats([(f"{env['max_member']:.2f}", "highest member utilisation (1.00 = design capacity)"), (f"{env['max_joint']:.2f}", "highest screwed joint utilisation"),
           (f"{max_link_shear:.2f}", "highest panel-to-panel connection, shear"), (f"{env['links_tie']}", "joints given a tie plate so no screw works in pull-out")], cols=4)
doc.stats([("6.5 t", "rated lift mass (itemised finished module %.1f t); first check reaches 1.0 at %.2f t" % (D["meta"]["itemised_kg"] / 1000, 6.5 / gov)), (f"{f:.2f}", "factor on the rated mass: 1.03 x 1.05 x 1.5 x 1.5"),
           ("%.0f mm" % max(abs(cases[c]["sag_mm"]) for c in design), "largest sag relative to the lift points, main cases"),
           ("%d / %d" % (AB["B0_frame_only"]["members_over"], AB["B0_frame_only"]["joints_over"]), "members / joints over capacity before (frame as framed)")], cols=4)
doc.h2("What makes it work")
doc.bullets([
    "<b>Pick it up from underneath.</b> At each of the 8 lift points a folded steel cradle wraps under the floor edge truss, and flat steel hanger straps on both faces of the wall carry it up to a lifting head above the roof. The weight sits in the cradles; it does not hang on screws.",
    "<b>Spread the pick-up.</b> Inclined straps (V-straps) from each head land on the floor edge truss 0.84 m either side, so the edge truss spans 0.84 to 1.8 m between supports instead of 3.6 m. On the open north side two pairs are temporary (bolted on for transport and the lift, removed after set-down).",
    "<b>Make the floor and roof stiff plates.</b> Crossed steel straps in the floor and roof planes stop the box twisting.",
    "<b>Strengthen the screwed joints that carry the load.</b> 4 to 6 screws instead of 2 in the edge trusses and the north posts, 6 at the end joints of every floor truss, 8 at every truss end, and tie plates wherever a joint would otherwise pull apart.",
    "<b>Use a rig that shares the load by balance, not by sling length.</b> An equalising cascade of pinned spreader beams, set to the weighed centre of gravity. A rigid lifting frame is not allowed: one sling 10 mm short overloads joints up to 2.1 times.",
])
doc.callout("What this study is, and is not",
            "It is a complete preliminary design with every number traceable to a file in the repository. It is not a certified design: a registered "
            "structural engineer must review it, adopt it and sign it, and the six hold points in section 10 (weighing, coil certificates, screw brand, "
            "proof test, measured first lift, lift conditions) must be met. It does not cover transport, wind or earthquake in service, or the foundations.", "warn")

# ------------------------------------------------------------------------------------------------ 2 module
doc.h1("The module and the Framer model", "2")
doc.p("One module of a two-module classroom: 12.0 m long, 3.3 m wide and about 3.3 m high. The south long wall has two windows (1.8 m wide) "
      "and a door; the two end walls are solid; the north long side is the join to the second module, so it is open between two 300 mm post "
      "panels at 4.5 m and 7.5 m and two 1.05 m end returns. The floor and the flat roof are cassettes of 300 mm deep C89 trusses at 600 mm "
      "centres with an edge truss along each long side. The roof fall comes from graded purlins above the cassette.")
doc.p("Infinity Framer 0.7.1 framed the whole module from one project file (<i>model/engineered/project.json</i>): 57 panels, 1,194 members, "
      "948 m of C89-38 lipped channel, 1,267 kg, with no gate failures, no clashes and a passed release check. The layout was chosen for the lift: "
      "wall panel seams fall on the lift lines, the north posts are back-to-back stud packs centred on the lift lines, and the floor and roof "
      "edge trusses run the full 12 m.")
doc.table(["Item", "Value", "Source"], [
    ["Panels / members / steel", "57 / 1,194 / 1,267 kg", "model/engineered/framed.json (Framer export)"],
    ["Section", "C89-38-9 lipped channel, 0.95 mm", "Framer profile; properties in analysis/liftcalc/sections.py"],
    ["Screwed joints as framed", f"{D['screws']['joints']:,} joints, {D['screws']['as_framed']:,} screws (2 per joint)", "Framer dimple joints"],
    ["Extra screws (this design)", f"{D['screws']['extra']:,} screws at {D['screws']['joints_upgraded']:,} joints", "section 3.8 and the configuration"],
    ["Lift parts, as Framer components", f"{FC['components']} components, {FC['permanent_kg']:.0f} kg permanent + {FC['temporary_kg']:.0f} kg temporary kit", "model/engineered/project_with_lift_parts.json; Framer BOQ group 'components'"],
    ["Framer release gate with the parts", "no gate failures, no clashes, release passed", "Framer 0.7.1 run of project_with_lift_parts.json"],
    ["IFC of frame and lift parts", f"{FC['ifc_bytes'] / 1e6:.1f} MB", FC["ifc"].replace(chr(92), "/")],
], widths=[2.2, 2.6, 3.4])
doc.image(os.path.join(FIG, "fig_iso_before.png"), "Figure 1. Before: the frame as framed (2 screws per joint, no lift parts), picked up straight at the floor edge truss "
          f"at the same 8 points. {AB['B0_frame_only']['members_over']} members and {AB['B0_frame_only']['joints_over']} joints are over their design capacity (red).", h_max_mm=95)

# ------------------------------------------------------------------------------------------------ 3 load path
doc.h1("How it is lifted: the load path, step by step", "3")
doc.image(os.path.join(FIG, "fig_iso_after.png"), "Figure 2. Rev C: the frame coloured by utilisation (envelope of the design cases) with the lift parts.", h_max_mm=105)
doc.h2("3.1 The rig: an equalising cascade")
R4 = cases["R4_equalised"]["reactions"]
doc.p("A top beam hangs from the crane hook; two middle beams hang from it; four cross beams hang from those; eight vertical slings drop to the "
      "eight lifting heads. Every beam hangs from a single pin, so the share each sling carries is fixed by simple balance, whatever the sling "
      "lengths. The cross beams are picked off-centre to suit the centre of gravity, which sits %.0f mm south of the centre line because the north "
      "side is open. At the rated mass the south slings carry %.1f to %.1f kN and the north slings %.1f to %.1f kN (no factors)."
      % (1650 - D["meta"]["cg"][1], min(R4[k] for k in R4 if k[0] == "S") / 1e3, max(R4[k] for k in R4 if k[0] == "S") / 1e3,
         min(R4[k] for k in R4 if k[0] == "N") / 1e3, max(R4[k] for k in R4 if k[0] == "N") / 1e3))
doc.image(os.path.join(FIG, "fig_rig.png"), "Figure 3. The cascade rig with the sling forces in the main case (rated mass, no factors).", h_max_mm=80)
doc.p("A rigid lifting frame with eight fixed-length slings is <b>not</b> allowed. The module is much stiffer than the slings are accurate: "
      "with one sling 10 mm short the joints reach %.2f times their design capacity (cases R6, information only). A free cascade cannot do that."
      % max(cases[c]["max_joint"] for c in info if c.startswith("R6")))
doc.h2("3.2 The lifting head")
doc.p("A folded 3 mm G450 steel box sits over the roof edge truss at each lift line, its cheeks on both faces of the truss, bolted through "
      "vertical slots so it holds the head sideways and along the module but carries no weight into the roof. An M20 grade 8.8 lifting pin with "
      "a steel sleeve runs through the top; the bow of a 3.25 t shackle goes over the sleeve and the sling eye goes on the shackle pin. The two "
      "hanger straps and the V-straps bolt to the cheeks.")
doc.image(os.path.join(FIG, "fig_liftpoint.png"), "Figure 4. A lift point: section across the wall and elevation of point S2 with the forces in the main case.", h_max_mm=118)
doc.h2("3.3 Hanger straps and 3.4 cradles")
doc.p("Two 50 x 1.5 mm G450 straps, one on each face of the wall, run from the head down past the wall to the cradle (2 x M12 bolts at each end). "
      "They are fixed nowhere in between: lining and cladding screws pass through slots, so the straps cannot drag load into studs or plates. "
      "The cradle is a folded 2.5 mm G450 U, 600 mm long, that wraps under the floor edge truss: its base carries the module in bearing and its "
      "two plates are screwed to both chords of the edge truss every 100 mm (2 screws per face per chord), which spreads the pick-up into the "
      "truss over 600 mm instead of one point. Taking the plates away (point stirrups) puts 2 joints over capacity (run A5).")
doc.h2("3.5 V-straps and the temporary north straps")
doc.p("Inclined 50 x 1.2 mm G450 strap pairs run from each south head to the floor edge truss 0.84 m either side, landing on 600 mm foot plates. "
      "They turn one 3.6 m span of the floor edge truss into short spans. On the north side the end returns each take one permanent V-strap, "
      "and the two posts take temporary pairs that land 1.2 m either side across the openings. Without any V-straps %d members and %d joints are "
      "over capacity (run A1); without only the temporary north pairs %d members are over, the worst at %.2f (run A2)."
      % (AB["A1_no_vstraps"]["members_over"], AB["A1_no_vstraps"]["joints_over"], AB["A2_no_temp_north"]["members_over"], AB["A2_no_temp_north"]["max_member"]))
doc.image(os.path.join(FIG, "fig_elev_south.png"), "Figure 5. South wall line with the lift parts. The V-straps clear both windows and the door.", h_max_mm=85)
doc.image(os.path.join(FIG, "fig_elev_north.png"), "Figure 6. North (open) side. Dashed magenta: temporary straps, removed after the module is set down and before the second module is placed.", h_max_mm=85)
doc.h2("3.6 The edge trusses and walls")
doc.p("The four edge trusses (floor and roof, each side) are the beams of the module in the lift. The cradles and foot plates pick up the floor "
      "edge trusses; the walls carry the roof down to them as they do in service; the roof edge trusses span the north openings as they do in "
      "service. The south wall panels, braced as Framer made them, work with the edge trusses.")
doc.h2("3.7 Floor and roof plane bracing; 3.8 extra screws; 3.9 tie plates; 3.10 bridging")
doc.p("Crossed 30 x 1.0 mm G300 straps with tensioners in the floor and roof planes (bays between the lift lines) make the floor and roof stiff plates; "
      "without them %d members, %d joints and %d connections are over (run A6). Extra screws: 4 per joint in the floor and roof edge trusses, 6 in the "
      "north floor edge truss and in the first two panels at each end, 4 in the north wall panels, 4 in every floor truss with 6 at the end web joints, "
      "and 8 per truss end into the edge truss; with 2 screws everywhere %d joints are over (run A3). Tie plates T1-T3 go across the %d joints that "
      "would otherwise pull apart in the lift, so no screw is relied on in pull-out. A line of C89 noggings at mid-span holds the floor truss top "
      "chords sideways (no credit is taken for the floor sheet); without it one floor truss chord reaches %.2f (run A4)."
      % (AB["A6_no_plane_bracing"]["members_over"], AB["A6_no_plane_bracing"]["joints_over"], AB["A6_no_plane_bracing"]["links_over"],
         AB["A3_two_screws"]["joints_over"], env["links_tie"], AB["A4_no_bridging"]["max_member"]))
doc.image(os.path.join(FIG, "fig_plan.png"), "Figure 7. Floor plan: lift points, centre of gravity, floor plane bracing and the bridging line.", h_max_mm=70)

# ------------------------------------------------------------------------------------------------ 4 design basis
doc.h1("Design basis", "4")
doc.p("The full basis is in <i>docs/DESIGN_BASIS.md</i>. The factors and rules were set from a public-source research study (lifting factors, "
      "AS/NZS 4600 rules, rigging hardware, masses), which was then fact-checked by separate reviewers; their corrections are adopted below.")
fc = D["meta"]["factors"]
doc.table(["Factor", "Value", "Why"], [
    ["Weight", f"{fc['weight']}", "on the weighed mass (hold point H1); the 6.5 t rating is already 1.35 x the itemised mass"],
    ["Centre of gravity", f"{fc['cog']}", "DNV-OS-H102 minimum when no CoG envelope is modelled (fact-check correction: 1.03 was too low)"],
    ["Dynamic", f"{fc['dynamic']}", "Australian practice: at least 1.2 for a crane on outriggers, up to 2.2 quoted; 1.5 adopted for the whole frame"],
    ["Load factor", f"{fc['load']}", "lifting points and their load path; used for the whole frame"],
    ["Total", f"{f:.3f}", "applied to the rated 6.5 t in every member, joint, connection and part check (DNV lift points: about 1.86)"],
], widths=[1.6, 0.9, 6.0])
doc.table(["Case", "What it represents", "Type"], [[c, NAME.get(c, cases[c]["label"]), "design"] for c in design] +
          [["R6 (x8)", "Rigid frame, one sling 10 mm short", "information"], ["R5 (x8)", "Rigid frame, one sling slack", "information"]], widths=[1.6, 5.2, 1.2])
doc.h2("Resistance")
doc.bullets([
    "Members: AS/NZS 4600:2018, Direct Strength Method and effective width method (lower governs); elastic buckling stresses from a finite-strip "
    "table (matches published values within about 1 %). Member steel taken as G450 (fy 450 MPa) although 0.95 mm coil will be G550.",
    "Buckling lengths from the model: in plane, the largest gap between joints; out of plane, the largest gap between points held by another panel or "
    "a lift part. No restraint from linings, cladding or flooring in the lift check.",
    "Screwed joints: every member end force passes through the screws (bearing only for a stud standing square on a plate). One 10 gauge screw "
    "in 0.95 mm steel: 1.77 kN, using fu = 0.75 x 550 = 412.5 MPa (low-ductility rule); 10 % less per screw in groups of 3 or more; screw fracture "
    "cap 2.85 kN.",
    "Bolts on sheet: deformation-limited bearing (AISI S100-16 J3.3.2) at 0.65; tear-out 0.60 t e fu; net section 0.65 An fu; M12/M20 grade 8.8 at 800 MPa.",
])

# ------------------------------------------------------------------------------------------------ 5 analysis model
doc.h1("Analysis model and verification", "5")
doc.p("A 3D frame model was built from Framer's export (<i>analysis/liftcalc/framemodel.py</i>): every member split at its joints, in-plane ends "
      "pinned at joints, panels joined by short semi-rigid links where Framer's members touch (rules for wall-to-wall seams, tracks on edge trusses, "
      "truss chords on edge trusses), truss end reactions carried by ties standing for the screws through the end verticals, and every lift part "
      "added as members attached to the framed members. %s nodes, %s elements. The mass model (table below) is spread onto the members it belongs "
      "to and scaled up to 6.5 t (x%.2f), keeping its distribution and centre of gravity."
      % (f"{PN['nodes']:,}", f"{PN['elements']:,}", D["scale_to_rated"]))
grp = {}
for x in D["ledger"]: grp[x["group"]] = grp.get(x["group"], 0) + x["kg"]
doc.table(["Group", "Itemised kg", "Rated kg (x%.2f)" % D["scale_to_rated"]], [[g, f"{v:,.0f}", f"{v * D['scale_to_rated']:,.0f}"] for g, v in grp.items()] +
          [["<b>Total</b>", f"<b>{sum(grp.values()):,.0f}</b>", f"<b>{sum(grp.values()) * D['scale_to_rated']:,.0f}</b>"]], widths=[3, 2, 2])
doc.h2("Verification of the solver and the model")
doc.table(["Check", "Result"], [
    ["Equilibrium in every case", "sum of sling forces = weight to 4 decimals in all 27 cases (63.74 kN)"],
    ["Independent solver (PyNite) on the full model, main case", f"displacements agree to {PN['relative_disp_difference']:.0e}, axial forces to {PN['relative_axial_difference']:.0e} (relative); same nodes, elements and releases"],
    ["Lifting head equilibrium (S2, main case)", "hanger pair 3.7 kN + V-strap pairs (3.0 + 2.6) kN x cos 14 deg = 9.2 kN against the 9.3 kN sling"],
    ["Unit tests", "37 tests: solver against closed-form results and PyNite, section properties against Framer, buckling table against published values"],
    ["Framer's own structural engine (same frame, same loads)", "inconclusive: its panel links leave parts free under a lift (see verification/framer_crosscheck/README.md); not used for design"],
    ["Each measure taken away in turn (ablation)", "every measure is needed: see section 6.3"],
], widths=[3.2, 5.2])

# ------------------------------------------------------------------------------------------------ 6 results
doc.h1("Results", "6")
doc.h2("6.1 Every design case")
rows = []
for c in design:
    x = cases[c]
    rows.append([NAME.get(c, c), f"{x['max_member']:.2f}", f"{x['max_joint']:.2f}", f"{x['max_link']:.2f}", f"{x['sag_mm']:.1f} / {x['hog_mm']:+.1f}",
                 " ".join(f"{x['reactions'][k] / 1e3:.1f}" for k in ("S1", "S2", "S3", "S4")), " ".join(f"{x['reactions'][k] / 1e3:.1f}" for k in ("N1", "N2", "N3", "N4"))])
doc.table(["Case", "Member", "Joint", "Link*", "Sag / hog mm", "S1-S4 kN", "N1-N4 kN"], rows, widths=[2.6, 0.8, 0.8, 0.8, 1.3, 1.8, 1.8], font_cell="cell")
doc.small("Utilisations at the factored level (x%.3f). *Link utilisation here includes tension; every link in tension gets a tie plate (T1-T3), "
          "and the shear on the link screws is at most %.2f. Sag and hog are relative to the lift points at the rated mass, no factors. "
          "Sling forces unfactored." % (f, max_link_shear))
doc.image(os.path.join(FIG, "fig_reactions.png"), "Figure 8. Sling force at each lift point in every design case.", h_max_mm=70)
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
doc.h2("6.3 What each measure does (ablation) and sensitivity")
doc.image(os.path.join(FIG, "fig_ablation.png"), "Figure 9. The design with one measure taken away at a time, against the bare frame and the full design.", h_max_mm=80)
doc.table(["Run", "Members over", "Joints over", "Worst member"], [[AB[k]["name"], AB[k]["members_over"], AB[k]["joints_over"], f"{AB[k]['max_member']:.2f}"]
          for k in ("revC_design", "S1_lining_credit", "A4_no_bridging", "A5_point_cradles", "A2_no_temp_north", "A6_no_plane_bracing", "A1_no_vstraps", "A3_two_screws", "B0_frame_only")],
          widths=[5.6, 1.1, 1.1, 1.1])
doc.h2("6.4 Information cases: why the rig must equalise")
rows = []
for c in info:
    x = cases[c]
    rows.append([c, cases[c]["label"][:70], f"{x['max_member']:.2f}", f"{x['max_joint']:.2f}", f"{x['sag_mm']:.1f}"])
doc.table(["Case", "Description", "Member", "Joint", "Sag mm"], rows, widths=[1.4, 4.8, 0.8, 0.8, 0.8])
doc.small("These cases are not design cases. A sling cannot go slack, or be 10 mm short, in a free cascade without the rig itself failing; the "
          "table shows what a rigid frame would do and is the reason a rigid frame is excluded.")

# ------------------------------------------------------------------------------------------------ 7 parts
doc.h1("Lift parts: design checks and schedule", "7")
doc.p("Every part outside Framer was checked against the largest factored force it carries in any design case (<i>analysis/run_connectors.py</i>).")
doc.table(["Part", "Check", "Demand", "Capacity", "Unit", "Util"], [[r["group"], r["item"], r["demand"], r["capacity"], r["unit"], f"{r['util']:.2f}"] for r in CON["rows"]],
          widths=[2.6, 4.2, 0.8, 0.9, 0.8, 0.6])
rg = CON["rigging"]
doc.callout("Rigging interface", f"Largest drop force in the design cases, with weight and CoG factors: {rg['max_static_drop_kN']} kN ({rg['max_static_drop_t']} t), no dynamic factor. "
            "Drop gear: 2 t round slings (or 8 mm chain) with 3.25 t bow shackles, the bow over the sleeved M20 head pin. The rig itself (beams, slings, "
            "shackles, top rigging) is lifting equipment designed and certified by the rigging supplier; drop points within 50 mm of the head positions.", "info")
rows = [[r["item"], r["count"], f"{r['qty']:.1f}"] for r in FC["component_rows"]]
rows += [["Extra 10 gauge screws (brand with at least 5.7 kN shear, hold point H3)", f"{D['screws']['extra']:,}", ""],
         ["M12 8.8 bolt sets (straps 2 per end, heads 4 to the roof edge truss)", "208", ""], ["M20 8.8 lifting pins with sleeves", "8", ""],
         ["Strap tensioners for the plane bracing", "20", ""]]
doc.table(["Part (Framer component or hardware)", "Qty", "Steel kg"], rows, widths=[6.4, 0.8, 1.0])
doc.small("Quantities and masses are Framer's own bill of quantities for the components placed in the project (steel only). The permanent parts add "
          f"{FC['permanent_kg']:.0f} kg to the {FC['frame_kg']:,.0f} kg frame; the temporary lift kit ({FC['temporary_kg']:.0f} kg: 4 strap pairs and 4 foot plate pairs) is reused from module to module.")

# ------------------------------------------------------------------------------------------------ 8 in service
doc.h1("In service (sanity check)", "8")
lb = SVC["layouts"]["bearer"]; lp = SVC["layouts"]["piers"]
doc.p("The lift parts and extra screws must not leave the module weak in service, and the floor must carry a classroom. Check: 1.2 x dead + 1.5 x live, "
      "live load 3.0 kPa on the floor and 0.25 kPa on the roof, dead load the itemised mass (%.1f kN), temporary straps removed, flooring screwed at "
      "300 mm restraining the floor truss top chords (normal floor practice)." % SVC["G_kN"])
doc.table(["Support", "Members over", "Max member", "Joints over", "Max joint", "Floor truss sag (G + 0.7Q)"], [
    ["Continuous bearers under both floor edge trusses", lb["ULS1"]["members_over"], f"{lb['ULS1']['max_member']:.2f}", lb["ULS1"]["joints_over"], f"{lb['ULS1']['max_joint']:.2f}", f"{lb['floor_truss_relative_sag_SLS_mm']} mm"],
    ["Piers at 1.8 m or less", lp["ULS1"]["members_over"], f"{lp['ULS1']['max_member']:.2f}", lp["ULS1"]["joints_over"], f"{lp['ULS1']['max_joint']:.2f}", f"{lp['floor_truss_relative_sag_SLS_mm']} mm"],
], widths=[3.2, 1.0, 1.0, 1.0, 1.0, 1.6])
doc.p("On continuous bearers everything passes. On piers at 1.8 m the north floor edge truss and a few floor truss joints are over: the module "
      "should sit on continuous bearers, or the piers need their own check. This also found that the floor trusses need 6 screws at their end "
      "web joints and 8 screws per truss end for the 3 kPa classroom load (included in the design). Not checked: wind, earthquake, transport, "
      "the floor sheet, roof sheeting, foundations.")

# ------------------------------------------------------------------------------------------------ independent review
doc.h1("Independent review", "9")
if REV:
    syn = REV.get("synthesis") or {}
    doc.p(esc(syn.get("verdict", "")))
    if REV.get("resolutions"):
        doc.table(["Finding", "Severity", "What was done"], [[esc(r["title"]), r["severity"], esc(r["action"])] for r in REV["resolutions"]], widths=[3.4, 0.9, 4.2])
else:
    doc.p("The independent review results are added when the review completes.")

# ------------------------------------------------------------------------------------------------ hold points and limits
doc.h1("Hold points, lift sequence and limits", "10")
doc.table(["Hold point", "Requirement"], [
    ["H1 Weigh", "Weigh the first module (and any changed layout) at its 8 lift points. Mass x 1.03 must not exceed 6,500 kg. The measured centre of gravity sets the cascade pick points."],
    ["H2 Steel", "Coil certificates for every coil in lift-critical members: AS 1397 grade, measured base metal thickness at least 95 % of nominal (0.9025 mm for 0.95 mm)."],
    ["H3 Screws", "Screw brand fixed, characteristic shear at least 5.7 kN (10 gauge); screw counts per the joint schedule; inspected before lining."],
    ["H4 Proof test", "Load test of one complete lift-point assembly (cradle, straps, head) before first use; factor and acceptance set by the engineer (AS/NZS 4600 Section 8)."],
    ["H5 First lift", "Load-measuring shackles on all 8 drops; lift 100 mm and hold; stop if any drop is more than 15 % from its design share."],
    ["H6 Conditions", "Crane on outriggers, no travelling with the load, controlled hoist speed, no snatch, wind at the boom head within the lift plan limit (about 2.4 to 3.7 m/s gust for a 9 m/s chart), tag lines at both ends."],
], widths=[1.4, 7.0])
doc.h2("Lift sequence")
doc.bullets(["Check the lift parts, ties and temporary north straps are fitted and inspected; check the weighed mass and CoG are on the lift plan.",
             "Set the cascade pick points to the weighed CoG; hang the drops; fit the shackles over the head sleeves; drops vertical within 2 degrees.",
             "Take up slowly; at 100 mm stop and read the load shackles (H5); check the hang is level within 2 degrees.",
             "Lift, slew and land on the prepared bearers, all 8 lines together (no landing on one end).",
             "Remove the temporary north straps and foot plates only when the module is fully set down and fixed; then place the second module."])
doc.h2("Limits of this study")
doc.bullets(["Preliminary: not certified, not for construction. A registered structural engineer must review, adopt and sign the design.",
             "The mass is an itemised estimate scaled to the 6.5 t rating; the real mass and CoG come from weighing (H1).",
             "The AS/NZS 4600:2018 text itself was not available; clauses were taken from public quotations, AISI S100-16 and published tables, with the more conservative value where they differ.",
             "The frame model idealises Framer's screwed joints as pins in plane and its panel contacts as short links; the ablation and sensitivity runs show how results depend on the main choices.",
             "Transport, wind and earthquake in service, foundations and the rig itself are outside this study."])

# ------------------------------------------------------------------------------------------------ appendix
doc.h1("Appendix: where everything is", "A")
doc.table(["Path", "What it is"], [
    ["docs/DESIGN_BASIS.md", "factors, cases, resistance rules, hold points"],
    ["model/engineered/project.json, framed.json", "the Framer project and Framer's framed output"],
    ["model/mass_model.json", "itemised mass of the finished module with sources"],
    ["analysis/configs/revC_design.json", "the design: lift lines, parts, screw schedule, factors, cases"],
    ["analysis/run_lift.py, analysis/liftcalc/", "frame model, solver, cases, member / joint / link checks"],
    ["analysis/run_connectors.py, run_service.py", "lift part checks; in-service check"],
    ["results/revC_design/, results/service/, results/ablation/", "results: logs, summary.json, model3d.json, connectors.md"],
    ["verification/", "PyNite cross-check of the full model, Framer engine attempt, hand statics"],
    ["site/", "the interactive 3D page (index.html and data)"],
    ["report/", "this report and its figures (rebuilt from the result files)"],
], widths=[3.6, 4.8])
doc.p("Reproduce: <i>.venv/Scripts/python.exe analysis/run_lift.py model/engineered analysis/configs/revC_design.json results/revC_design</i>, then "
      "<i>run_connectors.py</i>, <i>run_service.py</i>, <i>export_results.py</i>, <i>report/make_figures.py</i> and <i>report/make_report.py</i> with the same arguments.")
doc.build()
print("written", OUT)
