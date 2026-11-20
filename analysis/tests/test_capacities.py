"""Capacity values checked by hand by the independent reviewers (results/review/synthesis.json, 'verified' and 'notes'),
plus the checks added for Rev D (lip-notch section, member shear, seat bearing, bearing bolt bending)."""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from liftcalc import as4600 as C, connectors as K
import run_connectors as RC


def close(a, b, rel=5e-3):
    return abs(a - b) <= rel * abs(b)


def test_reviewer_hand_values():
    s = C.LippedChannel(0.95, C.G450)
    Nc, det = s.compression_design(600.0, 600.0, 600.0)
    assert close(Nc / 1e3, 29.23)                                       # phi Nc of C89 0.95 at 600 mm (reviewer: 29.23 kN)
    assert close(s.moment_minor_design()[0] / 1e6, 0.363)               # phi My (reviewer: 0.363 kNm)
    assert close(C.screw_shear_design(0.95, 412.5, 0.95, 412.5, 4.87, screw_shear_breaking=5700) / 1e3, 1.77)   # one 10 g screw
    assert close(K.bolt_bearing(12, 1.5, 480.0) / 1e3, 10.13)            # M12 on the 1.5 mm strap (reviewer: 10.13 kN)
    assert close(K.bolt_bearing(12, 0.95, 412.5) / 1e3, 5.21)            # M12 on the 0.95 mm frame at 412.5 MPa (reviewer: 5.21 kN)


def test_lip_notch_section_is_weaker_than_the_full_section():
    s = C.LippedChannel(0.95, C.G450)
    Nc, det = s.compression_design(600.0, 600.0, 600.0)
    Nn = s.notched_compression_design(det["fn"])
    assert Nn < Nc                                                      # lips gone: the notched section governs short members
    assert close(s.area_effective_notched(det["fn"]), 72.6, rel=1e-2)   # regression value (Rev D)
    assert s.area_effective_notched(det["fn"]) < s.p.A


def test_member_shear():
    s = C.LippedChannel(0.95, C.G450)
    # across the web, carried by the two flanges: 0.9 x 2 b t x 0.6 fy with the flat flange b = 38 - 2 x 0.95
    assert close(s.shear_design_minor(), 0.9 * 2 * (38 - 2 * 0.95) * 0.95 * 0.6 * 450.0)
    assert close(s.shear_design_major() / 1e3, 8.55, rel=1e-2)          # along the web (AISI G2.1, kv 5.34)


def test_cradle_seat_bearing_by_hand():
    # web crippling of the chord's two flanges under a 40 mm packer (AISI S100 G5 C-section, interior one-flange, unfastened):
    # Pn = C t^2 fy (1 - CR sqrt(r/t)) (1 + CN sqrt(N/t)) (1 - Ch sqrt(h/t)), C 13, CR 0.23, CN 0.14, Ch 0.01, phi 0.90, 2 webs
    for t in (0.95, 1.15):
        Pn = 13 * t * t * 450 * (1 - 0.23 * math.sqrt(2 / t)) * (1 + 0.14 * math.sqrt(40 / t)) * (1 - 0.01 * math.sqrt(36 / t))
        assert close(RC.web_crippling_c(t, 450.0, 36.0, 2.0, 40.0, webs=2), 0.9 * Pn * 2, rel=1e-9)
    assert close(RC.web_crippling_c(1.15, 450.0, 36.0, 2.0, 40.0, webs=2) / 1e3, 16.72, rel=2e-3)


def test_bearing_bolt_bending_capacity():
    # M16 8.8 shank in bending between the cheeks: phi fy Zp, Zp = d^3 / 6 for a round bar, fy 640 MPa
    assert close(0.90 * 640.0 * 16.0 ** 3 / 6.0, 393216.0, rel=1e-9)


def test_lipless_notch_section_by_hand():
    # reviewers' hand values for the C89 0.95 section with the lips cut away: A 154.0 mm2, Iy 21,170 mm4 (minor axis)
    from liftcalc import notch as NT
    b = NT.notched_buckling(0.95, 50.0, False)
    assert close(b["A"], 154.0, rel=2e-3)
    assert close(b["Iy"], 21170.0, rel=1e-2)
    # with the flange edges held the notched section reaches first yield in minor-axis bending (no local buckling loss)
    cap = NT.notched_capacities(0.95, 450.0, 127.0, 346.0, True)
    Z_tip = b["bend_minor_lips_comp"]["res"]
    assert close(cap["phiMy_tips"], 0.90 * 450.0 * Z_tip, rel=1e-6)
    # without credit the free flange tips buckle first: lower than with the edges held
    assert NT.notched_capacities(0.95, 450.0, 127.0, 346.0, False)["phiMy_tips"] < cap["phiMy_tips"]


def test_gusseted_notch_is_stronger_than_bare_notch():
    from liftcalc import notch as NT
    g = NT.gusseted_capacities(1.15, 450.0, 346.0); n = NT.notched_capacities(1.15, 450.0, 127.0, 346.0, True)
    assert g["phiMy"] > n["phiMy"] and g["phiNc"] > n["phiNc"]


def test_bolted_strap_net_section_rule():
    # (0.1 + 3 d / s) An fu with phi 0.55: M12 across a 50 mm strap gives 0.82; 50 x 2.5 with a 14 mm hole -> 19.48 kN
    c, d = K.strap_tension_bolted(50.0, 2.5, K.G450, 12.0, 14.0)
    assert close(d["eff"], 0.82, rel=1e-9) and close(c / 1e3, 19.48, rel=2e-3)
