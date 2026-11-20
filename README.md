# Crane-liftable light-gauge-steel classroom module: engineering study (Rev D)

**Status: complete preliminary design. Not certified. Not for construction or lifting.**
It needs review, adoption and sign-off by a registered structural engineer, a rigging design by a competent person,
and the hold points in [docs/DESIGN_BASIS.md](docs/DESIGN_BASIS.md) (weighing and CoG, coil certificates, screws, proof test,
measured first lift, lift conditions, certified rig, landing, fit-up) before any lift.

**Interactive 3D page:** https://reidsimon4-jpg.github.io/lgs-module-crane-lift/site/  
**Engineering report (PDF):** [report/LGS module lift engineering - Rev D (preliminary).pdf](report/LGS%20module%20lift%20engineering%20-%20Rev%20D%20(preliminary).pdf)

A 12.0 m x 3.3 m single-storey classroom module, framed only in light-gauge cold-formed steel (C89-38 lipped channel,
screwed), is engineered to be lifted by crane as a finished unit at a rated mass of 6.5 t. Every number in the report and
the 3D page comes from a file here and can be re-run.

## Result in one paragraph
Picked up straight at 8 points, the frame as framed has 20 members and 334 screwed joints over their design capacity.
With the lift system below, every member is at most 0.97, every joint at most 0.88, every panel connection at most 0.58
(shear) and every lift part at most 0.90 of its design capacity, in 15 design cases (rig cases, the module hanging 2 degrees
out of level in 8 directions, slings leaning 5 % sideways), with a combined factor of 2.433 on the rated mass (weight 1.03 x
centre of gravity 1.05 x dynamic 1.5 x load 1.5), steel taken as G450 and screw strength in the frame steel taken at 75 %
(412.5 MPa).

## The lift system (Rev D)
* **8 identical lift points** on the edge-truss joint pairs (x = 0.93, 4.46, 7.54, 11.07 m, both sides): a **saddle head** over
  the roof edge truss (no fasteners, carries no weight into the roof, keyed along the module), a **hanger strap pair**
  (2 x 50 x 1.5 mm, one strap on each face) straight down to a **cradle** under the floor edge truss.
* **Cradle at a truss joint pair**: two 3 mm cheeks joined under the chord by two M16 bearing bolts, one under each joint, so
  the lift pushes straight up into the truss diagonals and the thin chord does not bend. Screwed at the first joint only.
* **1.15 mm** floor edge trusses and north roof edge truss (everything else 0.95 mm as framed).
* **Joints**: 4 screws instead of 2 at truss and wall joints, 227 gussets sized joint by joint, folded cleats at every truss
  end, 205 tie plates; **floor and roof plane strap bracing**; **bridging lines**. Nothing is temporary.
* **Rig**: an equalising pinned-beam cascade set to the weighed centre of gravity. A rigid lifting frame is excluded.

## Where things are
| Path | Contents |
|---|---|
| [docs/DESIGN_BASIS.md](docs/DESIGN_BASIS.md) | Factors, cases, resistance rules, hold points |
| [report/](report/) | The engineering report (PDF) and the scripts that build it and its figures |
| [site/](site/) | The interactive 3D page (`index.html`, data in `site/data/`) |
| `model/engineered/` | Infinity Framer project (`project.json`), Framer's framed output (`framed.json`), the project with the lift parts as Framer components (`project_with_lift_parts.json`) and its IFC |
| `model/mass_model.json` | Itemised mass of the finished module, with sources |
| `analysis/configs/revD_final.json` | The design: lift lines, parts, screw schedule, gussets, gauges, factors, cases |
| `analysis/run_lift.py`, `analysis/liftcalc/` | Frame model, 3D solver, lift cases, member / joint / link checks |
| `analysis/run_connectors.py`, `run_service.py` | Lift-part checks; in-service check (3 kPa classroom floor) |
| `analysis/size_joints.py`, `run_ablation.py` | Gusset sizing joint by joint; each lift measure removed in turn |
| `results/revD_final/`, `revD_connectors/`, `revD_service/`, `ablation_revD/`, `joint_schedule.json` | Logs and results |
| `results/review/` | Independent AI reviews (Rev C, Rev D) and how each finding was answered |
| `tools/add_lift_components.py` | Puts the lift parts into the Framer project and runs Framer's clash and release checks |
| `verification/solver_crosscheck/` | The full model re-solved by PyNite (agrees to 1e-8) |
| `verification/framer_crosscheck/` | Infinity Framer's own structural engine on the same frame (inconclusive; explained) |
| `analysis/tests/` | 42 unit tests (solver, sections, buckling table, capacities against the reviewers' hand values) |
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
.venv/Scripts/python report/make_figures.py . report/fig
.venv/Scripts/python report/make_report.py . "report/LGS module lift engineering - Rev D (preliminary).pdf"
```
`analysis/size_joints.py` re-sizes the gussets and rewrites the list in the config. Framing the project again, and
`tools/add_lift_components.py`, need Infinity Framer 0.7.1, which is not included; `framed.json` is its saved output.

## For reviewers (human or AI)
Please try to break it. The places most worth attacking: the idealisation of the screwed dimple joints (pinned in plane)
and the twist restraint they give, the panel-to-panel link rules and stiffness, the cradle model (two seats at the truss
joints), the lip-notch section check, the mass estimate, and the rig assumption. `AUDIT.md` and `results/review/` list the
independent reviews already done and how each finding was resolved.

## How this was produced
The frame is framed in Infinity Framer (ILO's own framing software). The analysis code, checks and report were produced
with AI assistance under the direction of Infinity Living Options, reviewed by independent AI reviewers, and have not
been checked or certified by a registered engineer.
