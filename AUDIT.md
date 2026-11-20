# Audit trail

What has been checked, by what means, and what is still open. Newest first.

## Rev D.1: the answers to the review of Rev D
Every blocking and should-fix finding of the Rev D review is answered in `results/review/review_revD.json` (finding, severity,
what Rev D.1 does, with the numbers read from the result files by `tools/write_review_revD.py`) and in section 9 of the report.
One more finding came out of the re-run itself: the in-service check had not been given the list of gusseted joints, so every
notched floor-truss joint was checked as bare steel (up to 1.11 on the packers). Fixed (`run_lift.set_notch_rules` is now
used by both runs); the gusset sizing now also has an in-service lip-notch pass, which added 8 floor gussets.

## Independent review of Rev D (four AI reviewers, one lens each, then a synthesis)
Lenses: frame model and load path; capacity checks and connectors; load cases, rigging and in-service; buildability and the
Framer model. Each reviewer was told to try to break the design, could re-run the code in its own scratch folder, and could
not edit the repository. Reviewed commit: f4d20e3. Verdict: "not yet" - 4 blocking and 16 should-fix findings: gussets
credited inside the cradles where no plate could be fitted; the lip-notch check using the full section for bending and skipping
tension; the lifting head's sideways check assuming a closed box that was not drawn; and a first-lift stop rule that let the
lift continue at a 15 % drop imbalance. The reviewers' reports are in `results/review/reviews_revD.json` and
`synthesis_revD.json`.

## Independent review of Rev C (five AI reviewers, then a synthesis)
Lenses: frame modelling and load path; capacity code; load cases, factors and rigging; buildability of the added parts;
independent re-computation by hand. Verdict on Rev C: "not yet" - 7 blocking and 16 should-fix findings. Rev D answers all of
them (21 resolved, 1 partly, 1 open): `results/review/review.json` (finding, severity, status, what Rev D does). The reviewers'
own reports are in `results/review/reviews.json` and `synthesis.json`.

## Checks of the solver and the model (Rev D.1)
| Check | Result | Where |
|---|---|---|
| Full Rev D.1 model re-solved by PyNite (an independent open-source solver), main case | displacements agree to 3e-08, axial forces to 6e-09 (relative), on 2,993 nodes / 4,722 elements | `verification/solver_crosscheck/pynite_full_R4_revD.json` |
| Equilibrium | sum of sling forces equals the weight in all 77 cases (57 design, 20 information) | `results/revD_final/summary.json` |
| Unit tests | 45 pass: solver vs closed form and PyNite, sections vs Framer values, buckling table vs published values, capacities vs the reviewers' hand values (phi Nc 29.23 kN, phi My 0.363 kNm, screw 1.77 kN, M12 bearing 10.13 / 5.21 kN), lipless notch section (A 154.0 mm2, Iy 21,170 mm4), member shear, cradle seat bearing, bearing bolt bending, the bolted strap rule | `analysis/tests/` |
| Finite-strip buckling table | local and distortional stresses within about 1 % of published values | `analysis/liftcalc/data/c89_buckling.json` |
| Each lift measure removed in turn | the 4-screw joints, gussets, plane bracing, seats at the truss joints and the 1.15 mm edge trusses are all needed (A1, A2, A4, A5, A6, A8); the bridging line is not relied on in the lift (A3: nothing over without it) and stays as normal floor-truss practice; one inside hanger instead of the pair passes the frame checks (A7) but its strap would carry the whole drop force; the bare frame fails (B0: 23 members, 334 joints over), linings add nothing that governs (S1), twist restraint at the joints is essential (S2: 10 members over), the lip-notch credit matters (S3: 13 members over without it - hence the load test H4), links 4 x softer / stiffer and partly fixed joints (S4-S6) | `results/ablation_revD/`, `site/data/ablation.json` |
| Gussets sized joint by joint | 235 joints: 51 where 4 screws are not enough in a design lift case, 0 where a notched chord is over in a lift case, 184 for the classroom floor in service (176 screws, 8 lip notch) | `analysis/size_joints.py`, `results/joint_schedule.json` |
| In-service check, 3 kPa classroom floor | on a packer under every floor-truss end: members 0.92, joints 0.90; with 1.2 x the dead load: members 0.96, joints 0.91; on rigid bearers: members 0.93; piers at 1.8 m do not pass | `results/revD_service/service.json` |
| Framer clash and release checks with the lift parts as components | 0 clashes, release check passed, 453 components, 257.5 kg (the three 1.15 mm edge trusses re-gauged after framing and Framer's tooling rules re-run on them) | `results/framer_components/summary.json` |
| Clearance of every cradle to the truss-end cleats | at least 101.8 mm | `site/data/revD.json` (`foot_layout`) |
| Infinity Framer's own structural engine, same frame and loads | inconclusive (Rev C) - its panel links leave parts of the frame free in a lift; not used for design | `verification/framer_crosscheck/README.md` |

## Design-basis research
Public sources only (standards are paywalled): lifting factors, AS/NZS 4600 rules, rigging hardware, masses. Three of
four topics were fact-checked by separate reviewers (the AS/NZS 4600 fact-check did not run). Adopted corrections are
listed in `docs/DESIGN_BASIS.md` and the report, section 4. Values read from unofficial copies of standards are not
cited here and must be confirmed against licensed editions.

## Known limits (open)
* Not certified. A registered structural engineer must review, adopt and sign.
* The AS/NZS 4600:2018 text was not available; public quotations, AISI S100-16 and published tables were used, taking the
  more conservative value (the bolted thin-sheet net section rule and the end distance of Framer's screws need confirming).
* The mass is an itemised estimate scaled to the 6.5 t rating; weighing with a CoG limit (hold point H1) is required.
* Joint and link idealisation (pinned in plane at dimple joints; short semi-rigid links between panels); twist restraint
  credited at every screwed joint (hold point H3). Bounding runs S4-S6 bracket the link and joint stiffness.
* The lip-notch credit (the nested member holding the cut flange edges) and the cradle seat bearing formula are outside
  their test basis: both are load tested before first use (H4).
* A full elastic buckling (geometric stiffness) analysis of the whole model was not run (Rev C review, should-fix 11).
* Framer 0.7.1 has no per-element gauge: the three 1.15 mm edge trusses are set after framing (factory: roll them from 1.15 mm
  coil; a certified 1.15 mm G450 coil source is still to be found).
* Transport, wind and earthquake in service, the module-to-module connection, foundations and the rig are outside the study.
