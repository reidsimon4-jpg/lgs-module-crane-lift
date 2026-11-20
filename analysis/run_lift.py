"""Run the lift analysis of a framed module and write the results.

usage: python analysis/run_lift.py <model folder> <config.json> <results folder>

The config names the lift lines, the added (non-Framer) parts, the lifting factors and the rig cases.
Every case is solved on the same stiffness model. Member, joint and link checks are made at the factored
(ultimate) level; deflections and sling loads are reported at the rated mass with no factor.
"""
from __future__ import annotations
import sys, os, json, time
from collections import defaultdict, Counter
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liftcalc import framemodel as F, masses as MS, liftcase as LC, as4600 as C  # noqa: E402


# ------------------------------------------------------------------------------------------------ added parts
def _pitch(L, p):
    """Interior stations at pitch p along a length L (the plate is screwed to the chord at these points)."""
    n = max(1, int(round(L / p)))
    return [L * k / n for k in range(1, n)]


def additions_from_config(cfg):
    """Parts that Infinity Framer does not frame: hanger straps, lifting heads, stirrups under the floor rim, plane bracing."""
    out = []
    lines = cfg["lift_lines_x"]; ys = cfg["rim_y"]
    zb, zt = cfg["floor_rim_z"]; zr = cfg["roof_rim_top_z"]; zh = cfg["head_z"]
    hg = cfg["hanger"]; st = cfg["stirrup"]; gd = cfg["guide"]

    def rim(types):
        return {"kinds": ["rim_truss"], "types": [types], "tol": 60.0, "snap": 3.0}

    def strap(i, P, Q, role, A, kgm, typ="STRAP", label=None, temporary=False):
        out.append(dict(id=i, kind="added", type=typ, profile=label or hg["label"], a=P, b=Q, nrm=[0.0, 1.0, 0.0], temporary=temporary,
                        props=dict(A=A, I_major=10.0, I_minor=10.0, J=10.0, kg_m=kgm), pinned=True, role=role, attach={"a": rim("BOTTOM CHORD")}))

    def stirrup(i, x, y, role, half=None, temporary=False):
        """A cradle / foot bracket: two plates (one on each face of the rim truss) screwed to both chords over a length 2 x half.
        Modelled as a stiff panel: bottom and top members along the chords (attached to them at the ends and the centre),
        end and centre verticals and two diagonals. The strap connects at the centre of the bottom member."""
        h = float(half if half is not None else cfg.get("cradle_half", 300.0))
        pr = dict(A=st["A"], I_major=st["I_major"], I_minor=st["I_minor"], J=st["J"], kg_m=st["kg_m"])
        common = dict(kind="added", profile=st["label"], nrm=[0.0, 1.0, 0.0], role=role, cradle=i, temporary=temporary)
        if h <= 1.0:
            out.append(dict(id=i, type="STIRRUP", a=[x, y, zb], b=[x, y, zt], props=pr, pinned=True,
                            attach={"a": rim("BOTTOM CHORD"), "b": rim("TOP CHORD")}, **common)); return
        Lr = cfg.get("length", 12000.0)
        x0, x1 = x - h, x + h
        if x0 < 25.0: x0, x1 = 25.0, 25.0 + 2.0 * h                       # plate kept on the rim: shifted inwards at the ends
        if x1 > Lr - 25.0: x0, x1 = Lr - 25.0 - 2.0 * h, Lr - 25.0
        thin = dict(pr, kg_m=0.0)                                          # the plate mass is booked once, on the centre member
        out.append(dict(id=i, type="STIRRUP", a=[x, y, zb], b=[x, y, zt], props=dict(pr, kg_m=st["kg_m"] * (1.0 + 4.0 * h / (zt - zb))), pinned=True,
                        attach={"a": rim("BOTTOM CHORD"), "b": rim("TOP CHORD")}, **common))
        for nm, P, Q, typ in (("B", [x0, y, zb], [x1, y, zb], "BOTTOM CHORD"), ("T", [x0, y, zt], [x1, y, zt], "TOP CHORD")):
            mids = sorted(set([round(v, 1) for v in _pitch(x1 - x0, cfg.get("cradle_screw_pitch", 100.0))] + [round(x - x0, 1)]))
            mids = [v for v in mids if 1.0 < v < (x1 - x0) - 1.0]
            out.append(dict(id=f"{i}_{nm}", type="CRADLE", a=P, b=Q, props=thin, rigid=True,
                            attach={"a": rim(typ), "b": rim(typ), "mid": [dict(rim(typ), s=ss) for ss in mids]}, **common))
        for nm, xx in (("L", x0), ("R", x1)):
            out.append(dict(id=f"{i}_{nm}", type="CRADLE", a=[xx, y, zb], b=[xx, y, zt], props=thin, pinned=True,
                            attach={"a": rim("BOTTOM CHORD"), "b": rim("TOP CHORD")}, **common))
        xc = min(max(x, x0 + 50.0), x1 - 50.0)
        for nm, P, Q in (("D1", [x0, y, zb], [xc, y, zt]), ("D2", [x1, y, zb], [xc, y, zt]), ("D3", [x0, y, zt], [xc, y, zb]), ("D4", [x1, y, zt], [xc, y, zb])):
            out.append(dict(id=f"{i}_{nm}", type="CRADLE", a=P, b=Q, props=thin, pinned=True,
                            attach={"a": rim("BOTTOM CHORD" if P[2] == zb else "TOP CHORD"), "b": rim("BOTTOM CHORD" if Q[2] == zb else "TOP CHORD")}, **common))

    for side, y in (ys.items() if not cfg.get("no_lift_parts") else []):
        for k, x in enumerate(lines, 1):
            tag = f"{side}{k}"
            strap(f"HANG_{tag}", [x, y, zb], [x, y, zh], f"hanger strap pair, lift point {tag}", hg["A"], hg["kg_m"])
            stirrup(f"STIR_{tag}", x, y, f"cradle under the floor rim (folded plate pair, 600 long), lift point {tag}")
            zrb = cfg["roof_rim_bot_z"]
            # the head bracket clamps the roof rim over its full depth (cheeks screwed to both chords through vertical slots):
            # it holds the head sideways and along the module, and carries no vertical load into the roof rim
            out.append(dict(id=f"GUIDE_{tag}", kind="added", type="GUIDE", profile=gd["label"], a=[x, y, zrb], b=[x, y, zh], nrm=[0.0, 1.0, 0.0],
                            props=dict(A=gd["A"], I_major=gd["I"], I_minor=gd["I"], J=gd["I"], kg_m=gd["kg_m"]), rigid=True,
                            role=f"lifting head bracket on the roof rim (sideways restraint only), lift point {tag}",
                            attach={"a": {"kinds": ["roof_rim"], "types": ["BOTTOM CHORD"], "tol": 60.0, "snap": 3.0},
                                    "mid": [{"s": zr - zrb, "kinds": ["roof_rim"], "types": ["TOP CHORD"], "tol": 60.0, "snap": 3.0}]}))
            legs = [lg for lg in cfg.get("v_legs", []) if lg["side"] == side and lg["line"] == k]
            if not legs:
                dx = (cfg.get("v_straps") or {}).get(side)
                if dx and k not in (cfg.get("v_strap_skip") or {}).get(side, []):
                    legs = [dict(dx=-dx), dict(dx=dx)]
            for lg in legs:
                if True:
                    sgn, nm = (1, "b") if lg["dx"] > 0 else (-1, "a"); xf = x + lg["dx"]
                    if xf < 60.0 or xf > cfg.get("length", 12000.0) - 60.0:
                        continue                                           # no room for this leg (it would land past the module end)
                    tmp = bool(lg.get("temporary"))
                    strap(f"VSTR_{tag}{nm}", [xf, y, zb], [x, y, zh], f"inclined hanger strap pair, lift point {tag}" + (" (TEMPORARY, removed after set-down)" if tmp else ""),
                          cfg["v_strap"]["A"], cfg["v_strap"]["kg_m"], "V-STRAP", cfg["v_strap"].get("label"), temporary=tmp)
                    stirrup(f"VFOOT_{tag}{nm}", xf, y, f"foot plates of the inclined strap, lift point {tag}" + (" (TEMPORARY, bolted, removed after set-down)" if tmp else ""),
                            half=cfg.get("foot_half", 100.0), temporary=tmp)
    for dname in ("floor_diaphragm", "roof_diaphragm"):
        dp = cfg.get(dname)
        if not dp: continue
        xs = dp["x_stations"]; z = dp["z"]; kinds = dp["attach_kinds"]
        for i in range(len(xs) - 1):
            for tag, (ya, yb) in (("a", (ys["S"], ys["N"])), ("b", (ys["N"], ys["S"]))):
                att = {"kinds": kinds, "types": ["TOP CHORD"], "tol": 60.0, "snap": 25.0}
                out.append(dict(id=f"{dname[:1].upper()}DIA_{i}{tag}", kind="added", type="PLANE BRACE", profile=dp["label"], a=[xs[i], ya, z], b=[xs[i + 1], yb, z],
                                nrm=[0.0, 0.0, 1.0], props=dict(A=dp["A_eq"], I_major=1.0, I_minor=1.0, J=1.0, kg_m=dp.get("kg_m", 0.4)), pinned=True, role=dp["label"],
                                attach={"a": att, "b": dict(att)}))
    for m in cfg.get("extra_members", []):
        out.append(m)
    return out



C89 = dict(A=170.2, I_major=216189.0, I_minor=33146.0, J=51.2, kg_m=1.336)


def truss_x(proj, tag):
    """x of every truss of one cassette ('F' floor, 'R' roof) from the Framer project (end trusses and the array)."""
    els = {e["id"]: e for e in proj.get("elements", [])}
    xs = [els[f"{tag}TE1"]["p1"][0]]
    a = els[f"{tag}T"]; arr = a.get("array") or {"count": 1, "spacing": 0}
    xs += [a["p1"][0] + k * arr["spacing"] for k in range(int(arr["count"]))]
    xs.append(els[f"{tag}TE2"]["p1"][0])
    return sorted(xs)


def additions_revd(cfg, proj):
    """Rev D lift parts. Each lift point is an A-frame: one pair of inclined straps from the lifting head down to two feet on
    the floor edge truss, so the share between the two legs is fixed by statics (no vertical hanger, no fit-up dependence).
    South: straps on both wall faces, feet are U-cradles that wrap under the floor edge truss (bearing, compression only)
    and are screwed to both chords over their middle 200 mm only. North (the marriage side): every lift part sits on the
    INSIDE face (nothing on the face that meets the second module): single straps, screwed foot plates, a one-sided head,
    all joined to the truss centre line by short offset links. Heads restrain the module sideways (y) only: no vertical
    load into the roof and free along the module (x), so each A-frame balances its own sling force."""
    out = []
    lines = cfg["lift_lines_x"]; ys = cfg["rim_y"]
    zb, zt = cfg["floor_rim_z"]; zr = cfg["roof_rim_top_z"]; zrb = cfg["roof_rim_bot_z"]; zh = cfg["head_z"]
    zbase = zb - cfg.get("cradle_base_drop", 20.5)
    Lr = cfg.get("length", 12000.0)
    inner = set(cfg.get("inner_face_sides", ["N"]))
    off = cfg.get("inner_face_offset", 45.5)
    vs = cfg["v_strap"]; cr = cfg["cradle"]; fp = cfg["foot_plate"]; gd = cfg["guide"]

    def rim(types, kind="rim_truss"):
        return {"kinds": [kind], "types": [types], "tol": 60.0, "snap": 3.0}

    def mem(i, typ, a, b, props, role, **kw):
        d = dict(id=i, kind="added", type=typ, a=list(map(float, a)), b=list(map(float, b)), props=props, role=role,
                 nrm=kw.pop("nrm", [0.0, 1.0, 0.0]), profile=kw.pop("profile", typ.lower()))
        d.update(kw); out.append(d)

    def plate_x(x):                                         # 600 mm plate kept on the truss at the module ends
        h = cfg.get("cradle_half", 300.0)
        x0, x1 = x - h, x + h
        if x0 < 25.0: x0, x1 = 25.0, 25.0 + 2 * h
        if x1 > Lr - 25.0: x0, x1 = Lr - 25.0 - 2 * h, Lr - 25.0
        return x0, x1

    def stations(x0, x1, extra=()):
        n = int(round((x1 - x0) / cfg.get("cradle_screw_pitch", 100.0)))
        return sorted({round(x0 + (x1 - x0) * k / n, 1) for k in range(n + 1)} | {round(v, 1) for v in extra})

    ftx = truss_x(proj, "F"); shw = cfg.get("strap_half_width", 25.0)
    fhw = cfg.get("floor_truss_half_width", 44.5) + cfg.get("cleat_leg", 0.0)     # the truss end plus the cleat leg each side of it
    cfg["_foot_layout"] = []

    def gap(lo, hi):
        """Clear distance from the x range [lo, hi] (on the inside face of the floor edge truss) to the nearest floor-truss
        end (89 mm wide) with its truss-end cleats (a 50 mm leg each side); negative = overlap."""
        return min(max(t - fhw - hi, lo - t - fhw) for t in ftx)

    def strap_range(xs, xh):
        """x range swept by a 50 mm strap from its foot at xs (cradle level) up through the floor depth, heading for xh."""
        k = (zt - zbase) / (zh - zbase)
        xt = xs + (xh - xs) * k
        w = shw * float(np.hypot(1.0, (xh - xs) / (zh - zbase)))
        return min(xs, xt) - w, max(xs, xt) + w

    def place_foot(xh, j1, j2):
        """Strap foot between the two joints j1 < j2 of a bottom-chord joint pair, and a cradle that holds both joints
        (15 mm edge) - each as close to the pair centre as the floor-truss ends allow (strap 15 mm clear, cradle 8 mm)."""
        L = 2.0 * cfg.get("cradle_half", 60.0); edge = cfg.get("seat_edge", 15.0)
        xc = 0.5 * (j1 + j2)
        cand = [j1 + 5.0 + 0.5 * i for i in range(int(round((j2 - j1 - 10.0) / 0.5)) + 1)] if j2 - j1 > 10.0 else [xc]
        ok = [v for v in cand if gap(*strap_range(v, xh)) >= cfg.get("strap_clear", 15.0)]
        xs = min(ok, key=lambda v: abs(v - xc)) if ok else max(cand, key=lambda v: gap(*strap_range(v, xh)))
        return round(xs, 1), place_cradle(xs, j1, j2)

    def place_cradle(xs, j1, j2):
        """Cradle extents: both joints of the pair inside (15 mm edge), the strap bolt 20 mm from the ends, centred on the
        strap where the floor-truss ends allow (8 mm clear)."""
        L = 2.0 * cfg.get("cradle_half", 60.0); edge = cfg.get("seat_edge", 15.0)
        lo0, hi0 = j2 + edge - L, j1 - edge                                # x0 range that keeps both joints inside
        x0c = [lo0 + 0.5 * i for i in range(int(round((hi0 - lo0) / 0.5)) + 1)] if hi0 > lo0 else [0.5 * (j1 + j2) - L / 2.0]
        x0c = [v for v in x0c if v + 20.0 <= xs <= v + L - 20.0] or x0c
        ok0 = [v for v in x0c if gap(v, v + L) >= cfg.get("cradle_clear", 8.0)]
        x0 = min(ok0, key=lambda v: abs(v + L / 2.0 - xs)) if ok0 else max(x0c, key=lambda v: gap(v, v + L))
        return (round(x0, 1), round(x0 + L, 1))

    def joint_pair(side, x):
        """The bottom-chord joint pair of the floor edge truss nearest x."""
        xs_ = (cfg.get("_bc_x") or {}).get(side, [])
        if not xs_: return None
        jn = min(xs_, key=lambda v: abs(v - x)); i = xs_.index(jn)
        if i + 1 < len(xs_) and xs_[i + 1] - jn < 70.0: return jn, xs_[i + 1]
        if i > 0 and jn - xs_[i - 1] < 70.0: return xs_[i - 1], jn
        return jn, jn

    def foot_south(cid, x, y, role, tmp, extent=None, xh=None):
        """U-cradle wrapping the bottom chord of the floor edge truss. It is seated (a bearing packer, and the cheeks
        screwed to the chord flanges) only at the chord's truss joints inside its length, so the strap force goes straight
        into the truss webs and does not bend the chord between joints; elsewhere there is clearance under the chord.
        The strap pair bolts to the cheeks at x; the cradle base carries the force to the seat(s)."""
        x0, x1 = extent or plate_x(x)
        side = "S" if y < 1650 else "N"
        joints = [xp for xp in (cfg.get("_bc_x") or {}).get(side, []) if x0 + 10.0 < xp < x1 - 10.0]
        if len(joints) >= 2:                            # two or more bearing seats: pinned in the truss plane at the chord
            seats, rel = [x if abs(xp - x) < 5.0 else xp for xp in joints], "b"   # a strap within 5 mm of a joint: one node (the seat snaps to the joint)
        elif joints and abs(joints[0] - x) <= cfg.get("seat_snap", 20.0):
            seats, rel = [x], ""                         # the strap lands on the bearing packer of one joint (within 20 mm)
        else:
            seats, rel = (joints or [x]), ""
            cfg.setdefault("_warnings", []).append(f"{cid}: cradle seat not at a truss joint pair (joints inside {joints})")
        xh_ = x if xh is None else xh
        sr = strap_range(x, xh_) if side == "S" else (x - shw, x + shw)
        cfg["_foot_layout"].append(dict(id=cid, side=side, x_strap=round(x, 1), x_head=round(xh_, 1), cradle=[round(x0, 1), round(x1, 1)],
                                        seats=[round(v, 1) for v in seats], joints=[round(v, 1) for v in joints],
                                        strap_gap=round(gap(*sr), 1), cradle_gap=round(gap(x0, x1), 1)))
        common = dict(cradle=cid, temporary=tmp, profile=cr["label"])
        base_pr = dict(A=cr["base_A"], I_major=cr["base_I_major"], I_minor=cr["base_I_minor"], J=cr["base_J"], kg_m=cr["kg_per_cradle"] / ((x1 - x0) / 1000.0))
        st = sorted({round(v - x0, 1) for v in seats + [x, x0, x1]})
        mem(f"{cid}_BASE", "CRADLE", [x0, y, zbase], [x1, y, zbase], base_pr, role, rigid=True, stations=st, **common)
        for k, xp in enumerate(seats):
            if k == 0 or not rel:      # the screwed seat: bearing packer + 2 cheek screws each side; pinned in the truss plane at the chord
                mem(f"{cid}_SEAT{k}", "CRADLE SEAT", [xp, y, zbase], [xp, y, zb], dict(A=400.0, I_major=4.0e5, I_minor=4.0e5, J=1.0e3, kg_m=0.0),
                    role + f" - screwed seat at the chord joint x {xp:.0f} (bearing packer + cheek screws)", rigid=True, release_inplane=rel, stations=[0.0],
                    attach={"b": rim("BOTTOM CHORD")}, **common)
            else:                      # bearing only (no screws): pushes up, never pulls, and does not share the chord's axial force
                mem(f"{cid}_SEAT{k}", "CRADLE SEAT", [xp, y, zbase], [xp, y, zb], dict(A=400.0, I_major=1.0, I_minor=1.0, J=1.0, kg_m=0.0),
                    role + f" - bearing-only seat at the chord joint x {xp:.0f} (packer, no screws)", pinned=True, compression_only=True, stations=[0.0],
                    attach={"b": rim("BOTTOM CHORD")}, **common)
        return [x, y, zbase]

    def foot_inner(cid, x, yw, yp, role, tmp):
        """Plate on the inside face only, screwed to both chords at 7 stations (every 100 mm over 600): a stiff plate
        panel at the face, joined to each chord by a short offset link per station (the screws). The strap pulls at x."""
        x0, x1 = plate_x(x)
        xs = stations(x0, x1, extra=(x,))
        common = dict(cradle=cid, temporary=tmp, profile=fp["label"])
        pr = dict(A=fp["A"], I_major=fp["I_major"], I_minor=fp["I_minor"], J=fp["J"], kg_m=0.0)
        for nm, z in (("B", zb), ("T", zt)):
            mem(f"{cid}_{nm}", "FOOT PLATE", [x0, yp, z], [x1, yp, z], dict(pr, kg_m=(fp["kg_per_plate"] / 0.6 if nm == "B" else 0.0)), role, rigid=True,
                stations=[v - x0 for v in xs], **common)
        for k, xv in enumerate(xs):
            mem(f"{cid}_V{k}", "FOOT PLATE", [xv, yp, zb], [xv, yp, zt], pr, role, rigid=True, stations=[0.0, zt - zb], **common)
            for nm, z, ty in (("b", zb, "BOTTOM CHORD"), ("t", zt, "TOP CHORD")):
                mem(f"{cid}_S{k}{nm}", "PLATE SCREWS", [xv, yp, z], [xv, yw, z], dict(A=400.0, I_major=200.0, I_minor=200.0, J=200.0, kg_m=0.0),
                    role + " - screws to the chord", rigid=True, stations=[0.0], attach={"b": rim(ty)}, **common)
        return [x, yp, zb]

    for side, yw in ys.items():
        face_inner = side in inner
        yp = (yw - off if yw > 1650 else yw + off) if face_inner else yw
        for k, x in enumerate(lines, 1):
            tag = f"{side}{k}"
            # lifting head: guide restrains y only (no vertical load, free along x)
            hang_pt = side in set(cfg.get("hanger_sides", []))
            # hanger points: the head is also held along the module (x); A-frame points: x is left free (the A-frame balances it)
            gpr = dict(A=gd["A"], I_major=gd["I"], I_minor=(gd["I"] if hang_pt else gd["I_free"]), J=(gd["I"] if hang_pt else 1.0), kg_m=gd["kg_m"])
            if not face_inner:
                mem(f"GUIDE_{tag}", "GUIDE", [x, yw, zrb], [x, yw, zh], gpr, f"lifting head saddle over the roof edge truss, lift point {tag}",
                    rigid=True, profile=gd["label"], stations=[zh - zrb],
                    attach={"a": rim("BOTTOM CHORD", "roof_rim"), "mid": [dict(rim("TOP CHORD", "roof_rim"), s=zr - zrb)]})
            else:
                mem(f"GUIDE_{tag}", "GUIDE", [x, yp, zrb], [x, yp, zh], gpr, f"lifting head on the inside face of the roof edge truss, lift point {tag}",
                    rigid=True, profile=gd["label_inner"], stations=[0.0, zr - zrb, zh - zrb])
                for nm, z, ty in (("b", zrb, "BOTTOM CHORD"), ("t", zr, "TOP CHORD")):
                    if hang_pt:   # bears sideways (y) and is keyed along the module (x); vertical slots: no vertical load
                        mem(f"GUIDE_{tag}_L{nm}", "GUIDE LINK", [x, yp, z], [x, yw, z], dict(A=400.0, I_major=1.0, I_minor=2.0e5, J=1.0, kg_m=0.0),
                            f"head bears on and is keyed to the inside face of the roof edge truss (no vertical load), lift point {tag}", rigid=True,
                            nrm=[0.0, 0.0, 1.0], stations=[0.0], attach={"b": rim(ty, "roof_rim")})
                    else:
                        mem(f"GUIDE_{tag}_L{nm}", "GUIDE LINK", [x, yp, z], [x, yw, z], dict(A=400.0, I_major=1.0, I_minor=1.0, J=1.0, kg_m=0.0),
                            f"head bears on the inside face of the roof edge truss (sideways only), lift point {tag}", pinned=True, stations=[0.0],
                            attach={"b": rim(ty, "roof_rim")})
            if side in set(cfg.get("hanger_sides", [])):     # a single vertical hanger under the lift point (determinate)
                cid = f"FOOT_{tag}h"
                lab = f"lift point {tag}"
                jp = joint_pair(side, float(x)) if cfg.get("feet_at_joints") else None
                ext = place_cradle(float(x), *jp) if (jp and jp[1] > jp[0]) else None
                P0 = foot_south(cid, x, yw, f"cradle under the floor edge truss, {lab}", False, extent=ext)
                if face_inner:          # the strap is on the inside face: it bolts to the inner cheek, joined to the cradle base by the base plate
                    Pi = [x, yp, P0[2]]
                    mem(f"{cid}_OFF", "CRADLE", Pi, P0, dict(A=cr["strip_A"], I_major=cr["strip_I_major"], I_minor=cr["strip_I_minor"], J=cr["strip_J"], kg_m=0.0),
                        f"cradle base plate to the inner cheek, {lab}", rigid=True, stations=[0.0, abs(yw - yp)], cradle=cid, profile=cr["label"])
                    P0 = Pi
                hs = cfg["hanger"]
                mem(f"HANG_{tag}", "STRAP", P0, [x, yp, zh], dict(A=hs["A"], I_major=10.0, I_minor=10.0, J=10.0, kg_m=hs["kg_m"]),
                    f"vertical hanger strap{'' if face_inner else ' pair'}, {lab}", pinned=True, profile=hs["label_inner" if face_inner else "label"],
                    stations=[0.0, zh - P0[2]])
            legs = [lg for lg in cfg["v_legs"] if lg["side"] == side and lg["line"] == k]
            for lg in legs:
                nm = "b" if lg["dx"] > 0 else "a"
                xf = x + lg["dx"]
                if cfg.get("feet_at_joints"):                  # land the foot on the nearest bottom-chord joint pair of the edge truss
                    xs_ = (cfg.get("_bc_x") or {}).get(side, [])
                    pairs = []
                    i = 0
                    while i < len(xs_):
                        if i + 1 < len(xs_) and xs_[i + 1] - xs_[i] < 70.0: pairs.append((xs_[i] + xs_[i + 1]) / 2.0); i += 2
                        else: pairs.append(xs_[i]); i += 1
                    pc = min(pairs, key=lambda c: abs(c - xf))
                    i = xs_.index(min(xs_, key=lambda v: abs(v - pc + 29.3)))
                    j1, j2 = (xs_[i], xs_[i + 1]) if (i + 1 < len(xs_) and xs_[i + 1] - xs_[i] < 70.0) else (pc, pc)
                    xf, ext = place_foot(float(x), j1, j2)
                else:
                    ext = None
                if xf < 60.0 or xf > Lr - 60.0:
                    continue
                tmp = bool(lg.get("temporary"))
                cid = f"FOOT_{tag}{nm}"
                lab = f"lift point {tag}" + (" (TEMPORARY, removed after set-down)" if tmp else "")
                if face_inner:
                    P0 = foot_inner(cid, xf, yw, yp, f"foot plate on the inside face, {lab}", tmp)
                    prof = vs["label_inner"]
                else:
                    P0 = foot_south(cid, xf, yw, f"cradle under the floor edge truss, {lab}", tmp, extent=ext, xh=float(x))
                    prof = vs["label"]
                Lst = float(np.linalg.norm(np.array([x, yp, zh]) - np.array(P0)))
                mem(f"VSTR_{tag}{nm}", "V-STRAP", P0, [x, yp, zh], dict(A=vs["A"], I_major=10.0, I_minor=10.0, J=10.0, kg_m=vs["kg_m"]),
                    f"A-frame strap{'' if face_inner else ' pair'}, {lab}", pinned=True, temporary=tmp, profile=prof, stations=[0.0, Lst])
    # plane bracing (unchanged from Rev C)
    for dname in ("floor_diaphragm", "roof_diaphragm"):
        dp = cfg.get(dname)
        if not dp: continue
        xs = dp["x_stations"]; z = dp["z"]; kinds = dp["attach_kinds"]
        for i in range(len(xs) - 1):
            for tg, (ya, yb) in (("a", (ys["S"], ys["N"])), ("b", (ys["N"], ys["S"]))):
                att = {"kinds": kinds, "types": ["TOP CHORD"], "tol": 60.0, "snap": 25.0}
                mem(f"{dname[:1].upper()}DIA_{i}{tg}", "PLANE BRACE", [xs[i], ya, z], [xs[i + 1], yb, z],
                    dict(A=dp["A_eq"], I_major=1.0, I_minor=1.0, J=1.0, kg_m=dp.get("kg_m", 0.4)), dp["label"], pinned=True, profile=dp["label"],
                    nrm=[0.0, 0.0, 1.0], attach={"a": att, "b": dict(att)})
    # bridging: a line of C89 noggings at mid-span between neighbouring trusses, floor and roof
    for nm, tag, z, kind in (("FBR", "F", cfg["floor_rim_z"][1], "floor_truss"), ("RBR", "R", zr, "roof_truss")):
        if not (cfg.get("bridging") or {}).get(nm): continue
        xs = truss_x(proj, tag); yb = cfg.get("bridging_y", 1650.0)
        for i in range(len(xs) - 1):
            ka = "floor_truss" if kind == "floor_truss" else "roof_truss"
            mem(f"{nm}_{i}", "BRIDGING", [xs[i], yb, z], [xs[i + 1], yb, z], dict(C89), "C89 0.95 bridging nogging at truss mid-span, 2 screws each end",
                pinned=True, profile="C89-38-0.95 nogging", attach={"a": {"kinds": [ka], "types": ["TOP CHORD"], "tol": 60.0, "snap": 3.0},
                                                                     "b": {"kinds": [ka], "types": ["TOP CHORD"], "tol": 60.0, "snap": 3.0}})
    return out


def head_y(cfg, side):
    yw = cfg["rim_y"][side]
    if cfg.get("design") == "revD" and side in set(cfg.get("inner_face_sides", ["N"])):
        off = cfg.get("inner_face_offset", 45.5)
        return yw - off if yw > 1650 else yw + off
    return yw


def lift_nodes(B, cfg):
    """Model node of each lifting head (the sling shackle sits here, above the roof)."""
    pts = {}
    for side, y in cfg["rim_y"].items():
        for i, x in enumerate(cfg["lift_lines_x"], 1):
            if cfg.get("pickup") == "rim":                                   # frame only: slings straight onto the floor rim chord
                pts[f"{side}{i}"] = LC.nearest_node(B, (x, y, cfg["floor_rim_z"][0]), kinds={"rim_truss"}, types={"BOTTOM CHORD"}, max_dist=60.0)[0]
            else:
                pts[f"{side}{i}"] = B.added_nodes[(round(float(x), 1), round(float(head_y(cfg, side)), 1), round(float(cfg["head_z"]), 1))]
    return pts


TENSION_ONLY = {"STRAP", "V-STRAP"}


def _unilateral(B, M, lc, max_iter=12):
    """Solve with tension-only straps and compression-only bearing links. A member found working the wrong way is taken
    out; a member taken out is put back if its ends move the way that would load it. Returns (result, members out)."""
    uni = [m for m in B.members.values() if m.get("added") and m.get("elements") and (m["type"] in TENSION_ONLY or m.get("compression_only"))]
    out = set()
    for e_m in uni:
        for e in e_m["elements"]: M.el[e].setdefault("A_full", M.el[e]["A"])
    for _ in range(max_iter):
        for m in uni:
            off = 1e-3 * M.el[m["elements"][0]]["A_full"] if m.get("compression_only") else 1e-6   # a lifted-off bearing seat still touches lightly
            for e in m["elements"]: M.el[e]["A"] = off if m["id"] in out else M.el[e]["A_full"]
        if hasattr(M, "K"): del M.K
        res = M.solve([lc])[lc]
        u = res["u"]; changed = False
        for m in uni:
            e0 = m["elements"][0]; e1 = m["elements"][-1]
            ni, nj = M.el[e0]["i"], M.el[e1]["j"]
            d = np.array(M.xyz[nj]) - np.array(M.xyz[ni]); d /= np.linalg.norm(d)
            stretch = float(np.dot(u[nj, :3] - u[ni, :3], d))
            N = min(res["end_forces"][e][6] for e in m["elements"]) if not m.get("compression_only") else max(res["end_forces"][e][6] for e in m["elements"])
            if m["id"] not in out:
                if (not m.get("compression_only") and N < -1.0) or (m.get("compression_only") and N > 1.0):
                    out.add(m["id"]); changed = True
            else:
                if (not m.get("compression_only") and stretch > 1e-4) or (m.get("compression_only") and stretch < -1e-4):
                    out.discard(m["id"]); changed = True
        if not changed: break
    for m in uni:                                                   # restore full areas for the next case
        for e in m["elements"]: M.el[e]["A"] = M.el[e]["A_full"]
    if hasattr(M, "K"): del M.K
    return res, sorted(out)


def cascade_forces(M, base_case, pts, ex=0.0, ey=0.0):
    """Drop forces of the 1-over-2-over-4 pinned-beam cascade with its pick points set off the true centre of gravity by
    (ex, ey): cross beams picked at y_cg + ey, middle beams at their centres, top beam at x_cg + ex. Returns (forces,
    'up' unit vector in module axes, tilt angle in degrees, CoG). Under such a rig the module hangs tilted so that the CoG
    is under the hook: 'up' points from the CoG to the centroid of the drop forces."""
    W = 0.0; r = np.zeros(3)
    for (nd, d), v in M.loads[base_case].items():
        if d == 2: W -= v; r -= v * np.array(M.xyz[nd])
    cg = r / W
    names = list(pts); xyz = {k: np.array(M.xyz[pts[k]]) for k in names}
    xl = sorted({round(xyz[k][0], 1) for k in names})
    yS = np.mean([xyz[k][1] for k in names if k.startswith("S")]); yN = np.mean([xyz[k][1] for k in names if k.startswith("N")])
    xm1, xm2 = (xl[0] + xl[1]) / 2, (xl[2] + xl[3]) / 2
    fW = (xm2 - (cg[0] + ex)) / (xm2 - xm1); fS = (yN - (cg[1] + ey)) / (yN - yS)
    F = {}
    for k in names:
        i = xl.index(round(xyz[k][0], 1))
        line = W * (fW if i < 2 else 1.0 - fW) / 2.0
        F[k] = line * (fS if k.startswith("S") else 1.0 - fS)
    rF = sum(F[k] * xyz[k] for k in names) / W
    u = rF - cg; u /= np.linalg.norm(u)
    return F, u, float(np.degrees(np.arccos(u[2]))), cg


# ------------------------------------------------------------------------------------------------ cases
def balance_forces(f0, xyz, M, case):
    """Smallest change to the wanted sling forces that puts them in equilibrium with the load (sum, and moments about x and y).
    Physically: the hook sits over the centre of gravity, so the set of sling forces always balances the weight."""
    names = list(f0)
    Wz = 0.0; Mx = 0.0; My = 0.0
    for (nd, d), v in M.loads[case].items():
        if d == 2:
            Wz -= v; Mx -= v * M.xyz[nd][0]; My -= v * M.xyz[nd][1]
    A = np.array([[1.0] * len(names), [xyz[k][0] for k in names], [xyz[k][1] for k in names]])
    b = np.array([Wz, Mx, My]); f = np.array([f0[k] for k in names], float)
    f = f + A.T @ np.linalg.solve(A @ A.T, b - A @ f)
    return {k: float(v) for k, v in zip(names, f)}


def solve_case(B, pts, case, base_case="G"):
    """Solve one rig case at the rated mass (no factor). Returns (result, info)."""
    M = B.model
    names = list(pts); nodes = [pts[k] for k in names]
    kind = case["rig"]
    active = [k for k in names if k not in case.get("slack", [])]
    lc = "C_" + case["id"]
    M.loads[lc] = dict(M.loads[base_case])
    W = LC.total_vertical_load(M, base_case)
    forces = None
    if kind == "rigid":
        LC.hold(M, [pts[k] for k in active], "rigid")
    elif kind == "springs":
        LC.hold(M, [pts[k] for k in active], "springs", k_sling=case["k_sling"])
        for k, dz in case.get("sling_short_mm", {}).items():                  # a sling shorter than the others by dz: pre-load k*dz upward
            M.load(lc, pts[k], 2, case["k_sling"] * dz)
    elif kind == "forces":
        forces = balance_forces(case["forces"], {k: M.xyz[pts[k]] for k in names}, M, base_case)
        for k, f in forces.items():
            M.load(lc, pts[k], 2, f)
        LC.hold(M, nodes, "forces")
    elif kind == "tilt":                                              # module hanging tilted under the cascade
        forces, u, theta, cg = cascade_forces(M, base_case, pts, case.get("ex", 0.0), case.get("ey", 0.0))
        M.loads[lc] = {}
        for (nd, d), v in M.loads[base_case].items():
            if d == 2:
                for dd in range(3): M.load(lc, nd, dd, v * u[dd])
        for k, f in forces.items():
            for dd in range(3): M.load(lc, pts[k], dd, f * u[dd])
        LC.hold(M, nodes, "forces")
        case["_theta"] = theta
    else:
        raise ValueError(kind)
    for (k, dof, force) in case.get("horizontal", []):                       # sling out of vertical: sideways force at the head
        M.load(lc, pts[k], dof, force)
    if case.get("horizontal_frac") and forces:
        dof, fr = case["horizontal_frac"]
        for k, f in forces.items(): M.load(lc, pts[k], dof, fr[k] * f)
    # flat straps carry tension only and cradle bearing pushes only
    res, slack_straps = _unilateral(B, M, lc)
    if kind in ("forces", "tilt"):
        unb = max([abs(res["reactions"][nd][2]) for nd in M.meta["force_holds"]] + [abs(v) for nd in M.fixed for v in res["reactions"][nd][:2]])
        info = dict(reactions=dict(forces), unbalance=float(unb), W=W)
    elif kind == "springs":
        sp = {nd: f for (nd, d, f) in res["spring_forces"] if d == 2}
        info = dict(reactions={k: float(sp.get(pts[k], 0.0)) + float(case.get("sling_short_mm", {}).get(k, 0.0) * case["k_sling"]) for k in active}, W=W)
    else:
        info = dict(reactions={k: float(res["reactions"][pts[k]][2]) for k in active}, W=W)
    info["sum_R"] = float(sum(info["reactions"].values())); info["slack_straps"] = slack_straps
    return res, info


def build_cases(cfg, names, W, cg, xyz):
    """Rig cases. Design cases enter the envelope; information cases are reported only."""
    cs = []
    n = len(names)
    cs.append(dict(id="R1_rigid", label="Rigid lifting frame, 8 slings of exact equal length and no stretch", rig="rigid"))
    cs.append(dict(id="R4_equalised", label="Equalising rig (beam cascade): four equal sling forces on each side, sides by statics", rig="forces",
                   forces={k: W / n for k in names}))
    sk = cfg.get("skew", 0.0)
    if sk:
        xm = np.mean([xyz[k][0] for k in names])
        xs = sorted({round(xyz[k][0]) for k in names}); outer = {xs[0], xs[-1]}
        pats = {"R7a_outer_high": {k: (1 + sk if round(xyz[k][0]) in outer else 1 - sk) for k in names},
                "R7b_inner_high": {k: (1 - sk if round(xyz[k][0]) in outer else 1 + sk) for k in names},
                "R7c_one_end_high": {k: (1 + sk if xyz[k][0] < xm else 1 - sk) for k in names},
                "R7d_twist": {k: (1 + sk if (xyz[k][0] < xm) == k.startswith("S") else 1 - sk) for k in names}}
        for cid, pat in pats.items():
            cs.append(dict(id=cid, label=f"Equalising rig with {sk * 100:.0f} % skew ({cid[4:].replace('_', ' ')}): robustness margin on the shares",
                           rig="forces", forces={k: W / n * pat[k] for k in names}, design=cfg.get("skew_in_envelope", True)))
    td = cfg.get("tilt_deg", 0.0)
    if td:
        h = float(np.mean([xyz[k][2] for k in names])) - float(cg[2])
        e = h * np.tan(np.radians(td)); ec = e / np.sqrt(2.0)
        for cid, ex, ey, lab in (("T1_roll_S", 0.0, -e, "rolls down to the south"), ("T2_roll_N", 0.0, e, "rolls down to the north"),
                                 ("T3_pitch_W", -e, 0.0, "pitches down at the west end"), ("T4_pitch_E", e, 0.0, "pitches down at the east end"),
                                 ("T5_SW", -ec, -ec, "tilts down to the south-west"), ("T6_SE", ec, -ec, "tilts down to the south-east"),
                                 ("T7_NW", -ec, ec, "tilts down to the north-west"), ("T8_NE", ec, ec, "tilts down to the north-east")):
            # the cascade picks are set off the CoG by (ex, ey), so the module hangs tilted by td degrees
            cs.append(dict(id=cid, label=f"Cascade picks off the CoG: module {lab} by {td:g} deg (net sideways load on the module)",
                           rig="tilt", ex=-ex, ey=-ey))
    ks = cfg.get("k_sling_N_per_mm")
    if ks:
        cs.append(dict(id="R2_springs", label="Rigid frame with elastic slings", rig="springs", k_sling=ks))
        tol = cfg.get("sling_tolerance_mm", 0.0)
        for k in names if tol else []:
            cs.append(dict(id=f"R6_short_{k}", label=f"Rigid frame with elastic slings, sling {k} short by {tol:.0f} mm", rig="springs", k_sling=ks,
                           sling_short_mm={k: tol}, design=cfg.get("short_in_envelope", True)))
    h = cfg.get("sideways_fraction", 0.0) * W / n
    if h and (cfg.get("design") == "revD" or cfg.get("sideways_per_head")):
        # 5 % of each head's own drop force (south heads carry more than north ones)
        share = {k: (W / n) * (1.0 + 0.0) for k in names}
        h = None
    if h is None:
        sgn_y = {k: (1.0 if k.startswith("S") else -1.0) for k in names}
        xm = np.mean([xyz[k][0] for k in names]); sgn_x = {k: (1.0 if xyz[k][0] < xm else -1.0) for k in names}
        fr = cfg["sideways_fraction"]
        for cid, lab, dof, sg, mult in (("L1_squeeze_y", "slings lean inwards across the module", 1, sgn_y, 1.0), ("L2_spread_y", "slings lean outwards across the module", 1, sgn_y, -1.0),
                                        ("L3_squeeze_x", "slings lean inwards along the module", 0, sgn_x, 1.0), ("L4_spread_x", "slings lean outwards along the module", 0, sgn_x, -1.0)):
            cs.append(dict(id=cid, label=f"Equalising rig, {lab} ({fr * 100:.0f} % of each head's sling force sideways)", rig="forces",
                           forces={k: W / n for k in names}, horizontal_frac=(dof, {k: mult * sg[k] * fr for k in names})))
    elif h:
        sgn_y = {k: (1.0 if k.startswith("S") else -1.0) for k in names}
        xm = np.mean([xyz[k][0] for k in names]); sgn_x = {k: (1.0 if xyz[k][0] < xm else -1.0) for k in names}
        for cid, lab, dof, sg, mult in (("L1_squeeze_y", "slings lean inwards across the module", 1, sgn_y, 1.0), ("L2_spread_y", "slings lean outwards across the module", 1, sgn_y, -1.0),
                                        ("L3_squeeze_x", "slings lean inwards along the module", 0, sgn_x, 1.0), ("L4_spread_x", "slings lean outwards along the module", 0, sgn_x, -1.0)):
            cs.append(dict(id=cid, label=f"Equalising rig, {lab} ({cfg['sideways_fraction'] * 100:.0f} % of the sling force sideways at every head)", rig="forces",
                           forces={k: W / n for k in names}, horizontal=[(k, dof, mult * sg[k] * h) for k in names]))
    for k in names if cfg.get("slack_cases", True) else []:
        cs.append(dict(id=f"R5_slack_{k}", label=f"Rigid frame, sling {k} slack (accident check, not a design case)", rig="rigid", slack=[k], design=False,
                       factor_scale=cfg.get("slack_factor_scale", 1.0)))
    return cs


# ------------------------------------------------------------------------------------------------ checks
def _scaled(res, f):
    r = dict(res); r["end_forces"] = res["end_forces"] * f
    return r


def summarise(B, res, factor, steel, extra_fasteners=None, lining=False, restraint=None, screws_by_rule=None):
    r = _scaled(res, factor)
    mc = LC.check_members(B, r, steel, lining=lining, restraint=restraint)
    jc = LC.check_joints(B, r, C.CONN_LOW, extra_fasteners=extra_fasteners)
    lk = LC.check_links(B, r, C.CONN_LOW, screws_by_rule=screws_by_rule)
    return mc, jc, lk, LC.added_forces(B, r)


def bc_joint_x(snap):
    """x of every truss joint on the bottom chords of the floor edge trusses, by side (the cradle seats)."""
    bc = {}
    for m in F.members_from_snapshot(snap):
        if m["kind"] == "rim_truss" and m["type"] == "BOTTOM CHORD":
            side = "S" if m["a"][1] < 1650 else "N"
            bc.setdefault(side, []).extend(float(m["a"][0] + p * m["dir"][0]) for p, _ in m["joints"])
    return {k: sorted(set(round(v, 1) for v in vs)) for k, vs in bc.items()}


def lift_additions(cfg, proj, snap):
    """The added lift parts for a config (Rev D builder, or the Rev C one)."""
    if cfg.get("design") == "revD":
        cfg["_bc_x"] = bc_joint_x(snap)
        return additions_revd(cfg, proj)
    return additions_from_config(cfg)


def extra_fasteners(B, cfg):
    """Screws per joint from the config: by panel kind, by panel, and by rules (member types, panels, x/y zones, near the
    lift points). Returns {joint id: screws added to the Framer count}."""
    M = B.model
    extra = dict(cfg.get("extra_fasteners") or {})
    gus = set(cfg.get("gusset_joints") or [])
    for jid, j in B.joints.items():                                          # fastener count per joint by panel kind (default 2)
        want = (cfg.get("joint_fasteners_panels") or {}).get(j["panel"]) or (cfg.get("joint_fasteners") or {}).get(B.members[j["members"][0]]["kind"])
        for rule in cfg.get("joint_rules", []):                              # e.g. more screws in the first panels of a rim
            kind = B.members[j["members"][0]]["kind"]; xj = M.xyz[j["node"]][0]
            if rule.get("kinds") and kind not in rule["kinds"]: continue
            if "x_lt" in rule and not xj < rule["x_lt"]: continue
            if "x_gt" in rule and not xj > rule["x_gt"]: continue
            yj = M.xyz[j["node"]][1]
            if "y_lt" in rule and not yj < rule["y_lt"]: continue
            if "y_gt" in rule and not yj > rule["y_gt"]: continue
            if rule.get("types") and not any(B.members[x]["type"] in rule["types"] for x in j["members"]): continue
            if rule.get("panels") and j["panel"] not in rule["panels"]: continue
            if rule.get("x_near"):
                xn_ = rule["x_near"]
                if xn_ == "lift":                                            # the lift lines and every strap foot
                    xn_ = list(cfg["lift_lines_x"]) + [f["x_strap"] for f in cfg.get("_foot_layout", [])]
                if min(abs(xj - xn) for xn in xn_) > rule.get("r", 600.0): continue
            want = max(want or 0, rule["n"])
        if jid in gus: want = max(want or 0, 10)                              # a gusset, sized joint by joint (size_joints.py)
        if want: extra[jid] = extra.get(jid, 0) + want - j["fasteners"]
    return extra


def run(model_dir, cfg, out_dir=None, quiet=False):
    say = (lambda *a, **k: None) if quiet else print
    snap = F.load_snapshot(os.path.join(model_dir, "framed.json")); proj = json.load(open(os.path.join(model_dir, "project.json"), encoding="utf-8"))
    add = lift_additions(cfg, proj, snap)
    LC.TWIST["mode"] = cfg.get("twist_mode", "cap")
    t0 = time.time()
    B = F.build(snap, options=cfg.get("build_options"), additions={"members": add})
    M = B.model
    mm = MS.load_mass_model(os.path.join(os.path.dirname(model_dir.rstrip("/\\")), "mass_model.json"))
    if "rated_lift_mass_kg" in cfg: mm["rated_lift_mass_kg"] = cfg["rated_lift_mass_kg"]
    for lump in cfg.get("extra_lumps", []): mm.setdefault("lumps", []).append(lump)
    led = MS.apply(B, mm, proj, case="G")
    pts = lift_nodes(B, cfg)
    steel = getattr(C, cfg.get("steel", "G450"))
    fc = cfg["factors"]; factor = fc["weight"] * fc["cog"] * fc["dynamic"] * fc["load"]
    W = LC.total_vertical_load(M, "G")
    say(f"model: {len(M.xyz)} nodes, {len(M.el)} elements, {len(B.links)} links, {len(B.joints)} joints; built in {time.time() - t0:.1f}s")
    for l in B.log: say("  -", l)
    say(f"itemised {led['itemised_kg']:.0f} kg -> rated {led['applied_kg']:.0f} kg (x{led['factor_to_rated']:.3f}); W = {W / 1e3:.2f} kN; CoG {[round(v) for v in led['cg']]}; factor {factor:.3f}")
    names = list(pts)
    out = {"meta": {"config": cfg.get("name"), "W_N": W, "rated_kg": led["applied_kg"], "itemised_kg": led["itemised_kg"], "cg": led["cg"], "factor": factor,
                    "factors": cfg["factors"], "member_steel": steel.name, "connection_steel": C.CONN_LOW.name,
                    "lift_points": {k: {"node": int(v), "xyz": list(M.xyz[v])} for k, v in pts.items()}}, "cases": {}}
    extra = extra_fasteners(B, cfg)
    cases = build_cases(cfg, names, W, led["cg"], {k: M.xyz[v] for k, v in pts.items()})
    if cfg.get("only_cases"): cases = [c for c in cases if c["id"] in cfg["only_cases"]]      # diagnostics: a subset of the cases
    if cfg.get("only_design"): cases = [c for c in cases if c.get("design", True)]           # ablations: the design cases only
    env_m = {}; env_j = {}; env_l = {}; env_a = {}
    used = sorted({nd for m in B.members.values() if not m.get("added") for _, nd in (m.get("nodes") or [])})
    for case in cases:
        res, info = solve_case(B, pts, case)
        f = factor * case.get("factor_scale", 1.0)
        mc, jc, lk, af = summarise(B, res, f, steel, extra, cfg.get("lining", False), cfg.get("restraint_lines"), cfg.get("link_screws"))
        u = res["u"]
        zs = np.array([u[pts[k], 2] for k in names])
        sag = float((u[used, 2] - np.mean(zs)).min()); hog = float((u[used, 2] - np.mean(zs)).max())
        n_m = sum(1 for v in mc.values() if v["util"] > 1.0); n_j = sum(1 for v in jc.values() if v["util"] > 1.0); n_l = sum(1 for v in lk if v["util_shear"] > 1.0)
        mx_m = max(mc.values(), key=lambda v: v["util"]); mx_j = max(jc.values(), key=lambda v: v["util"]); mx_l = dict(util=max(v["util_shear"] for v in lk))
        R = info["reactions"]
        say(f"{case['id']:14s} R(kN) " + " ".join(f"{k}:{R.get(k, 0) / 1e3:5.1f}" for k in names) + f" | sumR/W {info['sum_R'] / W:.4f}"
            f" | mem>1 {n_m:3d} (max {mx_m['util']:.2f}) jnt>1 {n_j:3d} (max {mx_j['util']:.2f}) link shear>1 {n_l:3d} (max {mx_l['util']:.2f}) | dz {sag:.1f}/{hog:+.1f} mm")
        out["cases"][case["id"]] = dict(label=case["label"], rig=case["rig"], reactions=R, sum_R=info["sum_R"], unbalance=info.get("unbalance", 0.0), factor=f,
                                         members_over=n_m, joints_over=n_j, links_over=n_l, max_member=mx_m["util"], max_joint=mx_j["util"], max_link=mx_l["util"],
                                         sag_mm=sag, hog_mm=hog, design=case.get("design", True), slack_straps=info["slack_straps"])
        if case.get("design", True):
            for k, v in mc.items():
                if k not in env_m or v["util"] > env_m[k]["util"]: env_m[k] = dict(v, case=case["id"])
            for k, v in jc.items():
                if k not in env_j or v["util"] > env_j[k]["util"]: env_j[k] = dict(v, case=case["id"])
            for i, v in enumerate(lk):
                tie = env_l.get(i, {}).get("tie", False) or v["needs_tie"]; nmax = max(env_l.get(i, {}).get("N_max", 0.0), v["N"])
                ushr = max(env_l.get(i, {}).get("util_shear", 0.0), v["util_shear"])          # worst shear over the cases
                if i not in env_l or v["util"] > env_l[i]["util"]: env_l[i] = dict(v, case=case["id"])
                env_l[i]["tie"] = tie; env_l[i]["N_max"] = nmax; env_l[i]["util_shear"] = ushr
            for k, v in af.items():
                e = env_a.setdefault(k, dict(N_max=-1e18, N_min=1e18, V=0.0, M=0.0, type=v["type"], role=v["role"]))
                e["N_max"] = max(e["N_max"], v["N_max"]); e["N_min"] = min(e["N_min"], v["N_min"]); e["V"] = max(e["V"], v["V"]); e["M"] = max(e["M"], v["M"])
        case["_res"] = res; case["_mc"] = mc; case["_jc"] = jc; case["_lk"] = lk; case["_info"] = info
    # envelope report
    worst_m = sorted(env_m.items(), key=lambda kv: -kv[1]["util"])[:12]
    say("\nENVELOPE over design cases, factor %.3f:" % factor)
    say(" members over 1.0: %d of %d" % (sum(1 for v in env_m.values() if v["util"] > 1), len(env_m)))
    for mid, v in worst_m:
        m = B.members[mid]
        say(f"   {m['panel']:6s} {m['type']:13s} {m['kind']:11s} x={(m['a'][0] + m['b'][0]) / 2:7.0f} util {v['util']:.2f} N={v['N'] / 1e3:6.1f} kN Min={v['M_in'] / 1e6:.3f} Mout={v['M_out'] / 1e6:.3f} kNm Lin={v['L_in']:.0f} Lout={v['L_out']:.0f} [{v['case']}] {v['mode'][:30]}")
    worst_j = sorted(env_j.items(), key=lambda kv: -kv[1]["util"])
    over_j = [x for x in worst_j if x[1]["util"] > 1.0]
    say(" joints over 1.0: %d of %d" % (len(over_j), len(env_j)))
    byk = Counter((B.members[v["member"]]["kind"], B.members[v["member"]]["type"]) for _, v in over_j)
    say("   by member:", dict(byk))
    for jid, v in worst_j[:10]:
        m = B.members[v["member"]]
        say(f"   {v['panel']:6s} {m['type']:13s} {m['kind']:11s} x={M.xyz[v['node']][0]:7.0f} y={M.xyz[v['node']][1]:6.0f} z={M.xyz[v['node']][2]:6.0f} demand {v['demand'] / 1e3:5.2f} kN cap {v['capacity'] / 1e3:.2f} util {v['util']:.2f} [{v['case']}]")
    over_l = [v for v in env_l.values() if v["util_shear"] > 1.0]; ties = [v for v in env_l.values() if v["tie"]]
    say(" links over 1.0 in shear: %d of %d; links in tension that need a positive tie (tie checked in run_connectors): %d" % (len(over_l), len(env_l), len(ties)))
    for rule, n in Counter(v["rule"] for v in over_l).items(): say("   over:", n, rule, "max util %.2f" % max(v["util_shear"] for v in over_l if v["rule"] == rule))
    for rule, n in Counter(v["rule"] for v in ties).items():
        say("   tie :", n, rule, "max tension %.2f kN" % (max(v["N_max"] for v in ties if v["rule"] == rule) / 1e3))
    say(" added parts (factored envelope):")
    byt = defaultdict(list)
    for k, v in env_a.items(): byt[v["type"]].append((k, v))
    for t, lst in byt.items():
        say(f"   {t:12s} n={len(lst):3d} tension {max(x[1]['N_max'] for x in lst) / 1e3:6.2f} kN compression {max(0.0, -min(x[1]['N_min'] for x in lst)) / 1e3:6.2f} kN shear {max(x[1]['V'] for x in lst) / 1e3:5.2f} kN moment {max(x[1]['M'] for x in lst) / 1e6:.3f} kNm")
    steel_kg = sum(m["kg_m"] * m["L"] / 1000.0 for m in B.members.values() if not m.get("added"))
    add_kg = sum(m["kg_m"] * m["L"] / 1000.0 for m in B.members.values() if m.get("added"))
    say(" framed steel %.0f kg, added parts (as modelled) %.0f kg" % (steel_kg, add_kg))
    out["foot_layout"] = cfg.get("_foot_layout", []); out["layout_warnings"] = cfg.get("_warnings", [])
    say(" largest link shear utilisation: %.2f" % max(v["util_shear"] for v in env_l.values()))
    out["envelope"] = dict(members_over=sum(1 for v in env_m.values() if v["util"] > 1), joints_over=len(over_j), links_over=len(over_l), links_tie=len(ties),
                           max_link_shear=max(v["util_shear"] for v in env_l.values()),
                           max_member=max(v["util"] for v in env_m.values()), max_joint=max(v["util"] for v in env_j.values()),
                           added=env_a, framed_steel_kg=steel_kg, added_kg=add_kg)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        json.dump(out, open(os.path.join(out_dir, "summary.json"), "w"), indent=1)
    return dict(B=B, cfg=cfg, cases=cases, env_m=env_m, env_j=env_j, env_l=env_l, env_a=env_a, out=out, pts=pts, led=led, factor=factor, steel=steel, extra_fasteners=extra)


def main():
    model_dir, cfg_path, out_dir = sys.argv[1:4]
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    run(model_dir, cfg, out_dir)


if __name__ == "__main__":
    main()
