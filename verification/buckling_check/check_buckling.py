"""Independent check of the C89 buckling table (analysis/liftcalc/data/c89_buckling.json).

Run:  .venv/Scripts/python.exe verification/buckling_check/check_buckling.py
Writes verification/buckling_check/check_results.json and prints a report.

Nothing is imported from analysis/liftcalc. Everything here is written from scratch:
  1. section properties: closed-form centreline formulas + my own sectorial-coordinate integration
  2. hand plate-buckling stresses and implied k
  3. distortional buckling: Lau-Hancock / Hancock (AS/NZS 4600 App. D form) and Schafer-Pekoz (AISI S100 commentary)
  4. my own finite strip runs: pycufsm.fsm.strip called directly, own nodes/elements, own hand-written stress field,
     different mesh (12/6/3 strips, 5 per corner; and 20/10/5) and different half-wave set (70 points, 15..1500 mm)
  5. minor-axis stress convention and sense
  6. JSON against my values

Units: mm, N, MPa. Compression positive. x = across the section from web centreline towards the lips, y = up the web.
"""
from __future__ import annotations

import builtins
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TABLE = ROOT / "analysis" / "liftcalc" / "data" / "c89_buckling.json"

E, NU = 200000.0, 0.3
G = E / 2.6
D, B, C, RI = 89.0, 38.0, 9.0, 2.0
THICK = (0.75, 0.95, 1.15)
FREF = 100.0
REF_TABLE = {("axial", 0.95): 201.8, ("axial", 1.15): 253.2, ("bend_major", 0.95): 350.6, ("bend_major", 1.15): 435.4}


# ------------------------------------------------------------------------------------------ 1. section properties
def closed_form_props(t):
    """Sharp-corner centreline lipped channel, web a, flange b, lip c. Textbook thin-walled expressions."""
    a, b, c = D - t, B - t, C - t / 2
    L = a + 2 * b + 2 * c
    A = t * L
    xc = b * (b + 2 * c) / L                                   # from web centreline
    Ix = t * (a ** 3 / 12 + 2 * b * (a / 2) ** 2 + 2 * (c ** 3 / 12 + c * (a / 2 - c / 2) ** 2))
    Iy = t * (a * xc ** 2 + 2 * (b ** 3 / 12 + b * (b / 2 - xc) ** 2) + 2 * c * (b - xc) ** 2)
    J = t ** 3 * L / 3
    # shear centre behind the web centreline (AISI cold-formed design manual, lips turned in)
    m = b * t / (12 * Ix) * (6 * c * a ** 2 + 3 * b * a ** 2 - 8 * c ** 3)
    # warping constant: sectorial coordinate about the shear centre is piecewise linear, antisymmetric
    w1 = m * a / 2                       # web/flange corner
    w2 = w1 - (a / 2) * b                # flange/lip corner
    w3 = w2 - (b + m) * c                # lip tip
    Cw = 2 * t * ((a / 2) * w1 ** 2 / 3 + b * (w1 ** 2 + w1 * w2 + w2 ** 2) / 3 + c * (w2 ** 2 + w2 * w3 + w3 ** 2) / 3)
    return dict(A=A, xc=xc, Ix=Ix, Iy=Iy, J=J, e=m, x0=m + xc, Cw=Cw)


def numeric_props(pts, t):
    """General open thin-walled section from a polyline (my own routine). Returns centroid, I, shear centre, Cw."""
    p = np.asarray(pts, float)
    d = np.diff(p, axis=0)
    L = np.hypot(d[:, 0], d[:, 1])
    A = t * L.sum()
    mid = (p[:-1] + p[1:]) / 2
    xc, yc = (mid * L[:, None]).sum(0) * t / A
    q = p - [xc, yc]

    def integ(f, g):                     # integral f*g dA, both linear on each segment (exact)
        return float(np.sum(t * L / 6 * (2 * f[:-1] * g[:-1] + 2 * f[1:] * g[1:] + f[:-1] * g[1:] + f[1:] * g[:-1])))

    x, y = q[:, 0], q[:, 1]
    Ixx, Iyy, Ixy = integ(y, y), integ(x, x), integ(x, y)
    w = np.concatenate([[0.0], np.cumsum(x[:-1] * y[1:] - x[1:] * y[:-1])])     # pole = centroid
    Iwx, Iwy = integ(w, x), integ(w, y)
    det = Ixx * Iyy - Ixy ** 2
    xs = (Iyy * Iwy - Ixy * Iwx) / det
    ys = -(Ixx * Iwx - Ixy * Iwy) / det
    ws = w - xs * y + ys * x             # sectorial coordinate about the shear centre
    one = np.ones_like(ws)
    ws = ws - integ(ws, one) / A
    Cw = integ(ws, ws)
    return dict(A=A, xc=xc, yc=yc, Ix=Ixx, Iy=Iyy, Ixy=Ixy, J=t ** 3 * L.sum() / 3, xs=xc + xs, ys=yc + ys,
                x0=abs(xs), Cw=Cw, resid=(integ(ws, x), integ(ws, y)))


def outline(t, corners, n_arc=40):
    """Centreline polyline, lip tip (bottom) -> ... -> lip tip (top). Web centreline at x = 0, bottom flange at y = 0."""
    a, b, c = D - t, B - t, C - t / 2
    if corners == "sharp":
        return [(b, c), (b, 0), (0, 0), (0, a), (b, a), (b, a - c)], {}
    r = RI + t / 2
    pts = [(b, c)]

    def arc(cx, cy, a0, a1):
        for k in range(n_arc + 1):
            th = math.radians(a0 + (a1 - a0) * k / n_arc)
            pts.append((cx + r * math.cos(th), cy + r * math.sin(th)))

    arc(b - r, r, 0, -90)
    arc(r, r, 270, 180)
    arc(r, a - r, 180, 90)
    arc(b - r, a - r, 90, 0)
    pts.append((b, a - c))
    return pts, {}


def plain_channel_selftest():
    """Validate numeric_props on a plain channel: e = 3b^2/(a+6b), Cw = t a^2 b^3 (3b+2a) / (12 (6b+a))."""
    a, b, t = 100.0, 40.0, 1.0
    n = numeric_props([(b, 0), (0, 0), (0, a), (b, a)], t)
    e = 3 * b ** 2 / (a + 6 * b)
    cw = t * a ** 2 * b ** 3 * (3 * b + 2 * a) / (12 * (6 * b + a))
    return dict(e_num=-n["xs"], e_exact=e, Cw_num=n["Cw"], Cw_exact=cw)


# ------------------------------------------------------------------------------------------ 2. plate buckling
def plate(k, t, w):
    return k * math.pi ** 2 * E / (12 * (1 - NU ** 2)) * (t / w) ** 2


# ------------------------------------------------------------------------------------------ 3. distortional closed form
def flange_props(b, d, t):
    """Flange + simple lip about its own centroid. x along the flange from the web junction, y towards the lip tip."""
    A = (b + d) * t
    xb = (b ** 2 + 2 * b * d) / (2 * (b + d))
    yb = d ** 2 / (2 * (b + d))
    Ix = b * t ** 3 / 12 + t * d ** 3 / 12 + b * t * yb ** 2 + d * t * (d / 2 - yb) ** 2
    Iy = t * b ** 3 / 12 + d * t ** 3 / 12 + d * t * (b - xb) ** 2 + b * t * (xb - b / 2) ** 2
    Ixy = b * t * yb * (xb - b / 2) + d * t * (d / 2 - yb) * (b - xb)          # both parts same sign
    J = t ** 3 * (b + d) / 3
    return A, xb, yb, Ix, Iy, Ixy, J


def lau_hancock(t, bending=False):
    """AS/NZS 4600 Appendix D form (Lau & Hancock 1987 for compression; Hancock 1997 for bending)."""
    bw, bf, dl = D - t, B - t, C - t / 2
    A, xb, yb, Ix, Iy, Ixy, J = flange_props(bf, dl, t)
    lam = 4.80 * (Ix * bf ** 2 * bw / ((2 if bending else 1) * t ** 3)) ** 0.25
    eta = (math.pi / lam) ** 2
    beta1 = xb ** 2 + (Ix + Iy) / A

    def fod(kphi):
        a1 = eta / beta1 * (Ix * bf ** 2 + 0.039 * J * lam ** 2) + kphi / (beta1 * eta * E)
        a2 = eta * (Iy + 2 / beta1 * yb * bf * Ixy)
        a3 = eta * (a1 * Iy - eta / beta1 * Ixy ** 2 * bf ** 2)
        return E / (2 * A) * ((a1 + a2) - math.sqrt((a1 + a2) ** 2 - 4 * a3))

    f0 = fod(0.0)
    if not bending:
        kphi = E * t ** 3 / (5.46 * (bw + 0.06 * lam)) * (1 - 1.11 * f0 / (E * t ** 2) * (bw ** 2 * lam / (bw ** 2 + lam ** 2)) ** 2)
    else:
        kphi = 2 * E * t ** 3 / (5.46 * (bw + 0.06 * lam)) * (
            1 - 1.11 * f0 / (E * t ** 2) * (bw ** 4 * lam ** 2 / (12.56 * lam ** 4 + 2.192 * bw ** 4 + 13.39 * lam ** 2 * bw ** 2)))
    neg = kphi < 0
    if neg:                                # explicit negative branch: web destabilises the flange; keep the negative value
        pass
    return dict(fod=fod(kphi), lam=lam, kphi=kphi, fod_kphi0=f0, kphi_negative=neg)


def schafer(t, bending=False):
    """Schafer & Pekoz closed form as in the AISI S100 commentary / Appendix 2 (centreline dimensions)."""
    ho, b, d = D - t, B - t, C - t / 2
    Af = (b + d) * t
    Jf = t ** 3 * (b + d) / 3
    Ixf = t * (t ** 2 * b ** 2 + 4 * b * d ** 3 + t ** 2 * b * d + d ** 4) / (12 * (b + d))
    Iyf = t * (b ** 4 + 4 * d * b ** 3) / (12 * (b + d))
    Ixyf = t * b ** 2 * d ** 2 / (4 * (b + d))
    xof = b ** 2 / (2 * (b + d))
    hxf = -(b ** 2 + 2 * d * b) / (2 * (b + d))
    yof = -d ** 2 / (2 * (b + d))
    dx = xof - hxf
    core = Ixf * dx ** 2 - Ixyf ** 2 / Iyf * dx ** 2                     # Cwf = 0
    if not bending:
        Lcr = (6 * math.pi ** 4 * ho * (1 - NU ** 2) / t ** 3 * core) ** 0.25
    else:
        Lcr = (4 * math.pi ** 4 * ho * (1 - NU ** 2) / t ** 3 * core + math.pi ** 4 * ho ** 4 / 720) ** 0.25
    k = math.pi / Lcr
    kfe = k ** 4 * E * core + k ** 2 * G * Jf
    kfg = k ** 2 * (Af * (dx ** 2 * (Ixyf / Iyf) ** 2 - 2 * yof * dx * (Ixyf / Iyf) + hxf ** 2 + yof ** 2) + Ixf + Iyf)
    if not bending:
        kwe = E * t ** 3 / (6 * ho * (1 - NU ** 2))
        kwg = k ** 2 * t * ho ** 3 / 60
    else:
        xi = 2.0
        kwe = E * t ** 3 / (12 * (1 - NU ** 2)) * (3 / ho + k ** 2 * 19 * ho / 60 + k ** 4 * ho ** 3 / 240)
        r = Lcr / ho
        kwg = ho * t * math.pi ** 2 / 13440 * (
            ((45360 * (1 - xi) + 62160) * r ** 2 + 448 * math.pi ** 2 + (1 / r) ** 2 * (53 + 3 * (1 - xi)) * math.pi ** 4)
            / (math.pi ** 4 + 28 * math.pi ** 2 * r ** 2 + 420 * r ** 4))
    return dict(fod=(kfe + kwe) / (kfg + kwg), Lcr=Lcr)


# ------------------------------------------------------------------------------------------ 4. finite strip (pycufsm)
def load_strip():
    """pycufsm.fsm.strip. Stock pycufsm 0.2.0 fails under numpy 2.5 in the compiled assembler; if so, fall back to
    pycufsm's own pure-Python assembler with an int() that accepts one-element arrays (same workaround the author
    used; written here independently, no installed file touched)."""
    import pycufsm.fsm as pf
    nodes = np.array([[0, 0, 0, 1, 1, 1, 1, 1.0], [1, 10, 0, 1, 1, 1, 1, 1.0], [2, 10, 10, 1, 1, 1, 1, 1.0]])
    els = np.array([[0, 0, 1, 1.0, 0], [1, 1, 2, 1.0, 0]])
    kw = dict(props=np.array([[0, E, E, NU, NU, G]]), nodes=nodes, elements=els, lengths=np.array([50.0]),
              springs=np.array([]), constraints=np.array([]), GBT_con=GBT_OFF, B_C="S-S", m_all=np.ones((1, 1)),
              n_eigs=1, sect_props={})
    try:
        pf.strip(**kw)
        return pf.strip, "stock"
    except Exception as exc:                                     # noqa: BLE001
        import pycufsm.solve.analysis_p as ap

        def safe_int(v, *a):
            if isinstance(v, np.ndarray):
                v = v.reshape(-1)[0] if v.size == 1 else v
            return builtins.int(v, *a)

        ap.int = safe_int
        pf.analysis = ap
        pf.strip(**kw)
        return pf.strip, f"pure-python assembler (stock failed: {type(exc).__name__})"


GBT_OFF = {"glob": [0], "dist": [0], "local": [0], "other": [0], "o_space": 1, "couple": 1, "orth": 2, "norm": 0}


def mesh_section(t, corners, nw, nf, nl, nc=5):
    """Nodes of my own mesh, bottom lip tip -> top lip tip. Returns xy and indices of the 4 fold lines."""
    a, b, c = D - t, B - t, C - t / 2
    pts = []
    marks = {}

    def line(p, q, n, last=False):
        for k in range(n + (1 if last else 0)):
            s = k / n
            pts.append((p[0] + s * (q[0] - p[0]), p[1] + s * (q[1] - p[1])))

    if corners == "sharp":
        line((b, c), (b, 0), nl); marks["fl_b"] = len(pts)
        line((b, 0), (0, 0), nf); marks["wf_b"] = len(pts)
        line((0, 0), (0, a), nw); marks["wf_t"] = len(pts)
        line((0, a), (b, a), nf); marks["fl_t"] = len(pts)
        line((b, a), (b, a - c), nl, last=True)
    else:
        r = RI + t / 2

        def arc(cx, cy, a0, a1, key):
            n0 = len(pts)
            for k in range(nc):
                th = math.radians(a0 + (a1 - a0) * k / nc)
                pts.append((cx + r * math.cos(th), cy + r * math.sin(th)))
            marks[key] = n0 + nc // 2

        line((b, c), (b, r), nl)
        arc(b - r, r, 0, -90, "fl_b")
        line((b - r, 0), (r, 0), nf)
        arc(r, r, 270, 180, "wf_b")
        line((0, r), (0, a - r), nw)
        arc(r, a - r, 180, 90, "wf_t")
        line((r, a), (b - r, a), nf)
        arc(b - r, a - r, 90, 0, "fl_t")
        line((b, a - r), (b, a - c), nl, last=True)
    return np.array(pts), marks


def stress_field(xy, action):
    """Hand-written linear stress field, compression positive, scaled so the largest COMPRESSIVE node stress = FREF.
    Centroid from my own thin-walled integration of the mesh polyline (uniform t so t cancels)."""
    d = np.diff(xy, axis=0)
    L = np.hypot(d[:, 0], d[:, 1])
    mid = (xy[:-1] + xy[1:]) / 2
    xc, yc = (mid * L[:, None]).sum(0) / L.sum()
    x, y = xy[:, 0], xy[:, 1]
    if action == "axial":
        s = np.full(len(xy), 1.0)
    elif action == "bend_major":
        s = (y - yc) / (y.max() - yc)                     # top flange in compression
    elif action == "bend_minor_web_comp":
        s = (xc - x) / (xc - x.min())                     # web (x = 0) in compression
    elif action == "bend_minor_lips_comp":
        s = (x - xc) / (x.max() - xc)                     # lips (x = b) in compression
    else:
        raise ValueError(action)
    assert abs(s.max() - 1.0) < 1e-12
    return FREF * s, xc, yc


class Model:
    def __init__(self, strip, t, corners, action, mesh=(12, 6, 3), nc=5):
        self.strip = strip
        self.xy, self.marks = mesh_section(t, corners, *mesh, nc=nc)
        self.s, self.xc, self.yc = stress_field(self.xy, action)
        n = len(self.xy)
        self.n = n
        self.nodes = np.column_stack([np.arange(n), self.xy, np.ones((n, 4)), self.s])
        self.els = np.column_stack([np.arange(n - 1), np.arange(n - 1), np.arange(1, n), np.full(n - 1, t), np.zeros(n - 1)])
        self.props = np.array([[0, E, E, NU, NU, G]])

    def solve(self, lengths, n_eigs=3):
        lengths = np.atleast_1d(np.asarray(lengths, float))
        _, curve, shapes = self.strip(props=self.props, nodes=self.nodes, elements=self.els, lengths=lengths,
                                      springs=np.array([]), constraints=np.array([]), GBT_con=GBT_OFF, B_C="S-S",
                                      m_all=np.ones((len(lengths), 1)), n_eigs=n_eigs, sect_props={})
        lf = np.array([np.asarray(c).reshape(-1)[0] for c in curve], float)
        sh = [np.asarray(s)[0] for s in shapes]            # shapes[length][mode][dof], dof = [u1 v1 .. un vn | w1 th1 .. wn thn]
        return lf * FREF, sh

    def f1(self, length):
        return float(self.solve([length], n_eigs=2)[0][0])

    def metrics(self, shape):
        """In-plane translations: junction movement relative to the largest translation, and where the max is."""
        n = self.n
        u = np.real(shape[0:2 * n:2])
        w = np.real(shape[2 * n::2])
        tr = np.hypot(u, w)
        mx = tr.max()
        fl = max(tr[self.marks["fl_b"]], tr[self.marks["fl_t"]]) / mx
        wf = max(tr[self.marks["wf_b"]], tr[self.marks["wf_t"]]) / mx
        i = int(tr.argmax())
        part = ("lip" if i < self.marks["fl_b"] or i > self.marks["fl_t"] else
                "flange" if i < self.marks["wf_b"] or i > self.marks["wf_t"] else "web")
        if i in (self.marks["fl_b"], self.marks["fl_t"]):
            part = "flange/lip junction"
        if i in (0, n - 1):
            part = "lip tip"
        # largest translation inside each plate element (to see which plate really bends)
        seg = {"lip": tr[self.marks["fl_t"]:].max() / mx, "flange": tr[self.marks["wf_t"]:self.marks["fl_t"] + 1].max() / mx,
               "web": tr[self.marks["wf_b"]:self.marks["wf_t"] + 1].max() / mx}
        return dict(junction=float(fl), web_junction=float(wf), max_at=part, plate_max=seg)

    def minima(self, lengths):
        f, sh = self.solve(lengths)
        out = []
        for i in range(1, len(lengths) - 1):
            if f[i] < f[i - 1] and f[i] < f[i + 1]:
                res = minimize_scalar(self.f1, bounds=(lengths[i - 1], lengths[i + 1]), method="bounded",
                                      options={"xatol": 1e-3})
                fm, shm = self.solve([res.x], n_eigs=2)
                m = self.metrics(shm[0])
                cls = "distortional" if m["junction"] >= 0.5 and m["web_junction"] <= 0.3 else \
                      "local" if m["junction"] <= 0.25 else "mixed"
                out.append(dict(half_wave=float(res.x), stress=float(fm[0]), cls=cls, **m))
        return out, f


def shs_benchmark(strip):
    """Square hollow section 100 x 100 x 2 in uniform compression: every wall is a simply supported plate, k = 4."""
    w, t, n = 100.0, 2.0, 8
    pts = []
    for p, q in (((0, 0), (w, 0)), ((w, 0), (w, w)), ((w, w), (0, w)), ((0, w), (0, 0))):
        for k in range(n):
            pts.append((p[0] + (q[0] - p[0]) * k / n, p[1] + (q[1] - p[1]) * k / n))
    xy = np.array(pts)
    N = len(xy)
    nodes = np.column_stack([np.arange(N), xy, np.ones((N, 4)), np.full(N, FREF)])
    els = np.column_stack([np.arange(N), np.arange(N), (np.arange(N) + 1) % N, np.full(N, t), np.zeros(N)])

    def f(L):
        _, curve, _ = strip(props=np.array([[0, E, E, NU, NU, G]]), nodes=nodes, elements=els, lengths=np.array([L]),
                            springs=np.array([]), constraints=np.array([]), GBT_con=GBT_OFF, B_C="S-S",
                            m_all=np.ones((1, 1)), n_eigs=2, sect_props={})
        return float(np.asarray(curve[0]).reshape(-1)[0]) * FREF

    res = minimize_scalar(f, bounds=(60, 160), method="bounded")
    return dict(k=res.fun / plate(1.0, t, w), half_wave=res.x)


# ------------------------------------------------------------------------------------------ main
def pct(a, b):
    return 100.0 * (a / b - 1.0)


def main():
    out = {"checks": {}}
    table = json.loads(TABLE.read_text())
    rows = {(r["t"], r["corners"], r["action"]): r for r in table["rows"]}
    sprops = {(r["t"], r["corners"]): r for r in table["section_props"]}
    worst = {}

    def track(name, v):
        worst[name] = max(worst.get(name, 0.0), abs(v))

    # ---- 1
    print("=" * 110, "\n1. SECTION PROPERTIES (theirs vs mine, % difference)")
    st = plain_channel_selftest()
    print(f"   self-test plain channel: e {st['e_num']:.5f} vs exact {st['e_exact']:.5f}; Cw {st['Cw_num']:.6g} vs exact {st['Cw_exact']:.6g}")
    out["checks"]["plain_channel_selftest"] = st
    sec_out = []
    for corners in ("sharp", "rounded"):
        for t in THICK:
            pts, _ = outline(t, corners)
            n = numeric_props(pts, t)
            th = sprops[(t, corners)]
            mine = dict(A=n["A"], Ix=n["Ix"], Iy=n["Iy"], J=n["J"], Cw=n["Cw"], xc_from_web=n["xc"], x0_shear_centre_to_centroid=n["x0"])
            line = f"   t={t} {corners:7s}"
            rec = dict(t=t, corners=corners, mine_numeric=mine, diff_pct={})
            for k, v in mine.items():
                dp = pct(th[k], v)
                rec["diff_pct"][k] = dp
                track("props_numeric", dp)
                line += f" {k.split('_')[0]}={v:.6g}({dp:+.3f}%)"
            if corners == "sharp":
                cf = closed_form_props(t)
                cfm = dict(A=cf["A"], Ix=cf["Ix"], Iy=cf["Iy"], J=cf["J"], Cw=cf["Cw"], xc_from_web=cf["xc"], x0_shear_centre_to_centroid=cf["x0"])
                rec["mine_closed_form"] = cfm
                rec["closed_vs_theirs_pct"] = {k: pct(th[k], v) for k, v in cfm.items()}
                for v in rec["closed_vs_theirs_pct"].values():
                    track("props_closed", v)
                line += f"\n        closed form: e={cf['e']:.4f} x0={cf['x0']:.4f} Cw={cf['Cw']:.6g}; max |diff| vs theirs {max(abs(v) for v in rec['closed_vs_theirs_pct'].values()):.4f}%"
            print(line)
            sec_out.append(rec)
    out["checks"]["section_props"] = sec_out
    print(f"   worst difference: numeric {worst['props_numeric']:.4f} %, closed form {worst['props_closed']:.4f} %")

    # ---- 2 hand local
    print("=" * 110, "\n2. LOCAL BUCKLING: hand plate stresses (centreline flat widths) vs their finite strip f_local")
    loc_out = []
    for t in THICK:
        a, b, c = D - t, B - t, C - t / 2
        xc = closed_form_props(t)["xc"]
        web4, web697, web239 = plate(4, t, a), plate(6.97, t, a), plate(23.9, t, a)
        fl4, lip043, lip125 = plate(4, t, b), plate(0.43, t, c), plate(1.277, t, c)
        r_ = b / a
        # Schafer interaction fits (AISI S100 commentary hand method), flange/web and flange/lip local
        k_fw_ax = 4 * r_ ** 2 * (2 - r_ ** 0.4)
        k_fl = -11.07 * (c / b) ** 2 + 3.95 * (c / b) + 4
        exp_ax = min(plate(k_fw_ax, t, b), plate(k_fl, t, b))
        k_fw_b = 1.125 * min(4.0, (0.5 * 8 + 4 * 4 + 4) * r_ ** 2)
        exp_bm = min(plate(k_fw_b, t, b), plate(k_fl, t, b))
        psi = -xc / (b - xc)                                   # flange stress ratio, lips in compression
        k_flange_grad = 4 + 2 * (1 - psi) ** 3 + 2 * (1 - psi)
        fl_grad = plate(k_flange_grad, t, b)
        rr = {a_: rows[(t, "sharp", a_)]["f_local"] for a_ in ("axial", "bend_major", "bend_minor_web_comp", "bend_minor_lips_comp")}
        rec = dict(t=t, web_k4=web4, web_k6_97=web697, web_k23_9=web239, flange_k4=fl4, lip_k0_43=lip043, lip_k1_277_fixed_free=lip125,
                   flange_gradient_k=k_flange_grad, flange_gradient_stress=fl_grad,
                   expected_axial_interaction=exp_ax, expected_major_interaction=exp_bm,
                   implied_k=dict(axial_web=rr["axial"] / plate(1, t, a), major_web=rr["bend_major"] / plate(1, t, a),
                                  major_flange=rr["bend_major"] / plate(1, t, b),
                                  minor_web_comp_web=rr["bend_minor_web_comp"] / plate(1, t, a),
                                  minor_lips_comp_lip=rr["bend_minor_lips_comp"] / plate(1, t, c),
                                  minor_lips_comp_flange=rr["bend_minor_lips_comp"] / plate(1, t, b)),
                   their_f_local=rr,
                   ratio_axial_to_interaction=rr["axial"] / exp_ax, ratio_major_to_interaction=rr["bend_major"] / exp_bm)
        loc_out.append(rec)
        k = rec["implied_k"]
        print(f"   t={t}: web k=4 {web4:.1f}, k=6.97 {web697:.1f}, k=23.9 {web239:.1f}; flange k=4 {fl4:.1f}; lip k=0.43 {lip043:.1f}")
        print(f"      axial   FSM {rr['axial']:.1f}  implied web k {k['axial_web']:.2f} (4..6.97)   interaction hand {exp_ax:.1f} ratio {rec['ratio_axial_to_interaction']:.3f}")
        print(f"      major   FSM {rr['bend_major']:.1f}  implied web k {k['major_web']:.2f} (23.9), flange k {k['major_flange']:.2f} (4)   interaction hand {exp_bm:.1f} ratio {rec['ratio_major_to_interaction']:.3f}")
        print(f"      web-c   FSM {rr['bend_minor_web_comp']:.1f}  implied web k {k['minor_web_comp_web']:.2f}")
        print(f"      lips-c  FSM {rr['bend_minor_lips_comp']:.1f}  implied lip k {k['minor_lips_comp_lip']:.3f} (0.43 pinned .. 1.28 fixed), "
              f"flange k {k['minor_lips_comp_flange']:.2f} (gradient k = {k_flange_grad:.2f} -> {fl_grad:.0f} MPa)")
    out["checks"]["local_hand"] = loc_out

    # ---- 3 distortional
    print("=" * 110, "\n3. DISTORTIONAL closed form vs their sharp-corner f_dist (ratio = closed form / FSM)")
    dist_out = []
    for t in THICK:
        rec = dict(t=t)
        for act, bend in (("axial", False), ("bend_major", True)):
            lh, sp = lau_hancock(t, bend), schafer(t, bend)
            f = rows[(t, "sharp", act)]["f_dist"]
            rec[act] = dict(fsm=f, lau_hancock=lh["fod"], lh_ratio=lh["fod"] / f, lh_lambda=lh["lam"], lh_kphi=lh["kphi"],
                            lh_kphi_negative=lh["kphi_negative"], schafer=sp["fod"], sp_ratio=sp["fod"] / f, sp_Lcr=sp["Lcr"],
                            fsm_half_wave=rows[(t, "sharp", act)]["half_wave_dist"])
            track("dist_lh", pct(lh["fod"], f)); track("dist_sp", pct(sp["fod"], f))
            print(f"   t={t} {act:10s} FSM {f:7.1f} (L {rows[(t, 'sharp', act)]['half_wave_dist']:.0f}) | Lau-Hancock {lh['fod']:7.1f} ratio {lh['fod'] / f:.3f} "
                  f"(lambda {lh['lam']:.0f}, kphi {lh['kphi']:.1f}) | Schafer {sp['fod']:7.1f} ratio {sp['fod'] / f:.3f} (Lcr {sp['Lcr']:.0f})")
        dist_out.append(rec)
    out["checks"]["distortional_closed_form"] = dist_out

    # ---- 4 own FSM
    print("=" * 110, "\n4. OWN FINITE STRIP RUNS (pycufsm.fsm.strip called directly)")
    strip, backend = load_strip()
    print("   pycufsm backend:", backend)
    out["checks"]["pycufsm_backend"] = backend
    bm = shs_benchmark(strip)
    print(f"   benchmark SHS 100x100x2 uniform compression: k = {bm['k']:.4f} at half-wave {bm['half_wave']:.1f} mm (exact 4.000 at 100)")
    out["checks"]["shs_benchmark"] = bm
    lengths = np.geomspace(15.0, 1500.0, 70)
    fsm_out = []
    actions = ("axial", "bend_major", "bend_minor_web_comp", "bend_minor_lips_comp")
    fast = "--fast" in sys.argv
    cases = [(t, c) for c in ("sharp", "rounded") for t in THICK]
    if fast:
        cases = [(0.95, "sharp")]
    for t, corners in cases:
        for act in actions:
            m = Model(strip, t, corners, act)
            mins, curve = m.minima(lengths)
            r = rows[(t, corners, act)]
            loc = [x for x in mins if x["cls"] == "local"]
            dis = [x for x in mins if x["cls"] == "distortional"]
            rec = dict(t=t, corners=corners, action=act, mesh="12/6/3 (+5 per corner)", nodes=m.n, minima=mins,
                       their_f_local=r["f_local"], their_f_dist=r.get("f_dist"),
                       curve_end_stress=float(curve[-1]), curve_min=float(curve.min()))
            if loc:
                rec["my_f_local"] = loc[0]["stress"]; rec["my_half_wave_local"] = loc[0]["half_wave"]
                rec["local_diff_pct"] = pct(r["f_local"], loc[0]["stress"]); track("fsm_local", rec["local_diff_pct"])
            if dis:
                rec["my_f_dist"] = dis[0]["stress"]; rec["my_half_wave_dist"] = dis[0]["half_wave"]
                if r.get("f_dist"):
                    rec["dist_diff_pct"] = pct(r["f_dist"], dis[0]["stress"]); track("fsm_dist", rec["dist_diff_pct"])
            rec["dist_presence_agrees"] = bool(dis) == bool(r.get("f_dist"))
            rec["n_minima"] = len(mins)
            fsm_out.append(rec)
            s = f"   t={t} {corners:7s} {act:21s}"
            for x in mins:
                s += f" | {x['cls'][:5]} {x['stress']:8.2f} @ {x['half_wave']:6.1f} (junc {x['junction']:.2f}, max at {x['max_at']})"
            s += f" || theirs L {r['f_local']} D {r.get('f_dist')}"
            if "local_diff_pct" in rec:
                s += f" | dL {rec['local_diff_pct']:+.2f}%"
            if "dist_diff_pct" in rec:
                s += f" dD {rec['dist_diff_pct']:+.2f}%"
            print(s, flush=True)
    out["checks"]["own_fsm"] = fsm_out

    # finer mesh + linear length grid for the required case
    print("   second mesh 20/10/5 with a LINEAR half-wave grid (20..800 step 20), t = 0.95 sharp:")
    fine = []
    for act in actions:
        m = Model(strip, 0.95, "sharp", act, mesh=(20, 10, 5))
        mins, _ = m.minima(np.arange(20.0, 801.0, 20.0))
        r = rows[(0.95, "sharp", act)]
        fine.append(dict(action=act, minima=mins))
        print(f"      {act:21s}", " | ".join(f"{x['cls'][:5]} {x['stress']:.2f} @ {x['half_wave']:.1f}" for x in mins),
              f"|| theirs {r['f_local']} / {r.get('f_dist')}")
    out["checks"]["own_fsm_fine"] = fine

    # reference table
    print("   reference table (other program, sharp corners): mine / reference, theirs / reference")
    ref_out = []
    for (act, t), ref in REF_TABLE.items():
        mine = next(x for x in fsm_out if x["t"] == t and x["corners"] == "sharp" and x["action"] == act).get("my_f_dist") if not fast or t == 0.95 else None
        th = rows[(t, "sharp", act)]["f_dist"]
        ref_out.append(dict(action=act, t=t, reference=ref, theirs=th, mine=mine))
        print(f"      {act:10s} t={t}: ref {ref}  theirs {th} ({th / ref:.4f})  mine {mine if mine is None else round(mine, 2)} ({'' if mine is None else round(mine / ref, 4)})")
    out["checks"]["reference_table"] = ref_out

    # ---- 5 minor axis senses and convention
    print("=" * 110, "\n5. MINOR-AXIS STRESS CONVENTION")
    conv = []
    for t in THICK:
        xy, _ = mesh_section(t, "sharp", 12, 6, 3)
        b = B - t
        for act in ("bend_minor_web_comp", "bend_minor_lips_comp"):
            s, xc, _ = stress_field(xy, act)
            web_s = float(s[np.isclose(xy[:, 0], 0)].mean())
            lip_s = float(s[np.isclose(xy[:, 0], b)].mean())
            r = rows[(t, "sharp", act)]
            eff = (xc + t / 2) / xc if act.endswith("web_comp") else (b - xc + t / 2) / (b - xc)
            Iy = closed_form_props(t)["Iy"]
            # critical moment from the centreline stress, and what their JSON says
            ext = xc if act.endswith("web_comp") else (b - xc)
            Mcr = r["f_local"] * Iy / ext / 1e6
            conv.append(dict(t=t, action=act, web_stress=web_s, lip_stress=lip_s, max_compressive=float(s.max()),
                             min=float(s.min()), my_outer_factor=eff, their_outer_factor=r["extreme_fibre_factor"],
                             my_Mcr_local_kNm=Mcr, their_resultant_local=r["resultant_local"], f_local=r["f_local"]))
            print(f"   t={t} {act:21s}: reference field web {web_s:+7.1f}, lips {lip_s:+7.1f} MPa (max compression {s.max():.1f}); "
                  f"outer/centreline factor mine {eff:.4f} theirs {r['extreme_fibre_factor']}; Mcr,local mine {Mcr:.5f} theirs {r['resultant_local']} kNm")
        fw, fl_ = rows[(t, "sharp", "bend_minor_web_comp")]["f_local"], rows[(t, "sharp", "bend_minor_lips_comp")]["f_local"]
        print(f"      web-in-compression local {fw} vs lips-in-compression local {fl_}: ratio {fl_ / fw:.1f} (web sense must be much lower)")
    out["checks"]["minor_axis_convention"] = conv

    # ---- 6 units / resultants / outer values in JSON
    print("=" * 110, "\n6. JSON INTERNAL CONSISTENCY (resultants, outer-fibre values, units)")
    cons = []
    for (t, corners, act), r in rows.items():
        pts, _ = outline(t, corners)
        n = numeric_props(pts, t)
        xs = np.array(pts)[:, 0]
        ys = np.array(pts)[:, 1]
        if act == "axial":
            res = lambda f: f * n["A"] / 1e3; eff = 1.0
        elif act == "bend_major":
            ext = ys.max() - n["yc"]; res = lambda f: f * n["Ix"] / ext / 1e6; eff = (ext + t / 2) / ext
        elif act == "bend_minor_web_comp":
            ext = n["xc"] - xs.min(); res = lambda f: f * n["Iy"] / ext / 1e6; eff = (ext + t / 2) / ext
        else:
            ext = xs.max() - n["xc"]; res = lambda f: f * n["Iy"] / ext / 1e6; eff = (ext + t / 2) / ext
        d1 = pct(r["resultant_local"], res(r["f_local"]))
        d2 = pct(r["resultant_dist"], res(r["f_dist"])) if r.get("f_dist") else 0.0
        d3 = pct(r["extreme_fibre_factor"], eff)
        d4 = pct(r["f_local_outer"], r["f_local"] * eff)
        track("json_resultant", d1); track("json_resultant", d2); track("json_factor", d3); track("json_outer", d4)
        cons.append(dict(t=t, corners=corners, action=act, resultant_local_diff_pct=d1, resultant_dist_diff_pct=d2, factor_diff_pct=d3))
    print(f"   worst difference: resultants {worst['json_resultant']:.3f} %, extreme fibre factor {worst['json_factor']:.4f} %, outer stresses {worst['json_outer']:.4f} %")
    out["checks"]["json_consistency"] = dict(worst_resultant_pct=worst["json_resultant"], worst_factor_pct=worst["json_factor"],
                                             worst_outer_pct=worst["json_outer"])
    out["worst"] = worst
    print("=" * 110)
    print("WORST DIFFERENCES (%):", json.dumps({k: round(v, 4) for k, v in worst.items()}))
    (HERE / ("check_results_fast.json" if fast else "check_results.json")).write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
