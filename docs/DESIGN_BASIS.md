# Design basis - crane lift of a light-gauge-steel classroom module (Rev D.1)

PRELIMINARY - SUBJECT TO STRUCTURAL ENGINEERING. Not issued for construction. Not a statement that the module is safe to lift:
a registered engineer must review, adopt and sign the design, and the hold points below must be met.

## 1. The module
* One module of a two-module classroom: 12.0 m x 3.3 m in plan, about 3.3 m high. Framed in Infinity Framer 0.7.1
  (project `model/engineered/project.json`, frame `model/engineered/framed.json`): floor cassette of 300 mm deep C89 trusses
  (21 floor trusses: two end trusses at x 44.5 and 11955.5 and 19 between at 600 mm centres, plus the two floor edge trusses
  along the long sides), wall panels (south wall with two windows and a door, two end walls, open north side with two 300 mm
  piers at 4.5 and 7.5 m and two 1.05 m end returns), flat roof cassette like the floor. 1,194 members.
* Edge trusses are Warren trusses with 57 degree diagonals; the diagonals meet the bottom chord in joint pairs 58.6 mm apart,
  the pairs 441 mm apart. Chord orientation (Howick style): the chord web lies across the truss, the flanges are the truss faces,
  the web members nest between them, and Framer notches the lips at the panel points.
* Gauge: the two floor edge trusses (NFT1, NFT2) and the north roof edge truss (NFT25) in **1.15 mm**; every other member 0.95 mm
  as framed. Framer 0.7.1 has no per-element gauge, so the three trusses are re-gauged after framing and Framer's own tooling
  rules are run again on them (`tools/add_lift_components.py`, `framer.modelling.regenerate`). Factory: roll those three trusses
  from 1.15 mm coil, AS 1397 grade G450 or better (the checks use G450). BlueScope Indonesia lists TRUECORE G550 only up to
  1.00 mm, so the certified 1.15 mm source must be confirmed before production; at 1.00 mm the design does not pass (run A8).
* The north side is the marriage line to the second module, so it is open between the piers. The two modules meet north face to
  north face with their lift lines opposite each other.
* Rated (not-to-exceed) lift mass **6,500 kg**. The itemised finished mass is about 4,650 kg (frame + lift parts + finishes +
  fit-out, `model/mass_model.json`); the analysis scales the itemised mass up to 6,500 kg, keeping its distribution.

## 2. How it is lifted (the rig is part of the design)
* 8 identical lift points: 4 lines on the edge-truss joint-pair centres (x = 928.5, 4456.5, 7543.5, 11071.5 mm) x 2 sides.
* **Lifting head**: a closed box over the roof edge truss - two 3 mm G450 cheeks (120 x 480) on the faces of the truss, joined
  above the truss by two 3 mm end plates, open at the top. The cheeks seat on pads with 8 mm clearance over the joint screw
  heads, with running clearance and no fasteners: the head holds the module sideways, a stop block holds it along the module,
  and it cannot carry vertical load into the roof. An M20 8.8 plain-shank pin with a 40 mm free-turning sleeve crosses the box at
  z 3150; the round sling eye goes down through the open top onto the sleeve; the cheek tops carry edge protectors.
* **Hanger strap pair**: 2 x 50 x 2.5 G450, one strap on each face, 2 x M12 8.8 with washers at each end, the two straps of a pair
  match-drilled; fixed nowhere between the end bolts (no lining, batten or cladding fixing through a strap; floor sheet and
  ceiling notched round them).
* **Cradle** under the floor edge truss at the joint pair below the lift line: the joint gusset plates go on first; then two
  3 mm G450 cheeks (120 x 200) fit over them, joined under the chord by 2 x M16 8.8 bearing bolts with 92 mm sleeves, one under
  each joint, each on a 3 x 40 x 89 packer; the strap bolts sit below the bearing bolts. Cheeks screwed to the chord at the first
  joint only (2 per cheek, through the gusset); bearing only at the second. One load path per lift point: the share is fixed by
  statics. Each cradle is at least 100 mm clear of the truss-end cleats; the cradles stand 153 mm below the edge truss.
* **Equalising pinned-beam cascade** (one top beam, two middle beams, four cross beams, eight vertical drops): the drop spacing
  equals the head spacing so the drops hang within 2 degrees of vertical; each cross beam is set to its own line's measured
  south / north split within 25 mm, the middle beams at their centres and the top beam at the measured centre of gravity; beams
  free to rotate; hang at most 1.5 degrees out of level (stop). Doubled slings over hooks or sheaves are NOT allowed. A rigid
  lifting frame with eight fixed-length drops is NOT allowed (cases R6).
* Other parts: 4 screws instead of 2 at truss and wall joints; joint gussets (two 1.5 mm G450 plates flush with the chord face,
  one plate per joint or joint pair, 3 + 3 screws per face per joint) where 4 screws are not enough or a notched chord needs
  them, sized joint by joint (`analysis/size_joints.py`, list in the config and `results/joint_schedule.json`: lift, notch and
  in-service floor gussets); full-depth folded 1.5 mm cleats each side of every truss end (5 screws into the end vertical, 5 into
  the edge-truss chords: 3 bottom, 2 top); tie plates T2 (40 x 1.0 G300, 4 + 4 screws) and T3 (30 x 0.8 G300, 2 + 2) on the
  side faces wherever a wall link goes into tension; floor and roof plane bracing (crossed 30 x 1.0 G300 straps with tensioners)
  anchored on the truss top chords 205 mm in from the edge trusses at x 44.5, 1200, 4200, 7800, 10800 and 11955.5; bridging
  lines (C89 noggings, 2 screws each end) 90 mm off the truss mid-span panel point, ends tied to the plane-bracing crossings.
  Nothing is temporary; the heads, the north cradles and the marriage-face straps come off after set-down (H9).

## 3. Factors (ultimate checks)
| Factor | Value | Why |
|---|---|---|
| Weight | 1.03 | weighed mass (hold point H1); the 6.5 t rating is already about 1.4 x the itemised mass |
| Centre of gravity | 1.05 | DNV-OS-H102 minimum when no CoG envelope is modelled; 1.0 in the CoG-envelope cases, where the shift is modelled |
| Dynamic (DAF) | 1.5 | Australian practice 1.2 minimum on outriggers, up to 2.2 quoted; 1.5 adopted for the whole frame |
| Load factor | 1.5 | lifting points and their load path; used everywhere |
| **Total on the rated mass** | **2.433** | applied to every member, joint, link and added part, in every design case (2.317 in the CoG-envelope cases) |

## 4. Load cases
Design cases (all enter the envelope):
* R1 rigid rig with equal slings, R2 elastic slings, R4 equalised cascade (main case);
* T1-T8 the module hanging 2 degrees out of level (roll south / north, pitch west / east, and the four corners), solved with the
  cascade geometry (pick offsets h tan 2 deg, gravity turned with the module);
* L1-L4 drops 2 degrees off vertical (3.5 % of the larger drop force on each beam, equal and opposite on the two drops of a cross
  beam or on the two lines of a middle beam, so the rig is in balance), squeeze and spread, across and along;
* T1+L1 ... T8+L4: every tilt with every lean (32 cases);
* TW1, TW2: the cross beams set 25 mm off their own lines' split in opposite senses at the two ends (the module twists);
* CG_NE ... CG_SW and CG_NE+T ... CG_SW+T: the centre of gravity 150 mm along and 90 mm across off its design position (the H1
  limits), modelled by reweighting the mass, with the cascade set to it, level and hanging 2 degrees toward that corner
  (CoG factor 1.0, as the shift is modelled).
Information cases (reported, not design): R7a-d +-10 % sling share (a pinned cascade shares by balance), R6 one sling 10 mm short
on a rigid rig (x8), R5 one sling slack (x8; shows that a hang-up is catastrophic, so snagging at the marriage line is controlled
in the lift plan).

## 5. Resistance
* Members: AS/NZS 4600:2018 with the Direct Strength Method and the effective width method (lower governs), elastic buckling
  stresses from a finite-strip table (`analysis/liftcalc/data/c89_buckling.json`). Member steel taken as **G450** (fy 450 MPa).
* **Lip notches** (`analysis/liftcalc/notch.py`): at every element end that sits on a Framer lip notch the member is checked as
  the lipless section for axial load, both bending axes and tension, by the Direct Strength Method, with the section's elastic
  local buckling from the repository's finite strip solver at a half-wave equal to the notch length (50 mm; notches less than
  90 mm apart, as at a truss joint pair, count as one notch of about 127 mm). Design credit: the nested web member or stud lies
  against the cut flange and is screwed to it, so the flange edges are held (finite strip with the edge displacement fixed); at a
  gusseted joint the section is the lipless channel plus the two 1.5 mm plates over the flange height (first yield). Never more
  than the full section. Sensitivity S3 takes no credit at all; the notched chord joint is load tested (H4).
* The wall bottom and top tracks bear on the edge-truss chords under every stud (one link per stud), so stud loads pass straight
  into the chord without false track bending.
* Service holes: net area with a 32 mm hole. Member shear (AISI G2.1 form) and bending with shear.
* Buckling lengths from the model: in plane = largest gap between joints; out of plane = largest gap between points held by
  another panel or by an added part. **Twist (torsional) buckling length = the gap between screwed joints**: the screws pass
  through both flanges at every truss joint and wall noggin (hold point H3; sensitivity S2 shows this restraint is essential).
  **No restraint is taken from linings, cladding or flooring in the lift check** (sensitivity S1).
* Joints (Framer dimple joints, screwed): the end force of every member that ends at the joint passes through its screws.
  Bearing credit only for a stud standing square on a plate (with the stud end gap hold point). Screw capacity AS/NZS 4600
  cl 5.4.2.4 with the frame steel at **fu = 0.75 x 550 = 412.5 MPa** (low-ductility rule): 1.77 kN per 10 gauge screw in
  0.95 mm; 10 % less per screw in groups of 3 or more; screw fracture limit 2.85 kN; end rupture at every Framer screw from its
  distance to the member end (Framer's dimple screws sit 9-11 mm from the web ends, between 1.5d and 3d; the more conservative
  0.6 t (e - d/2) fu form is used; confirm the AS/NZS 4600:2018 minimum end distance). Added screws at least 15 mm from the end.
  At most 4 screws per joint (2 per side); a gusset counts as 10 screw-equivalents only where its plate is drawn.
* Links between panels: short members with both ends fixed (A 400 mm2, I 200 mm4): shear stiffness 12 EI / L^3 (about
  7 kN/mm for a 41 mm link, stiffer for shorter ones), rotational stiffness 4 EI / L (about 4 kNm/rad at 41 mm). Checked in shear
  on their screws; any link in tension gets a positive tie - no screw is relied on in pull-out. Bounding runs: links x0.25 (S4)
  and x4 (S5), and partly fixed joints (S6).
* Cradle: bearing under a joint = web crippling of the chord's two flanges under a 40 mm packer (AISI S100-16 G5 form, C-section,
  interior one-flange, unfastened, phi 0.90) - outside its test basis here, so marked unverified until the seat test (H4); M16
  bearing bolt in bending as a point load at mid-span between the cheeks (92 mm, phi fy Zp, plain shank); bolt shear, bearing
  and tear-out on the cheeks; cheek screws at the screwed seat for the along-truss force and any uplift.
* Straps: gross yield 0.90 Ag fy and the bolted thin-sheet net section (0.1 + 3d/s) An fu with phi 0.55 in single shear with
  washers (AS/NZS 4600 cl 5.3.3 form; confirm against the licensed 2018 text), checked at a 65 / 35 split between the two straps.
* Head: pin double shear and bending, pin bearing and tear-out on the cheeks, strap bolts, head bearing on the roof edge truss at
  1.6 x the guide force, and the closed box as a cantilever for the 3.5 % lean.
* Other added parts (bolts on sheet): deformation-limited bearing (AISI S100-16 J3.3.2) at phi 0.65, tear-out 0.60 t e fu
  (inner bolts: clear distance), bolt shear 0.8 x 0.62 x 800 x core area.

## 6. In service (sanity check only)
1.2 G + 1.5 Q with Q = 3.0 kPa on the floor (classroom) and 0.25 kPa on the roof; G = itemised mass (and 1.2 x itemised as a
variant); every lift part left in place. Supports: a packer under every floor-truss end on both sides (the landing and storage
rule), continuous rigid bearers (reference), and piers at 1.8 m (does not pass: piers need their own design). Flooring screwed at
300 mm restrains the floor truss top chords (normal floor design). Lip notches are checked exactly as in the lift (lipless section
with the edge credit; a gusseted joint as the plated section), at 1.0 and 1.2 x the itemised dead load. The floor-truss gussets this
check needs (where 4 screws are not enough, or where a notched chord is over without a gusset) are floor structure, needed whether
or not the module is lifted. Not checked: wind, earthquake, transport (a 0.5 g transport case is roughly 5-10 x the
2 degree roll effect and will probably govern wall racking and the support layout), point loads (1.1 kN roof, 2.7 kN floor), the
roof live load per truss by AS/NZS 1170.1 (about 1.03 kPa), link tension in service, foundations, the floor sheet, roof sheeting,
the module-to-module connection.

## 7. Hold points (the design depends on them)
* H1 Weigh the first module (and every module of a changed layout) on load cells under the 8 lift points (accuracy +-1 % of
  reading): mass x 1.03 must not exceed 6,500 kg; if the mass is more than 1.2 x the itemised estimate, re-run the in-service
  check with it. The centre of gravity from the readings must be within 90 mm across and 150 mm along of the design position
  (the modelled envelope; otherwise the engineer re-checks); it sets the cascade.
* H2 Coil certificates for every coil in lift-critical members: AS 1397 grade and measured base metal thickness at least 95 %
  of nominal (0.9025 mm for 0.95 mm, 1.0925 mm for 1.15 mm). NFT1, NFT2 and NFT25 from 1.15 mm coil, G450 minimum; gauge
  inspected before assembly.
* H3 Screw brand fixed, characteristic shear at least 5.7 kN (10 gauge); cradle cheek screws with a drill point rated for the
  full thickness (cheek + gusset + chord); screws through both flanges at every truss joint and wall noggin; joint screws,
  gussets, cleats and ties per the schedule; no fixings through the lift straps; inspected before lining.
* H4 Load tests before first use, test factor and acceptance set by the engineer from AS/NZS 4600 Section 8: one complete lift
  point (cradle on a 1.15 mm truss joint pair with its nested diagonals, including both seats; strap pair; head); and one notched
  chord joint in combined axial load and in-plane bending.
* H5 Measured first lift with load-measuring shackles on all 8 drops: lift 100 mm and hold; stop if any drop is more than 4 % from
  its design share or the module hangs more than 1.5 degrees out of level (inclinometer +-0.1 deg).
* H6 Lift conditions: crane on outriggers, no travelling with the load, controlled hoist speed, no snatch at lift-off, wind at
  the boom head within the lift plan limit, tag lines at both ends; snagging at the marriage line controlled (guides, tag lines).
* H7 Cascade beams, slings and shackles designed, certified to AS 4991, proof tested and rated by the rigging supplier; drop
  spacing equal to the head spacing (drops within 2 degrees of vertical); each cross beam set to its own line's measured split
  within 25 mm; beams free to rotate; planning hook load = 6.5 t + rigging.
* H8 Land and store only on a packer under every floor-truss end on both sides, shimmed to full bearing after set-down
  (feeler-gauge check), never on corners. The cradles stand 153 mm below the edge truss.
* H9 Stud end gap at most 1 mm within 600 mm of the lift lines. After set-down and before the second module is placed, unbolt and
  remove the 8 heads, the 4 north (marriage-side) cradles and the marriage-face hanger straps (they carry nothing in service and are
  reused). Marriage gap at least 15 mm. Gutter fitted after the heads come off.
