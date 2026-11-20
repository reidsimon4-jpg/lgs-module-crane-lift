"""Frame a project with the Infinity Framer engine and write a plain JSON snapshot of the result.

This is the only step that needs the Framer engine (not included in this repository). Everything downstream reads the
snapshot it writes, so the analysis can be re-run and audited without Framer.

usage (Framer's Python):  python tools/export_framer_frame.py <framer app dir> <project.json> <out framed.json>
"""
import sys, json, hashlib, datetime

app_dir, project_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
# optional 4th argument: JSON list of [source-id prefix, kind] pairs that rename panel kinds, e.g. '[["RIMF","rim_truss"],["RT","roof_truss"]]'
# (the engine frames every parallel-chord element truss as kind "floor_truss", whatever it is used for)
KIND_MAP = json.loads(sys.argv[4]) if len(sys.argv) > 4 else []
sys.path.insert(0, app_dir)
from framer import ai_tools  # noqa: E402

project = json.load(open(project_path, encoding="utf-8"))
fr = ai_tools.EmbeddedBackend().post("/api/frame", project)
panels = []
for pn in fr["panels"]:
    w = pn["world"]
    ms = []
    for m in pn["members"]:
        model = m.get("model") or {}
        # The engine measures feature positions from the machine-feed end: (x1, y1) for orient NORMAL, (x2, y2) for INVERTED
        # (checked: with this rule the two dimples of every joint coincide within 2.5 mm, median 0.002 mm).
        # Here every position is re-expressed as the distance from (x1, y1).
        inv = m.get("orient") == "INVERTED"
        s0 = (lambda pos: m["length"] - pos) if inv else (lambda pos: pos)
        joints = [{"joint": f["joint_id"], "pos": round(s0(f["pos"]), 3), "with": f.get("related_members") or []}
                  for f in (model.get("features") or []) if f.get("kind") == "DIMPLE" and f.get("joint_id")]
        loose = [round(s0(f["pos"]), 3) for f in (model.get("features") or []) if f.get("kind") == "DIMPLE" and not f.get("joint_id")]
        ms.append({"id": model.get("id"), "mark": m["mark"], "type": m["type"], "profile": m["profile"], "orient": m.get("orient"),
                   "length": m["length"], "x1": m["x1"], "y1": m["y1"], "x2": m["x2"], "y2": m["y2"],
                   "joints": joints, "dimples_without_joint": loose,
                   "ops": [[o[0], round(s0(o[1]), 3)] for o in (m.get("ops") or []) if o and o[0] not in ("DIMPLE",)]})
    kind = pn["kind"]
    for prefix, k2 in KIND_MAP:
        if str(pn.get("wall_id") or "").startswith(prefix):
            kind = k2; break
    panels.append({"name": pn["name"], "kind": kind, "engine_kind": pn["kind"], "wall_id": pn.get("wall_id"), "group": pn.get("group"),
                   "origin": w["origin"], "xdir": w["xdir"], "members": ms})
S = fr["summary"]
version = open(app_dir.rstrip("/\\") + "/VERSION").read().strip()
snap = {"meta": {"engine": "Infinity Framer", "engine_version": version, "project_file": project_path.replace("\\", "/").split("/")[-1],
                 "project_sha256": hashlib.sha256(open(project_path, "rb").read()).hexdigest(),
                 "units": "mm; panel-local x along xdir, y vertical (global z); joint, dimple and op positions are distances from (x1, y1)"},
        "summary": {k: S.get(k) for k in ("panels", "members", "total_metres", "total_kg", "walls", "roof_trusses", "floor_trusses")},
        "warnings": [str(w) for w in (fr.get("warnings") or [])],
        "panels": panels}
json.dump(snap, open(out_path, "w", encoding="utf-8"), separators=(",", ":"))
print("wrote", out_path, snap["summary"], "warnings", len(snap["warnings"]))
