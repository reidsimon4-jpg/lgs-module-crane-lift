"""Put the lift parts into the Infinity Framer project as parametric components, so Framer's own bill of quantities and
IFC carry them, then frame the project with Framer and report the BOQ rows, the release gate and the IFC file.

usage (Framer's interpreter; the Framer pin stays read only, engine user data goes to a temp profile):
  <framer python> -B tools/add_lift_components.py <framer app dir> <repo root>
Writes model/engineered/project_with_lift_parts.json, model/engineered/lift_module_frame_and_parts.ifc and
results/framer_components/summary.json.
Geometry comes from the lift analysis export (site/data/revC.json), so the components sit exactly where the analysis put
the parts. Components never change Framer's frame kg; they appear in the BOQ group 'components' and in the IFC.
"""
import os, sys, json, copy, math, tempfile, hashlib
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
D = json.load(open(R("site/data/revC.json"), encoding="utf-8"))
M = {m["id"]: m for m in D["members"]}
RHO = 7.85e-6          # kg per mm3
MAT = "steel G450 (G300 for straps T1-T3 and bracing) - grade by engineer"


def P(name, kind="length", value=0, instance=False, formula=None):
    d = {"name": name, "kind": kind, "value": value, "instance": instance}
    if formula: d["formula"] = formula
    return d


def box_xz(x0, x1, z0, z1, y0, t):           # rectangle in the x-z plane, extruded along +y from y0 by t
    return {"kind": "extrude", "plane": "xz", "profile": [[x0, z0], [x1, z0], [x1, z1], [x0, z1]], "from": y0, "depth": t, "material": "Material"}


defs = []
# lifting head: two 3 mm cheeks on the faces, top plate, M20 pin (shown square)
defs.append({"id": "LIFT_HEAD", "name": "LH lifting head - folded 3 mm box, M20 8.8 pin + sleeve", "category": "pod",
             "parameters": [P("Material", "material", MAT), P("Mass kg", "number", 0, formula="(2*120*450*3 + 120*101*3) * 7.85e-6 + 0.35")],
             "forms": [box_xz(-60, 60, 0, 450, -50.5, 3), box_xz(-60, 60, 0, 450, 47.5, 3),
                       {"kind": "extrude", "plane": "xy", "profile": [[-60, -50.5], [60, -50.5], [60, 50.5], [-60, 50.5]], "from": 447, "depth": 3, "material": "Material"},
                       box_xz(-10, 10, 380, 400, -60, 120)],
             "boq": {"code": "LIFT-LH", "unit": "kg", "qty_formula": "Mass kg"}})
# hanger strap pair, one 50 x 1.5 strap on each face
defs.append({"id": "LIFT_HS", "name": "HS hanger strap pair - 50 x 1.5 G450, 2 x M12 each end", "category": "pod",
             "parameters": [P("Length", "length", 3430, True), P("Material", "material", MAT), P("Mass kg", "number", 0, formula="2 * Length * 50 * 1.5 * 7.85e-6")],
             "forms": [box_xz(-25, 25, 0, "Length", -46, 1.5), box_xz(-25, 25, 0, "Length", 44.5, 1.5)],
             "boq": {"code": "LIFT-HS", "unit": "kg", "qty_formula": "Mass kg"}})
# inclined strap pair (parallelogram from the foot up to the head)
for did, label in (("LIFT_VS", "VS V-strap pair - 50 x 1.2 G450, 2 x M12 each end"), ("LIFT_VS_TEMP", "VS-T V-strap pair, TEMPORARY lift kit - removed after set-down")):
    prof = [[-25, 0], [25, 0], ["Run + 25", "Rise"], ["Run - 25", "Rise"]]
    defs.append({"id": did, "name": label, "category": "pod",
                 "parameters": [P("Run", "length", 840, True), P("Rise", "length", 3430, True), P("Material", "material", MAT),
                                P("Length", "length", 0, formula="sqrt(Run^2 + Rise^2)"), P("Mass kg", "number", 0, formula="2 * Length * 50 * 1.2 * 7.85e-6")],
                 "forms": [{"kind": "extrude", "plane": "xz", "profile": prof, "from": -46, "depth": 1.2, "material": "Material"},
                           {"kind": "extrude", "plane": "xz", "profile": prof, "from": 44.5, "depth": 1.2, "material": "Material"}],
                 "boq": {"code": "LIFT-VS-T" if "TEMP" in did else "LIFT-VS", "unit": "kg", "qty_formula": "Mass kg"}})
# cradle: folded U under the floor edge truss, 600 long
U = [[-50, 0], [50, 0], [50, 302.5], [47.5, 302.5], [47.5, 2.5], [-47.5, 2.5], [-47.5, 302.5], [-50, 302.5]]
defs.append({"id": "LIFT_FC", "name": "FC cradle - folded 2.5 mm G450 U, 600 long, 95 inside, wraps under the floor edge truss", "category": "pod",
             "parameters": [P("Material", "material", MAT), P("Mass kg", "number", 0, formula="(2*302.5 + 100) * 2.5 * 600 * 7.85e-6")],
             "forms": [{"kind": "extrude", "plane": "yz", "profile": U, "from": -300, "depth": 600, "material": "Material"}],
             "boq": {"code": "LIFT-FC", "unit": "kg", "qty_formula": "Mass kg"}})
for did, label in (("LIFT_FP", "FP foot plate pair - 2.0 mm G450, 600 x 300, both faces of the floor edge truss"), ("LIFT_FP_TEMP", "FP-T foot plate pair, TEMPORARY lift kit - bolted, removed after set-down")):
    defs.append({"id": did, "name": label, "category": "pod",
                 "parameters": [P("Material", "material", MAT), P("Mass kg", "number", 0, formula="2 * 600 * 300 * 2.0 * 7.85e-6")],
                 "forms": [box_xz(-300, 300, 0, 300, -46.5, 2.0), box_xz(-300, 300, 0, 300, 44.5, 2.0)],
                 "boq": {"code": "LIFT-FP-T" if "TEMP" in did else "LIFT-FP", "unit": "kg", "qty_formula": "Mass kg"}})
# plane bracing strap (in plan), 30 x 1.0 G300
defs.append({"id": "LIFT_PB", "name": "PB floor / roof plane bracing strap - 30 x 1.0 G300 with tensioner", "category": "pod",
             "parameters": [P("Run", "length", 3600, True), P("Span", "length", 3211, True), P("Material", "material", MAT),
                            P("Length", "length", 0, formula="sqrt(Run^2 + Span^2)"), P("Mass kg", "number", 0, formula="Length * 30 * 1.0 * 7.85e-6")],
             "forms": [{"kind": "extrude", "plane": "xy", "profile": [[0, -15], [0, 15], ["Run", "Span + 15"], ["Run", "Span - 15"]], "from": 0, "depth": 1.0, "material": "Material"}],
             "boq": {"code": "LIFT-PB", "unit": "kg", "qty_formula": "Mass kg"}})
# bridging nogging
defs.append({"id": "LIFT_BR", "name": "BR floor truss bridging - C89 0.95 nogging at mid-span", "category": "pod",
             "parameters": [P("Length", "length", 510, True), P("Material", "material", MAT), P("Mass kg", "number", 0, formula="Length * 1.33e-3")],
             "forms": [{"kind": "extrude", "plane": "yz", "profile": [[-44.5, -38], [44.5, -38], [44.5, 0], [-44.5, 0]], "from": "0 - Length / 2", "depth": "Length", "material": "Material"}],
             "boq": {"code": "LIFT-BR", "unit": "kg", "qty_formula": "Mass kg"}})
# tie plate
defs.append({"id": "LIFT_TIE", "name": "T1-T3 tie plate - 30-40 x 0.8-1.0 G300 strap across a joint, 2 + 2 screws", "category": "pod",
             "parameters": [P("Material", "material", MAT), P("Mass kg", "number", 0, formula="40 * 150 * 1.0 * 7.85e-6")],
             "forms": [{"kind": "extrude", "plane": "xy", "profile": [[-75, -20], [75, -20], [75, 20], [-75, 20]], "from": 0, "depth": 1.0, "material": "Material"}],
             "boq": {"code": "LIFT-TIE", "unit": "kg", "qty_formula": "Mass kg"}})
for d in defs:
    component_defs.validate_def(d)

comps = []
def place(defid, x, y, z, rot=0.0, values=None, note=""):
    c = {"id": f"LP{len(comps) + 1}", "def": defid, "position": [round(x, 1), round(y, 1)], "rotation": rot, "offset": round(z, 1)}
    if values: c["values"] = values
    comps.append(c)

for mid, m in M.items():
    if not m["added"]: continue
    a, b = m["a"], m["b"]
    if m["type"] == "GUIDE":
        place("LIFT_HEAD", a[0], a[1], 2700.0)
    elif m["type"] == "STRAP":
        place("LIFT_HS", a[0], a[1], a[2], values={"Length": round(b[2] - a[2], 1)})
    elif m["type"] == "V-STRAP":
        place("LIFT_VS_TEMP" if m.get("temporary") else "LIFT_VS", a[0], a[1], a[2], values={"Run": round(b[0] - a[0], 1), "Rise": round(b[2] - a[2], 1)})
    elif m["type"] == "CRADLE" and mid.endswith("_B"):
        xc = (a[0] + b[0]) / 2
        if mid.startswith("STIR_"):
            place("LIFT_FC", xc, a[1], -302.5)
        else:
            place("LIFT_FP_TEMP" if m.get("temporary") else "LIFT_FP", xc, a[1], -300.0)
    elif m["type"] == "PLANE BRACE":
        z = 0.0 if a[2] < 1000 else 3000.0
        place("LIFT_PB", a[0], a[1], z, values={"Run": round(b[0] - a[0], 1), "Span": round(b[1] - a[1], 1)})
# bridging between neighbouring floor trusses at mid-span
xs = sorted({round((m["a"][0] + m["b"][0]) / 2, 1) for m in D["members"] if m["kind"] == "floor_truss" and m["type"] == "TOP CHORD"})
for x0, x1 in zip(xs[:-1], xs[1:]):
    place("LIFT_BR", (x0 + x1) / 2, 1650.0, 0.0, values={"Length": round(x1 - x0 - 89.0, 1)})
for l in D["links"]:
    if l["tie"]:
        place("LIFT_TIE", (l["a"][0] + l["b"][0]) / 2, (l["a"][1] + l["b"][1]) / 2, (l["a"][2] + l["b"][2]) / 2)

p = copy.deepcopy(project)
p["component_defs"] = defs; p["components"] = comps
out_proj = R("model/engineered/project_with_lift_parts.json")
json.dump(p, open(out_proj, "w", encoding="utf-8"), indent=1)
srv = ai_tools._load_server()
proj, panels, warnings = srv.run_pipeline(copy.deepcopy(p))
res = srv.with_extras({"panels": [q.to_dict() for q in panels], "warnings": warnings, "summary": srv.summarize(panels, proj)}, proj, panels)
rows = [dict(code=l["item_code"], item=l["item"], qty=round(l["qty"], 2), unit=l["unit"], count=len(l["source_ids"])) for l in res["boq"]["lines"] if l["group"] == "components"]
ifc = R("model/engineered/lift_module_frame_and_parts.ifc")
open(ifc, "wb").write(export.assembly_ifc_bytes(panels, proj)[0])
summary = dict(frame_kg=res["summary"]["total_kg"], members=res["summary"]["members"], panels=res["summary"]["panels"], components=len(comps),
               component_rows=rows, component_kg=round(sum(r["qty"] for r in rows if r["unit"] == "kg"), 1),
               permanent_kg=round(sum(r["qty"] for r in rows if r["unit"] == "kg" and "TEMP" not in r["code"]), 1),
               temporary_kg=round(sum(r["qty"] for r in rows if r["unit"] == "kg" and "TEMP" in r["code"]), 1),
               warnings=[str(w)[:200] for w in warnings][:12], ifc=os.path.relpath(ifc, ROOT), ifc_bytes=os.path.getsize(ifc),
               project_with_parts_sha256=hashlib.sha256(open(out_proj, "rb").read()).hexdigest())
os.makedirs(R("results/framer_components"), exist_ok=True)
json.dump(summary, open(R("results/framer_components/summary.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in summary.items() if k != "warnings"}, indent=1))
