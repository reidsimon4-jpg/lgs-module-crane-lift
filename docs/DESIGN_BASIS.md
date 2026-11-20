# Design basis - crane lift of a light-gauge-steel classroom module (Rev D)

PRELIMINARY - SUBJECT TO STRUCTURAL ENGINEERING. Not issued for construction. Not a statement that the module is safe to lift:
a registered engineer must review, adopt and sign the design, and the hold points below must be met.

## 1. The module
* One module of a two-module classroom: 12.0 m x 3.3 m in plan, about 3.3 m high. Framed in Infinity Framer 0.7.1
  (project `model/engineered/project.json`, frame `model/engineered/framed.json`): floor cassette of 300 mm deep C89 trusses
  (21 floor trusses: two end trusses at x 44.5 and 11955.5 and 19 between at 600 mm centres, plus the two floor edge trusses
  along the long sides), wall panels (south wall with two windows and a door, two end walls, open north side with two 300 mm
  piers at 4.5 and 7.5 m and two 1.05 m end returns), flat roof cassette like the floor. 1,194 members.
* Edge trusses are Warren trusses with 57 degree diagonals; the diagonals meet the bottom chord in joint pairs 58.6 mm apart,
  the pairs 441 mm apart. Chord orientation (Howick style): the chord web lies across the truss (down for the bottom chord),
  the flanges are the truss faces, the web members nest between them, and Framer notches the lips at the panel points.
* Rev D gauge: the two floor edge trusses (NFT1, NFT2) and the north roof edge truss (NFT25) in **1.15 mm**; every other member
  0.95 mm as framed. Framer 0.7.1 has no per-element gauge, so the three trusses are re-gauged after framing and Framer's own
  tooling rules are run again on them (`tools/add_lift_components.py`, `framer.modelling.regenerate`). Factory: roll those three
  trusses from 1.15 mm coil, AS 1397 grade G450 or better (the checks use G450). BlueScope Indonesia lists TRUECORE G550 only up
  to 1.00 mm, so the certified 1.15 mm source must be confirmed before production; at 1.00 mm the design does not pass (run A8:
  3 members up to 1.19, 8 joints up to 1.05).
* The north side is the marriage line to the second module, so it is open between the piers.
* Rated (not-to-exceed) lift mass **6,500 kg**. The itemised finished mass is about 4,650 kg (frame + lift parts + finishes +
  fit-out, `model/mass_model.json`); the analysis scales the itemised mass up to 6,500 kg, keeping its distribution.

## 2. How it is lifted (the rig is part of the design)
* 8 identical lift points: 4 lines on the edge-truss joint-pair centres (x = 928.5, 4456.5, 7543.5, 11071.5 mm) x 2 sides.
* At each lift point: a **saddle head** over the roof edge truss (folded 3 mm G450 box, running clearance, no fasteners; it holds
  the module sideways, a stop block holds it along the module, and it cannot carry vertical load into the roof); an M20 8.8 pin
  with a 40 mm free-turning sleeve (the round sling eye goes straight over the sleeve); a **hanger strap pair** (2 x 50 x 1.5 G450,
  one on each face, 2 x M12 8.8 each end, fixed nowhere in between); and a **cradle** under the floor edge truss at the joint pair
  below: two 3 mm G450 cheeks (120 x 160) joined under the chord by 2 x M16 8.8 bearing bolts with 95 mm sleeves, one under each
  joint, each on a 3 x 40 x 89 packer. Cheeks screwed to the chord at the first joint only (2 per cheek); bearing only at the
  second. One load path per lift point: the share is fixed by statics, not by fit-up.
* Each cradle is at least 100 mm clear of the truss-end cleats on the inside face of the edge truss; the cradles stand 113 mm
  below the edge truss.
* **Equalising pinned-beam cascade** (one top beam, two middle beams, four cross beams, eight vertical drops), every pick
  point set to the weighed centre of gravity, hang at most 1.5 degrees out of level (stop), drops within 2 degrees of vertical.
  The share of each drop is fixed by statics (skew 1.0 for a determinate rig). Doubled slings over hooks or sheaves are NOT
  allowed. A rigid lifting frame with eight fixed-length drops is NOT allowed (cases R6).
* Other parts: 4 screws instead of 2 at truss and wall joints; joint gussets (two 1.5 mm G450 plates, 3 + 3 screws per face)
  where 4 screws are not enough, sized joint by joint (`analysis/size_joints.py`, list in the config and
  `results/joint_schedule.json`); folded 1.5 mm cleats each side of every truss end (5 + 5 screws); tie plates T2 (40 x 1.0
  G300, 4 + 4 screws) and T3 (30 x 0.8 G300, 2 + 2) wherever a link goes into tension; floor and roof plane bracing (crossed
  30 x 1.0 G300 straps with tensioners); bridging lines (C89 noggings at truss mid-span, 90 mm off the panel point, ends tied to
  the plane-bracing crossings). Nothing is temporary.

## 3. Factors (ultimate checks)
| Factor | Value | Why |
|---|---|---|
| Weight | 1.03 | weighed mass (hold point H1); the 6.5 t rating is already about 1.4 x the itemised mass |
| Centre of gravity | 1.05 | DNV-OS-H102 minimum when no CoG envelope is modelled; with the H1 CoG limits below |
| Dynamic (DAF) | 1.5 | Australian practice 1.2 minimum on outriggers, up to 2.2 quoted; 1.5 adopted for the whole frame |
| Load factor | 1.5 | lifting points and their load path; used everywhere |
| **Total on the rated mass** | **2.433** | applied to every member, joint, link and added part, in every design case |

## 4. Load cases
Design cases (all enter the envelope): R1 rigid rig with equal slings, R2 elastic slings, R4 equalised cascade (main case);
T1-T8 the module hanging 2 degrees out of level (roll south / north, pitch west / east, and the four corners), solved with the
cascade geometry (pick offsets h tan 2 deg, gravity turned with the module); L1-L4 slings 5 % out of vertical at each head
(its own drop force; squeeze / spread, across / along).
Information cases (reported, not design): R7a-d +-10 % sling share (a pinned cascade shares by balance), R6 one sling 10 mm short
on a rigid rig (x8), R5 one sling slack (x8).

## 5. Resistance
* Members: AS/NZS 4600:2018 with the Direct Strength Method and the effective width method (lower governs), elastic buckling
  stresses from a finite-strip table (`analysis/liftcalc/data/c89_buckling.json`). Member steel taken as **G450** (fy 450 MPa)
  although the coil will be G550 (conservative).
* Lip notches: every member with a Framer lip notch is also checked at the notched section in compression with bending (lips
  and lip corners gone, each flange an unstiffened element with k = 0.425 + (b/a)^2 over a = 50 mm, web as usual; the swaged web
  end in the notch is ignored). Service holes: net area with a 32 mm hole. Member shear (AISI G2.1 form) and bending with shear.
* Buckling lengths from the model: in plane = largest gap between joints; out of plane = largest gap between points held by
  another panel or by an added part. **Twist (torsional) buckling length = the gap between screwed joints**: the screws pass
  through both flanges at every truss joint and wall noggin (hold point H3). Sensitivity S2 (twist length = out-of-plane
  length): 9 members over, so this restraint is essential. **No restraint is taken from linings, cladding or flooring in the
  lift check** (sensitivity S1: counting them changes nothing that governs).
* Joints (Framer dimple joints, screwed): the end force of every member that ends at the joint passes through its screws.
  Bearing credit only for a stud standing square on a plate (with the stud end gap hold point). Screw capacity AS/NZS 4600
  cl 5.4.2.4 with the frame steel at **fu = 0.75 x 550 = 412.5 MPa** (low-ductility rule): 1.77 kN per 10 gauge screw in
  0.95 mm; 10 % less per screw in groups of 3 or more; screw fracture limit 2.85 kN; end rupture at every Framer screw from its
  distance to the member end (lower of 0.5 t e fu and 0.6 t (e - d/2) fu); added screws at least 15 mm from the end. At most
  4 screws per joint (2 per side); a gusset counts as 10 screw-equivalents.
* Links between panels: short members with both ends fixed (A 400 mm2, I 200 mm4): shear stiffness 12 EI / L^3 (about
  7 kN/mm for a 41 mm link, stiffer for shorter ones), rotational stiffness 4 EI / L (about 4 kNm/rad at 41 mm), every 300 mm
  where members lie side by side. Checked in shear on their screws; any link in tension gets a positive tie - no screw is relied
  on in pull-out. (Review sensitivity: link stiffness x0.2 / x5 moves the maxima by 0.03 or less.)
* Cradle: bearing under a joint = web crippling of the chord's two flanges under a 40 mm packer (AISI S100-16 G5, C-section,
  interior one-flange, unfastened, phi 0.90; conservative because the nested diagonals stiffen the flanges); M16 bearing bolt
  in bending as a point load at mid-span between the cheeks (phi fy Zp, plain shank); bolt shear, bearing and tear-out on the
  cheeks; cheek screws at the screwed seat for the along-truss force and any uplift.
* Added parts (straps, plates, bolts, pins): `analysis/liftcalc/connectors.py`; bolts on sheet use deformation-limited
  bearing (AISI S100-16 J3.3.2) at phi 0.65, tear-out 0.60 t e fu (inner bolts: clear distance), net section 0.65 An fu,
  gross yield 0.90 Ag fy, bolt shear 0.8 x 0.62 x 800 x core area.

## 6. In service (sanity check only)
1.2 G + 1.5 Q with Q = 3.0 kPa on the floor (classroom) and 0.25 kPa on the roof; G = itemised mass; every lift part left in
place. Module on continuous bearers under both floor edge trusses (passes) and on piers at 1.8 m (does not pass: piers need
their own design). Flooring screwed at 300 mm restrains the floor truss top chords (normal floor design). Not checked: wind,
earthquake, transport (a 0.5 g transport case is roughly 5-10 x the 2 degree roll effect and will probably govern wall racking
and the support layout), foundations, the floor sheet, roof sheeting, the module-to-module connection.

## 7. Hold points (the design depends on them)
* H1 Weigh the first module (and every module of a changed layout) on load cells under the 8 lift points: mass x 1.03 must not
  exceed 6,500 kg; the centre of gravity from the readings must be within 90 mm across and 150 mm along of the design position
  (otherwise the engineer re-checks); it sets the cascade pick points.
* H2 Coil certificates for every coil in lift-critical members: AS 1397 grade and measured base metal thickness at least 95 %
  of nominal (0.9025 mm for 0.95 mm, 1.0925 mm for 1.15 mm). NFT1, NFT2 and NFT25 from 1.15 mm coil.
* H3 Screw brand fixed, characteristic shear at least 5.7 kN (10 gauge); screws through both flanges at every truss joint and
  wall noggin; joint screws, gussets, cleats and ties per the schedule; inspected before lining.
* H4 Proof load test of one complete lift point (cradle on a truss joint pair, strap pair, head) before first use; test factor
  and acceptance set by the engineer from AS/NZS 4600 Section 8.
* H5 Measured first lift with load-measuring shackles on all 8 drops; stop if any drop is more than 15 % from its design share
  or the module hangs more than 1.5 degrees out of level.
* H6 Lift conditions: crane on outriggers, no travelling with the load, controlled hoist speed, no snatch at lift-off, wind at
  the boom head within the lift plan limit, tag lines at both ends.
* H7 Cascade beams, slings and shackles designed, certified to AS 4991, proof tested and rated by the rigging supplier;
  planning hook load = 6.5 t + rigging.
* H8 Land and store only on continuous levelled bearers (+-2 mm) under both floor edge trusses, on packers between the cradles,
  never on corners.
* H9 Stud end gap at most 1 mm within 600 mm of the lift lines. After set-down and before the second module is placed, unbolt and
  remove the 8 heads, the 4 north (marriage-side) cradles and the marriage-face hanger straps: the modules meet north face to north
  face with their lift lines opposite each other, so both modules' north cradles would otherwise face each other in the gap. They
  carry nothing in service and are reused. Marriage gap at least 15 mm. Gutter fitted after the heads come off.
