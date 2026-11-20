"""Checks of the C89 finite strip buckling table and of the solver that made it.

The table is analysis/liftcalc/data/c89_buckling.json, written by analysis/liftcalc/buckling_fsm.py.
Most tests read the table; a few recompute single cases with the independent solver (a second or two each).
"""
import json
import math
import os
import re
import sys

import numpy as np
import pytest
from scipy.optimize import brentq

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from liftcalc import buckling_fsm as B

E, NU = B.E_MPA, B.NU
PLATE = math.pi ** 2 * E / (12.0 * (1.0 - NU ** 2))            # f_cr = k * PLATE * (t / b)^2


@pytest.fixture(scope="module")
def table():
    assert B.JSON_PATH.exists(), "run analysis/liftcalc/buckling_fsm.py to create the table"
    return json.loads(B.JSON_PATH.read_text(encoding="utf-8"))


def pick(table, t, corners, action):
    rows = [r for r in table["rows"] if abs(r["t"] - t) < 1e-9 and r["corners"] == corners and r["action"] == action]
    assert len(rows) == 1
    return rows[0]


def props(table, t, corners):
    found = [p for p in table["section_props"] if abs(p["t"] - t) < 1e-9 and p["corners"] == corners]
    assert len(found) == 1
    return found[0]


# ------------------------------------------------------------------------------------------------ the table itself
def test_table_is_complete(table):
    assert set(table) == {"meta", "rows", "section_props"}
    keys = {(r["t"], r["corners"], r["action"]) for r in table["rows"]}
    assert keys == {(t, c, a) for t in B.THICKNESSES for c in B.CORNER_MODELS for a in B.ACTIONS}
    assert len(table["rows"]) == 24 and len(table["section_props"]) == 6
    for r in table["rows"]:
        for name in ("t", "corners", "action", "f_local", "half_wave_local", "f_dist", "half_wave_dist", "note"):
            assert name in r
        assert r["f_local"] > 0 and B.L_MIN < r["half_wave_local"] < B.L_MAX
        assert (r["f_dist"] is None) == (r["half_wave_dist"] is None)
        if r["f_dist"] is not None:
            assert r["f_dist"] > 0 and B.L_MIN < r["half_wave_dist"] < B.L_MAX
    for p in table["section_props"]:
        for name in ("t", "corners", "A", "Ix", "Iy", "J", "Cw", "xc_from_web", "x0_shear_centre_to_centroid"):
            assert name in p and (name == "corners" or p[name] > 0)


def test_table_carries_no_date(table):
    text = B.JSON_PATH.read_text(encoding="utf-8")
    assert not re.search(r"\b(19|20)\d\d-\d\d-\d\d\b", text), "an ISO date slipped into the table"
    assert not re.search(r"\b\d\d:\d\d:\d\d\b", text), "a clock time slipped into the table"

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert not re.search(r"date|time|timestamp|generated", k, re.I), k
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
    walk(table["meta"])


def test_design_module_can_read_the_table(table):
    """liftcalc.as4600.load_buckling_table matches rows by thickness and by corners.startswith('sharp') and reads
    f_local and f_dist by action. Keep that contract."""
    for t in B.THICKNESSES:
        out = {}
        for r in table["rows"]:
            if abs(r["t"] - t) < 1e-6 and str(r.get("corners", "")).lower().startswith("sharp"):
                out[r["action"]] = {"f_local": r["f_local"], "f_dist": r.get("f_dist")}
        assert set(out) == set(B.ACTIONS)
        assert all(isinstance(v["f_local"], float) for v in out.values())


def test_curves_file_matches_the_table(table):
    path = B.DATA_DIR / table["meta"]["curves_file"]
    curves = json.loads(path.read_text(encoding="utf-8"))
    lengths = np.array(curves["half_wave_lengths"])
    assert len(lengths) == B.N_LENGTHS and np.allclose(lengths, B.half_wave_lengths(), atol=1e-3)
    assert len(curves["curves"]) == 24
    for c in curves["curves"]:
        r = pick(table, c["t"], c["corners"], c["action"])
        mode1 = np.array(c["mode1"])
        assert len(mode1) == len(c["mode2"]) == len(c["class_mode1"]) == B.N_LENGTHS
        assert np.all(np.array(c["mode2"]) >= mode1 * (1.0 - 1e-9))
        for f, length in ((r["f_local"], r["half_wave_local"]), (r["f_dist"], r["half_wave_dist"])):
            if f is not None:
                i = int(np.argmin(np.abs(lengths - length)))
                assert f <= mode1[i] * (1.0 + 1e-6) and mode1[i] / f < 1.003      # the refined minimum sits just under the grid
        # along the half-wave axis the first mode goes local -> (distortional) -> global, never backwards
        seen = []
        for ch in c["class_mode1"]:
            if ch != "M" and (not seen or seen[-1] != ch):
                seen.append(ch)
        assert "".join(seen) in ("LDG", "LG"), seen
        assert ("D" in seen) == (r["f_dist"] is not None)


def test_plots_were_written():
    for t in B.THICKNESSES:
        for action in B.ACTIONS:
            path = B.PLOT_DIR / B.plot_name(t, action)
            assert path.exists() and path.stat().st_size > 20_000, path


# ---------------------------------------------------------------------------------------------- engineering sanity
def test_web_local_buckling_lies_between_simply_supported_and_clamped_plate(table):
    """Uniformly compressed web: the flanges restrain it, so k must sit between 4 (simply supported) and 6.97 (clamped)."""
    for action in ("axial", "bend_minor_web_comp"):
        for t in B.THICKNESSES:
            for corners in B.CORNER_MODELS:
                r = pick(table, t, corners, action)
                flat = B.DEPTH - t if corners == "sharp" else B.DEPTH - 2.0 * (B.R_INSIDE + t)
                k = r["f_local"] / (PLATE * (t / flat) ** 2)
                assert 4.0 < k < 6.97, (action, t, corners, k)
                assert r["mode_local"]["max_displacement_at"] == "web"
                assert 0.5 * flat < r["half_wave_local"] < 1.0 * flat      # about one buckle per web depth


def test_distortional_stress_agrees_with_reference_table(table):
    """Sharp corners against the other program's table: required within 15 %, and in fact within 2 %."""
    assert len(B.REFERENCE_DIST) == 4
    for (action, t), ref in B.REFERENCE_DIST.items():
        f = pick(table, t, "sharp", action)["f_dist"]
        assert abs(f / ref - 1.0) < 0.15, (action, t, f, ref)
        assert abs(f / ref - 1.0) < 0.02, (action, t, f, ref)


def hand_formula_distortional_stress(t, bending):
    """Closed-form elastic distortional buckling stress and half-wave length of a simple lipped channel: Lau and Hancock
    (1987) for compression, Hancock (1997) for bending - the expressions behind AS/NZS 4600 Appendix D. Sharp corners,
    centreline dimensions; the flange-plus-lip strut is restrained in rotation by the web."""
    bf, dl, bw = B.FLANGE - t, B.LIP - t / 2.0, B.DEPTH - t
    area = (bf + dl) * t
    xb = (bf * bf + 2.0 * bf * dl) / (2.0 * (bf + dl))
    yb = dl * dl / (2.0 * (bf + dl))
    j = t ** 3 * (bf + dl) / 3.0
    ix = bf * t ** 3 / 12.0 + t * dl ** 3 / 12.0 + bf * t * yb ** 2 + dl * t * (dl / 2.0 - yb) ** 2
    iy = t * bf ** 3 / 12.0 + dl * t ** 3 / 12.0 + dl * t * (bf - xb) ** 2 + bf * t * (xb - bf / 2.0) ** 2
    ixy = bf * t * (bf / 2.0 - xb) * (-yb) + dl * t * (dl / 2.0 - yb) * (bf - xb)
    lam = 4.80 * (ix * bf ** 2 * bw / ((2.0 if bending else 1.0) * t ** 3)) ** 0.25
    eta = (math.pi / lam) ** 2
    beta1 = xb ** 2 + (ix + iy) / area

    def stress(k_phi):
        a1 = eta / beta1 * (ix * bf ** 2 + 0.039 * j * lam ** 2) + k_phi / (beta1 * eta * E)
        a2 = eta * (iy + 2.0 / beta1 * yb * bf * ixy)
        a3 = eta * (a1 * iy - eta / beta1 * ixy ** 2 * bf ** 2)
        return E / (2.0 * area) * ((a1 + a2) - math.sqrt((a1 + a2) ** 2 - 4.0 * a3))

    f0 = stress(0.0)                                               # flange and lip with no help from the web
    if bending:
        web = bw ** 4 * lam ** 2 / (12.56 * lam ** 4 + 2.192 * bw ** 4 + 13.39 * lam ** 2 * bw ** 2)
        k_phi = 2.0 * E * t ** 3 / (5.46 * (bw + 0.06 * lam)) * (1.0 - 1.11 * f0 / (E * t ** 2) * web)
    else:
        web = (bw ** 2 * lam / (bw ** 2 + lam ** 2)) ** 2
        k_phi = E * t ** 3 / (5.46 * (bw + 0.06 * lam)) * (1.0 - 1.11 * f0 / (E * t ** 2) * web)
    return stress(k_phi), lam


def test_distortional_stress_agrees_with_hand_formula(table):
    """A third, closed-form opinion for all three thicknesses (the reference table has none for 0.75 mm).
    The hand formula is an approximation: within 10 % is agreement (it lands 7 % high in compression, 1 % low in bending)."""
    for t in B.THICKNESSES:
        for action, bending in (("axial", False), ("bend_major", True)):
            r = pick(table, t, "sharp", action)
            f_hand, half_wave_hand = hand_formula_distortional_stress(t, bending)
            assert r["f_dist"] == pytest.approx(f_hand, rel=0.10), (t, action, r["f_dist"], f_hand)
            assert r["half_wave_dist"] == pytest.approx(half_wave_hand, rel=0.10), (t, action, r["half_wave_dist"], half_wave_hand)


def test_minima_are_classified_from_their_mode_shapes(table):
    for r in table["rows"]:
        loc, dist = r["mode_local"], r["mode_dist"]
        assert loc["class"] == "local"
        assert loc["junction_ratio"] <= 0.25 and loc["web_junction_ratio"] <= 0.25      # fold lines do not translate
        if dist is not None:
            assert dist["class"] == "distortional"
            assert dist["junction_ratio"] >= 0.5 and dist["web_junction_ratio"] <= 0.25   # flange and lip swing about the web junction
            assert dist["flange_rotation_ratio"] >= 0.5 and dist["flange_bending_ratio"] <= 0.1   # the flange stays straight
            assert dist["rigid_body_fraction"] < 0.9                                     # the section distorts: not a global mode
            assert r["half_wave_dist"] > 3.0 * r["half_wave_local"]


def test_web_in_compression_has_no_distortional_mode(table):
    for t in B.THICKNESSES:
        for corners in B.CORNER_MODELS:
            r = pick(table, t, corners, "bend_minor_web_comp")
            assert r["f_dist"] is None and r["half_wave_dist"] is None
            assert "No distortional minimum" in r["note"]
            assert "distortional" not in r["scan_lowest_by_class"]
            assert len(r["signature_minima"]) == 1
    # every other action has both minima
    for r in table["rows"]:
        if r["action"] != "bend_minor_web_comp":
            assert r["f_dist"] is not None


def test_trends_with_thickness_and_corner_model(table):
    for corners in B.CORNER_MODELS:
        for action in B.ACTIONS:
            rows = [pick(table, t, corners, action) for t in B.THICKNESSES]
            assert rows[0]["f_local"] < rows[1]["f_local"] < rows[2]["f_local"]
            if rows[0]["f_dist"] is not None:
                assert rows[0]["f_dist"] < rows[1]["f_dist"] < rows[2]["f_dist"]
                assert rows[0]["half_wave_dist"] > rows[1]["half_wave_dist"] > rows[2]["half_wave_dist"]
    for t in B.THICKNESSES:
        for action in B.ACTIONS:
            sharp, rounded = pick(table, t, "sharp", action), pick(table, t, "rounded", action)
            assert 1.0 <= rounded["f_local"] / sharp["f_local"] < 1.05
            if sharp["f_dist"] is not None:
                assert 1.0 <= rounded["f_dist"] / sharp["f_dist"] < 1.10
        # one flange or the lips in compression: distortional buckling is the lower mode
        for action in ("bend_major", "bend_minor_lips_comp"):
            r = pick(table, t, "sharp", action)
            assert r["f_dist"] < r["f_local"]


def test_stress_resultant_and_outer_fibre_fields_are_consistent(table):
    for r in table["rows"]:
        p = props(table, r["t"], r["corners"])
        modulus = {"axial": (p["A"], p["A"], 1.0e-3),
                   "bend_major": (p["Zx_centreline"], p["Zx_outer_face"], 1.0e-6),
                   "bend_minor_web_comp": (p["Zy_web_centreline"], p["Zy_web_outer_face"], 1.0e-6),
                   "bend_minor_lips_comp": (p["Zy_lip_centreline"], p["Zy_lip_outer_face"], 1.0e-6)}[r["action"]]
        # the resultants belong to the finite strip model; its 8-chord corners carry 0.05 % less than the true arcs
        sec = B.build_section(r["t"], r["corners"])
        exact = B.reference_stress(sec, r["action"])[1]["resultant_per_unit_stress"] * modulus[2]
        for kind in ("local", "dist"):
            if r["f_" + kind] is None:
                assert r["resultant_" + kind] is None and r["f_" + kind + "_outer"] is None
                continue
            assert r["f_" + kind] * exact == pytest.approx(r["resultant_" + kind], rel=2e-5)
            # centreline stress x centreline modulus = outer stress x outer-face modulus = the critical force or moment
            assert r["f_" + kind] * modulus[0] * modulus[2] == pytest.approx(r["resultant_" + kind], rel=1e-3)
            assert r["f_" + kind + "_outer"] * modulus[1] * modulus[2] == pytest.approx(r["resultant_" + kind], rel=1e-3)
            assert r["f_" + kind + "_outer"] == pytest.approx(r["f_" + kind] * r["extreme_fibre_factor"], rel=5e-5)
        assert (r["extreme_fibre_factor"] == 1.0) == (r["action"] == "axial")
        assert 1.0 <= r["extreme_fibre_factor"] < 1.07


def test_mesh_is_at_least_the_required_minimum_and_converged(table):
    assert all(B.MESH[k] >= B.MESH_MINIMUM[k] for k in B.MESH_MINIMUM)
    assert B.MESH_MINIMUM == {"web": 8, "flange": 4, "lip": 2, "corner": 4}
    lengths = B.half_wave_lengths()
    assert len(lengths) >= 80 and lengths[0] == pytest.approx(10.0) and lengths[-1] == pytest.approx(3000.0)
    assert table["meta"]["mesh"]["strips"] == B.MESH
    assert table["meta"]["mesh"]["largest_change_when_mesh_is_doubled_pct"] < 0.25
    for r in table["rows"]:
        assert all(abs(v) < 0.25 for v in r["mesh_doubling_change_pct"].values())
    sec = B.build_section(0.95, "rounded")
    for part, n in (("web", 16), ("flange_top", 8), ("lip_bottom", 4), ("corner_web_flange_top", 8), ("corner_flange_lip_bottom", 8)):
        assert sec.elem_part.count(part) == n


def test_two_solvers_were_compared_for_every_row(table):
    meta = table["meta"]
    if meta["solver"]["rows_from_pycufsm"] == 0:
        pytest.skip("table was made without pycufsm")
    assert meta["solver"]["rows_from_pycufsm"] == 24 and meta["solver"]["rows_from_independent"] == 0
    both = meta["crosscheck"]["pycufsm_vs_independent"]
    assert both["cases_compared"] == 24
    assert both["rel_diff_at_reported_minima_below"] <= both["tolerance_at_minima"] <= 1.0e-6
    assert both["rel_diff_modes_1_to_4_all_lengths_below"] <= both["tolerance_all_lengths"] <= 1.0e-4
    for r in table["rows"]:
        assert r["solver"] == "pycufsm" and "note" not in r["pycufsm_vs_independent"]
        assert r["pycufsm_vs_independent"]["at_reported_minima_below"] <= 1.0e-6
        assert r["pycufsm_vs_independent"]["modes_1_to_4_all_lengths_below"] <= 1.0e-4


# ----------------------------------------------------------------------------------- the independent solver itself
def free_edge_plate_coefficient(a_over_b, nu):
    """Exact k of a plate simply supported on three sides and free on one unloaded side, uniform compression
    (Timoshenko and Gere, Theory of Elastic Stability, art. 9.4):
        beta (alpha^2 - nu L^2)^2 tanh(alpha b) = alpha (beta^2 + nu L^2)^2 tan(beta b),   L = pi / a."""
    lam = math.pi / a_over_b                                       # b = 1

    def f(k):
        s = math.sqrt(k) * math.pi
        alpha, beta = math.sqrt(lam * lam + lam * s), math.sqrt(lam * s - lam * lam)
        return beta * (alpha ** 2 - nu * lam ** 2) ** 2 * math.tanh(alpha) - alpha * (beta ** 2 + nu * lam ** 2) ** 2 * math.tan(beta)

    lo = (1.0 / a_over_b) ** 2 * (1.0 + 1e-9)                      # beta is real above this
    ks = np.linspace(lo, lo + 1.0, 4001)
    for k0, k1 in zip(ks[:-1], ks[1:]):
        if f(k0) * f(k1) < 0 and abs(f(k0)) < 1e6:
            return brentq(f, k0, k1, xtol=1e-13)
    raise AssertionError("no root found")


def test_independent_solver_reproduces_classical_plate_buckling():
    got = {k: v["k"] for k, v in B.plate_benchmarks().items()}
    assert got["simply_supported_uniform_compression"] == pytest.approx(4.0, abs=2e-4)
    assert got["clamped_uniform_compression"] == pytest.approx(6.97, abs=0.01)
    assert got["simply_supported_pure_bending"] == pytest.approx(23.9, abs=0.05)
    assert got["one_edge_free_uniform_compression_at_a_equals_b"] == pytest.approx(free_edge_plate_coefficient(1.0, NU), abs=2e-4)
    # simply supported plate at other half-wave lengths: k = (b/a + a/b)^2 ; free edge at other lengths: exact equation
    b, t, n = 100.0, 1.0, 16
    xy = np.array([[b * i / n, 0.0] for i in range(n + 1)])
    elems = [(i, i + 1) for i in range(n)]
    ss = B.FiniteStrip(xy, elems, t, np.ones(n + 1), [(0, "U"), (0, "W"), (n, "W")])
    free = B.FiniteStrip(xy, elems, t, np.ones(n + 1), [(0, "U"), (0, "W")])
    for a in (50.0, 80.0, 120.0, 200.0):
        assert ss.first(a) / (PLATE * (t / b) ** 2) == pytest.approx((b / a + a / b) ** 2, rel=2e-4)
    for ratio in (0.5, 2.0, 5.0):
        assert free.first(ratio * b) / (PLATE * (t / b) ** 2) == pytest.approx(free_edge_plate_coefficient(ratio, NU), rel=3e-4)


def test_sharp_section_properties_match_closed_form(table):
    for t in B.THICKNESSES:
        sec = B.build_section(t, "sharp")
        p = B.section_properties(sec)
        a, b, c = B.DEPTH - t, B.FLANGE - t, B.LIP - t / 2.0
        area = t * (a + 2 * b + 2 * c)
        xbar = t * (b * b + 2 * c * b) / area
        ix = t * (a ** 3 / 12 + 2 * b * (a / 2) ** 2 + 2 * (c ** 3 / 12 + c * (a / 2 - c / 2) ** 2))
        iy = t * (a * xbar ** 2 + 2 * (b ** 3 / 12 + b * (b / 2 - xbar) ** 2) + 2 * c * (b - xbar) ** 2)
        assert p["A"] == pytest.approx(area, rel=1e-12)
        assert p["xc"] == pytest.approx(xbar, rel=1e-12)
        assert p["Ix"] == pytest.approx(ix, rel=1e-12)
        assert p["Iy"] == pytest.approx(iy, rel=1e-12)
        assert p["J"] == pytest.approx(area * t * t / 3.0, rel=1e-12)
        assert abs(p["Ixy"]) < 1e-9 * p["Ix"] and p["zc"] == pytest.approx(a / 2.0)
        assert p["x_sc"] < 0 < p["xc"]                              # shear centre behind the web, centroid in front
        row = props(table, t, "sharp")
        assert row["A"] == pytest.approx(area, rel=1e-6) and row["Ix"] == pytest.approx(ix, rel=1e-6)
        assert row["Iy"] == pytest.approx(iy, rel=1e-6) and row["xc_from_web"] == pytest.approx(xbar, rel=1e-6)
        assert row["x0_shear_centre_to_centroid"] == pytest.approx(p["xc"] - p["x_sc"], rel=1e-6)
        assert row["Cw"] == pytest.approx(p["Cw"], rel=1e-6)


def test_rounded_section_properties(table):
    for t in B.THICKNESSES:
        row, sharp = props(table, t, "rounded"), props(table, t, "sharp")
        r_c = B.R_INSIDE + t / 2.0
        # developed length: four right-angle corners each replace 2 r by (pi/2) r
        length = (B.DEPTH - t) + 2 * (B.FLANGE - t) + 2 * (B.LIP - t / 2.0) - 4 * (2.0 - math.pi / 2.0) * r_c
        assert row["A"] == pytest.approx(t * length, rel=2e-5)
        assert row["J"] == pytest.approx(t ** 3 * length / 3.0, rel=2e-5)
        for name in ("A", "Ix", "Iy", "Cw"):
            assert 0.90 < row[name] / sharp[name] < 1.0              # rounding the corners removes a little material
        # the buckling mesh (8 chords per corner) carries the same properties to better than 0.1 %
        mesh = B.section_properties(B.build_section(t, "rounded"))
        for name in ("A", "Ix", "Iy", "Cw"):
            assert mesh[name] == pytest.approx(row[name], rel=1e-3)


def test_section_properties_agree_with_the_sections_module():
    """Second, separately written implementation in this repository (skipped if it is not there)."""
    sections = pytest.importorskip("liftcalc.sections")
    for t in B.THICKNESSES:
        mine = B.section_properties(B.build_section(t, "sharp"))
        theirs = sections.c89(t, 0.0)
        assert theirs.A == pytest.approx(mine["A"], rel=1e-9)
        assert theirs.Ix == pytest.approx(mine["Ix"], rel=1e-9) and theirs.Iy == pytest.approx(mine["Iy"], rel=1e-9)
        assert theirs.J == pytest.approx(mine["J"], rel=1e-9) and theirs.Cw == pytest.approx(mine["Cw"], rel=1e-9)
        assert theirs.x0 == pytest.approx(mine["x0"], rel=1e-9) and theirs.xc == pytest.approx(mine["xc"], rel=1e-9)


def test_long_half_wave_buckling_matches_beam_theory():
    """Flexural-torsional column buckling and lateral-torsional beam buckling from A, Ix, Iy, J, Cw, x0 against the
    plate model at a 3 m half-wave. This is the check on the warping constant."""
    for t, corners in ((0.75, "sharp"), (0.95, "sharp"), (1.15, "rounded")):
        chk = B.global_buckling_check(t, corners)
        assert chk["axial_ratio"] == pytest.approx(1.0, abs=0.005), chk
        assert chk["bend_major_ratio"] == pytest.approx(1.0, abs=0.005), chk
    # the check has teeth: a 10 % error in Cw moves the beam-theory value by far more than the tolerance
    sec = B.build_section(0.95, "sharp")
    p = B.section_properties(sec)
    good = B.column_buckling_stress(p, 3000.0)[0]
    bad = B.column_buckling_stress({**p, "Cw": 1.1 * p["Cw"]}, 3000.0)[0]
    assert abs(bad / good - 1.0) > 0.03


def test_recomputed_cases_match_the_table(table):
    for t, corners, action in ((0.95, "sharp", "axial"), (1.15, "rounded", "bend_minor_lips_comp")):
        new = B.analyse_case(t, corners, action, use_pycufsm=False)["row"]
        old = pick(table, t, corners, action)
        assert new["f_local"] == pytest.approx(old["f_local"], rel=2e-5)
        assert new["f_dist"] == pytest.approx(old["f_dist"], rel=2e-5)
        assert new["half_wave_local"] == pytest.approx(old["half_wave_local"], abs=0.05)
        assert new["half_wave_dist"] == pytest.approx(old["half_wave_dist"], abs=0.05)
        assert [m["class"] for m in new["signature_minima"]] == [m["class"] for m in old["signature_minima"]] == ["local", "distortional"]


def test_pycufsm_agrees_with_the_independent_solver():
    lib = B._load_pycufsm()
    if not lib["available"]:
        pytest.skip(f"pycufsm not usable: {lib['error']}")
    lengths = np.array([20.0, 46.0, 120.0, 300.0, 900.0, 2500.0])
    for corners, action in (("sharp", "bend_major"), ("rounded", "axial")):
        sec = B.build_section(0.95, corners, B.MESH_MINIMUM)
        p = B.section_properties(sec)
        stress = B.reference_stress(sec, action, p)[0]
        native = B.native_model(sec, stress)
        curve, shapes = B.PycufsmStrip(sec, action, p).solve(lengths, 3)
        ours = np.array([native.solve(a, 3)[0] for a in lengths])
        diff = np.abs(curve / ours - 1.0)
        assert diff[lengths < 1000.0].max() < B.MINIMA_TOL          # where the local and distortional minima are
        assert diff.max() < B.CROSSCHECK_TOL                         # long half-waves: round-off of an ill-conditioned matrix
        # the mode shapes say the same thing: same class at every length
        for i, a in enumerate(lengths):
            assert B.classify(B.mode_metrics(sec, shapes[i, 0])) == B.classify(B.mode_metrics(sec, native.solve(a, 1)[1][0]))


def test_reference_stress_fields():
    sec = B.build_section(0.95, "sharp")
    p = B.section_properties(sec)
    web = sec.nodes_of("web")
    tips = list(sec.tips)
    for action in B.ACTIONS:
        s, info = B.reference_stress(sec, action, p)
        assert s.max() == pytest.approx(1.0)                         # largest compression is the unit
        force = sum(0.5 * (s[i] + s[j]) * sec.t * math.hypot(*(sec.xy[j] - sec.xy[i])) for i, j in sec.elems)
        assert force == pytest.approx(p["A"] if action == "axial" else 0.0, abs=1e-9 * p["A"])
        assert info["extreme_fibre_factor"] >= 1.0
    assert np.all(B.reference_stress(sec, "bend_minor_web_comp", p)[0][web] == pytest.approx(1.0))
    assert np.all(B.reference_stress(sec, "bend_minor_web_comp", p)[0][tips] < 0)        # lips in tension
    assert np.all(B.reference_stress(sec, "bend_minor_lips_comp", p)[0][tips] == pytest.approx(1.0))
    assert np.all(B.reference_stress(sec, "bend_minor_lips_comp", p)[0][web] < 0)        # web in tension
    major = B.reference_stress(sec, "bend_major", p)[0]
    assert major[sec.j_flange_lip[1]] == pytest.approx(1.0) and major[sec.j_flange_lip[0]] == pytest.approx(-1.0)
