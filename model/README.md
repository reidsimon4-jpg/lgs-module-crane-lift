# Models

* `engineered/project.json` - the Infinity Framer 0.7.1 project of the lift-engineered module. `framed.json` is Framer's
  framed output for it (panels, members, joints, dimples); its `meta.project_sha256` is the hash of this project.
* `engineered/project_with_lift_parts.json` - the same project with the Rev D lift parts added as Framer parametric components
  (heads, hanger strap pairs, cradles, gussets, cleats, ties, plane bracing, bridging), written by `tools/add_lift_components.py`.
  `engineered/lift_module_frame_and_parts.ifc` is Framer's IFC of the frame with those parts. In that run the floor edge
  trusses NFT1, NFT2 and the north roof edge truss NFT25 are set to 1.15 mm after framing (Framer 0.7.1 has no per-element
  gauge) and Framer's tooling rules are run again on them; Framer's clash check and release check then pass
  (`results/framer_components/summary.json`).
* `concept/` - the first concept module (before the lift layout), kept for the record. Its project's name prefix was
  changed to a neutral one after framing, so `concept/framed.json` records the hash of the original file; the frame is
  unaffected.
* `mass_model.json` - itemised mass of the finished module (area items, openings, lumps) with sources.

Framer itself is not included. To re-frame, open `project.json` in Infinity Framer 0.7.1 (or run its framing pipeline).
