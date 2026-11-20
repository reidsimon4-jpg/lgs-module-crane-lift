"""Elastic local and distortional buckling of the C89 lipped channel by the finite strip method (FSM).

Run it (about 7 minutes with the pycufsm pass, about 1 minute with --native-only):

    .venv/Scripts/python.exe analysis/liftcalc/buckling_fsm.py

It writes
    analysis/liftcalc/data/c89_buckling.json          the table: {"meta": ..., "rows": [...], "section_props": [...]}
    analysis/liftcalc/data/c89_buckling_curves.json   the raw signature curves behind every row
    results/buckling/c89_t###_<action>.png            one signature-curve plot per thickness and action

Section and material
    Cold-formed lipped channel "C89", out-to-out: web D = 89, flange B = 38, lip C = 9 mm.
    Base metal thickness t = 0.75, 0.95, 1.15 mm.  E = 200 000 MPa, nu = 0.3, G = E / 2.6.
    Corner models:
      "sharp"    centreline dimensions D - t, B - t, C - t/2 with square corners
      "rounded"  inside radius 2.0 mm (centreline radius 2.0 + t/2), every corner meshed with 8 strips
    Mesh: 16 strips on the web, 8 per flange, 4 per lip, 8 per rounded corner (twice the minimum asked for).

Units and signs
    mm, N, MPa.  Compression is positive.
    x-x is the MAJOR axis: parallel to the flanges, through the centroid. Bending about it puts one flange in compression.
    y-y is the MINOR axis: parallel to the web. Bending about it has two senses: web in compression, lips in compression.
    Model coordinates: X runs from the web centreline towards the lips, Z runs up the web from the bottom flange
    centreline. (pycufsm calls these two section coordinates x and y and calls the member axis z.)

Actions
    axial                 uniform compression
    bend_major            bending about x-x, top flange in compression
    bend_minor_web_comp   bending about y-y, web in compression, lips in tension
    bend_minor_lips_comp  bending about y-y, lips in compression, web in tension

What the stresses mean
    f_local and f_dist are the critical value of the LARGEST COMPRESSIVE STRESS IN THE MID-THICKNESS (centreline) MODEL,
    i.e. buckling load factor x reference stress at the extreme compressive node. This is the CUFSM convention.
    Each row also gives the same buckling state as a stress at the outer surface (f_*_outer = f_* x extreme_fibre_factor)
    and as a stress resultant (kN or kNm), so a user never has to guess which section modulus goes with which stress:
        M_cr = f x (I / distance to the extreme CENTRELINE node) = f_outer x (I / distance to the OUTER face).

Method
    Semi-analytical finite strip method, simply supported ends, one longitudinal half-wave: the "signature curve".
    121 log-spaced half-wave lengths from 10 to 3000 mm. Each minimum of the curve is then refined with a bounded
    one-dimensional search. Two solvers are run on every case and compared at every length:
      1. pycufsm 0.2.0, function pycufsm.fsm.strip (the Python port of CUFSM)  - reported when the two agree
      2. an independent implementation in this file (class FiniteStrip)         - cross-check, and fallback
    They differ by round-off only: about 1e-8 at the reported minima, and up to about 1e-5 at the longest half-waves
    of the rounded-corner models, where the stiffness matrix is ill-conditioned and pycufsm's general (unsymmetric)
    eigen-solver loses digits. The largest differences are stored in meta["crosscheck"].

Exact pycufsm calls used (pycufsm 0.2.0)
    from pycufsm.fsm import strip
    from pycufsm.pre.stresses import stress_gen

    props    = np.array([[0, E, E, nu, nu, G]])                      # [mat#, E_x, E_y, nu_x, nu_y, G]
    nodes    = np.array([[i, X_i, Z_i, 1, 1, 1, 1, 0.0], ...])       # [node#, x, y, dof_x, dof_y, dof_z, dof_rot, stress]
    elements = np.array([[e, node_i, node_j, t, 0], ...])            # [elem#, node_i, node_j, thickness, mat#]
    sect     = {"A", "cx", "cy", "Ixx", "Iyy", "Ixy", "phi", "I11", "I22", "J", "x0", "y0", "Cw", "B1", "B2", "wn"}

    nodes = stress_gen(nodes=nodes, sect_props=sect,                 # writes column 7, compression positive
                       forces={"P": P, "Mxx": Mxx, "Myy": Myy, "M11": 0, "M22": 0, "restrain": False, "offset": [0, 0]})
        axial                 P   = +F_REF * A
        bend_major            Mxx = +F_REF * Ix / (Z_max - Z_c)      (+Mxx compresses the +Z flange)
        bend_minor_web_comp   Myy = +F_REF * Iy / (X_c - X_min)      (+Myy compresses the web side, X < X_c)
        bend_minor_lips_comp  Myy = -F_REF * Iy / (X_max - X_c)
      F_REF = 100 MPa. The result is checked against the hand-written linear stress field in reference_stress().

    signature, curve, shapes = strip(
        props=props, nodes=nodes, elements=elements, lengths=lengths,
        springs=np.array([]), constraints=np.array([]),
        GBT_con={"glob": [0], "dist": [0], "local": [0], "other": [0], "o_space": 1, "couple": 1, "orth": 2, "norm": 0},
        B_C="S-S", m_all=np.ones((len(lengths), 1)), n_eigs=4, sect_props=sect)      # n_eigs=2 at a refined minimum
      curve[i, k]  = load factor of mode k at lengths[i]; buckling stress = curve * F_REF
      shapes[i, k] = [u_1 v_1 ... u_n v_n | w_1 th_1 ... w_n th_n], u = X translation, v = along the member,
                     w = Z translation, th = twist about the member axis.

    Section properties with warping would come from pycufsm.pre.cutwp.prop2(coord, ends); it is only used here as a
    cross-check of A, centroid, Ix, Iy, J and shear centre because its warping constant is wrong (see below).

What is wrong with pycufsm 0.2.0 in this virtual environment (numpy 2.5.5), and what this file does about it
    1. strip() raises "TypeError: only 0-dimensional arrays can be converted to Python scalars" inside the compiled
       pycufsm.solve.analysis_c.k_kg_global (int() of a one-element array, which numpy 2.5 refuses).
       Fix used: an in-process shim, _load_pycufsm(). It points pycufsm.fsm.analysis at pycufsm's own pure-Python twin
       pycufsm.solve.analysis_p and gives that module an int() that accepts one-element arrays.
       Nothing in site-packages is edited and nothing is installed.
    2. strip() drops every eigenvalue above 1e6 and then crashes ("could not broadcast ...") when fewer than n_eigs
       survive at some length. A reference stress of 100 MPa (not 1 MPa) and n_eigs = 4 keep clear of that.
    3. Node fixity flags (dof_x .. dof_rot = 0) are not applied correctly by pycufsm.solve.cfsm.constr_user: a plate with
       both long edges held came out with one edge free (the routine keeps one column too few and leaves the last
       degrees of freedom unrestrained). No fixities are used here, so the section results are not affected, but the
       plate benchmarks in the tests therefore use the independent solver.
    4. pycufsm.pre.cutwp.prop2 raises ValueError under numpy 2.5.5, and when helped past that it returns Cw = 0
       (its unit-warping loop never fills the warping array). Section properties are therefore computed in this file
       (section_properties) and Cw is verified against flexural-torsional buckling of the finite strip model.
    5. Constrained FSM (cFSM, pycufsm.solve.cfsm) cannot be used: y_dofs builds a wrong warping vector for the torsion
       mode (node number 0 doubles as its "not visited" marker) and base_vectors raises ValueError under numpy 2.5.5.
       So where the signature curve has no distortional minimum this file reports null, not a cFSM value.

How a minimum is classified (by its mode shape, not by its position)
    junction_ratio      largest in-plane translation of a flange/lip junction  / largest translation in the section
    web_junction_ratio  largest in-plane translation of a web/flange junction  / largest translation in the section
    rigid_body_fraction share of the area-weighted squared translations explained by one rigid-body motion of the section
      global        rigid_body_fraction >= 0.90
      distortional  junction_ratio >= 0.50 and web_junction_ratio <= 0.25  (flange and lip rotate about the web junction)
      local         junction_ratio <= 0.25 and web_junction_ratio <= 0.25  (fold lines stay put, plates bend between them)
      mixed         anything else
    In this section the two families are far apart: local minima have junction_ratio <= 0.13, distortional >= 0.93.

Checks (analysis/tests/test_buckling_table.py)
    - independent solver against exact plate buckling: simply supported k = 4, clamped 6.97, pure bending 23.9, and a
      plate with one free edge against the exact Timoshenko equation
    - both solvers against each other on every case
    - section properties against closed form, and the warping constant through flexural-torsional and lateral-torsional
      buckling of the plate model at a 3 m half-wave against beam theory (within 0.4 %)
    - distortional stresses against the other program's table (within 1.3 %) and against the Lau-Hancock / Hancock
      closed-form expressions of AS/NZS 4600 Appendix D (within 7 %)
    - web local buckling coefficient between 4 and 6.97; mesh doubled: results move by less than 0.12 %
"""
from __future__ import annotations

import argparse
import builtins
import json
import math
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import linalg as spla
from scipy.optimize import minimize_scalar

# ======================================================================================================== inputs
E_MPA = 200_000.0
NU = 0.3
G_MPA = E_MPA / 2.6
DEPTH, FLANGE, LIP = 89.0, 38.0, 9.0          # out-to-out, mm
R_INSIDE = 2.0                                 # inside corner radius of the "rounded" model, mm
THICKNESSES = (0.75, 0.95, 1.15)
CORNER_MODELS = ("sharp", "rounded")
ACTIONS = ("axial", "bend_major", "bend_minor_web_comp", "bend_minor_lips_comp")
ACTION_TEXT = {
    "axial": "axial compression",
    "bend_major": "major-axis bending (one flange in compression)",
    "bend_minor_web_comp": "minor-axis bending, web in compression",
    "bend_minor_lips_comp": "minor-axis bending, lips in compression",
}
MESH = {"web": 16, "flange": 8, "lip": 4, "corner": 8}             # strips per part (corner: rounded model only)
MESH_MINIMUM = {"web": 8, "flange": 4, "lip": 2, "corner": 4}      # the smallest mesh the task allows
FINE_CORNER = 64                                                    # corner chords used for the reported gross properties
L_MIN, L_MAX, N_LENGTHS = 10.0, 3000.0, 121                        # half-wave lengths, mm
F_REF = 100.0                                                       # reference stress handed to pycufsm, MPa
N_MODES = 4                                                         # modes kept per length
N_SCAN_MODES = 6                                                    # modes searched when no distortional minimum shows
MINIMA_TOL = 1.0e-6                                                 # pycufsm vs independent solver at a reported minimum
CROSSCHECK_TOL = 1.0e-4                                             # ... and anywhere on the curves (modes 1-4, all lengths)
CLASS_LIMITS = {"global_rigid_body_fraction": 0.90, "junction_moves": 0.50, "junction_fixed": 0.25}

# Distortional stresses from another program's table for the sharp-corner section. A cross-check, not the truth.
REFERENCE_DIST = {("axial", 0.95): 201.8, ("axial", 1.15): 253.2, ("bend_major", 0.95): 350.6, ("bend_major", 1.15): 435.4}

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(__file__).resolve().parent / "data"
JSON_PATH = DATA_DIR / "c89_buckling.json"
CURVES_PATH = DATA_DIR / "c89_buckling_curves.json"
PLOT_DIR = ROOT / "results" / "buckling"


def half_wave_lengths(n=N_LENGTHS, lo=L_MIN, hi=L_MAX):
    return np.logspace(math.log10(lo), math.log10(hi), n)


# ====================================================================================================== geometry
@dataclass
class Section:
    """Centreline model of the channel. Nodes run from the bottom lip tip, round the section, to the top lip tip."""
    t: float
    corners: str
    xy: np.ndarray            # (n, 2) node coordinates X, Z
    elems: list               # [(i, j), ...] strips
    elem_part: list           # part name of every strip
    h: float                  # centreline web depth  D - t
    b: float                  # centreline flange width  B - t
    c: float                  # centreline lip length  C - t/2
    r: float                  # centreline corner radius (0 for sharp)
    mesh: dict
    j_web_flange: tuple       # nodes at the web/flange junctions (bottom, top)
    j_flange_lip: tuple       # nodes at the flange/lip junctions (bottom, top)
    tips: tuple               # lip tip nodes (bottom, top)

    @property
    def n_nodes(self):
        return len(self.xy)

    def node_part(self, i):
        return self.elem_part[min(i, len(self.elems) - 1)]

    def nodes_of(self, part):
        return sorted({k for e, p in zip(self.elems, self.elem_part) if p == part for k in e})


def build_section(t, corners="sharp", mesh=None):
    """Mesh the channel. `mesh` may override entries of MESH, e.g. {"corner": 64}."""
    if corners not in CORNER_MODELS:
        raise ValueError(f"corners must be one of {CORNER_MODELS}")
    mesh = {**MESH, **(mesh or {})}
    h, b, c = DEPTH - t, FLANGE - t, LIP - t / 2.0
    r = 0.0 if corners == "sharp" else R_INSIDE + t / 2.0
    pts, parts = [(b, c)], []                         # start at the bottom lip tip

    def line_to(q, n, part):
        p = pts[-1]
        for i in range(1, n + 1):
            pts.append((p[0] + (q[0] - p[0]) * i / n, p[1] + (q[1] - p[1]) * i / n))
            parts.append(part)

    def arc_to(centre, a0, a1, n, part):
        for i in range(1, n + 1):
            a = a0 + (a1 - a0) * i / n
            pts.append((centre[0] + r * math.cos(a), centre[1] + r * math.sin(a)))
            parts.append(part)

    if corners == "sharp":
        line_to((b, 0.0), mesh["lip"], "lip_bottom")
        line_to((0.0, 0.0), mesh["flange"], "flange_bottom")
        line_to((0.0, h), mesh["web"], "web")
        line_to((b, h), mesh["flange"], "flange_top")
        line_to((b, h - c), mesh["lip"], "lip_top")
    else:
        if c - r <= 0 or b - 2 * r <= 0 or h - 2 * r <= 0:
            raise ValueError("corner radius too large for this section")
        nc = mesh["corner"]
        line_to((b, r), mesh["lip"], "lip_bottom")
        arc_to((b - r, r), 0.0, -math.pi / 2, nc, "corner_flange_lip_bottom")
        line_to((r, 0.0), mesh["flange"], "flange_bottom")
        arc_to((r, r), -math.pi / 2, -math.pi, nc, "corner_web_flange_bottom")
        line_to((0.0, h - r), mesh["web"], "web")
        arc_to((r, h - r), math.pi, math.pi / 2, nc, "corner_web_flange_top")
        line_to((b - r, h), mesh["flange"], "flange_top")
        arc_to((b - r, h - r), math.pi / 2, 0.0, nc, "corner_flange_lip_top")
        line_to((b, h - c), mesh["lip"], "lip_top")

    xy = np.array(pts, dtype=float)
    elems = [(i, i + 1) for i in range(len(xy) - 1)]
    if np.min(np.hypot(*np.diff(xy, axis=0).T)) < 1.0e-9:
        raise ValueError("zero-length strip in the section mesh")
    if not np.allclose(xy[::-1], np.column_stack([xy[:, 0], h - xy[:, 1]]), atol=1.0e-9):
        raise ValueError("section mesh is not symmetric about mid-depth")

    def near(x, z):                                    # node closest to an ideal (sharp) corner point
        return int(np.argmin(np.hypot(xy[:, 0] - x, xy[:, 1] - z)))

    return Section(t=float(t), corners=corners, xy=xy, elems=elems, elem_part=parts, h=h, b=b, c=c, r=r, mesh=mesh,
                   j_web_flange=(near(0.0, 0.0), near(0.0, h)), j_flange_lip=(near(b, 0.0), near(b, h)),
                   tips=(0, len(xy) - 1))


# ============================================================================================ section properties
def section_properties(sec):
    """Thin-walled (centreline) properties of an open single-branch section, exact for straight strips.

    A, centroid (xc, zc), Ix (about x-x, the major axis, = integral of Z^2 dA), Iy (minor), Ixy, J = sum(b t^3)/3,
    shear centre (x_sc, z_sc) and warping constant Cw by the sectorial-coordinate method. The plate's own t^3/12
    bending term is left out of Ix and Iy, as in CUFSM / CUTWP (it is below 0.03 % here).
    """
    xy, t = sec.xy, sec.t
    i_, j_ = np.array([e[0] for e in sec.elems]), np.array([e[1] for e in sec.elems])
    length = np.hypot(*(xy[j_] - xy[i_]).T)
    area = float(np.sum(length) * t)
    xc, zc = (((xy[i_] + xy[j_]) / 2.0) * length[:, None]).sum(axis=0) * t / area

    def integral(f, g):                                # integral of f g dA, f and g linear along every strip
        return float(np.sum(t * length * ((f[i_] * g[i_] + f[j_] * g[j_]) / 3.0 + (f[i_] * g[j_] + f[j_] * g[i_]) / 6.0)))

    x, z = xy[:, 0] - xc, xy[:, 1] - zc
    ix, iy, ixy = integral(z, z), integral(x, x), integral(x, z)
    j_tors = float(np.sum(length) * t ** 3 / 3.0)

    def sectorial(px, pz):                             # omega with pole (px, pz) in centroidal coordinates, zero at node 0
        w = np.zeros(len(xy))
        for a, b_ in sec.elems:
            w[b_] = w[a] + (x[a] - px) * (z[b_] - pz) - (x[b_] - px) * (z[a] - pz)
        return w

    w_c = sectorial(0.0, 0.0)
    i_wx, i_wz = integral(w_c, x), integral(w_c, z)
    det = ix * iy - ixy ** 2
    ex = (iy * i_wz - ixy * i_wx) / det                # shear centre relative to the centroid
    ez = -(ix * i_wx - ixy * i_wz) / det
    w_s = sectorial(ex, ez)
    w_n = w_s - integral(w_s, np.ones(len(xy))) / area  # normalised unit warping
    cw = integral(w_n, w_n)
    x0 = float(math.hypot(ex, ez))
    return {
        "A": area, "xc": float(xc), "zc": float(zc), "Ix": ix, "Iy": iy, "Ixy": ixy, "J": j_tors,
        "x_sc": float(xc + ex), "z_sc": float(zc + ez), "x0": x0, "Cw": cw, "wn": w_n,
        "rx": math.sqrt(ix / area), "ry": math.sqrt(iy / area), "ro1": math.sqrt((ix + iy) / area + x0 ** 2),
    }


def gross_properties(t, corners):
    """Gross properties reported in the table. Rounded corners are followed with FINE_CORNER chords per corner so the
    numbers are those of the true centreline arcs and do not depend on the buckling mesh."""
    sec = build_section(t, corners, {"corner": FINE_CORNER})
    p = section_properties(sec)
    return {
        "t": float(t), "corners": corners,
        "A": p["A"], "Ix": p["Ix"], "Iy": p["Iy"], "J": p["J"], "Cw": p["Cw"],
        "xc_from_web": p["xc"],                               # centroid from the WEB CENTRELINE
        "xc_from_web_outer_face": p["xc"] + t / 2.0,
        "x0_shear_centre_to_centroid": p["x0"],               # a distance, always positive
        "shear_centre_behind_web_centreline": -p["x_sc"],     # shear centre is on the far side of the web from the lips
        "Zx_centreline": p["Ix"] / (sec.h / 2.0), "Zx_outer_face": p["Ix"] / (DEPTH / 2.0),
        "Zy_web_centreline": p["Iy"] / p["xc"], "Zy_web_outer_face": p["Iy"] / (p["xc"] + t / 2.0),
        "Zy_lip_centreline": p["Iy"] / (sec.b - p["xc"]), "Zy_lip_outer_face": p["Iy"] / (sec.b - p["xc"] + t / 2.0),
        "rx": p["rx"], "ry": p["ry"], "ro1": p["ro1"],
        "centreline_web": sec.h, "centreline_flange": sec.b, "centreline_lip": sec.c, "centreline_corner_radius": sec.r,
    }


# ============================================================================================== reference stress
def reference_stress(sec, action, props=None):
    """Nodal longitudinal stress, compression positive, scaled so the largest compressive value is exactly 1.

    Returns (stress, info). info["resultant_per_unit_stress"] is A (mm2) for axial or the centreline section modulus
    (mm3) for bending, so buckling stress x that number = critical force (N) or moment (Nmm).
    info["extreme_fibre_factor"] = stress at the outer surface / stress at the extreme centreline node.
    """
    p = props or section_properties(sec)
    x, z = sec.xy[:, 0] - p["xc"], sec.xy[:, 1] - p["zc"]
    half_t = sec.t / 2.0
    if action == "axial":
        s, res, fac, unit = np.ones(sec.n_nodes), p["A"], 1.0, "kN"
    elif action == "bend_major":
        s, res, fac, unit = z / z.max(), p["Ix"] / z.max(), (z.max() + half_t) / z.max(), "kNm"
    elif action == "bend_minor_web_comp":
        s, res, fac, unit = x / x.min(), p["Iy"] / -x.min(), (-x.min() + half_t) / -x.min(), "kNm"
    elif action == "bend_minor_lips_comp":
        s, res, fac, unit = x / x.max(), p["Iy"] / x.max(), (x.max() + half_t) / x.max(), "kNm"
    else:
        raise ValueError(f"unknown action {action!r}")
    return s, {"resultant_per_unit_stress": float(res), "extreme_fibre_factor": float(fac), "resultant_unit": unit}


# =============================================================================== independent finite strip solver
_GAUSS_X, _GAUSS_W = np.polynomial.legendre.leggauss(5)       # exact to degree 9 (the integrands reach degree 7)
_GAUSS_X, _GAUSS_W = 0.5 * (_GAUSS_X + 1.0), 0.5 * _GAUSS_W


def _strip_parts(b, t, s1, s2):
    """Length-independent pieces of one strip's stiffness and geometric matrices, local DOF [u1 v1 w1 th1 u2 v2 w2 th2].

    Displacements (y along the member, k = pi / half-wave length a, simply supported ends):
        u = N(x).u sin(ky)   in the strip plane, across the strip        N = linear shape functions
        v = N(x).v cos(ky)   along the member
        w = H(x).q sin(ky)   normal to the strip, q = [w1 th1 w2 th2]     H = Hermite cubics, th = dw/dx
    Membrane strains  ex = u,x   ey = v,y   gxy = u,y + v,x      (plane stress, E1 = E / (1 - nu^2))
    Curvatures        kx = -w,xx ky = -w,yy kxy = 2 w,xy         (D = E t^3 / 12 (1 - nu^2), Dxy = G t^3 / 12)
    Geometric work    1/2 T (u,y^2 + v,y^2 + w,y^2), T = stress x t, linear across the strip
    After integrating along y (factor a/2):
        K  = (a/2) (K0 + k K1 + k^2 K2 + k^4 K4)        Kg = (a/2) k^2 G2
    """
    e1 = E_MPA / (1.0 - NU ** 2)
    d = E_MPA * t ** 3 / (12.0 * (1.0 - NU ** 2))
    dxy = G_MPA * t ** 3 / 12.0
    k0, k1, k2, k4, g2 = (np.zeros((8, 8)) for _ in range(5))
    iu, iv, iw = [0, 4], [1, 5], [2, 3, 6, 7]
    out = np.outer
    for xi, wt in zip(_GAUSS_X, _GAUSS_W):
        n = np.array([1.0 - xi, xi])
        dn = np.array([-1.0, 1.0]) / b
        hh = np.array([1 - 3 * xi ** 2 + 2 * xi ** 3, b * (xi - 2 * xi ** 2 + xi ** 3), 3 * xi ** 2 - 2 * xi ** 3, b * (xi ** 3 - xi ** 2)])
        dh = np.array([(-6 * xi + 6 * xi ** 2) / b, 1 - 4 * xi + 3 * xi ** 2, (6 * xi - 6 * xi ** 2) / b, 3 * xi ** 2 - 2 * xi])
        ddh = np.array([(-6 + 12 * xi) / b ** 2, (-4 + 6 * xi) / b, (6 - 12 * xi) / b ** 2, (6 * xi - 2) / b])
        ex, ey, ga, gb, kx, ky, kxy, nu_, nv_, nw_ = (np.zeros(8) for _ in range(10))
        ex[iu] = dn                 # ex  = N'.u
        ey[iv] = -n                 # ey  = -k N.v
        ga[iv] = dn                 # gxy = N'.v + k N.u
        gb[iu] = n
        kx[iw] = -ddh               # kx  = -H''.q
        ky[iw] = hh                 # ky  = k^2 H.q
        kxy[iw] = 2.0 * dh          # kxy = 2 k H'.q
        nu_[iu], nv_[iv], nw_[iw] = n, n, hh
        w_ = wt * b
        k0 += w_ * (t * (e1 * out(ex, ex) + G_MPA * out(ga, ga)) + d * out(kx, kx))
        k1 += w_ * t * (e1 * NU * (out(ex, ey) + out(ey, ex)) + G_MPA * (out(ga, gb) + out(gb, ga)))
        k2 += w_ * (t * (e1 * out(ey, ey) + G_MPA * out(gb, gb)) + d * NU * (out(kx, ky) + out(ky, kx)) + dxy * out(kxy, kxy))
        k4 += w_ * d * out(ky, ky)
        g2 += w_ * (s1 * (1.0 - xi) + s2 * xi) * t * (out(nu_, nu_) + out(nv_, nv_) + out(nw_, nw_))
    return k0, k1, k2, k4, g2


class FiniteStrip:
    """Independent simply supported finite strip model (one half-wave). Node DOF order: [U, V, W, TH] where U, W are
    the X and Z translations in the section plane, V is along the member and TH is the twist about the member axis.

    stress: nodal longitudinal stress, compression positive. solve() returns the critical multipliers of that stress
    field, so with a field whose largest compression is 1 MPa the multiplier is the buckling stress in MPa.
    fixed: optional list of (node, dof) restraints with dof in "U", "V", "W", "TH" (used for the plate benchmarks).
    """
    DOF = {"U": 0, "V": 1, "W": 2, "TH": 3}

    def __init__(self, xy, elems, thickness, stress, fixed=()):
        xy = np.asarray(xy, dtype=float)
        self.n_nodes = len(xy)
        nd = 4 * self.n_nodes
        self._m = [np.zeros((nd, nd)) for _ in range(5)]
        for e, (i, j) in enumerate(elems):
            dx, dz = xy[j] - xy[i]
            b = math.hypot(dx, dz)
            c, s = dx / b, dz / b
            t = thickness[e] if np.ndim(thickness) else thickness
            # local u = U c + W s (along the strip), w = -U s + W c (normal to it); v and th are unchanged
            tn = np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1.0]])
            tr = np.zeros((8, 8))
            tr[:4, :4] = tn
            tr[4:, 4:] = tn
            dof = np.r_[4 * i + np.arange(4), 4 * j + np.arange(4)]
            for target, part in zip(self._m, _strip_parts(b, t, stress[i], stress[j])):
                target[np.ix_(dof, dof)] += tr.T @ part @ tr
        fixed_dof = {4 * node + self.DOF[d] for node, d in fixed}
        self._free = np.array([k for k in range(nd) if k not in fixed_dof])

    def matrices(self, length):
        k = math.pi / length
        k0, k1, k2, k4, g2 = self._m
        return 0.5 * length * (k0 + k * k1 + k ** 2 * k2 + k ** 4 * k4), 0.5 * length * k ** 2 * g2

    def solve(self, length, n_modes=N_MODES):
        """Lowest positive multipliers and their shapes: (factors (m,), shapes (m, n_nodes, 4))."""
        stiff, geom = self.matrices(length)
        f = self._free
        stiff, geom = stiff[np.ix_(f, f)], geom[np.ix_(f, f)]
        d = 1.0 / np.sqrt(np.diag(stiff))               # unit-diagonal scaling: same eigenvalues, better conditioning
        # K is positive definite, Kg is not (tension zones), so solve Kg v = mu K v and take 1 / mu for mu > 0
        mu, vec = spla.eigh(geom * d[:, None] * d, stiff * d[:, None] * d)
        order = np.argsort(-mu)[:n_modes]
        mu, vec = mu[order], vec[:, order] * d[:, None]
        keep = mu > 0.0
        shapes = np.zeros((int(keep.sum()), 4 * self.n_nodes))
        shapes[:, f] = vec[:, keep].T
        return 1.0 / mu[keep], shapes.reshape(-1, self.n_nodes, 4)

    def first(self, length):
        return float(self.solve(length, 1)[0][0])


def native_model(sec, stress):
    return FiniteStrip(sec.xy, sec.elems, sec.t, stress)


# ======================================================================================================= pycufsm
_PYCUFSM = None
_GBT_OFF = {"glob": [0], "dist": [0], "local": [0], "other": [0], "o_space": 1, "couple": 1, "orth": 2, "norm": 0}


def _scalar_int(value, *args):
    """int() that also accepts a one-element numpy array, as pycufsm 0.2.0 expects (numpy 2.5 raises TypeError)."""
    if isinstance(value, np.ndarray) and value.size == 1:
        return builtins.int(value.reshape(-1)[0])
    return builtins.int(value, *args)


def _pycufsm_props():
    return np.array([[0, E_MPA, E_MPA, NU, NU, G_MPA]])


def _load_pycufsm():
    """Import pycufsm and make pycufsm.fsm.strip usable. Returns a dict; ["available"] says whether it worked.

    The shim is applied only if the stock call fails, lives in this Python process only, and edits no file.
    """
    global _PYCUFSM
    if _PYCUFSM is not None:
        return _PYCUFSM
    info = {"available": False, "version": None, "backend": None, "shim": None, "error": None}
    try:
        import pycufsm.fsm as pfsm
        from pycufsm.pre import stresses as pstresses
        try:
            from importlib.metadata import version
            info["version"] = version("pycufsm")
        except Exception:
            from pycufsm._version import __version__ as info_version
            info["version"] = info_version
    except Exception as exc:                                    # pycufsm not installed or not importable
        info["error"] = f"import failed: {type(exc).__name__}: {exc}"
        _PYCUFSM = info
        return info

    def probe():                                                # a 2-strip angle, one length, one mode
        nodes = np.array([[0, 0.0, 0.0, 1, 1, 1, 1, 1.0], [1, 40.0, 0.0, 1, 1, 1, 1, 1.0], [2, 40.0, 20.0, 1, 1, 1, 1, 1.0]])
        elements = np.array([[0, 0, 1, 1.0, 0], [1, 1, 2, 1.0, 0]])
        sect = {k: 0.0 for k in ("A", "cx", "cy", "Ixx", "Iyy", "Ixy", "phi", "I11", "I22", "J", "x0", "y0", "Cw", "B1", "B2")}
        sect["wn"] = np.zeros(3)
        pfsm.strip(props=_pycufsm_props(), nodes=nodes, elements=elements, lengths=np.array([100.0]), springs=np.array([]),
                   constraints=np.array([]), GBT_con=dict(_GBT_OFF), B_C="S-S", m_all=np.ones((1, 1)), n_eigs=1, sect_props=sect)

    try:
        probe()
        info["backend"] = pfsm.analysis.__name__
    except TypeError as first_error:
        try:
            import pycufsm.solve.analysis_p as analysis_p
            analysis_p.int = _scalar_int                         # shadows the builtin inside analysis_p only
            pfsm.analysis = analysis_p                           # strip() now assembles with the pure-Python twin
            probe()
            info["backend"] = "pycufsm.solve.analysis_p"
            info["shim"] = ("pycufsm.fsm.analysis -> pycufsm.solve.analysis_p with a one-element-array-safe int(); "
                            f"needed because the stock call raised TypeError: {first_error}")
        except Exception as exc:
            info["error"] = f"strip() unusable even with the shim: {type(exc).__name__}: {exc}"
            _PYCUFSM = info
            return info
    except Exception as exc:
        info["error"] = f"strip() failed: {type(exc).__name__}: {exc}"
        _PYCUFSM = info
        return info
    info.update(available=True, fsm=pfsm, stresses=pstresses)
    _PYCUFSM = info
    return info


def pycufsm_sect_props(p):
    """This module's property dict in pycufsm's Sect_Props layout (x0, y0 are shear-centre COORDINATES there)."""
    return {"A": p["A"], "cx": p["xc"], "cy": p["zc"], "Ixx": p["Ix"], "Iyy": p["Iy"], "Ixy": p["Ixy"], "phi": 0.0,
            "I11": p["Ix"], "I22": p["Iy"], "J": p["J"], "x0": p["x_sc"], "y0": p["z_sc"], "Cw": p["Cw"],
            "B1": 0.0, "B2": 0.0, "wn": p["wn"]}


class PycufsmStrip:
    """pycufsm.fsm.strip for one section and action. See the module docstring for the exact calls."""

    def __init__(self, sec, action, props=None):
        lib = _load_pycufsm()
        if not lib["available"]:
            raise RuntimeError(lib["error"])
        self._strip = lib["fsm"].strip
        p = props or section_properties(sec)
        n = sec.n_nodes
        self.sect = pycufsm_sect_props(p)
        nodes = np.column_stack([np.arange(n), sec.xy[:, 0], sec.xy[:, 1], np.ones((n, 4)), np.zeros(n)]).astype(float)
        x, z = sec.xy[:, 0], sec.xy[:, 1]
        forces = {"P": 0.0, "Mxx": 0.0, "Myy": 0.0, "M11": 0.0, "M22": 0.0, "restrain": False, "offset": [0.0, 0.0]}
        if action == "axial":
            forces["P"] = F_REF * p["A"]
        elif action == "bend_major":
            forces["Mxx"] = F_REF * p["Ix"] / (z.max() - p["zc"])
        elif action == "bend_minor_web_comp":
            forces["Myy"] = F_REF * p["Iy"] / (p["xc"] - x.min())
        elif action == "bend_minor_lips_comp":
            forces["Myy"] = -F_REF * p["Iy"] / (x.max() - p["xc"])
        else:
            raise ValueError(f"unknown action {action!r}")
        self.nodes = lib["stresses"].stress_gen(nodes=nodes, forces=forces, sect_props=self.sect)
        by_hand = F_REF * reference_stress(sec, action, p)[0]
        if not np.allclose(self.nodes[:, 7], by_hand, rtol=1e-9, atol=1e-9 * F_REF):
            raise RuntimeError("pycufsm stress_gen disagrees with the hand-written reference stress field")
        self.elements = np.array([[e, i, j, sec.t, 0] for e, (i, j) in enumerate(sec.elems)], dtype=float)
        self.n_nodes = n

    def solve(self, lengths, n_modes=N_MODES):
        """Buckling stresses (n_lengths, n_modes) in MPa and shapes (n_lengths, n_modes, n_nodes, 4) as [U V W TH]."""
        lengths = np.atleast_1d(np.asarray(lengths, dtype=float))
        _, curve, shapes = self._strip(
            props=_pycufsm_props(), nodes=self.nodes.copy(), elements=self.elements.copy(), lengths=lengths,
            springs=np.array([]), constraints=np.array([]), GBT_con=dict(_GBT_OFF), B_C="S-S",
            m_all=np.ones((len(lengths), 1)), n_eigs=n_modes, sect_props=self.sect)
        n = self.n_nodes
        out = np.empty(shapes.shape[:2] + (n, 4))
        out[..., 0] = shapes[..., 0:2 * n:2]            # u  = X translation
        out[..., 1] = shapes[..., 1:2 * n:2]            # v  = along the member
        out[..., 2] = shapes[..., 2 * n::2]             # w  = Z translation
        out[..., 3] = shapes[..., 2 * n + 1::2]         # th = twist
        return curve * F_REF, out


def cutwp_crosscheck(sec):
    """Compare section_properties() with pycufsm.pre.cutwp.prop2 (run behind a local numpy stand-in, because the stock
    call raises ValueError under numpy 2.5.5). Returns a small report; never raises."""
    report = {"ran": False}
    try:
        import pycufsm.pre.cutwp as cutwp
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        return report

    class _Numpy:                                       # numpy, except diff() of two numbers gives a number
        def __getattr__(self, name):
            return getattr(np, name)

        @staticmethod
        def diff(a, *args, **kwargs):
            out = np.diff(a, *args, **kwargs)
            return out.item() if getattr(out, "size", 0) == 1 else out

    mine = section_properties(sec)
    ends = np.array([[i, j, sec.t] for i, j in sec.elems], dtype=float)
    real = cutwp.np
    try:
        try:
            theirs = cutwp.prop2(coord=sec.xy.copy(), ends=ends.copy())
            report["stock_call"] = "ok"
        except Exception as exc:
            report["stock_call"] = f"{type(exc).__name__}: {exc}"
            cutwp.np = _Numpy()
            theirs = cutwp.prop2(coord=sec.xy.copy(), ends=ends.copy())
        pairs = {"A": ("A", "A"), "xc": ("cx", "xc"), "Ix": ("Ixx", "Ix"), "Iy": ("Iyy", "Iy"), "J": ("J", "J"), "x_sc": ("x0", "x_sc")}
        report["max_rel_diff_A_xc_Ix_Iy_J_xsc"] = float(max(abs(theirs[a] / mine[b] - 1.0) for a, b in pairs.values()))
        report["Cw_cutwp"] = float(theirs["Cw"])
        report["Cw_this_module"] = float(mine["Cw"])
        report["ran"] = True
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        cutwp.np = real
    return report


# ============================================================================================ mode classification
def mode_metrics(sec, shape):
    """Numbers that describe one buckled shape (n_nodes, 4) = [U, V, W, TH]; see the module docstring."""
    u, w = shape[:, 0], shape[:, 2]
    disp = np.hypot(u, w)
    dmax = float(disp.max())
    xy = sec.xy
    area = np.zeros(sec.n_nodes)                       # tributary area of every node
    for i, j in sec.elems:
        half = 0.5 * sec.t * math.hypot(*(xy[j] - xy[i]))
        area[i] += half
        area[j] += half
    # best rigid-body motion of the whole section: U = U0 - phi (Z - Z0), W = W0 + phi (X - X0)
    x0, z0 = np.average(xy[:, 0], weights=area), np.average(xy[:, 1], weights=area)
    a_mat = np.zeros((2 * sec.n_nodes, 3))
    a_mat[0::2, 0], a_mat[0::2, 2] = 1.0, -(xy[:, 1] - z0)
    a_mat[1::2, 1], a_mat[1::2, 2] = 1.0, xy[:, 0] - x0
    rhs = np.empty(2 * sec.n_nodes)
    rhs[0::2], rhs[1::2] = u, w
    sw = np.sqrt(np.repeat(area, 2))
    sol = np.linalg.lstsq(a_mat * sw[:, None], rhs * sw, rcond=None)[0]
    rigid = 1.0 - float(np.sum((sw * (rhs - a_mat @ sol)) ** 2) / np.sum((sw * rhs) ** 2))
    # flanges: rotation of the chord web-junction -> lip-junction, and bending of the flange away from that chord
    rotation, bending = 0.0, 0.0
    for jw, jf, part in ((sec.j_web_flange[0], sec.j_flange_lip[0], "flange_bottom"), (sec.j_web_flange[1], sec.j_flange_lip[1], "flange_top")):
        chord = xy[jf] - xy[jw]
        bf = float(np.hypot(*chord))
        e = chord / bf
        normal_disp = -u * e[1] + w * e[0]
        nodes = sec.nodes_of(part)
        s = ((xy[nodes] - xy[jw]) @ e) / bf
        dev = normal_disp[nodes] - (normal_disp[jw] + s * (normal_disp[jf] - normal_disp[jw]))
        rotation = max(rotation, abs(normal_disp[jf] - normal_disp[jw]) / dmax)
        bending = max(bending, float(np.max(np.abs(dev))) / dmax)
    where = sec.node_part(int(np.argmax(disp)))
    return {
        "junction_ratio": float(disp[list(sec.j_flange_lip)].max() / dmax),
        "web_junction_ratio": float(disp[list(sec.j_web_flange)].max() / dmax),
        "lip_tip_ratio": float(disp[list(sec.tips)].max() / dmax),
        "rigid_body_fraction": rigid,
        "flange_rotation_ratio": float(rotation),      # (chord rotation x flange width) / largest translation
        "flange_bending_ratio": float(bending),        # flange bow away from its chord / largest translation
        "max_displacement_at": where.replace("_bottom", "").replace("_top", ""),
    }


def classify(metrics):
    lim = CLASS_LIMITS
    if metrics["rigid_body_fraction"] >= lim["global_rigid_body_fraction"]:
        return "global"
    if metrics["web_junction_ratio"] <= lim["junction_fixed"]:
        if metrics["junction_ratio"] >= lim["junction_moves"]:
            return "distortional"
        if metrics["junction_ratio"] <= lim["junction_fixed"]:
            return "local"
    return "mixed"


# ================================================================================================== one case
def local_minima(values):
    """Indices i (interior) with values[i] < values[i-1] and values[i] <= values[i+1]."""
    v = np.asarray(values)
    return [i for i in range(1, len(v) - 1) if v[i] < v[i - 1] and v[i] <= v[i + 1]]


def refine_minimum(model, lo, hi):
    """Half-wave length of the minimum of the first-mode curve of the independent model between lo and hi."""
    res = minimize_scalar(model.first, bounds=(lo, hi), method="bounded", options={"xatol": 1.0e-4})
    return float(res.x)


def analyse_case(t, corners, action, use_pycufsm=True, lengths=None, mesh=None):
    """Signature curve, minima and their classification for one thickness, corner model and action.

    Returns a dict with the table row under "row" and the arrays used for the plots and the curves file.
    """
    lengths = half_wave_lengths() if lengths is None else np.asarray(lengths, dtype=float)
    sec = build_section(t, corners, mesh)
    props = section_properties(sec)
    stress, info = reference_stress(sec, action, props)
    native = native_model(sec, stress)

    # ---- independent solver over the whole range; classify every mode on the way
    curve_native = np.empty((len(lengths), N_MODES))
    classes_mode1 = []
    scan_lowest = {}                                   # lowest grid value of each shape class among modes 1..N_SCAN_MODES
    for i, length in enumerate(lengths):
        lam, shapes = native.solve(length, N_SCAN_MODES)
        curve_native[i] = lam[:N_MODES]
        for k in range(len(lam)):
            cls = classify(mode_metrics(sec, shapes[k]))
            if k == 0:
                classes_mode1.append(cls)
            if cls not in scan_lowest or lam[k] < scan_lowest[cls]["stress"]:
                scan_lowest[cls] = {"stress": float(lam[k]), "half_wave": float(length), "mode": k + 1}

    # ---- pycufsm over the whole range, compared mode by mode
    engine, curve, cross = "native", curve_native, {"pycufsm_used": False}
    py = None
    if use_pycufsm:
        try:
            py = PycufsmStrip(sec, action, props)
            curve_py, _ = py.solve(lengths, N_MODES)
            diff = np.abs(curve_py / curve_native - 1.0)
            cross = {"pycufsm_used": True, "curves": float(diff.max()), "signature": float(diff[:, 0].max()), "at_minima": 0.0}
            if cross["curves"] <= CROSSCHECK_TOL:
                engine, curve = "pycufsm", curve_py
            else:
                cross["note"] = "pycufsm and the independent solver disagree beyond the tolerance; independent values reported"
        except Exception as exc:                        # keep going with the independent solver
            cross = {"pycufsm_used": False, "error": f"{type(exc).__name__}: {exc}"}
            py = None
    signature = curve[:, 0]

    # ---- minima of the signature curve, refined and classified from the mode shape
    minima = []
    for i in local_minima(signature):
        length = refine_minimum(native, lengths[i - 1], lengths[i + 1])
        lam_n, shapes_n = native.solve(length, 2)
        f_min, shape = float(lam_n[0]), shapes_n[0]
        if engine == "pycufsm":
            lam_p, shapes_p = py.solve([length], 2)
            diff_here = abs(float(lam_p[0, 0]) / f_min - 1.0)
            cross["at_minima"] = max(cross["at_minima"], diff_here)
            if diff_here <= MINIMA_TOL:
                f_min, shape = float(lam_p[0, 0]), shapes_p[0, 0]
            else:                                       # never seen; keep the independent value and say so
                cross["note"] = "pycufsm differs from the independent solver at a minimum; independent value reported there"
        metrics = mode_metrics(sec, shape)
        minima.append({"half_wave": length, "stress": f_min, "class": classify(metrics), **metrics, "shape": shape})

    def lowest(cls):
        found = [m for m in minima if m["class"] == cls]
        return min(found, key=lambda m: m["stress"]) if found else None

    loc, dist = lowest("local"), lowest("distortional")

    # ---- how much the answer moves when the mesh is doubled (same half-wave length)
    mesh_check = {}
    fine_mesh = {k: 2 * v for k, v in sec.mesh.items()}
    if loc or dist:
        sec2 = build_section(t, corners, fine_mesh)
        native2 = native_model(sec2, reference_stress(sec2, action)[0])
        for name, m in (("local", loc), ("dist", dist)):
            if m:
                mesh_check[name] = 100.0 * (native2.first(m["half_wave"]) / native.first(m["half_wave"]) - 1.0)

    row = _make_row(sec, action, info, loc, dist, minima, scan_lowest, engine, cross, mesh_check)
    return {"row": row, "section": sec, "lengths": lengths, "curve": curve, "curve_native": curve_native,
            "classes_mode1": classes_mode1, "minima": minima, "local": loc, "dist": dist, "engine": engine, "cross": cross}


def _mode_summary(m):
    if m is None:
        return None
    keys = ("class", "junction_ratio", "web_junction_ratio", "lip_tip_ratio", "rigid_body_fraction",
            "flange_rotation_ratio", "flange_bending_ratio", "max_displacement_at")
    return {k: (round(m[k], 4) if isinstance(m[k], float) else m[k]) for k in keys}


def _make_row(sec, action, info, loc, dist, minima, scan_lowest, engine, cross, mesh_check):
    t = sec.t
    fac = info["extreme_fibre_factor"]
    scale = 1.0e-3 if info["resultant_unit"] == "kN" else 1.0e-6

    def stress(m):
        return None if m is None else round(m["stress"], 3)

    def length(m):
        return None if m is None else round(m["half_wave"], 2)

    def outer(m):
        return None if m is None else round(m["stress"] * fac, 3)

    def resultant(m):
        return None if m is None else _sig(m["stress"] * info["resultant_per_unit_stress"] * scale, 6)

    notes = []
    if loc:
        notes.append(f"Local: {loc['max_displacement_at']} plate buckling, junctions stay put "
                     f"(flange/lip junction moves {loc['junction_ratio']:.2f} of the largest displacement).")
    else:
        notes.append("No local minimum found on the signature curve.")
    if dist:
        notes.append(f"Distortional: flange and lip rotate about the web junction (flange/lip junction moves "
                     f"{dist['junction_ratio']:.2f}, web junction {dist['web_junction_ratio']:.2f} of the largest displacement); "
                     "a distinct second minimum of the signature curve.")
        if loc and dist["stress"] < loc["stress"]:
            notes.append("The distortional minimum is LOWER than the local minimum, so distortional buckling governs elastically "
                         "and a check that uses f_local alone would be unconservative.")
    else:
        d_any = scan_lowest.get("distortional")
        if d_any is None:
            reason = ("both flange/lip junctions are in tension for this sense of bending. " if action == "bend_minor_web_comp" else "")
            notes.append(
                "No distortional minimum: the signature curve has no second minimum and no mode with a distortional shape "
                f"exists among modes 1-{N_SCAN_MODES} at any of the {N_LENGTHS} half-wave lengths; {reason}"
                "f_dist is null (constrained FSM is not usable in pycufsm 0.2.0 here, so no cFSM value is given). "
                + ("For the opposite sense of bending see bend_minor_lips_comp." if action == "bend_minor_web_comp" else ""))
        else:
            notes.append(
                "No distinct distortional minimum on the signature curve; f_dist is null (no constrained FSM available). "
                f"Lowest distortional-shaped mode found: {d_any['stress']:.1f} MPa at {d_any['half_wave']:.0f} mm (mode {d_any['mode']}).")
    ref = REFERENCE_DIST.get((action, round(t, 2))) if sec.corners == "sharp" else None
    row = {
        "t": t, "corners": sec.corners, "action": action,
        "f_local": stress(loc), "half_wave_local": length(loc),
        "f_dist": stress(dist), "half_wave_dist": length(dist),
        "note": " ".join(n.strip() for n in notes),
        "extreme_fibre_factor": round(fac, 5),
        "f_local_outer": outer(loc), "f_dist_outer": outer(dist),
        "resultant_unit": info["resultant_unit"], "resultant_local": resultant(loc), "resultant_dist": resultant(dist),
        "mode_local": _mode_summary(loc), "mode_dist": _mode_summary(dist),
        "signature_minima": [{"half_wave": round(m["half_wave"], 2), "stress": round(m["stress"], 3), "class": m["class"]} for m in minima],
        # grid scan (not refined) of modes 1-6: the lowest stress at which each shape class occurs anywhere on the curves
        "scan_lowest_by_class": {k: {"stress": round(v["stress"], 2), "half_wave": round(v["half_wave"], 1), "mode": v["mode"]}
                                 for k, v in sorted(scan_lowest.items()) if k != "mixed"},
        "solver": engine,
        # relative difference between pycufsm and the independent solver (round-off only), as a power-of-ten upper bound
        "pycufsm_vs_independent": ({"at_reported_minima_below": _decade(cross["at_minima"]),
                                    "signature_curve_below": _decade(cross["signature"]),
                                    "modes_1_to_4_all_lengths_below": _decade(cross["curves"])}
                                   | ({"note": cross["note"]} if "note" in cross else {})) if cross.get("pycufsm_used") else None,
        "mesh_doubling_change_pct": {k: round(v, 3) for k, v in mesh_check.items()},
    }
    if ref is not None and dist is not None:
        row["reference_f_dist"] = ref
        row["f_dist_over_reference"] = round(dist["stress"] / ref, 4)
    return row


# ================================================================================================= verification
def plate_benchmarks(n_strips=16):
    """Classical plate buckling coefficients k = f_cr / [pi^2 E / (12 (1 - nu^2)) (t/b)^2] from the independent solver."""
    b, t = 100.0, 1.0
    f_e = math.pi ** 2 * E_MPA / (12.0 * (1.0 - NU ** 2)) * (t / b) ** 2
    xy = np.array([[b * i / n_strips, 0.0] for i in range(n_strips + 1)])
    elems = [(i, i + 1) for i in range(n_strips)]
    last = n_strips
    simply = [(0, "U"), (0, "W"), (last, "W")]
    clamped = simply + [(0, "TH"), (last, "TH")]

    def k_min(stress, fixed, lo, hi):
        model = FiniteStrip(xy, elems, t, stress, fixed)
        return model.first(refine_minimum(model, lo, hi)) / f_e

    uniform = np.ones(n_strips + 1)
    return {
        "simply_supported_uniform_compression": {"k": k_min(uniform, simply, 60.0, 160.0), "theory": 4.0},
        "clamped_uniform_compression": {"k": k_min(uniform, clamped, 40.0, 110.0), "theory": 6.97},
        "simply_supported_pure_bending": {"k": k_min(1.0 - 2.0 * xy[:, 0] / b, simply, 40.0, 110.0), "theory": 23.9},
        "one_edge_free_uniform_compression_at_a_equals_b": {         # exact value for nu = 0.3, Timoshenko and Gere art. 9.4
            "k": FiniteStrip(xy, elems, t, uniform, [(0, "U"), (0, "W")]).first(b) / f_e, "theory": 1.4016},
    }


def column_buckling_stress(p, length):
    """Classical elastic buckling stresses of a singly symmetric column (symmetry axis x): minor-axis flexural,
    torsional, and flexural-torsional. Returns (least, parts)."""
    f_ex = math.pi ** 2 * E_MPA * p["Ix"] / (p["A"] * length ** 2)
    f_ey = math.pi ** 2 * E_MPA * p["Iy"] / (p["A"] * length ** 2)
    f_t = (G_MPA * p["J"] + math.pi ** 2 * E_MPA * p["Cw"] / length ** 2) / (p["A"] * p["ro1"] ** 2)
    beta = 1.0 - (p["x0"] / p["ro1"]) ** 2
    f_ft = ((f_ex + f_t) - math.sqrt((f_ex + f_t) ** 2 - 4.0 * beta * f_ex * f_t)) / (2.0 * beta)
    return min(f_ey, f_ft), {"flexural_minor": f_ey, "torsional": f_t, "flexural_torsional": f_ft}


def beam_lateral_buckling_stress(p, length, z_extreme):
    """Classical lateral-torsional buckling of a channel bent about its axis of symmetry x-x under uniform moment,
    as the stress at the extreme centreline node."""
    m_cr = math.sqrt((math.pi ** 2 * E_MPA * p["Iy"] / length ** 2) * (G_MPA * p["J"] + math.pi ** 2 * E_MPA * p["Cw"] / length ** 2))
    return m_cr * z_extreme / p["Ix"]


def global_buckling_check(t, corners, length=L_MAX):
    """Finite strip model at a long half-wave against beam theory with this module's A, Ix, Iy, J, Cw and x0.
    Agreement checks the warping constant, which pycufsm's cutwp cannot supply."""
    sec = build_section(t, corners)
    p = section_properties(sec)
    fsm_axial = native_model(sec, reference_stress(sec, "axial", p)[0]).first(length)
    fsm_bend = native_model(sec, reference_stress(sec, "bend_major", p)[0]).first(length)
    th_axial = column_buckling_stress(p, length)[0]
    th_bend = beam_lateral_buckling_stress(p, length, sec.h / 2.0)
    return {"t": t, "corners": corners, "half_wave": length,
            "axial_fsm": fsm_axial, "axial_beam_theory": th_axial, "axial_ratio": fsm_axial / th_axial,
            "bend_major_fsm": fsm_bend, "bend_major_beam_theory": th_bend, "bend_major_ratio": fsm_bend / th_bend}


# ======================================================================================================== plots
_INK, _INK2, _MUTED, _GRID, _AXIS, _SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
_SERIES = {"sharp": "#2a78d6", "rounded": "#eb6834"}        # validated two-colour set (colour-blind safe on this surface)
_MARK = {"sharp": "o", "rounded": "s"}
_MARK_SIZE = {"sharp": 9.5, "rounded": 5.5}                 # the two minima nearly coincide: small square inside a larger dot
_DASH = {"sharp": "-", "rounded": (0, (5, 2.5))}            # dashes keep the rounded curve visible where the two coincide


def deformed_outline(sec, shape, scale, n_sub=8):
    """Buckled centreline for drawing: cubic (Hermite) bending and linear in-plane movement inside every strip."""
    xi = np.linspace(0.0, 1.0, n_sub + 1)
    out = []
    for i, j in sec.elems:
        d = sec.xy[j] - sec.xy[i]
        b = float(np.hypot(*d))
        c, s = d / b
        ui, wi, uj, wj = (c * shape[i, 0] + s * shape[i, 2], -s * shape[i, 0] + c * shape[i, 2],
                          c * shape[j, 0] + s * shape[j, 2], -s * shape[j, 0] + c * shape[j, 2])
        u = (1 - xi) * ui + xi * uj
        w = ((1 - 3 * xi ** 2 + 2 * xi ** 3) * wi + b * (xi - 2 * xi ** 2 + xi ** 3) * shape[i, 3]
             + (3 * xi ** 2 - 2 * xi ** 3) * wj + b * (xi ** 3 - xi ** 2) * shape[j, 3])
        along, normal = xi * b + scale * u, scale * w
        pts = sec.xy[i] + np.outer(along, [c, s]) + np.outer(normal, [-s, c])
        out.append(pts if not out else pts[1:])
    return np.vstack(out)


def plot_name(t, action):
    return f"c89_t{int(round(t * 100)):03d}_{action}.png"


def plot_case(t, action, by_corner, path):
    """Signature curves of the sharp and rounded models on one pair of axes, minima marked, mode shapes alongside."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

    plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 9.5})
    fig = plt.figure(figsize=(10.6, 6.0), dpi=160, facecolor=_SURFACE)
    ax = fig.add_axes([0.075, 0.115, 0.585, 0.615], facecolor=_SURFACE)
    lengths = by_corner["sharp"]["lengths"]
    lo = min(np.min(by_corner[c]["curve"][:, 0]) for c in CORNER_MODELS)
    hi = max(np.max(by_corner[c]["curve"][:, 0]) for c in CORNER_MODELS)
    handles = []
    for corners in CORNER_MODELS:
        res = by_corner[corners]
        colour = _SERIES[corners]
        ax.plot(res["lengths"], res["curve"][:, 0], color=colour, lw=1.8, ls=_DASH[corners], solid_capstyle="round",
                solid_joinstyle="round", dash_capstyle="round", zorder=3 if corners == "sharp" else 4)
        text = []
        for name, m in (("local", res["local"]), ("distortional", res["dist"])):
            if m:
                ax.plot([m["half_wave"]], [m["stress"]], _MARK[corners], ms=_MARK_SIZE[corners], color=colour, mec=_SURFACE,
                        mew=1.4, zorder=5 if corners == "sharp" else 6)
                text.append(f"{name} {m['stress']:.1f} MPa at {m['half_wave']:.0f} mm")
            else:
                text.append(f"no {name} minimum")
        label = ("Sharp corners" if corners == "sharp" else "Rounded corners, inside radius 2 mm") + ":  " + ";  ".join(text)
        handles.append(Line2D([], [], color=colour, lw=1.8, ls=_DASH[corners], marker=_MARK[corners], ms=_MARK_SIZE[corners] - 1.5,
                              mec=_SURFACE, mew=1.2, label=label))
    ref = REFERENCE_DIST.get((action, round(t, 2)))
    if ref and by_corner["sharp"]["dist"]:
        ax.plot([by_corner["sharp"]["dist"]["half_wave"]], [ref], "x", ms=8, mew=1.8, color=_INK2, zorder=7)
        handles.append(Line2D([], [], color=_INK2, lw=0, marker="x", ms=8, mew=1.8,
                              label=f"Reference table (other program, sharp corners):  distortional {ref:.1f} MPa"))
    # one short name under each pair of minima
    for name, key in (("Local", "local"), ("Distortional", "dist")):
        pts = [by_corner[c][key] for c in CORNER_MODELS if by_corner[c][key]]
        if pts:
            x = math.exp(np.mean([math.log(m["half_wave"]) for m in pts]))
            y = min(m["stress"] for m in pts)
            ax.annotate(name, (x, y), xytext=(0, -15), textcoords="offset points", ha="center", va="top", color=_INK2, fontsize=9.5)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(L_MIN, L_MAX)
    ax.set_ylim(lo / 1.45, hi * 1.12)
    plain = FuncFormatter(lambda v, _: f"{v:,.0f}")
    ax.xaxis.set_major_locator(LogLocator(base=10, subs=(1.0, 2.0, 5.0), numticks=20))
    ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1.0, 2.0, 5.0), numticks=20))
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_formatter(plain)
        axis.set_minor_formatter(NullFormatter())
    ax.tick_params(which="both", colors=_MUTED, length=0, labelsize=9)
    ax.grid(True, which="major", color=_GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(_AXIS)
        ax.spines[side].set_linewidth(0.8)
    ax.set_xlabel("Half-wave length (mm)", color=_INK2)
    ax.set_ylabel("Elastic buckling stress (MPa)", color=_INK2)
    legend = ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.01, 1.015), frameon=False, fontsize=9.3,
                       handlelength=3.4, borderaxespad=0.0, labelspacing=0.45)
    for txt in legend.get_texts():
        txt.set_color(_INK)
    fig.text(0.075, 0.955, f"C89 lipped channel, t = {t:.2f} mm: {ACTION_TEXT[action]}", color=_INK, fontsize=13.5, fontweight="bold", va="center")
    fig.text(0.075, 0.915, "Finite strip signature curve (simply supported, one half-wave). Stress = largest compressive stress "
             "at mid-thickness when the section buckles.", color=_INK2, fontsize=9.3, va="center")

    # mode shapes of the sharp-corner model at its two minima
    sharp = by_corner["sharp"]
    sec = sharp["section"]
    for slot, (title, m) in enumerate((("Local mode", sharp["local"]), ("Distortional mode", sharp["dist"]))):
        axm = fig.add_axes([0.715, 0.50 - 0.42 * slot, 0.255, 0.335], facecolor=_SURFACE)
        axm.set_aspect("equal")
        axm.axis("off")
        if m:
            u, w = m["shape"][:, 0], m["shape"][:, 2]
            scale = 0.16 * DEPTH / float(np.hypot(u, w).max())
            if u[int(np.argmax(np.hypot(u, w)))] < 0 and abs(u).max() >= abs(w).max():
                scale = -scale                                   # draw the larger movement towards +X where it is sideways
            axm.plot(sec.xy[:, 0], sec.xy[:, 1], color=_AXIS, lw=1.2, solid_capstyle="round")
            outline = deformed_outline(sec, m["shape"], scale)
            axm.plot(outline[:, 0], outline[:, 1], color=_SERIES["sharp"], lw=1.7, solid_capstyle="round", solid_joinstyle="round")
            axm.set_title(f"{title}, half-wave {m['half_wave']:.0f} mm", color=_INK2, fontsize=9.3, pad=4)
        else:
            axm.set_title(title, color=_INK2, fontsize=9.3, pad=4)
            axm.text(sec.b / 2.0, sec.h / 2.0, "none for this action:\nno distortional minimum", color=_MUTED, fontsize=9,
                     ha="center", va="center")
        axm.set_xlim(-22, sec.b + 22)
        axm.set_ylim(-18, sec.h + 18)
    fig.text(0.715, 0.045, "Buckled shape of the sharp-corner model (blue) over the\nundeformed centreline (grey), displacements not to scale.",
             color=_MUTED, fontsize=8.3, va="center")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=_SURFACE)
    plt.close(fig)


# ====================================================================================================== run all
def _sig(x, digits=6):
    return float(f"{x:.{digits}g}")


def _decade(x):
    """Smallest power of ten that is not below x (1e-16 at least)."""
    return float(f"1e{math.ceil(math.log10(max(x, 1.0e-16)))}")


def run_all(use_pycufsm=True, make_plots=True, write=True, log=print):
    """Analyse every thickness, corner model and action; write the JSON files and the plots. Returns the table dict."""
    lengths = half_wave_lengths()
    results = {}
    for corners in CORNER_MODELS:
        for t in THICKNESSES:
            for action in ACTIONS:
                res = analyse_case(t, corners, action, use_pycufsm=use_pycufsm, lengths=lengths)
                results[(t, corners, action)] = res
                r = res["row"]
                fd = "   none" if r["f_dist"] is None else f"{r['f_dist']:7.1f}"
                ld = "    -" if r["half_wave_dist"] is None else f"{r['half_wave_dist']:5.0f}"
                diff = None if r["pycufsm_vs_independent"] is None else r["pycufsm_vs_independent"]["at_reported_minima_below"]
                fl = "   none" if r["f_local"] is None else f"{r['f_local']:7.1f}"
                ll = "    -" if r["half_wave_local"] is None else f"{r['half_wave_local']:5.0f}"
                log(f"t={t:.2f} {corners:7s} {action:21s} local {fl} MPa @ {ll} mm   "
                    f"dist {fd} MPa @ {ld} mm   solver={r['solver']}" + ("" if diff is None else f" (differs below {diff:.0e} at the minima)"))

    rows = [results[(t, c, a)]["row"] for c in CORNER_MODELS for t in THICKNESSES for a in ACTIONS]
    props = [{k: (_sig(v, 7) if isinstance(v, float) else v) for k, v in gross_properties(t, c).items()}
             for c in CORNER_MODELS for t in THICKNESSES]

    # ---- cross-checks and verification stored with the table
    lib = _load_pycufsm() if use_pycufsm else {"available": False, "version": None, "backend": None, "shim": None, "error": "not requested"}
    checks = [r["pycufsm_vs_independent"] for r in rows if r["pycufsm_vs_independent"] is not None]
    reference = [{"t": r["t"], "action": r["action"], "f_dist": r["f_dist"], "reference": r["reference_f_dist"],
                  "ratio": r["f_dist_over_reference"]} for r in rows if "reference_f_dist" in r]
    benchmarks = {k: {"k": round(v["k"], 4), "theory": v["theory"]} for k, v in plate_benchmarks().items()}
    global_checks = [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in global_buckling_check(t, c).items()}
                     for c in CORNER_MODELS for t in THICKNESSES]
    cutwp = cutwp_crosscheck(build_section(0.95, "sharp")) if use_pycufsm else {"ran": False}
    if cutwp.get("ran"):
        cutwp = {**cutwp, "max_rel_diff_A_xc_Ix_Iy_J_xsc": float(f"{cutwp['max_rel_diff_A_xc_Ix_Iy_J_xsc']:.0e}"),
                 "Cw_this_module": _sig(cutwp["Cw_this_module"], 7)}
    n_sharp, n_round = build_section(0.95, "sharp").n_nodes, build_section(0.95, "rounded").n_nodes
    mesh_changes = [abs(v) for r in rows for v in r["mesh_doubling_change_pct"].values()]

    meta = {
        "title": "Elastic local and distortional buckling of the C89 lipped channel (finite strip method)",
        "units": {"length": "mm", "stress": "MPa", "area": "mm2", "second_moment": "mm4", "warping": "mm6", "resultant": "kN or kNm"},
        "section": {"web_D": DEPTH, "flange_B": FLANGE, "lip_C": LIP, "dimensions": "out-to-out", "thicknesses": list(THICKNESSES),
                    "corner_models": {"sharp": "centreline D - t, B - t, C - t/2, square corners",
                                      "rounded": f"inside radius {R_INSIDE} mm, centreline radius {R_INSIDE} + t/2"}},
        "material": {"E": E_MPA, "nu": NU, "G": round(G_MPA, 3), "G_rule": "E / 2.6"},
        "axes": {"x-x": "major axis, parallel to the flanges, through the centroid; bending about it compresses one flange",
                 "y-y": "minor axis, parallel to the web; two senses: web in compression, lips in compression"},
        "actions": dict(ACTION_TEXT),
        "stress_definition": ("f_local and f_dist are the critical largest compressive stress at mid-thickness (centreline model, CUFSM "
                              "convention) = load factor x reference stress at the extreme compressive node. f_*_outer = f_* x "
                              "extreme_fibre_factor is the same buckling state read at the outer surface. resultant_* is the critical "
                              "axial force (kN) or moment (kNm) of the finite strip model. Pair f_* with a centreline section modulus "
                              "and f_*_outer with an outer-face section modulus; both give the same moment."),
        "usage_notes": [
            "Multiplying f_local or f_dist by an OUTER-FACE section modulus understates the critical moment by the "
            "extreme_fibre_factor (0.9 to 1.3 % for major-axis bending, 1.4 to 2.2 % for lips in compression, 3.3 to 5.3 % for "
            "web in compression). "
            "That is on the safe side; use f_*_outer or resultant_* for the exact value.",
            "bend_major and bend_minor_lips_comp: the distortional minimum is below the local minimum for every thickness, "
            "so a distortional check is needed for both; f_local alone is not enough.",
            "bend_minor_web_comp has no distortional mode (f_dist is null): only local buckling of the web applies.",
            "Rounded-corner rows are 0.6 to 7 % above the sharp-corner rows; the sharp-corner rows are the conservative choice.",
        ],
        "method": {
            "analysis": "semi-analytical finite strip method, simply supported ends, one longitudinal half-wave (signature curve)",
            "half_wave_lengths": {"min": L_MIN, "max": L_MAX, "count": N_LENGTHS, "spacing": "logarithmic"},
            "minima": "strict local minima of the first-mode curve, each refined by a bounded 1-D search (tolerance 1e-4 mm)",
            "classification": {"basis": "mode shape at the refined minimum", "limits": dict(CLASS_LIMITS),
                               "rule": "global if rigid_body_fraction >= 0.90; else distortional if junction_ratio >= 0.50 and "
                                       "web_junction_ratio <= 0.25; else local if both ratios <= 0.25; else mixed"},
            "no_distortional_minimum": "f_dist = null with the reason in the row note; cFSM is not usable in pycufsm 0.2.0 here",
            "reference_stress_mpa": F_REF, "modes_kept": N_MODES,
        },
        "mesh": {"strips": dict(MESH), "minimum_required": dict(MESH_MINIMUM), "nodes_sharp": n_sharp, "nodes_rounded": n_round,
                 "dof_sharp": 4 * n_sharp, "dof_rounded": 4 * n_round,
                 "largest_change_when_mesh_is_doubled_pct": round(max(mesh_changes), 3) if mesh_changes else None},
        "solver": {
            "reported": "pycufsm.fsm.strip where it agrees with the independent solver, else the independent solver (see each row)",
            "pycufsm_version": lib.get("version"), "pycufsm_backend": lib.get("backend"), "pycufsm_shim": lib.get("shim"),
            "pycufsm_error": lib.get("error"),
            "independent": "class FiniteStrip in buckling_fsm.py: own strip matrices by Gauss quadrature, scipy.linalg.eigh",
            "rows_from_pycufsm": sum(1 for r in rows if r["solver"] == "pycufsm"), "rows_from_independent": sum(1 for r in rows if r["solver"] == "native"),
        },
        "pycufsm_calls": [
            "pycufsm.pre.stresses.stress_gen(nodes=nodes, forces={'P','Mxx','Myy','M11','M22','restrain': False,'offset': [0, 0]}, sect_props=sect)",
            "pycufsm.fsm.strip(props=[[0,E,E,nu,nu,G]], nodes=[[n,x,y,1,1,1,1,stress]], elements=[[e,i,j,t,0]], lengths=lengths, "
            "springs=np.array([]), constraints=np.array([]), GBT_con={'glob':[0],'dist':[0],'local':[0],'other':[0],'o_space':1,"
            "'couple':1,'orth':2,'norm':0}, B_C='S-S', m_all=np.ones((n_lengths,1)), n_eigs=4, sect_props=sect)",
        ],
        "crosscheck": {
            "pycufsm_vs_independent": {
                "cases_compared": len(checks),
                "rel_diff_at_reported_minima_below": max(c["at_reported_minima_below"] for c in checks) if checks else None,
                "rel_diff_signature_curve_below": max(c["signature_curve_below"] for c in checks) if checks else None,
                "rel_diff_modes_1_to_4_all_lengths_below": max(c["modes_1_to_4_all_lengths_below"] for c in checks) if checks else None,
                "tolerance_at_minima": MINIMA_TOL, "tolerance_all_lengths": CROSSCHECK_TOL,
                "compared": f"modes 1-{N_MODES} at all {N_LENGTHS} half-wave lengths, and mode 1 at every refined minimum",
                "why_they_differ": "round-off only. The difference grows with half-wave length because the stiffness matrix becomes "
                                   "ill-conditioned there (condition number about 1e11 at 3000 mm for the rounded-corner mesh); "
                                   "at the local and distortional minima it is far smaller.",
            },
            "reference_table_sharp_corners": reference,
            "cutwp": cutwp,
        },
        "verification": {
            "plate_buckling_coefficients_independent_solver": benchmarks,
            "long_half_wave_vs_beam_theory": global_checks,
            "note": "the long half-wave check confirms A, Ix, Iy, J, Cw and x0 together (ratios within 0.5 % of 1)",
        },
        "section_props_note": ("Thin-walled centreline properties. xc_from_web is measured from the WEB CENTRELINE "
                               "(xc_from_web_outer_face adds t/2). x0_shear_centre_to_centroid is a distance. Rounded corners "
                               f"use {FINE_CORNER} chords per corner. Centroid and shear centre lie on the x-x axis at mid-depth."),
        "known_issues": [
            "pycufsm 0.2.0 strip() raises TypeError under numpy 2.5.5 in the compiled analysis_c; run here through an in-process shim "
            "that uses pycufsm's own pure-Python analysis_p. No installed file is changed.",
            "pycufsm strip() crashes when fewer than n_eigs eigenvalues are below 1e6 at some length; avoided with a 100 MPa reference stress.",
            "pycufsm node fixity flags are not applied correctly (cfsm.constr_user); not used here.",
            "pycufsm.pre.cutwp.prop2 fails under numpy 2.5.5 and returns Cw = 0 when helped past it; Cw comes from this module.",
            "pycufsm constrained FSM (cFSM) is unusable (wrong warping vector in y_dofs, ValueError in base_vectors); "
            "rows with no distortional minimum therefore carry f_dist = null.",
        ],
        "software": {"python": platform.python_version(), "numpy": np.__version__, "scipy": __import__("scipy").__version__},
        "curves_file": CURVES_PATH.name,
        "plots": {"folder": "results/buckling", "pattern": "c89_t###_<action>.png (### = thickness x 100)"},
    }
    table = {"meta": meta, "rows": rows, "section_props": props}

    if write:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        JSON_PATH.write_text(json.dumps(table, indent=1) + "\n", encoding="utf-8")
        curves = {
            "meta": {"content": "first and second mode buckling stress (MPa) at every half-wave length (mm) behind c89_buckling.json; "
                                "class_mode1 gives the shape class of the first mode: L local, D distortional, G global, M mixed",
                     "table": JSON_PATH.name},
            "half_wave_lengths": [round(float(v), 4) for v in lengths],
            "curves": [{"t": t, "corners": c, "action": a, "solver": results[(t, c, a)]["engine"],
                        "mode1": [round(float(v), 4) for v in results[(t, c, a)]["curve"][:, 0]],
                        "mode2": [round(float(v), 4) for v in results[(t, c, a)]["curve"][:, 1]],
                        "class_mode1": "".join(k[0].upper() for k in results[(t, c, a)]["classes_mode1"])}
                       for c in CORNER_MODELS for t in THICKNESSES for a in ACTIONS],
        }
        CURVES_PATH.write_text(json.dumps(curves, separators=(",", ":")) + "\n", encoding="utf-8")
        log(f"wrote {JSON_PATH}")
        log(f"wrote {CURVES_PATH}")
    if make_plots:
        for t in THICKNESSES:
            for action in ACTIONS:
                path = PLOT_DIR / plot_name(t, action)
                plot_case(t, action, {c: results[(t, c, action)] for c in CORNER_MODELS}, path)
        log(f"wrote {len(THICKNESSES) * len(ACTIONS)} plots to {PLOT_DIR}")
    return table


def main(argv=None):
    parser = argparse.ArgumentParser(description="Finite strip buckling table for the C89 lipped channel.")
    parser.add_argument("--native-only", action="store_true", help="skip pycufsm (fast; independent solver only)")
    parser.add_argument("--no-plots", action="store_true", help="do not write the PNG plots")
    args = parser.parse_args(argv)
    table = run_all(use_pycufsm=not args.native_only, make_plots=not args.no_plots)
    cross = table["meta"]["crosscheck"]
    both = cross["pycufsm_vs_independent"]
    print("pycufsm vs independent solver, relative difference: below", both["rel_diff_at_reported_minima_below"],
          "at the minima | below", both["rel_diff_modes_1_to_4_all_lengths_below"], "anywhere on the curves")
    for ref in cross["reference_table_sharp_corners"]:
        print(f"reference check t={ref['t']} {ref['action']}: {ref['f_dist']} vs {ref['reference']} MPa (ratio {ref['ratio']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
