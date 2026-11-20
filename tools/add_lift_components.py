"""Put the Rev D lift parts into the Infinity Framer project as parametric components, so Framer's own bill of quantities
and IFC carry them; frame the project with Framer; set the three edge trusses to 1.15 mm; run Framer's clash detection and
release check; write the IFC and a summary.

usage (Framer's interpreter; the Framer pin stays read only, engine user data goes to a temp profile):
  <framer python> -B tools/add_lift_components.py <framer app dir> <repo root>
Writes model/engineered/project_with_lift_parts.json, model/engineered/lift_module_frame_and_parts.ifc and
results/framer_components/summary.json. The Rev C version is tools/add_lift_components_revC.py.

Geometry comes from the lift analysis export (site/data/revD.json), so the components sit where the analysis put the parts.
Components never change Framer's frame kg; they appear in the BOQ group 'components' and in the IFC.

Edge-truss gauge: Framer 0.7.1 frames a floor-truss element at the job gauge (elements.py _floor_panel uses project.profile)
and has no per-element or per-panel gauge (overrides can add / delete / move / retype members, not change the profile). The
analysis rolls the floor edge trusses (NFT1, NFT2) and the north roof edge truss (NFT25) in 1.15 mm, so this script sets
those panels' member profiles to C89-38-1.15 AFTER Framer's framing run, before the BOQ, the checks and the IFC. In the
factory those three trusses must be rolled from 1.15 mm coil. A per-element gauge in Framer would remove this step.
"""
import os, sys, json, copy, math, tempfile, hashlib, collections
APP, ROOT = sys.argv[1], sys.argv[2]
PROFILE = os.path.join(tempfile.gettempdir(), "framer_components_profile")
for k in ("INFINITY_FRAMER_HOME", "INFINITY_FRAMER_LOG_DIR", "LOCALAPPDATA"):
    os.environ[k] = os.path.join(PROFILE, k.lower()); os.makedirs(os.environ[k], exist_ok=True)
os.environ["INFINITY_FRAMER_NO_OPEN"] = "1"
for k in ("FRAMER_PORTAL_TOKEN", "FRAMER_FACTORY_TOKEN", "ANTHROPIC_API_KEY"):
    os.environ.pop(k, None)
sys.dont_write_bytecode = True
sys.path.insert(0, APP)
from framer import ai_tools, component_defs, export

R = lambda p: os.path.join(ROOT, p)
project = json.load(open(R("model/engineered/project.json"), encoding="utf-8"))
D = json.load(open(R("site/data/revD.json"), encoding="utf-8"))
CFG = json.load(open(R("analysis/configs/revD_final.json"), encoding="utf-8"))
GAUGE = (CFG.get("build_options") or {}).get("gauge") or {}
MAT = "steel G450 (G300 for ties and plane bracing) - grade by engineer"


def P(name, kind="length", value=0, instance=False, formula=None):
    d = {"name": name, "kind": kind, "value": value, "instance": instance}
    if formula: d["formula"] = formula
    return d


def box_xz(x0, x1, z0, z1, y0, t):           # rectangle in the x-z plane, extruded along +y from y0 by t
    return {"kind": "extrude", "plane": "xz", "profile": [[x0, z0], [x1, z0], [x1, z1], [x0, z1]], "from": y0, "depth": t, "material": "Material"}


defs = []
# lifting head: saddle over the roof edge truss - two 3 mm cheeks on the faces, top plate, M20 pin (shown square)
defs.append({"id": "LIFT_HEAD", "name": "LH lifting head saddle - folded 3 mm G450 box over the roof edge truss, M20 8.8 pin + 40 mm sleeve, no fasteners, stop block along the module",
             "category": "pod",
             "parameters": [P("Material", "material", MAT), P("Mass kg", "number", 0, formula="(2*120*450*3 + 120*101*3) * 7.85e-6 + 0.35")],
             "forms": [box_xz(-60, 60, 0, 450, -50.5, 3), box_xz(-60, 60, 0, 450, 47.5, 3),
                       {"kind": "extrude", "plane": "xy", "profile": [[-60, -50.5], [60, -50.5], [60, 50.5], [-60, 50.5]], "from": 447, "depth": 3, "material": "Material"},
                       box_xz(-10, 10, 380, 400, -60, 120)],
             "boq": {"code": "LIFT-LH", "unit": "kg", "qty_formula": "Mass kg"}})
# north hanger strap pair, one 50 x 1.5 strap on each face of the edge truss
defs.append({"id": "LIFT_HS", "name": "HS hanger strap pair - 2 x 50 x 1.5 G450, one on each face, 2 x M12 8.8 each end", "category": "pod",
             "parameters": [P("Length", "length", 3430, True), P("Material", "material", MAT), P("Mass kg", "number", 0, formula="2 * Length * 50 * 1.5 * 7.85e-6")],
             "forms": [box_xz(-25, 25, 0, "Length", -46, 1.5), box_xz(-25, 25, 0, "Length", 44.5, 1.5)],
             "boq": {"code": "LIFT-HS", "unit": "kg", "qty_formula": "Mass kg"}})
# south A-frame strap pair (parallelogram from the foot up to the head)
prof = [[-25, 0], [25, 0], ["Run + 25", "Rise"], ["Run - 25", "Rise"]]
defs.append({"id": "LIFT_VS", "name": "VS A-frame strap pair (south) - 2 x 50 x 1.2 G450, one on each wall face, 2 x M12 8.8 each end", "category": "pod",
             "parameters": [P("Run", "length", 441, True), P("Rise", "length", 3450, True), P("Material", "material", MAT),
                            P("Length", "length", 0, formula="sqrt(Run^2 + Rise^2)"), P("Mass kg", "number", 0, formula="2 * Length * 50 * 1.2 * 7.85e-6")],
             "forms": [{"kind": "extrude", "plane": "xz", "profile": prof, "from": -46, "depth": 1.2, "material": "Material"},
                       {"kind": "extrude", "plane": "xz", "profile": prof, "from": 44.5, "depth": 1.2, "material": "Material"}],
             "boq": {"code": "LIFT-VS", "unit": "kg", "qty_formula": "Mass kg"}})
# cradle: two cheeks, two M16 bearing bolts with sleeves (shown square), two 3 x 40 x 89 packers; local origin = cradle start x,
# truss centre line y, cheek bottom z (410 mm under the floor level, 113 mm under the edge truss)
def bolt(sx):
    return {"kind": "extrude", "plane": "xz", "profile": [[f"{sx} - 8", 89.5], [f"{sx} + 8", 89.5], [f"{sx} + 8", 105.5], [f"{sx} - 8", 105.5]],
            "from": -55, "depth": 110, "material": "Material"}


defs.append({"id": "LIFT_CR", "name": "CR cradle - two 3 mm G450 cheeks 120 x 160, 2 x M16 8.8 bearing bolts + sleeves under the truss joints, 3 x 40 x 89 packers; screwed at the first joint, bearing only at the second",
             "category": "pod",
             "parameters": [P("S1", "length", 40, True), P("S2", "length", 99, True), P("Material", "material", MAT),
                            P("Mass kg", "number", 0, formula="2*120*160*3*7.85e-6 + 2*0.32 + 2*0.05 + 2*40*89*3*7.85e-6 + 4*0.06")],
             "forms": [box_xz(0, 120, 0, 160, -47.5, 3), box_xz(0, 120, 0, 160, 44.5, 3), bolt("S1"), bolt("S2"),
                       box_xz("S1 - 20", "S1 + 20", 110, 113, -44.5, 89), box_xz("S2 - 20", "S2 + 20", 110, 113, -44.5, 89)],
             "boq": {"code": "LIFT-CR", "unit": "kg", "qty_formula": "Mass kg"}})
# joint gusset: a 1.5 mm plate on each face of the panel, 100 x 100, 3 + 3 screws per face
defs.append({"id": "LIFT_GU", "name": "GU joint gusset pair - 1.5 mm G450 100 x 100 plate each face, 3 + 3 screws per face", "category": "pod",
             "parameters": [P("Material", "material", MAT), P("Mass kg", "number", 0, formula="2 * 100 * 100 * 1.5 * 7.85e-6")],
             "forms": [box_xz(-50, 50, -50, 50, -46, 1.5), box_xz(-50, 50, -50, 50, 44.5, 1.5)],
             "boq": {"code": "LIFT-GU", "unit": "kg", "qty_formula": "Mass kg"}})
# truss-end cleat pair: a folded 1.5 mm angle each side of the truss end (drawn as the two legs on the edge truss face)
defs.append({"id": "LIFT_CL", "name": "CL truss-end cleat pair - folded 1.5 mm G450 50 x 50 angle each side of the truss end, 5 + 5 screws", "category": "pod",
             "parameters": [P("Material", "material", MAT), P("Mass kg", "number", 0, formula="2 * 100 * 200 * 1.5 * 7.85e-6")],
             "forms": [box_xz(-96.5, -46.5, -100, 100, 0, 1.5), box_xz(46.5, 96.5, -100, 100, 0, 1.5)],
             "boq": {"code": "LIFT-CL", "unit": "kg", "qty_formula": "Mass kg"}})
# plane bracing strap (in plan), 30 x 1.0 G300
defs.append({"id": "LIFT_PB", "name": "PB floor / roof plane bracing strap - 30 x 1.0 G300 with tensioner", "category": "pod",
             "parameters": [P("Run", "length", 3600, True), P("Span", "length", 3211, True), P("Material", "material", MAT),
                            P("Length", "length", 0, formula="sqrt(Run^2 + Span^2)"), P("Mass kg", "number", 0, formula="Length * 30 * 1.0 * 7.85e-6")],
             "forms": [{"kind": "extrude", "plane": "xy", "profile": [[0, -15], [0, 15], ["Run", "Span + 15"], ["Run", "Span - 15"]], "from": 0, "depth": 1.0, "material": "Material"}],
             "boq": {"code": "LIFT-PB", "unit": "kg", "qty_formula": "Mass kg"}})
# bridging nogging (floor and roof)
defs.append({"id": "LIFT_BR", "name": "BR truss bridging - C89 0.95 nogging at mid-span, 2 screws each end", "category": "pod",
             "parameters": [P("Length", "length", 510, True), P("Material", "material", MAT), P("Mass kg", "number", 0, formula="Length * 1.33e-3")],
             "forms": [{"kind": "extrude", "plane": "yz", "profile": [[-44.5, -38], [44.5, -38], [44.5, 0], [-44.5, 0]], "from": "0 - Length / 2", "depth": "Length", "material": "Material"}],
             "boq": {"code": "LIFT-BR", "unit": "kg", "qty_formula": "Mass kg"}})
# tie plate
defs.append({"id": "LIFT_TIE", "name": "T2-T3 tie plate - 30-40 x 0.8-1.0 G300 strap across a joint, 4 + 4 / 2 + 2 screws", "category": "pod",
             "parameters": [P("Material", "material", MAT), P("Mass kg", "number", 0, formula="40 * 150 * 1.0 * 7.85e-6")],
             "forms": [{"kind": "extrude", "plane": "xy", "profile": [[-75, -20], [75, -20], [75, 20], [-75, 20]], "from": 0, "depth": 1.0, "material": "Material"}],
             "boq": {"code": "LIFT-TIE", "unit": "kg", "qty_formula": "Mass kg"}})
for d in defs:
    component_defs.validate_def(d)

comps = []
def place(defid, x, y, z, rot=0.0, values=None):
    c = {"id": f"LP{len(comps) + 1}", "def": defid, "position": [round(x, 1), round(y, 1)], "rotation": rot, "offset": round(z, 1)}
    if values: c["values"] = values
    comps.append(c)

zt = CFG["floor_rim_z"][1]; zr = CFG["roof_rim_top_z"]
for m in D["members"]:
    if not m["added"]: continue
    a, b = m["a"], m["b"]
    if m["type"] == "GUIDE":
        place("LIFT_HEAD", a[0], a[1], 2700.0)
    elif m["type"] == "STRAP":
        place("LIFT_HS", a[0], b[1], a[2], values={"Length": round(b[2] - a[2], 1)})
    elif m["type"] == "V-STRAP":
        place("LIFT_VS", a[0], a[1], a[2], values={"Run": round(b[0] - a[0], 1), "Rise": round(b[2] - a[2], 1)})
    elif m["type"] == "PLANE BRACE":
        place("LIFT_PB", a[0], a[1], a[2], values={"Run": round(b[0] - a[0], 1), "Span": round(b[1] - a[1], 1)})
    elif m["type"] == "BRIDGING":
        L = math.dist(a, b)
        place("LIFT_BR", (a[0] + b[0]) / 2, (a[1] + b[1]) / 2, a[2], rot=0.0, values={"Length": round(L - 89.0, 1)})
for f in D["foot_layout"]:
    x0 = f["cradle"][0]; y = CFG["rim_y"][f["side"]]
    s = sorted(f["joints"] if len(f["joints"]) >= 2 else f["seats"] * 2)
    place("LIFT_CR", x0, y, -410.0, values={"S1": round(s[0] - x0, 1), "S2": round(s[-1] - x0, 1)})
for g in D["gussets"]:
    rot = 0.0 if abs(g["nrm"][1]) > 0.5 else 90.0          # panels in the x-z plane (edge trusses, long walls) or the y-z plane
    place("LIFT_GU", g["xyz"][0], g["xyz"][1], g["xyz"][2], rot=rot)
# truss-end cleats at both ends of every floor and roof truss (on the inside face of the edge truss)
for kind, zc in (("floor_truss", (CFG["floor_rim_z"][0] + zt) / 2), ("roof_truss", None)):
    tops = [m for m in D["members"] if m["kind"] == kind and m["type"] == "TOP CHORD"]
    for x in sorted({round((m["a"][0] + m["b"][0]) / 2, 1) for m in tops}):
        z = zc if zc is not None else max(m["a"][2] for m in tops) - 150.0
        place("LIFT_CL", x, CFG["rim_y"]["S"] + 44.5, z)
        place("LIFT_CL", x, CFG["rim_y"]["N"] - 44.5 - 1.5, z)
for l in D["links"]:
    if l["tie"]:
        place("LIFT_TIE", (l["a"][0] + l["b"][0]) / 2, (l["a"][1] + l["b"][1]) / 2, (l["a"][2] + l["b"][2]) / 2)

p = copy.deepcopy(project)
p["component_defs"] = defs; p["components"] = comps
p.setdefault("notes", {})["lift_engineering"] = ("Rev D lift parts as components (see the lgs-module-lift repository). Edge trusses NFT1, NFT2 and NFT25 "
                                                 "are rolled in 1.15 mm (set after framing; Framer 0.7.1 has no per-element gauge).")
out_proj = R("model/engineered/project_with_lift_parts.json")
json.dump(p, open(out_proj, "w", encoding="utf-8"), indent=1)
srv = ai_tools._load_server()
body = json.loads(json.dumps(p))
proj, panels, warnings = srv.run_pipeline(body)
panels, edits = srv._replay_edits(body, proj, panels, warnings)
# the three edge trusses at 1.15 mm (see the module note)
from framer import modelling
gauged = collections.Counter(); regen_warnings = []
for i, q in enumerate(panels):
    t = GAUGE.get(q.name)
    if t:
        for mm in q.members:
            mm.profile = mm.profile.rsplit("-", 1)[0] + f"-{float(t):.2f}"
        q2, w = modelling.regenerate(q, proj)          # Framer's own tooling rules again, at the new gauge (no stale features)
        panels[i] = q2; regen_warnings += [str(x)[:160] for x in w]
        gauged[q.name] += len(q2.members)
res = srv.with_extras({"panels": [q.to_dict() for q in panels], "warnings": warnings, "summary": srv.summarize(panels, proj)}, proj, panels)
rows = [dict(code=l["item_code"], item=l["item"], qty=round(l["qty"], 2), unit=l["unit"], count=len(l["source_ids"])) for l in res["boq"]["lines"] if l["group"] == "components"]
frame_rows = collections.defaultdict(float)
for l in res["boq"]["lines"]:
    if l["group"] != "components" and l["unit"] == "kg": frame_rows[l["item"]] += l["qty"]
# Framer's own checks on the gauged frame
from framer import clash as CL, release_gate as RG
det = CL.detect(proj, panels, tolerance_mm=20.0)
rel = RG.release_check(proj, {"panels": panels, "warnings": warnings},
                       {"clash_tolerance_mm": 20.0, "orphan_tolerance_mm": 20.0, "test_only": ["orphan_tolerance_mm"]}, run_clash=False)
ifc = R("model/engineered/lift_module_frame_and_parts.ifc")
open(ifc, "wb").write(export.assembly_ifc_bytes(panels, proj)[0])
by_def = collections.Counter(c["def"] for c in comps)
summary = dict(frame_kg=res["summary"]["total_kg"], members=res["summary"]["members"], panels=res["summary"]["panels"],
               gauged_panels=dict(gauged), components=len(comps), components_by_def=dict(by_def),
               component_rows=rows, component_kg=round(sum(r["qty"] for r in rows if r["unit"] == "kg"), 1),
               clashes=len(det["clashes"]), clash_kinds=dict(collections.Counter(x["kind"] for x in det["clashes"])),
               release_ok=bool(rel["ok"]), release_blockers=len(rel["blockers"]),
               release_blocker_checks=dict(collections.Counter(b["check"] for b in rel["blockers"])),
               release_blocker_details=[dict(check=b["check"], reason=str(b.get("reason", ""))[:300], elements=[str(e)[:120] for e in b.get("elements", [])][:4]) for b in rel["blockers"]][:10],
               regen_warnings=regen_warnings[:10],
               warnings=[str(w)[:200] for w in warnings][:12], ifc=os.path.relpath(ifc, ROOT), ifc_bytes=os.path.getsize(ifc),
               project_with_parts_sha256=hashlib.sha256(open(out_proj, "rb").read()).hexdigest())
os.makedirs(R("results/framer_components"), exist_ok=True)
json.dump(summary, open(R("results/framer_components/summary.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in summary.items() if k not in ("warnings", "component_rows")}, indent=1))
for r_ in rows: print(f"  {r_['code']:14s} {r_['count']:4d}  {r_['qty']:8.2f} {r_['unit']}  {r_['item'][:90]}")
