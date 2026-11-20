"""Capacity of the lift-point parts that Infinity Framer does not make: flat straps, folded plates, bolts, pins, screws.

All values are DESIGN capacities (capacity factor included), in N and mm. Rules (see docs/DESIGN_BASIS.md):
  * AS/NZS 4600:2018 forms where the public record states them; AISI S100-16 where it does not (marked in the text).
  * Screws in shear only; 10 gauge screw fracture limit 0.5 x 5.7 kN = 2.85 kN; 10 % less per screw in groups of 3 or more.
  * Connection strength of the 0.95 mm frame steel taken as 0.75 x 550 = 412.5 MPa (low-ductility rule) for every screw into it.
  * Folded plates and straps: G450 (fy 450, fu 480 MPa); bolts M12 / M16 / M20 property class 8.8 at 800 MPa (not 830).
  * Bolt bearing: deformation-limited bearing (AISI S100-16 J3.3.2) at phi 0.65, washers under head and nut;
    tear-out 0.60 t e fu; net section 0.65 An fu; gross yield 0.90 Ag fy; bolt shear 0.8 x 0.62 x 800 x core area.
"""
from __future__ import annotations
import math
from . import as4600 as C

G450 = dict(fy=450.0, fu=480.0)
G300 = dict(fy=300.0, fu=340.0)
FRAME_CONN_FU = 412.5               # MPa, 0.95 mm frame steel in connections (0.75 x 550)
SCREW10_D = 4.87
SCREW10_BREAK = 5700.0
GROUP = 0.90
BOLT_CORE = {12: 76.2, 16: 144.0, 20: 225.0}      # mm2, core (minor) area, threads in the shear plane


def screw_shear(t_head, t_far, fu_head, fu_far, d=SCREW10_D, n=1, breaking=SCREW10_BREAK):
    """Design shear of n screws through two sheets (head side t_head, far side t_far)."""
    one = C.screw_shear_design(t_head, fu_head, t_far, fu_far, d, screw_shear_breaking=breaking)
    return n * one * (GROUP if n >= 3 else 1.0), one


def bolt_shear(d, planes=1):
    return planes * 0.8 * 0.62 * 800.0 * BOLT_CORE[d]


def bolt_bearing(d, t, fu):
    """Deformation-limited bearing of one bolt on one ply (AISI S100-16 J3.3.2, SI form), phi 0.65."""
    return 0.65 * (0.183 * t + 1.53) * d * t * fu


def bolt_tearout(e, t, fu):
    return 0.60 * t * e * fu


def strap_tension(b, t, mat, hole=0.0):
    gross = 0.90 * b * t * mat["fy"]
    net = 0.65 * (b - hole) * t * mat["fu"]
    return min(gross, net), dict(gross=gross, net=net)


def strap_tension_bolted(b, t, mat, d, hole, n_across=1, phi_net=0.55):
    """Flat strap with bolts in a line along it (one bolt across the width), bolted to a plate in single shear with washers
    under head and nut: gross yield 0.90 Ag fy, and the bolted thin-sheet net section (AS/NZS 4600 cl 5.3.3 form,
    AISI S100 E3.2): Nf = (0.1 + 3 d / s) An fu <= An fu with s = b / n_across, phi 0.55 in single shear."""
    gross = 0.90 * b * t * mat["fy"]
    s = b / n_across
    An = (b - n_across * hole) * t
    net = phi_net * min(1.0, 0.1 + 3.0 * d / s) * An * mat["fu"]
    return min(gross, net), dict(gross=gross, net=net, eff=min(1.0, 0.1 + 3.0 * d / s))


def plate_bending_strip(t, fy=450.0):
    """Design moment per mm width of a flat plate strip (elastic section, phi 0.90)."""
    return 0.90 * fy * t * t / 6.0
