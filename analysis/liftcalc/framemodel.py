"""Build a 3D analysis model from a Framer snapshot (model/<name>/framed.json).

What the builder does, in order:
 1. Every framed member becomes a line in 3D (panel origin + x-direction + vertical).
 2. JOINTS INSIDE A PANEL come from the engine's own data: each joint is a pair of coincident dimples (one fastener
    position, two fasteners: one through each flange face). Dimples the engine did not pair are paired here when two
    of them in the same panel coincide within `loose_tol`; these are marked `engine_validated = False`.
 3. Each member is cut into beam elements at its joints. A member that ENDS at a joint is given a pinned (or
    semi-rigid) end for bending in the panel plane; a member that runs THROUGH a joint is continuous.
 4. CONNECTIONS BETWEEN PANELS are not in the engine data. They are created by explicit rules (see `LINK_RULES`):
    members of different panels that touch (crossing or lying side by side / on top of each other) and whose types
    match a rule are joined by a short stiff link that carries force but no moment. Every link is logged.
 5. Extra members that Framer does not frame (straps, lifting hardware, diaphragm equivalents) are added from the
    project's additions file.

Conventions passed to the solver: ref = panel normal, so local y' is out of the panel plane;
Iz = major second moment (out-of-plane bending), Iy = minor (in-plane bending), in-plane end fixity = ry.
Units: N, mm.
"""
from __future__ import annotations
import json, math
from collections import defaultdict
import numpy as np
from . import sections as S
from .fea3d import Model

G_ACC = 9.80665
STEEL_E = 200000.0

# (type group A, type group B, max centreline distance mm, rule name).  Type groups are sets of (panel kind, member type).
PLATE = {"BOTTOM TRACK", "TOP TRACK"}
CHORD = {"TOP CHORD", "BOTTOM CHORD"}
VERT = {"STUD", "KING STUD", "CRIPPLE", "WEB", "POST", "JAMB"}


def profile_thickness(profile: str) -> float:
    """'C89-38-0.95' -> 0.95"""
    return float(profile.split("-")[-1])


class Built:
    """Result of build(): the solver model plus the bookkeeping needed for loads, checks and the viewer."""

    def __init__(self):
        self.model = Model()
        self.members = {}            # member id -> dict
        self.elements = []           # per solver element: dict(member, kind, s0, s1, link info)
        self.joints = {}             # joint id -> dict(node, members, fasteners, validated, panel)
        self.links = []              # inter-panel links
        self.log = []
        self.node_key = {}
        self.added_nodes = {}        # shared end nodes of added members, by coordinates

    def note(self, msg):
        self.log.append(msg)


def _unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def load_snapshot(path):
    return json.load(open(path, encoding="utf-8"))


def members_from_snapshot(snap):
    """Flat list of members with 3D geometry."""
    out = []
    for pn in snap["panels"]:
        o = np.array(pn["origin"], float); xd = _unit(np.array(pn["xdir"], float)); up = np.array([0.0, 0.0, 1.0])
        nrm = _unit(np.cross(xd, up))
        for k, m in enumerate(pn["members"]):
            a = o + xd * m["x1"] + up * m["y1"]; b = o + xd * m["x2"] + up * m["y2"]
            L = float(np.linalg.norm(b - a))
            mid = m["id"] or f"{pn['name']}#{k}"
            out.append(dict(id=mid, panel=pn["name"], kind=pn["kind"], wall=pn.get("wall_id"), mark=m["mark"], type=m["type"],
                            profile=m["profile"], t=profile_thickness(m["profile"]), a=a, b=b, L=L, dir=(b - a) / L, nrm=nrm,
                            joints=[(j["pos"], j["joint"]) for j in m["joints"]], loose=list(m.get("dimples_without_joint") or []),
                            plies=1, built_up=None, ops=[(o[0], float(o[1])) for o in (m.get("ops") or [])]))
    return out


def _seg_closest(a0, a1, b0, b1):
    """Closest points between two 3D segments. Returns (distance, s on A in [0,1], t on B in [0,1])."""
    u, v, w = a1 - a0, b1 - b0, a0 - b0
    a, b, c, d, e = u.dot(u), u.dot(v), v.dot(v), u.dot(w), v.dot(w)
    D = a * c - b * b
    sN, sD, tN, tD = 0.0, D, 0.0, D
    if D < 1e-9 * a * c:                 # parallel
        sN, sD, tN, tD = 0.0, 1.0, e, c
    else:
        sN, tN = (b * e - c * d), (a * e - b * d)
        if sN < 0: sN, tN, tD = 0.0, e, c
        elif sN > sD: sN, tN, tD = sD, e + b, c
    if tN < 0:
        tN = 0.0
        if -d < 0: sN = 0.0
        elif -d > a: sN = sD
        else: sN, sD = -d, a
    elif tN > tD:
        tN = tD
        if (-d + b) < 0: sN = 0.0
        elif (-d + b) > a: sN = sD
        else: sN, sD = (-d + b), a
    s = 0.0 if abs(sN) < 1e-12 else sN / sD
    t = 0.0 if abs(tN) < 1e-12 else tN / tD
    return float(np.linalg.norm(w + s * u - t * v)), s, t


DEFAULT_OPTIONS = dict(
    steel_E=STEEL_E,
    corner_ri=0.0,                 # sharp-cornered section properties, as the engine weighs them
    joint_fixity=0.0,              # in-plane end fixity of a member that ends at a joint: 0 pinned ... 1 rigid
    stub_max=60.0,                 # an end stub shorter than this beyond the last joint is not modelled (its weight is kept)
    loose_tol=6.0,                 # pair unvalidated dimples closer than this
    link_tol=48.0,                 # members of different panels closer than this (centreline to centreline) can be linked
    link_spacing=600.0,            # spacing of links along members that lie side by side / on top of each other
    link_A=400.0, link_I=200.0, link_J=200.0,
    # A link stands for a small group of screws through two members in contact. It is stiff along its axis; its bending
    # stiffness is set so that a 41 mm link has a shear stiffness of about 7 kN/mm and a rotational stiffness of about
    # 4 kNm/rad, the order of two 10 gauge screws 60 mm apart. Both ends are rigidly attached, so a link passes a small
    # moment, which is what stops a truss standing on two links from rolling over.
    fasteners_per_joint=2,
)


def build(snap, options=None, additions=None, link_rules=None):
    """Build the model. Returns a Built object (not yet loaded or supported)."""
    opt = dict(DEFAULT_OPTIONS); opt.update(options or {})
    B = Built(); M = B.model
    mem = members_from_snapshot(snap)
    for m in mem:                                   # a heavier gauge for a whole panel or one member type in it (rolled so in Framer)
        g = opt.get("gauge") or {}
        t_ = g.get(f'{m["panel"]}|{m["type"]}', g.get(m["panel"]))
        if t_:
            m["t"] = float(t_); m["profile"] = m["profile"].rsplit("-", 1)[0] + f"-{float(t_):.2f}"
    for m in mem:                                   # members strengthened outside Framer (e.g. a flat bar screwed to a chord): built-up
        bu = (opt.get("built_up") or {}).get(f'{m["panel"]}|{m["type"]}')
        if bu: m["built_up"] = bu
    for m in (additions or {}).get("members", []):
        a, b = np.array(m["a"], float), np.array(m["b"], float)
        nrm = _unit(np.array(m.get("nrm", [0.0, 1.0, 0.0]), float))
        mem.append(dict(id=m["id"], panel=m.get("panel", "ADD"), kind=m.get("kind", "added"), wall=None, mark=m.get("mark", m["id"]),
                        type=m.get("type", "ADDED"), profile=m.get("profile", "custom"), t=m.get("t", 0.0), a=a, b=b,
                        L=float(np.linalg.norm(b - a)), dir=_unit(b - a), nrm=nrm, joints=[], loose=[], plies=m.get("plies", 1),
                        built_up=m.get("built_up"), props=m.get("props"), pinned=m.get("pinned", False), added=True,
                        stations=list(m.get("stations", [])), attach=m.get("attach"), no_weight=m.get("no_weight", False),
                        role=m.get("role", ""), rigid=m.get("rigid", False), cradle=m.get("cradle"), temporary=m.get("temporary", False),
                        compression_only=m.get("compression_only", False), release_inplane=m.get("release_inplane", ""), ops=[]))
    byid = {m["id"]: m for m in mem}
    B.members = byid
    bypanel = defaultdict(list)
    for m in mem: bypanel[m["panel"]].append(m)

    # ---- joints from the engine, plus pairing of loose dimples
    jmap = defaultdict(list)                                   # joint id -> [(member id, s)]
    for m in mem:
        for s, jid in m["joints"]:
            jmap[jid].append((m["id"], s))
    n_loose = 0
    for pname, ms in bypanel.items():
        pts = [(m, s, m["a"] + m["dir"] * s) for m in ms for s in m["loose"]]
        used = set()
        for i in range(len(pts)):
            if i in used: continue
            for j in range(i + 1, len(pts)):
                if j in used or pts[i][0] is pts[j][0]: continue
                if np.linalg.norm(pts[i][2] - pts[j][2]) <= opt["loose_tol"]:
                    jid = f"LOOSE-{pname}-{n_loose}"; n_loose += 1
                    jmap[jid] = [(pts[i][0]["id"], pts[i][1]), (pts[j][0]["id"], pts[j][1])]
                    used.add(i); used.add(j); break
    B.note(f"joints from engine: {len(jmap) - n_loose}; loose dimples paired here (not validated by the engine): {n_loose}")

    # ---- stations per member
    stations = defaultdict(list)                               # member id -> [(s, node key)]
    for jid, lst in jmap.items():
        if len(lst) < 2: continue
        P = np.mean([byid[mid]["a"] + byid[mid]["dir"] * s for mid, s in lst], axis=0)
        nd = M.node(*P)
        B.joints[jid] = dict(node=nd, members=[mid for mid, _ in lst], fasteners=opt["fasteners_per_joint"],
                             validated=not jid.startswith("LOOSE-"), panel=byid[lst[0][0]]["panel"], xyz=P.tolist())
        for mid, s in lst:
            stations[mid].append((s, nd, jid))
    for m in mem:                                                # distance from each joint's screws to the member end
        for pos, jid in m.get("joints") or []:
            if jid in B.joints:
                B.joints[jid].setdefault("edist", {})[m["id"]] = float(min(pos, m["L"] - pos))
    for m in mem:                                                # stations requested for added members
        for s in m.get("stations", []):
            stations[m["id"]].append((float(s), None, "ADD"))
    return _finish(B, mem, byid, stations, opt, additions or {}, link_rules)


def _member_props(m, opt):
    """Section properties (A, I_major, I_minor, J) of a member, allowing built-up plies."""
    if m.get("props"):
        p = m["props"]; return p["A"], p["I_major"], p["I_minor"], p["J"], p.get("kg_m", p["A"] * 7.85e-3)
    s = S.c89(m["t"], opt["corner_ri"])
    if m.get("built_up") in ("b2b", "boxed"):
        bu = S.BuiltUp(m["built_up"], s)
        return bu.A, bu.Ix, bu.Iy, bu.J, bu.kg_per_m
    n = m.get("plies", 1)
    return n * s.A, n * s.Ix, n * s.Iy, n * s.J, n * s.kg_per_m


def _node_on(B, m, s, stations, tol=3.0):
    """Node on member m at distance s from its start; reuse a station within tol, else create one."""
    lst = stations[m["id"]]
    for (s0, nd, _) in lst:
        if abs(s0 - s) <= tol and nd is not None:
            return nd
    P = m["a"] + m["dir"] * s
    nd = B.model.node(*P)
    lst.append((s, nd, "LINK"))
    return nd


def default_link_rules():
    """Pairs of (panel kind, member type) that are fastened together where they touch. `tol` = largest centreline distance
    (mm) at which the pair counts as touching (default: options['link_tol'])."""
    R = []
    def add(name, ka, ta, kb, tb, tol=None): R.append(dict(name=name, ka=set(ka), ta=set(ta), kb=set(kb), tb=set(tb), tol=tol))
    wall = {"wall"}
    add("wall bottom track on floor rim / end floor truss", wall, {"BOTTOM TRACK"}, {"rim_truss", "floor_truss"}, {"TOP CHORD"})
    add("wall top track under roof rim / end roof truss", wall, {"TOP TRACK"}, {"roof_rim", "roof_truss"}, {"BOTTOM CHORD"})
    add("floor truss chord end to floor rim chord", {"floor_truss"}, CHORD, {"rim_truss"}, CHORD)
    add("roof truss chord end to roof rim chord", {"roof_truss"}, CHORD, {"roof_rim"}, CHORD)
    add("wall top track to roof blocking", wall, {"TOP TRACK"}, {"roof_blocking"}, {"BOTTOM CHORD", "WEB"})
    add("roof blocking to roof truss", {"roof_blocking"}, {"WEB", "TOP CHORD", "BOTTOM CHORD"}, {"roof_truss"}, {"WEB", "TOP CHORD", "BOTTOM CHORD"})
    add("wall panel to wall panel (seam studs, corner studs, stacked tracks)", wall, VERT | PLATE | {"HEADER"}, wall, VERT | PLATE | {"HEADER"}, tol=72.0)
    return R


def _rule_for(rules, ma, mb):
    for r in rules:
        if ma["kind"] in r["ka"] and ma["type"] in r["ta"] and mb["kind"] in r["kb"] and mb["type"] in r["tb"]:
            return r
        if mb["kind"] in r["ka"] and mb["type"] in r["ta"] and ma["kind"] in r["kb"] and ma["type"] in r["tb"]:
            return r
    return None


def _finish(B, mem, byid, stations, opt, additions, link_rules):
    M = B.model
    rules = link_rules if link_rules is not None else default_link_rules()
    # ---- added members: attach each end to the framed member it sits on (shared node = a direct pinned connection)
    n_att = 0
    for m in mem:
        att = m.get("attach")
        if not att: continue
        targets = [("a", m["a"], 0.0, att.get("a")), ("b", m["b"], m["L"], att.get("b"))]
        for k_mid, spec in enumerate(att.get("mid", [])):            # attachments part-way along the added member
            targets.append((f"mid{k_mid}", m["a"] + m["dir"] * float(spec["s"]), float(spec["s"]), spec))
        for end, P, s_end, spec in targets:
            if not spec: continue
            best = (1e18, None, 0.0)
            for t in mem:
                if t is m or t.get("added"): continue
                if spec.get("kinds") and t["kind"] not in spec["kinds"]: continue
                if spec.get("types") and t["type"] not in spec["types"]: continue
                st = float(np.clip((P - t["a"]).dot(t["dir"]), 0.0, t["L"]))
                dist = float(np.linalg.norm(t["a"] + t["dir"] * st - P))
                if dist < best[0]: best = (dist, t, st)
            if best[1] is None or best[0] > spec.get("tol", 30.0):
                raise ValueError(f"added member {m['id']}: nothing to attach end {end} to within {spec.get('tol', 30.0)} mm (nearest {best[0]:.0f} mm)")
            nd = _node_on(B, best[1], best[2], stations, tol=spec.get("snap", 3.0))
            stations[m["id"]].append((s_end, nd, "ATTACH")); n_att += 1
            m.setdefault("attached_to", {})[end] = best[1]["id"]
    if n_att: B.note(f"added-member ends attached to framed members: {n_att}")

    # ---- inter-panel links by rule
    tol = opt["link_tol"]
    tmax = max([tol] + [r["tol"] for r in rules if r.get("tol")])
    A0 = np.array([m["a"] for m in mem]); A1 = np.array([m["b"] for m in mem])
    lo = np.minimum(A0, A1) - tmax; hi = np.maximum(A0, A1) + tmax
    near_miss = []
    link_specs = []
    for i in range(len(mem)):
        ma = mem[i]
        cand = np.nonzero(np.all(lo[i] <= hi[i + 1:], axis=1) & np.all(hi[i] >= lo[i + 1:], axis=1))[0] + i + 1
        for j in cand:
            mb = mem[j]
            if ma["panel"] == mb["panel"]: continue
            r_ = _rule_for(rules, ma, mb)
            d, s, t = _seg_closest(ma["a"], ma["b"], mb["a"], mb["b"])
            if d > ((r_ or {}).get("tol") or tol): continue
            if r_ is None:
                near_miss.append((ma["panel"], ma["type"], mb["panel"], mb["type"], round(d, 1)))
                continue
            rule = r_["name"]
            par = abs(float(ma["dir"].dot(mb["dir"])))
            if par > 0.999:                                    # side by side or stacked: links along the overlap
                ta = sorted(((mb["a"] - ma["a"]).dot(ma["dir"]), (mb["b"] - ma["a"]).dot(ma["dir"])))
                s0, s1 = max(0.0, ta[0]), min(ma["L"], ta[1])
                if s1 - s0 < 20.0:
                    link_specs.append((ma, s * ma["L"], mb, t * mb["L"], rule, d)); continue
                n = max(2, int(math.ceil((s1 - s0) / opt["link_spacing"])) + 1)
                for k in range(n):
                    sa = s0 + (s1 - s0) * (k + 0.5) / n if n > 2 else (s0 + 25.0 if k == 0 else s1 - 25.0)
                    Pa = ma["a"] + ma["dir"] * sa
                    sb = float(np.clip((Pa - mb["a"]).dot(mb["dir"]), 0.0, mb["L"]))
                    link_specs.append((ma, sa, mb, sb, rule, d))
            else:
                link_specs.append((ma, s * ma["L"], mb, t * mb["L"], rule, d))
    for (ma, sa, mb, sb, rule, d) in link_specs:
        na = _node_on(B, ma, sa, stations); nb = _node_on(B, mb, sb, stations)
        if na == nb: continue
        if np.linalg.norm(np.array(M.xyz[na]) - np.array(M.xyz[nb])) < 1e-6:
            continue
        B.links.append(dict(a=ma["id"], b=mb["id"], na=na, nb=nb, rule=rule, gap=round(d, 2)))
    # ---- truss ends on a rim truss: the end vertical of the truss is screwed to the rim. The two chord links alone would pass
    # the end reaction only by twisting the thin rim chord (not real). Two pinned diagonal ties per truss end carry the vertical
    # reaction as a direct force into the rim chords, which is what the screws through the end vertical do.
    grp = defaultdict(list)
    for lk in B.links:
        if "truss chord end to" not in lk["rule"]: continue
        ma, mb = byid[lk["a"]], byid[lk["b"]]
        tr, rm = (ma, mb) if ma["kind"] in ("floor_truss", "roof_truss") else (mb, ma)
        nt, nr = (lk["na"], lk["nb"]) if tr is ma else (lk["nb"], lk["na"])
        grp[(tr["panel"], rm["panel"])].append((M.xyz[nt][2], nt, nr, tr["id"], rm["id"], lk["rule"]))
    n_diag = 0
    for key, lst in grp.items():
        lst.sort()
        lo, hi = lst[0], lst[-1]
        if hi[0] - lo[0] < 100.0: continue
        for (tn, tid), (rn, rid) in (((hi[1], hi[3]), (lo[2], lo[4])), ((lo[1], lo[3]), (hi[2], hi[4]))):
            B.links.append(dict(a=tid, b=rid, na=tn, nb=rn, rule="truss end vertical screwed to the rim (end reaction)", gap=0.0, diag=True)); n_diag += 1
    if n_diag: B.note(f"truss-end reaction ties added: {n_diag}")
    B.note(f"inter-panel links created: {len(B.links)}; pairs within tolerance with no rule (not connected): {len(near_miss)}")
    B.near_miss = near_miss

    # ---- elements per member
    # Station tags: a joint id (member meets another member of its own panel there), "LINK" (inter-panel link),
    # "ADD" (requested station on an added member) or "FREE" (free end of a stub that sticks out past the last joint).
    fix = opt["joint_fixity"]
    for m in mem:
        A, Imaj, Imin, J, kgm = _member_props(m, opt)
        m["A"], m["I_major"], m["I_minor"], m["J"], m["kg_m"] = A, Imaj, Imin, J, kgm
        st = sorted(stations[m["id"]], key=lambda x: x[0])
        merged = []                                              # merge stations closer than 1 mm
        for s_, nd, tag in st:
            tag = tag or "LINK"
            if merged and abs(s_ - merged[-1][0]) < 1.0:
                if merged[-1][1] is None and nd is not None: merged[-1] = (merged[-1][0], nd, tag)
                continue
            merged.append((s_, nd, tag))
        def _nd(P):
            # free ends of ADDED members that meet at the same point share one node (strap legs meeting at a lifting head)
            if not m.get("added"): return M.node(*P)
            key = tuple(round(float(v), 1) for v in P)
            if key not in B.added_nodes: B.added_nodes[key] = M.node(*P)
            return B.added_nodes[key]
        st = [(s_, nd if nd is not None else _nd(m["a"] + m["dir"] * s_), tag) for s_, nd, tag in merged]
        if not st:
            B.note(f"member {m['panel']} {m['mark']} ({m['type']}) has no joint and no link: left out of the model")
            m["nodes"] = []; m["elements"] = []; m["in_model"] = False; continue
        if st[0][0] > opt["stub_max"]:
            st.insert(0, (0.0, _nd(m["a"]), "FREE"))
        if m["L"] - st[-1][0] > opt["stub_max"]:
            st.append((m["L"], _nd(m["b"]), "FREE"))
        m["nodes"] = [(s_, nd) for s_, nd, _ in st]
        m["tags"] = [(s_, str(tag)) for s_, _, tag in st]
        m["elements"] = []; m["in_model"] = True
        if len(st) < 2:
            B.note(f"member {m['panel']} {m['mark']} ({m['type']}) touches the model at one point only: carried as weight, no stiffness")
            continue
        for k in range(len(st) - 1):
            (s0, n0, t0), (s1, n1, t1) = st[k], st[k + 1]
            if n0 == n1: continue
            # the member ENDS at its first and last station: pinned in the panel plane there unless that end is a free stub end
            r0 = 1.0 if (k > 0 or t0 == "FREE") else fix
            r1 = 1.0 if (k < len(st) - 2 or t1 == "FREE") else fix
            rz = (0.0 if (m.get("pinned") and k == 0) else 1.0, 0.0 if (m.get("pinned") and k == len(st) - 2) else 1.0)
            if m.get("pinned"):
                r0 = 0.0 if k == 0 else 1.0; r1 = 0.0 if k == len(st) - 2 else 1.0
            if m.get("rigid"): r0 = r1 = 1.0
            rel = m.get("release_inplane") or ""                   # a bearing seat: no bending in the panel plane at that end
            if "a" in rel and k == 0: r0 = 0.0
            if "b" in rel and k == len(st) - 2: r1 = 0.0
            e = M.beam(n0, n1, A, Imin, Imaj, J, E=m.get("E", opt["steel_E"]), ref=tuple(m["nrm"]), ry=(r0, r1), rz=rz,
                       torsion_release=bool(m.get("pinned")), tag=m["id"])
            B.elements.append(dict(member=m["id"], kind="member", s0=s0, s1=s1))
            m["elements"].append(e)
    # ---- link elements
    for lk in B.links:
        if lk.get("diag"):
            e = M.beam(lk["na"], lk["nb"], opt["link_A"], 1.0, 1.0, 1.0, E=opt["steel_E"], ref=(0.577, 0.577, 0.577), ry=(0.0, 0.0), rz=(0.0, 0.0),
                       torsion_release=True, tag="LINK")
        else:
            e = M.beam(lk["na"], lk["nb"], opt["link_A"], opt["link_I"], opt["link_I"], opt["link_J"], E=opt["steel_E"],
                       ref=(0.577, 0.577, 0.577), tag="LINK")
        lk["element"] = e
        B.elements.append(dict(member=None, kind="link", rule=lk["rule"]))
    # ---- every node needs in-plane rotational stiffness from at least one element: un-pin one if a node has none
    _stabilise_rotations(B)
    return B


def _stabilise_rotations(B):
    """If all elements meeting at a node are pinned there for in-plane bending, make the first member element rigid at
    that node (a real joint always has some rotational stiffness; this only removes a numerical mechanism)."""
    M = B.model
    stiff = defaultdict(int); cand = defaultdict(list)
    for idx, e in enumerate(M.el):
        for end, nd in ((0, e["i"]), (1, e["j"])):
            if e["ry"][end] > 1e-9 and e["Iy"] > 0: stiff[nd] += 1
            else: cand[nd].append((idx, end))
    fixed = 0
    for nd, lst in cand.items():
        if stiff[nd] == 0:
            for idx, end in lst:
                if B.elements[idx]["kind"] == "member":
                    ry = list(M.el[idx]["ry"]); ry[end] = 1.0; M.el[idx]["ry"] = tuple(ry); fixed += 1; break
    if fixed:
        B.note(f"nodes where every member was pinned: {fixed} (one member made continuous there to avoid a mechanism)")
