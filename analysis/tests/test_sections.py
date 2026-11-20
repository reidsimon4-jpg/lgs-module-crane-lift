"""Checks of the thin-walled section routine: closed-form results and pyCUFSM's independent routine."""
import sys, os, math
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from liftcalc import sections as S


def test_plain_channel_shear_centre_and_warping():
    # plain channel, centreline web a, flange b, thickness t: e = 3 b^2 / (6 b + a) behind the web,
    # Cw = t b^3 a^2 (3 b + 2 a) / (12 (6 b + a))   (Timoshenko & Gere / standard tables)
    a, b, t = 100.0, 40.0, 1.0
    p = S.open_section_props([(b, -a / 2), (0, -a / 2), (0, a / 2), (b, a / 2)], t)
    e = 3 * b * b / (6 * b + a)
    assert abs(p.xs - (-e)) < 1e-9 * a and abs(p.ys) < 1e-9
    Cw = t * b ** 3 * a ** 2 * (3 * b + 2 * a) / (12 * (6 * b + a))
    assert abs(p.Cw - Cw) < 1e-9 * Cw
    assert abs(p.J - (a + 2 * b) * t ** 3 / 3) < 1e-12


def test_lipped_channel_closed_form():
    for t in (0.75, 0.95, 1.15):
        p = S.c89(t); cf = S.closed_form_lipped_channel(89.0, 38.0, 9.0, t)
        assert abs(p.A - cf["A"]) < 1e-9 and abs(p.xc - cf["xbar"]) < 1e-9
        assert abs(p.Ix - cf["Ix"]) < 1e-6 * cf["Ix"] and abs(p.Iy - cf["Iy"]) < 1e-6 * cf["Iy"]
        # the engine weighs the same centreline strip: kg/m = t (D - t + 2 (B - t) + 2 (C - t/2)) * 7850e-6
        assert abs(p.kg_per_m - t * ((89 - t) + 2 * (38 - t) + 2 * (9 - t / 2)) * 7850e-6) < 1e-12


def test_shear_centre_by_shear_flow():
    """Independent method: the shear centre is where a transverse shear produces no twist. Integrate the shear flow
    q(s) = -V Q(s) / Ix from one lip tip and take moments about the origin (no sectorial coordinates involved)."""
    for t, ri in ((0.95, 0.0), (1.15, 0.0), (0.95, 2.0)):
        nodes = S.lipped_channel_nodes(89.0, 38.0, 9.0, t, ri)
        p = S.open_section_props(nodes, t)
        Q = 0.0; torque = 0.0; n = 400
        for (x1, y1), (x2, y2) in zip(nodes[:-1], nodes[1:]):
            L = math.hypot(x2 - x1, y2 - y1); dx, dy = (x2 - x1) / L, (y2 - y1) / L
            for k in range(n):
                s0 = (k + 0.5) * L / n; x, y = x1 + dx * s0, y1 + dy * s0
                Q += t * (y - p.yc) * (L / n) / 2                      # first moment up to the middle of this slice
                q = -Q / p.Ix                                          # shear flow for V = 1 along +y
                torque += q * (x * dy - y * dx) * (L / n)             # moment of q ds about the origin
                Q += t * (y - p.yc) * (L / n) / 2
        # resultant of the flow is V = 1 in +y acting at x = torque (moment of a unit +y force at x_s about the origin is +x_s)
        assert abs(torque - p.xs) < 2e-3 * 89.0


def test_against_other_codes():
    """Second and third opinions. (1) pyCUFSM's CUTWP routine when it runs (pyCUFSM 0.2.0 fails under numpy 2.x: then skipped).
    (2) Values printed by the Infinity Framer engine's own cold-formed module for the same sharp-cornered section
    (recorded 20 Nov 2026, engine 0.7.1); the engine code is not part of this repository."""
    framer = {0.75: dict(A=134.981, Ix=172332.0, Iy=26622.2, J=25.309, x0=28.409, Cw=4.1961e7),
              0.95: dict(A=170.240, Ix=216189.0, Iy=33146.0, J=51.214, x0=28.188, Cw=5.1898e7),
              1.15: dict(A=205.160, Ix=259175.9, Iy=39435.4, J=90.441, x0=27.968, Cw=6.1340e7)}
    for t, f in framer.items():
        p = S.c89(t)
        assert abs(p.A - f["A"]) < 2e-3 * f["A"] and abs(p.Ix - f["Ix"]) < 2e-3 * f["Ix"] and abs(p.Iy - f["Iy"]) < 2e-3 * f["Iy"]
        assert abs(p.J - f["J"]) < 2e-3 * f["J"] and abs(p.x0 - f["x0"]) < 2e-3 * f["x0"] and abs(p.Cw - f["Cw"]) < 2e-3 * f["Cw"]
    try:
        from pycufsm.pre.cutwp import prop2
        nodes = S.lipped_channel_nodes(89.0, 38.0, 9.0, 0.95)
        out = prop2(np.array(nodes, float), np.array([[i, i + 1, 0.95] for i in range(len(nodes) - 1)], float))
    except (ValueError, ImportError):
        return
    p = S.c89(0.95)
    assert abs(out["A"] - p.A) < 1e-6 * p.A and abs(out["Cw"] - p.Cw) < 1e-4 * p.Cw and abs(out["xo"] - p.xs) < 1e-2


def test_rounded_corners_reduce_area_slightly():
    sharp, rnd = S.c89(0.95, 0.0), S.c89(0.95, 2.0)
    assert 0.94 * sharp.A < rnd.A < sharp.A
    assert 0.9 * sharp.Ix < rnd.Ix < sharp.Ix


def test_built_up():
    s = S.c89(1.15)
    b2b, box = S.BuiltUp("b2b", s), S.BuiltUp("boxed", s)
    assert abs(b2b.A - 2 * s.A) < 1e-12 and b2b.Iy > 2 * s.Iy and box.Iy > b2b.Iy
