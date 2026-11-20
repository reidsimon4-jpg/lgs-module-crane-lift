"""Ablation and sensitivity runs for the Rev D design: take one measure away at a time (or change one assumption) and run
the design cases again.

usage: python analysis/run_ablation.py [--jobs 4]

Base: analysis/configs/revD_final.json. Each variant is the base with one change (listed below). Results go to
results/ablation_revD/<id>/summary.json; the table for the report and the 3D page is written to site/data/ablation.json
(the full design row is read from results/revD_final/summary.json, which has every case).
"""
from __future__ import annotations
import sys, os, json, copy, argparse, contextlib, io
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def _no_gussets(c):
    c["joint_rules"] = [r for r in c["joint_rules"] if r.get("n", 0) < 10]; c["gusset_joints"] = []


def _framed_screws(c):
    c["joint_rules"] = []; c["joint_fasteners"] = {}; c["joint_fasteners_panels"] = {}; c["link_screws"] = {}; c["gusset_joints"] = []


def _no_bridging(c):
    c["bridging"] = {}


def _no_plane_bracing(c):
    c.pop("floor_diaphragm", None); c.pop("roof_diaphragm", None)


def _seat_between_joints(c):
    c["lift_lines_x"] = [x + 220.5 for x in c["lift_lines_x"]]; c["feet_at_joints"] = False     # half a truss panel off the joint pairs
    for lg in c.get("v_legs", []): lg["dx"] = 600.0 if lg["dx"] > 0 else -600.0


def _north_095(c):
    c["build_options"].pop("gauge", None)


def _edge_100(c):
    c["build_options"]["gauge"] = {k: 1.0 for k in (c["build_options"].get("gauge") or {})}


def _single_inner_hanger(c):
    c["inner_face_sides"] = ["N"]


def _no_notch_credit(c):
    c["notch_credit"] = False


def _links_soft(c):
    c["build_options"]["link_I"] = 50.0


def _links_stiff(c):
    c["build_options"]["link_I"] = 800.0


def _joint_fixity(c):
    c["build_options"]["joint_fixity"] = 0.3


def _lining(c):
    c["lining"] = True


def _twist_out(c):
    c["twist_mode"] = "out"


VARIANTS = [
    ("A1_framed_screws", "ABLATION: no added screws or gussets (joints as framed, 2 screws)", _framed_screws),
    ("A2_no_gussets", "ABLATION: 4-screw joints but no joint gussets near the lift points", _no_gussets),
    ("A3_no_bridging", "ABLATION: no bridging line at truss mid-span (floor and roof)", _no_bridging),
    ("A4_no_plane_bracing", "ABLATION: no floor and roof plane strap bracing", _no_plane_bracing),
    ("A5_seat_between_joints", "ABLATION: lift points half a truss panel off the joint pairs, so the cradles bear between truss joints", _seat_between_joints),
    ("A6_north_trusses_095", "ABLATION: north edge trusses left at 0.95 mm (not 1.15 mm)", _north_095),
    ("A7_single_inner_hanger", "ABLATION: one hanger strap on the inside face at the north lift points (twists the edge truss)", _single_inner_hanger),
    ("A8_edge_trusses_100", "ABLATION: the three edge trusses at 1.00 mm (the thickest TRUECORE G550 listed in Indonesia), not 1.15 mm", _edge_100),
    ("S1_lining_credit", "SENSITIVITY: lining and flooring credited as restraint", _lining),
    ("S2_twist_length_out", "SENSITIVITY: twist buckling length = out-of-plane length (no credit for joint screws)", _twist_out),
    ("S3_no_notch_credit", "SENSITIVITY: no credit at lip notches for the nested member or the gusset plates (bare lipless section)", _no_notch_credit),
    ("S4_links_soft", "SENSITIVITY: panel-to-panel links 4 times softer (about 1.7 kN/mm)", _links_soft),
    ("S5_links_stiff", "SENSITIVITY: panel-to-panel links 4 times stiffer (about 28 kN/mm)", _links_stiff),
    ("S6_joint_fixity", "SENSITIVITY: truss and wall joints partly fixed in plane (fixity 0.3 instead of pinned)", _joint_fixity),
]


def _run_one(args):
    vid, label, base_path, patch_name, out_root = args
    import run_lift as RL
    cfg = json.load(open(base_path, encoding="utf-8"))
    if vid == "B0_frame_only":
        b0 = json.load(open(os.path.join(HERE, "configs", "B0_frame_only_revD.json"), encoding="utf-8"))   # the same design cases as Rev D
        b0["lift_lines_x"] = cfg["lift_lines_x"]                   # the same 8 points as the design
        cfg = b0
    else:
        dict(VARIANTS_BY_ID)[vid](cfg)
    cfg["name"] = label; cfg["only_design"] = True
    out_dir = os.path.join(out_root, vid)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = RL.run(os.path.join(ROOT, "model", "engineered"), cfg, out_dir)
    open(out_dir + ".log", "w", encoding="utf-8").write(buf.getvalue())
    e = r["out"]["envelope"]
    return dict(id=vid, name=label, members_over=e["members_over"], joints_over=e["joints_over"], links_over=e["links_over"],
                ties=e["links_tie"], max_member=round(e["max_member"], 2), max_joint=round(e["max_joint"], 2), max_link_shear=round(e.get("max_link_shear", 0.0), 2))


VARIANTS_BY_ID = [(v[0], v[2]) for v in VARIANTS]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--jobs", type=int, default=4); ap.add_argument("--only", default="")
    a = ap.parse_args()
    base = os.path.join(HERE, "configs", "revD_final.json")
    out_root = os.path.join(ROOT, "results", "ablation_revD"); os.makedirs(out_root, exist_ok=True)
    todo = [(v[0], v[1], base, v[0], out_root) for v in VARIANTS] + [("B0_frame_only", "BEFORE: Framer frame as framed (2 screws per joint), no lift parts, slings straight onto the floor edge truss bottom chords at the same 8 points", base, "", out_root)]
    if a.only: todo = [t for t in todo if t[0] in a.only.split(",")]
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        rows = list(ex.map(_run_one, todo))
    d = json.load(open(os.path.join(ROOT, "results", "revD_final", "summary.json"), encoding="utf-8"))["envelope"]
    design = dict(id="revD_final", name="Rev D.1 design (all measures)", members_over=d["members_over"], joints_over=d["joints_over"], links_over=d["links_over"],
                  ties=d["links_tie"], max_member=round(d["max_member"], 2), max_joint=round(d["max_joint"], 2), max_link_shear=round(d.get("max_link_shear", 0.0), 2))
    old = {}
    p = os.path.join(ROOT, "site", "data", "ablation.json")
    if a.only and os.path.exists(p):
        old = {r["id"]: r for r in json.load(open(p, encoding="utf-8"))}
    for r in rows: old[r["id"]] = r
    old["revD_final"] = design
    order = ["revD_final"] + [v[0] for v in VARIANTS if v[0][0] == "A"] + ["B0_frame_only"] + [v[0] for v in VARIANTS if v[0][0] == "S"]
    table = [old[k] for k in order if k in old]
    json.dump(table, open(p, "w", encoding="utf-8"), indent=1)
    json.dump(table, open(os.path.join(out_root, "ablation.json"), "w", encoding="utf-8"), indent=1)
    for r in table:
        print(f"{r['id']:24s} members>1 {r['members_over']:3d} (max {r['max_member']:.2f})  joints>1 {r['joints_over']:3d} (max {r['max_joint']:.2f})  link shear max {r['max_link_shear']:.2f}  ties {r['ties']}")


if __name__ == "__main__":
    main()
