# Crane-liftable light-gauge-steel classroom module: engineering study (Rev D.1)

**Status: complete preliminary design. Not certified. Not for construction or lifting.**
It needs review, adoption and sign-off by a registered structural engineer, a rigging design by a competent person,
and the hold points in [docs/DESIGN_BASIS.md](docs/DESIGN_BASIS.md) (weighing and CoG, coil certificates, screws, load tests,
measured first lift, lift conditions, certified rig, landing, fit-up) before any lift.

**Interactive 3D page:** https://reidsimon4-jpg.github.io/lgs-module-crane-lift/site/  
**Engineering report (PDF):** [report/LGS module lift engineering - Rev D.1 (preliminary).pdf](report/LGS%20module%20lift%20engineering%20-%20Rev%20D.1%20(preliminary).pdf)

A 12.0 m x 3.3 m single-storey classroom module, framed only in light-gauge cold-formed steel (C89-38 lipped channel,
screwed), is engineered to be lifted by crane as a finished unit at a rated mass of 6.5 t. Every number in the report and
the 3D page comes from a file here and can be re-run.

## Result in one paragraph
Picked up straight at 8 points, the frame as framed has 23 members and 334 screwed joints over their design capacity.
With the lift system below, every member is at most 0.90, every joint at most 0.87, every panel connection at most 0.60
(shear) and every lift part at most 0.82 of its design capacity, in 57 design cases: rig cases; the module hanging 2 degrees
out of level in 8 directions; the drops 2 degrees off vertical (squeeze and spread, across and along); every tilt with every
lean; two twist cases (cross beams set 25 mm off in opposite senses); and the centre of gravity at the four corners of its
hold-point envelope (150 mm along, 90 mm across), level and tilted. The combined factor on the rated mass is 2.433 (weight
1.03 x centre of gravity 1.05 x dynamic 1.5 x load 1.5; 2.317 in the centre-of-gravity cases, where the shift is modelled),
steel is taken as G450 and screw strength in the frame steel at 75 % (412.5 MPa). Lip notches are checked as the lipless
section. In service (3 kPa classroom floor) on a packer under every floor-truss end: members 0.92, joints 0.90.

## What changed in Rev D.1
A second independent review (of Rev D, four AI reviewers and a synthesis) found 4 blocking and 16 should-fix items.
Rev D.1 answers all of them; each finding and what was done is in `results/review/review_revD.json` and section 9 of the report.
The main changes: gussets are credited only where a plate is drawn, and the cradles fit over them; a new lip-notch check
(lipless section for axial load, both bending axes and tension, `analysis/liftcalc/notch.py`) with a load test of a notched
joint (hold point H4); hanger straps 50 x 2.5 mm checked at a 65 / 35 split; a closed-box lifting head with an open top;
explicit lean, tilt-plus-lean, twist and centre-of-gravity envelope cases (15 design cases became 57); a stop at 4 % of each
drop's share in the measured first lift (H5); and a landing rule of a packer under every floor-truss end (H8).

## The lift system (Rev D.1)
* **8 identical lift points** on the edge-truss joint pairs (x = 0.93, 4.46, 7.54, 11.07 m, both sides): a **closed-box lifting
  head** over the roof edge truss (two 3 mm cheeks and two end plates, open top for the sling eye, M20 pin with a sleeve, no
  fasteners, carries no weight into the roof, stop block along the module), a **hanger strap pair** (2 x 50 x 2.5 mm G450,
  one strap on each face, match-drilled, no fixings through it) straight down to a **cradle** under the floor edge truss.
* **Cradle at a truss joint pair**: two 3 mm cheeks (120 x 200) fitted over the joint gusset plates, joined under the chord by
  two M16 bearing bolts with sleeves and packers, one under each joint, so the lift pushes straight up into the truss
  diagonals and the thin chord does not bend. Screwed at the first joint only; the strap bolts sit below the bearing bolts.
* **1.15 mm** floor edge trusses and north roof edge truss (everything else 0.95 mm as framed).
* **Joints**: 4 screws instead of 2 at truss and wall joints; 235 gussets sized joint by joint (51 for the lift and
  184 floor gussets for the classroom load in service, 8 of them at notched chords); full-depth folded cleats at every truss end; 119 tie
  plates at the wall joints; **floor and roof plane strap bracing**; **bridging lines**. Nothing is temporary.
* **Rig**: an equalising pinned-beam cascade, each cross beam set to its own line's weighed split. A rigid lifting frame is
  excluded.

## Where things are
| Path | Contents |
|---|---|
| [docs/DESIGN_BASIS.md](docs/DESIGN_BASIS.md) | Factors, cases, resistance rules, hold points |
| [report/](report/) | The engineering report (PDF) and the scripts that build it and its figures |
| [site/](site/) | The interactive 3D page (`index.html`, data in `site/data/`) |
| `model/engineered/` | Infinity Framer project (`project.json`), Framer's framed output (`framed.json`), the project with the lift parts as Framer components (`project_with_lift_parts.json`) and its IFC |
| `model/mass_model.json` | Itemised mass of the finished module, with sources |
| `analysis/configs/revD_final.json` | The design: lift lines, parts, screw schedule, gussets, gauges, factors, cases |
| `analysis/run_lift.py`, `analysis/liftcalc/` | Frame model, 3D solver, lift cases, member / joint / link checks, lip-notch check (`notch.py`) |
| `analysis/run_connectors.py`, `run_service.py` | Lift-part checks; in-service check (3 kPa classroom floor) |
| `analysis/size_joints.py`, `run_ablation.py` | Gusset sizing joint by joint (lift, notch and in-service passes); each lift measure removed in turn, and sensitivities |
| `results/revD_final/`, `revD_connectors/`, `revD_service/`, `ablation_revD/`, `joint_schedule.json` | Logs and results |
| `results/review/` | Independent AI reviews (of Rev C and of Rev D) and how each finding was answered |
| `tools/add_lift_components.py` | Puts the lift parts into the Framer project and runs Framer's clash and release checks |
| `tools/write_review_revD.py` | Writes the answers to the Rev D review from the result files |
| `verification/solver_crosscheck/` | The full model re-solved by PyNite (agrees to 1e-8) |
| `verification/framer_crosscheck/` | Infinity Framer's own structural engine on the same frame (inconclusive; explained) |
| `analysis/tests/` | 45 unit tests (solver, sections, buckling table, capacities against the reviewers' hand values, lip-notch section, bolted straps) |
| `*_revC.py`, `analysis/configs/revC_*.json`, `results/revC_*` | The Rev C design, kept for the record |

## Re-running
```
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest -q analysis/tests
.venv/Scripts/python analysis/run_lift.py model/engineered analysis/configs/revD_final.json results/revD_final
.venv/Scripts/python analysis/run_connectors.py model/engineered analysis/configs/revD_final.json results/revD_connectors
.venv/Scripts/python analysis/run_service.py model/engineered analysis/configs/revD_final.json results/revD_service
.venv/Scripts/python analysis/run_ablation.py --jobs 4
.venv/Scripts/python analysis/export_results.py model/engineered analysis/configs/revD_final.json results/export_revD
.venv/Scripts/python verification/solver_crosscheck/pynite_full.py model/engineered analysis/configs/revD_final.json R4_equalised verification/solver_crosscheck/pynite_full_R4_revD.json
.venv/Scripts/python tools/write_review_revD.py
.venv/Scripts/python report/make_figures.py . report/fig
.venv/Scripts/python report/make_report.py . "report/LGS module lift engineering - Rev D.1 (preliminary).pdf"
```
`analysis/size_joints.py` re-sizes the gussets and rewrites the list in the config. Framing the project again, and
`tools/add_lift_components.py`, need Infinity Framer 0.7.1, which is not included; `framed.json` is its saved output.

## For reviewers (human or AI)
Please try to break it. The places most worth attacking: the idealisation of the screwed dimple joints (pinned in plane)
and the twist restraint they give, the panel-to-panel link rules and stiffness, the cradle model (two seats at the truss
joints) and the seat bearing formula (marked unverified until the load test), the lip-notch credit (the nested member holding
the cut flange edges), the mass estimate, and the rig assumption. `AUDIT.md` and `results/review/` list the independent reviews
already done and how each finding was resolved.

## How this was produced
The frame is framed in Infinity Framer (ILO's own framing software). The analysis code, checks and report were produced
with AI assistance under the direction of Infinity Living Options, reviewed by independent AI reviewers, and have not
been checked or certified by a registered engineer.
