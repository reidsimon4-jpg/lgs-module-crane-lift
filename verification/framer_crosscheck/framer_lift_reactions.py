"""Second opinion from Infinity Framer's own structural engine (framer/structural/full.py, PyNite inside).

The same frame (model/engineered/project.json, framed by Framer), held vertically at the 8 lift points on the floor rim
bottom chords, carrying exactly the project model's nodal loads (verification/framer_crosscheck/project_loads_B0.json,
mapped to the nearest Framer analysis node). Compares the 8 reactions with the project model (frame only, rigid supports).

Framer's engine is not edited: the build step is wrapped to swap the support set, PyNite's FEModel3D is subclassed so the
foundation call becomes vertical-only, and the loads are an extra basic case solved with the engine's own solver
(recipe 2 of the Framer capability map). Run with the Framer interpreter:
  C:/ILO/ilo-hub/apps/framer/.venv-desktop/Scripts/python.exe -B framer_lift_reactions.py <framer app dir> <project.json> <loads.json> <out.json>
The Framer pin is read only; all engine user data goes to a scratch profile.
"""
import os, sys, json, math, time, tempfile
APP, PROJECT, LOADS, OUT = sys.argv[1:5]
PROFILE = os.path.join(tempfile.gettempdir(), "framer_xcheck_profile")
for k in ("INFINITY_FRAMER_HOME", "INFINITY_FRAMER_LOG_DIR", "LOCALAPPDATA"):
    os.environ[k] = os.path.join(PROFILE, k.lower()); os.makedirs(os.environ[k], exist_ok=True)
os.environ["INFINITY_FRAMER_NO_OPEN"] = "1"
for k in ("FRAMER_PORTAL_TOKEN", "FRAMER_FACTORY_TOKEN", "ANTHROPIC_API_KEY"):
    os.environ.pop(k, None)
sys.dont_write_bytecode = True
sys.path.insert(0, APP)
import numpy as np
import Pynite
from framer import ai_tools
from framer.structural import full as F
from framer.structural.codes import base as CB
from framer.structural.codes.asnzs import ASNZS

project = json.load(open(PROJECT, encoding="utf-8"))
L = json.load(open(LOADS, encoding="utf-8"))
be = ai_tools.EmbeddedBackend(); frame = be.post("/api/frame", project); be.close()


class LIFT(ASNZS):
    key = "LIFT"; name = "Lifting check (unfactored dead load only)"
    def combinations(self, method, sp, wind_dirs, eq_dirs):
        return [{"name": "1.0G", "factors": {"D": 1.0}, "ref": "lift, unfactored"}]


CB.REGISTRY["LIFT"] = LIFT()
SRC = "placeholder for the cross-check; only the extra node-load case is used"
V = {"method": "LRFD", "risk_category": "II", "fy": 450.0, "fu": 480.0, "E": 200000.0, "nu": 0.3, "r_out": 2.0, "support": "pinned", "diaphragm": "semi-rigid",
     "diaphragm_k": 1.0, "loads_source": "kPa inputs", "roof_D": 0.01, "roof_Lr": 0.0, "floor_D": 0.01, "floor_L": 0.0, "wind_on": "no", "seismic_on": "no",
     "Lb_top_chord": 600.0, "Lb_bottom_chord": 600.0, "Lb_stud_weak": 1350.0, "bearing_N": 40.0, "defl_floor_L": 360, "defl_floor_T": 250, "defl_roof_T": 250,
     "screw_cap": 1.77, "wc_stiffener": "no", "engine_bracing": "as framed", "brace_model": "engine braces", "sheath_on": "no", "stud_track_joint": "pinned"}
TARGETS = [tuple(L["lift_points"][k]) for k in ("S1", "S2", "S3", "S4", "N1", "N2", "N3", "N4")]
cap = {}


def nearest(model, targets, types):
    ok = {n for m in model["phys"] if m["type"] in types for n in m["nodes"]}
    return [min(ok, key=lambda i: math.dist(model["nodes"][i], t)) for t in targets]


orig_build, orig_fe = F.build, Pynite.FEModel3D


def build(frame_, v, opts_=None):
    model = orig_build(frame_, v, opts_)
    lift = nearest(model, TARGETS, ("BOTTOM CHORD",))
    cap.update(lift=lift, model=model, v=v)
    model["supports"] = sorted(set(lift))
    cap["restraint"] = {"N%d" % n: (False, False, True) for n in lift}
    cap["restraint"]["N%d" % lift[0]] = (True, True, True); cap["restraint"]["N%d" % lift[3]] = (False, True, True)
    return model


class LiftFE(orig_fe):
    def __init__(s, *a, **k):
        super().__init__(*a, **k); cap.setdefault("M", s)
    def def_support(s, node, DX=False, DY=False, DZ=False, RX=False, RY=False, RZ=False):
        if s is cap["M"] and DX and DY and DZ: DX, DY, DZ = cap["restraint"][node]
        return super().def_support(node, DX, DY, DZ, RX, RY, RZ)


results = {}
for diaphragm in ("semi-rigid", "rigid"):
    cap.clear()
    V["diaphragm"] = diaphragm
    st = {"code_set": "LIFT", "values": {k: {"value": x, "source": SRC} for k, x in V.items()}}
    F.build, Pynite.FEModel3D = build, LiftFE
    try:
        t = time.time(); res = F.run(frame, st, {})
    finally:
        F.build, Pynite.FEModel3D = orig_build, orig_fe
    model, M = cap["model"], cap["M"]; X = model["nodes"]
    steel_nodes = sorted({n for m in model["phys"] for n in m["nodes"]})
    Xs = np.array([X[n] for n in steel_nodes])
    worst_map = 0.0
    for (x, y, z, fz) in L["loads"]:
        d = np.linalg.norm(Xs - np.array([x, y, z]), axis=1); i = int(np.argmin(d)); worst_map = max(worst_map, float(d[i]))
        M.add_node_load("N%d" % steel_nodes[i], "FZ", fz, case="PT")
    M.add_load_combo("_B_PT", {"PT": 1.0}, combo_tags=["blc"])
    F._linear_all(M, "blc")
    R = {k: M.nodes["N%d" % n].RxnFZ["_B_PT"] / 1e3 for k, n in zip(("S1", "S2", "S3", "S4", "N1", "N2", "N3", "N4"), cap["lift"])}
    dz = min(M.nodes["N%d" % n].DZ["_B_PT"] for n in steel_nodes)
    results[diaphragm] = dict(reactions_kN=R, sum_kN=sum(R.values()), applied_kN=L["W"] / 1e3, min_dz_mm=dz,
                              lift_nodes=[[round(c, 1) for c in X[n]] for n in cap["lift"]], worst_load_mapping_mm=worst_map,
                              model={k: res["model"][k] for k in ("panels", "physical", "segments", "nodes", "bearings")}, seconds=round(time.time() - t, 1))
    print(diaphragm, {k: round(v, 2) for k, v in R.items()}, "sum %.2f of %.2f kN, min dz %.1f mm, load mapping up to %.0f mm" % (sum(R.values()), L["W"] / 1e3, dz, worst_map))
ref = {k: v / 1e3 for k, v in L["reactions_R1"].items()}
out = dict(project_model_reactions_kN=ref, project_model_min_dz_mm=L["sag_mm"], framer=results,
           note="Framer's engine joins panels with its own bearing links and diaphragm; per its own caveats only reactions are robust in a lift case.")
json.dump(out, open(OUT, "w"), indent=1)
print("project model", {k: round(v, 2) for k, v in ref.items()})
