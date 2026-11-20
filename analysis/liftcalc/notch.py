"""Capacity of the C89 section at a Framer lip notch: the lips are cut away over a short length where a truss web member or a
stud nests into the member. At the notch the section is a plain (lipless) channel, so its flanges have free edges.

Method (AS/NZS 4600:2018 Section 7 / AISI S100-16 Appendix 1, Direct Strength Method):
  * section properties of the lipless channel (centreline model, sharp corners);
  * elastic local buckling of that section by the finite strip method (analysis/liftcalc/buckling_fsm.py, the same
    independent solver that made the C89 table), at a half-wave equal to the notch length a: the lips either side of the
    notch hold the flange, so the buckle cannot be longer than the notch. No credit is taken for the nested web member;
  * DSM local strength: P_nl (or M_nl) = P_ne for lambda <= 0.776, else (1 - 0.15 (Pcrl/Pne)^0.4) (Pcrl/Pne)^0.4 P_ne,
    with P_ne = A_notch x fn (the member's global buckling stress) and M_ne = M_y of the notched section;
  * there is no distortional mode (no lips);
  * phi 0.85 compression, 0.90 bending and tension (gross yield of the notched section).
Notch length: 50 mm for a single notch; notches whose centres are less than 90 mm apart (the two notches of a truss joint
pair, 76.8 mm apart) are taken as one notch from the first to the last plus 50 mm (about 127 mm), as the Rev D review asked.
"""
from __future__ import annotations
import math, functools
import numpy as np
from . import buckling_fsm as FSM

DEPTH, FLANGE = 89.0, 38.0
NOTCH_SINGLE = 50.0
CLUSTER_GAP = 90.0
PHI_C, PHI_B, PHI_T = 0.85, 0.90, 0.90


def lipless_section(t, n_flange=8, n_web=16):
    h, b = DEPTH - t, FLANGE - t
    pts, parts = [(b, 0.0)], []

    def line_to(q, n, part):
        p = pts[-1]
        for i in range(1, n + 1):
            pts.append((p[0] + (q[0] - p[0]) * i / n, p[1] + (q[1] - p[1]) * i / n)); parts.append(part)

    line_to((0.0, 0.0), n_flange, "flange_bottom")
    line_to((0.0, h), n_web, "web")
    line_to((b, h), n_flange, "flange_top")
    xy = np.array(pts, dtype=float)
    return FSM.Section(t=float(t), corners="sharp", xy=xy, elems=[(i, i + 1) for i in range(len(xy) - 1)], elem_part=parts,
                       h=h, b=b, c=0.0, r=0.0, mesh={"flange": n_flange, "web": n_web, "lip": 0},
                       j_web_flange=(n_flange, n_flange + n_web), j_flange_lip=(0, len(xy) - 1), tips=(0, len(xy) - 1))


EDGE = {"held": True}     # True: the flange free edges are held out of their plane by the nested member's flange screwed to them


@functools.lru_cache(maxsize=None)
def notched_buckling(t, a, held=False):
    """Section properties of the lipless channel and its local buckling stress at half-wave a for each action.
    held=True: the free edges of both flanges are restrained against moving out of the flange plane over the notch (the
    nested web member or stud lies against the flange there and is screwed to it), modelled in the finite strip model by
    fixing the normal displacement of the two tip nodes."""
    sec = lipless_section(round(float(t), 3))
    p = FSM.section_properties(sec)
    out = dict(A=float(p["A"]), Ix=float(p["Ix"]), Iy=float(p["Iy"]))
    fixed = [(sec.tips[0], "W"), (sec.tips[1], "W")] if held else []
    for action in ("axial", "bend_major", "bend_minor_web_comp", "bend_minor_lips_comp"):
        s, info = FSM.reference_stress(sec, action, p)
        f = FSM.FiniteStrip(sec.xy, sec.elems, sec.t, s, fixed=fixed).first(float(a))
        out[action] = dict(f_cr=float(f), res=float(info["resultant_per_unit_stress"]))
    return out


def _dsm(Pne, Pcr):
    lam = math.sqrt(Pne / Pcr) if Pcr > 0 else 99.0
    if lam <= 0.776: return Pne
    r = (Pcr / Pne) ** 0.4
    return (1.0 - 0.15 * r) * r * Pne


@functools.lru_cache(maxsize=None)
def notched_capacities(t, fy, a, fn, held=None):
    """Design capacities (N, Nmm) of the notched section: compression at the member's global buckling stress fn, tension,
    major-axis bending, minor-axis bending with the free flange tips in compression and with the web in compression."""
    held = EDGE["held"] if held is None else held
    b = notched_buckling(t, a, bool(held))
    A = b["A"]
    Pne = A * min(fn, fy)
    Nc = PHI_C * _dsm(Pne, A * b["axial"]["f_cr"])
    Nt = PHI_T * A * fy
    caps = dict(A=A, phiNc=Nc, phiNt=Nt)
    for key, action in (("phiMx", "bend_major"), ("phiMy_tips", "bend_minor_lips_comp"), ("phiMy_web", "bend_minor_web_comp")):
        Z = b[action]["res"]; My = Z * fy
        caps[key] = PHI_B * _dsm(My, Z * b[action]["f_cr"])
    caps["phiMy"] = min(caps["phiMy_tips"], caps["phiMy_web"])        # the sign of the in-plane moment is not tracked
    return caps


def notch_zones(member):
    """[(s_start, s_end, a)] notch zones along a member from its LIP NOTCH operations (positions along the member)."""
    pos = sorted(float(p) for o, p in (member.get("ops") or []) if o == "LIP NOTCH")
    zones, cur = [], []
    for p in pos:
        if cur and p - cur[-1] >= CLUSTER_GAP:
            zones.append(cur); cur = []
        cur.append(p)
    if cur: zones.append(cur)
    out = []
    for z in zones:
        a = (z[-1] - z[0]) + NOTCH_SINGLE
        out.append((z[0] - NOTCH_SINGLE / 2.0, z[-1] + NOTCH_SINGLE / 2.0, a))
    return out


GUSSET_T = 1.5          # mm, joint gusset plate (G450), one on each face of the panel
GUSSET_FY = 450.0


@functools.lru_cache(maxsize=None)
def gusseted_capacities(t, fy, fn):
    """Design capacities at a notch covered by a joint gusset pair: the lipless section plus the two 1.5 mm plates over
    the flange height (38 mm on each face; only the part of each plate lying on the chord flange is counted, screwed to it
    with 3 screws per face). The plates hold the flange edges, so the section is taken to yield (no local buckling);
    elastic first yield in bending. Axes as for the channel: x-x major (flanges at +-h/2), y-y minor (web at X = 0, flange
    tips at X = b)."""
    h, b = DEPTH - t, FLANGE - t
    tg, bg = GUSSET_T, FLANGE                      # plate strip over each flange: bg tall (along X), tg thick (along Z)
    # parts: (area, X centroid, Z centroid, Ix_own, Iy_own); Z measured from mid-depth
    parts = [(h * t, 0.0, 0.0, t * h ** 3 / 12.0, h * t ** 3 / 12.0)]
    for zf in (-h / 2.0, h / 2.0):
        parts.append((b * t, b / 2.0, zf, b * t ** 3 / 12.0, t * b ** 3 / 12.0))
        zg = zf - (t + tg) / 2.0 if zf < 0 else zf + (t + tg) / 2.0
        parts.append((bg * tg, bg / 2.0, zg, bg * tg ** 3 / 12.0, tg * bg ** 3 / 12.0))
    A = sum(q[0] for q in parts)
    Xc = sum(q[0] * q[1] for q in parts) / A
    Ix = sum(q[3] + q[0] * q[2] ** 2 for q in parts)
    Iy = sum(q[4] + q[0] * (q[1] - Xc) ** 2 for q in parts)
    zmax = h / 2.0 + t + tg
    Zx = Ix / zmax
    Zy_tips = Iy / (max(b, bg) - Xc); Zy_web = Iy / Xc
    f = min(fy, GUSSET_FY)
    return dict(A=A, phiNc=PHI_C * A * min(fn, f), phiNt=PHI_T * A * f, phiMx=PHI_B * Zx * f,
                phiMy_tips=PHI_B * Zy_tips * f, phiMy_web=PHI_B * Zy_web * f, phiMy=PHI_B * min(Zy_tips, Zy_web) * f)
