# Audit trail

What has been checked, by what means, and what is still open. Newest first.

## Independent review of Rev D (four AI reviewers, one lens each, then a synthesis)
Lenses: frame model and load path; capacity checks and connectors; load cases, rigging and in-service; buildability and the
Framer model. Each reviewer was told to try to break the design, could re-run the code in its own scratch folder, and could
not edit the repository. Reviewed commit: f4d20e3 (the A-frame variant of Rev D); the final Rev D (hangers at all 8 lift points)
changed only the south lift points. Findings and how each was answered: `results/review/review_revD.json` (added when the review
completes) and section 9 of the report.

## Independent review of Rev C (five AI reviewers, then a synthesis)
Lenses: frame modelling and load path; capacity code; load cases, factors and rigging; buildability of the added parts;
independent re-computation by hand. Verdict on Rev C: "not yet" - 7 blocking and 16 should-fix findings. Rev D answers all of
them (21 resolved, 1 partly, 1 open): `results/review/review.json` (finding, severity, status, what Rev D does). The reviewers'
own reports are in `results/review/reviews.json` and `synthesis.json`.

## Checks of the solver and the model (Rev D)
| Check | Result | Where |
|---|---|---|
| Full Rev D model re-solved by PyNite (an independent open-source solver), main case | displacements agree to 5e-8, axial forces to 1e-8 (relative), strap forces identical, on 3,205 nodes / 4,935 elements | `verification/solver_crosscheck/pynite_full_R4_revD.json` |
| Equilibrium | sum of sling forces equals the weight in all 35 cases (15 design, 20 information) | `results/revD_final/summary.json` |
| Unit tests | 42 pass: solver vs closed form and PyNite, sections vs Framer values, buckling table vs published values, capacities vs the Rev C reviewers' hand values (phi Nc 29.23 kN, phi My 0.363 kNm, screw 1.77 kN, M12 bearing 10.13 / 5.21 kN), lip-notch, shear, cradle seat bearing | `analysis/tests/` |
| Finite-strip buckling table | local and distortional stresses within about 1 % of published values | `analysis/liftcalc/data/c89_buckling.json` |
| Each lift measure removed in turn | every measure is needed (A1-A7), the bare frame fails (B0: 20 members, 334 joints over), linings add nothing that governs (S1), twist restraint at the joints is essential (S2: 9 members over) | `results/ablation_revD/`, `site/data/ablation.json` |
| Gussets sized joint by joint | 227 joints with a 4-screw utilisation above 0.90 in any design case (55) or in service on bearers (172) | `analysis/size_joints.py`, `results/joint_schedule.json` |
| In-service check, 3 kPa classroom floor | passes on continuous bearers (members 0.95, joints 0.89); piers at 1.8 m do not pass | `results/revD_service/service.json` |
| Framer clash and release checks with the lift parts as components | 0 clashes, release check passed, 600 components, 223.5 kg (the three 1.15 mm edge trusses re-gauged after framing and Framer's tooling rules re-run on them) | `results/framer_components/summary.json` |
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
  more conservative value.
* The mass is an itemised estimate scaled to the 6.5 t rating; weighing with a CoG limit (hold point H1) is required.
* Joint and link idealisation (pinned in plane at dimple joints; short semi-rigid links between panels); twist restraint
  credited at every screwed joint (hold point H3).
* A full elastic buckling (geometric stiffness) analysis of the whole model was not run (Rev C review, should-fix 11).
* Framer 0.7.1 has no per-element gauge: the three 1.15 mm edge trusses are set after framing (factory: roll them from 1.15 mm coil).
* Transport, wind and earthquake in service, the module-to-module connection, foundations and the rig are outside the study.
