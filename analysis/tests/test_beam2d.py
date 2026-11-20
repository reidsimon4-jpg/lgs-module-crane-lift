"""Checks of the 2D beam statics against textbook results."""
import numpy as np, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from liftcalc.beam2d import solve, summary


def test_simply_supported_udl():
    r = solve(6.0, 1e4, [0.0, 6.0], w_segments=[(0, 6, 2.0)])
    assert abs(max(r["M"]) - 2.0 * 6 ** 2 / 8) < 1e-3
    assert abs(r["reactions"][0.0] - 6.0) < 1e-3 and abs(r["reactions"][6.0] - 6.0) < 1e-3
    # midspan deflection 5wL^4/384EI
    assert abs(max(r["defl"]) - 5 * 2.0 * 6 ** 4 / (384 * 1e4)) < 1e-5


def test_three_equal_spans():
    # textbook: R = 0.4wl, 1.1wl, 1.1wl, 0.4wl ; support moment -0.1wl^2 ; end-span sag 0.08wl^2
    l, w = 3.0, 1.0
    r = solve(3 * l, 1e4, [0, l, 2 * l, 3 * l], w_segments=[(0, 3 * l, w)])
    R = r["reactions"]
    assert abs(R[0] - 0.4 * w * l) < 1e-3 and abs(R[l] - 1.1 * w * l) < 1e-3
    assert abs(min(r["M"]) + 0.1 * w * l * l) < 2e-3
    assert abs(max(r["M"]) - 0.08 * w * l * l) < 2e-3


def test_prescribed_equal_forces_balance():
    # uniform load, four equal forces at L/8, 3L/8, 5L/8, 7L/8: each = wL/4, max |M| = w(L/8)^2/2
    L, w = 12.0, 1.0
    xs = [1.5, 4.5, 7.5, 10.5]
    r = solve(L, 1e4, [], w_segments=[(0, L, w)], prescribed={x: w * L / 4 for x in xs})
    assert abs(r["unbalance"]) < 1e-6
    assert abs(max(abs(r["M"])) - w * 1.5 ** 2 / 2) < 2e-3


def test_support_on_mesh_node_is_not_duplicated():
    # regression: a support at 1.2 m coincides with a mesh node up to rounding; it must not create a zero-length element
    L, w = 12.0, 1.0
    xs = [1.2, 4.2, 7.8, 10.8]
    for n in (480, 1200):
        r = solve(L, 1e4, xs, w_segments=[(0, L, w)], n=n)
        assert abs(sum(r["reactions"].values()) - w * L) < 1e-3
        assert max(abs(r["M"])) < 2.0
