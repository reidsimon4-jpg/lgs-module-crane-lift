"""Itemised mass model of the finished module and its application to the frame model as nodal loads.

The mass model is a plain JSON file (model/mass_model.json):
  area items (kg/m2) for the roof, ceiling, floor and walls, each with its source;
  openings (windows per m2, doors each); lump items at given positions; the steel frame itself comes from the model.
`apply()` turns all of it into vertical nodal forces on a framemodel.Built and returns a ledger (item by item, with the
centre of gravity) so the total can be audited against the sum of reactions.
Units: kg, mm, N.
"""
from __future__ import annotations
import json, math
from collections import defaultdict
import numpy as np

G_ACC = 9.80665
VERTICAL_TYPES = {"STUD", "KING STUD", "CRIPPLE", "POST", "JAMB"}


def load_mass_model(path):
    return json.load(open(path, encoding="utf-8"))


def _spread_on_member(B, m, total_kg, out):
    """Spread a mass uniformly along a member onto its model nodes (tributary lengths)."""
    nodes = m.get("nodes") or []
    if not nodes:
        return False
    if len(nodes) == 1:
        out[nodes[0][1]] += total_kg; return True
    s = [x[0] for x in nodes]
    L = m["L"]
    for k, (sk, nd) in enumerate(nodes):
        left = 0.0 if k == 0 else (s[k - 1] + sk) / 2
        right = L if k == len(nodes) - 1 else (sk + s[k + 1]) / 2
        out[nd] += total_kg * (right - left) / L
    return True


def wall_areas(project):
    """Net face area (m2), opening areas and counts per wall id from the Framer project file."""
    out = {}
    for w in project.get("walls", []):
        L = math.hypot(w["end"][0] - w["start"][0], w["end"][1] - w["start"][1]) / 1000.0
        H = w.get("height", 2700.0) / 1000.0
        win = sum(o["width"] * o["height"] for o in w.get("openings", []) if o.get("kind") == "window") / 1e6
        doors = [o for o in w.get("openings", []) if o.get("kind") == "door"]
        dr = sum(o["width"] * o["height"] for o in doors) / 1e6
        out[w["id"]] = dict(length=L, height=H, gross=L * H, window_m2=win, door_m2=dr, n_doors=len(doors), net=max(L * H - win - dr, 0.0))
    return out


def apply(B, mm, project, case="G", scale=1.0):
    """Add gravity loads for the whole mass model to load case `case` of B.model. Returns the ledger."""
    M = B.model
    node_kg = defaultdict(float)
    ledger = []

    def book(name, group, kg, cg=None, note=""):
        ledger.append(dict(item=name, group=group, kg=kg, note=note))

    # 1. steel frame (every member, including those that are not in the stiffness model: their weight still hangs somewhere)
    steel = 0.0; orphan = 0.0
    for m in B.members.values():
        kg = m["kg_m"] * m["L"] / 1000.0
        if m.get("no_weight"):
            continue
        if _spread_on_member(B, m, kg, node_kg): steel += kg
        else: orphan += kg
    book("Steel frame (from the framed model)", "frame", steel)
    if orphan > 0:
        book("Steel of members with no joint (spread over the frame)", "frame", orphan, note="members the engine left unconnected")

    # 2. area items on trusses, by tributary width
    def truss_lines(kind, mtype):
        """Members of the given type grouped by panel, with the panel's position across the truss run."""
        ms = [m for m in B.members.values() if m["kind"] == kind and m["type"] == mtype and m.get("nodes")]
        if not ms: return []
        run = np.cross(ms[0]["dir"], [0, 0, 1.0]); run = run / max(np.linalg.norm(run), 1e-9)     # direction across the trusses
        bypanel = defaultdict(list)
        for m in ms: bypanel[m["panel"]].append(m)
        rows = [(float(np.mean([(mm_["a"] + mm_["b"]).dot(run) / 2 for mm_ in v])), v) for v in bypanel.values()]
        rows.sort(key=lambda r: r[0])
        return rows

    def spread_area(group, target_kind, target_type, kg_m2, edge=None):
        rows = truss_lines(target_kind, target_type)
        if not rows or kg_m2 <= 0: return 0.0
        pos = [r[0] for r in rows]
        lo = edge[0] if edge else pos[0]; hi = edge[1] if edge else pos[-1]
        total = 0.0
        for k, (p, ms) in enumerate(rows):
            left = lo if k == 0 else (pos[k - 1] + p) / 2
            right = hi if k == len(rows) - 1 else (p + pos[k + 1]) / 2
            trib = max(right - left, 0.0) / 1000.0
            Lh = sum(math.hypot(m["b"][0] - m["a"][0], m["b"][1] - m["a"][1]) for m in ms) / 1000.0     # horizontal run
            for m in ms:
                lh = math.hypot(m["b"][0] - m["a"][0], m["b"][1] - m["a"][1]) / 1000.0
                kg = kg_m2 * trib * lh
                _spread_on_member(B, m, kg, node_kg); total += kg
        return total

    ext = mm.get("extents", {})
    for it in mm["area_items"].get("roof", []):
        book(it["name"], "roof", spread_area("roof", "roof_truss", "TOP CHORD", it["kg_m2"] * scale_item(it), ext.get("x")), note=it.get("source", ""))
    for it in mm["area_items"].get("ceiling", []):
        book(it["name"], "ceiling", spread_area("ceiling", "roof_truss", "BOTTOM CHORD", it["kg_m2"] * scale_item(it), ext.get("x")), note=it.get("source", ""))
    for it in mm["area_items"].get("floor", []):
        book(it["name"], "floor", spread_area("floor", "floor_truss", "TOP CHORD", it["kg_m2"] * scale_item(it), ext.get("x")), note=it.get("source", ""))

    # 3. walls: lining, cladding and insulation on the net face area, hung on the vertical members of that wall
    WA = wall_areas(project)
    wall_unit = defaultdict(float)
    for it in mm["area_items"].get("wall", []):
        for wid in WA:
            if it.get("walls") and wid not in it["walls"]: continue
            wall_unit[(wid, it["name"])] = it["kg_m2"] * scale_item(it)
    per_item = defaultdict(float)
    for wid, A in WA.items():
        verts = [m for m in B.members.values() if m["kind"] == "wall" and m.get("wall") == wid and m["type"] in VERTICAL_TYPES and m.get("nodes")]
        if not verts: continue
        Ltot = sum(m["L"] for m in verts)
        kg_wall = 0.0
        for (w2, name), u in wall_unit.items():
            if w2 != wid: continue
            kg = u * A["net"]; per_item[name] += kg; kg_wall += kg
        op = mm.get("openings", {})
        kg_win = op.get("window_kg_m2", 0.0) * A["window_m2"]
        kg_door = op.get("door_kg_each", 0.0) * A["n_doors"] if A["door_m2"] < 6.0 or op.get("count_wide_openings_as_doors") else 0.0
        per_item["Windows"] += kg_win; per_item["Doors"] += kg_door
        for m in verts:
            _spread_on_member(B, m, (kg_wall + kg_win + kg_door) * m["L"] / Ltot, node_kg)
    for name, kg in per_item.items():
        if kg > 0: book(name, "walls", kg)

    # 4. lump items at the nearest floor-level node
    xyz = np.array(M.xyz)
    used = np.array(sorted({nd for m in B.members.values() for _, nd in (m.get("nodes") or [])}))
    for it in mm.get("lumps", []):
        P = np.array(it["at"], float)
        nd = int(used[np.argmin(np.linalg.norm(xyz[used] - P, axis=1))])
        node_kg[nd] += it["kg"]; book(it["name"], "fit-out", it["kg"], note=it.get("source", ""))

    # totals, centre of gravity, scaling to the rated mass
    base = sum(node_kg.values())
    k = scale
    if mm.get("rated_lift_mass_kg"):
        k = mm["rated_lift_mass_kg"] / base
    cg = sum(np.array(M.xyz[nd]) * kg for nd, kg in node_kg.items()) / base
    for nd, kg in node_kg.items():
        M.load(case, nd, 2, -kg * k * G_ACC)
    return dict(ledger=ledger, itemised_kg=base, factor_to_rated=k, applied_kg=base * k, cg=cg.tolist(), node_kg={int(n): v * k for n, v in node_kg.items()})


def scale_item(it):
    return float(it.get("factor", 1.0))
