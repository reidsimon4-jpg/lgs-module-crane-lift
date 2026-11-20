# Second opinion from Infinity Framer's own structural engine - result: inconclusive (not used for design)

`framer_lift_reactions.py` runs Framer 0.7.1's built-in 3D analysis (`framer/structural/full.py`, PyNite inside) on the same
frame (`model/engineered/project.json`), held vertically at the same 8 lift points on the floor rim bottom chords, under
exactly the project model's nodal loads for the frame-only case (`project_loads_B0.json`, 2,866 loads, 63.74 kN, mapped to
the nearest Framer analysis node). The engine is not edited (wrappers only, as in recipe 2 of the Framer capability map).

| Lift point | Project model, frame only, rigid supports (kN) | Framer engine, rigid diaphragm (kN) | Framer engine, semi-rigid diaphragm k = 1 N/mm (kN) |
|---|---|---|---|
| S1 | 9.47 | 5.07 | 8.85 |
| S2 | 9.65 | 14.52 | 6.34 |
| S3 | 8.59 | 12.62 | 7.07 |
| S4 | 9.57 | 5.09 | 5.30 |
| N1 | 7.66 | 6.53 | 3.43 |
| N2 | 5.63 | 6.58 | 1.79 |
| N3 | 5.57 | 6.55 | -0.78 |
| N4 | 7.60 | 6.77 | 7.37 |
| Sum | 63.74 | 63.72 | 39.38 (load lost) |

Why it is inconclusive:
* Framer's analysis joins panels with bearing links and stud ties written for gravity in service, with the frame resting on
  every bottom-chord node. Held only at 8 lift points, parts of its model are free to move: the largest displacement is
  2.2 x 10^7 mm with the rigid diaphragm and 4.5 x 10^10 mm with the semi-rigid one (the 1 N/mm diaphragm stiffness was a
  placeholder). The engine's own capability notes say the same: in a lift case "only the eight reactions are robust;
  everything else is dominated by how the engine links panels".
* With the rigid diaphragm the reactions balance the load, but the rigid floor and roof planes push load to the inner
  points (S2 14.5 kN against 9.7 kN in the project model). Some project loads land up to 656 mm from the node they belong to
  (members the Framer analysis does not model).
* The design does not depend on this split: the required rig is an equalising cascade, which fixes every sling force by
  statics (cases R4 and R7a-d). The rigid-frame cases (R1, R2, R6) are reported only, and a rigid lifting frame is excluded.

The solver arithmetic of the project model is checked separately and exactly against PyNite (`../solver_crosscheck`).
