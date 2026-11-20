"""Member and connection capacities for cold-formed steel to AS/NZS 4600:2018 (independent implementation).

Each function names the clause it follows. The standard itself is not reproduced here; the formulas were written
from the public literature on AS/NZS 4600 / AISI S100 and are checked in analysis/tests/test_as4600.py and
verification/ (published worked examples, a second method, and independent reviewers).

Two routes are provided for compression and bending and BOTH are evaluated; the lower result is used:
  EWM  effective width method (Sections 2 and 3)
  DSM  direct strength method (Section 7), using elastic buckling stresses from a finite strip analysis
       (analysis/liftcalc/data/c89_buckling.json)

Units: N, mm, MPa. Capacities returned by `*_design` functions already include the capacity factor phi.
"""
from __future__ import annotations
import json, math, os
from dataclasses import dataclass
from . import sections as S

E = 200000.0
NU = 0.3
G = 80000.0            # AS/NZS 4600 shear modulus

# capacity (phi) factors, AS/NZS 4600:2018 Table 1.6.3
PHI = {
    "tension": 0.90,
    "compression": 0.85,
    "bending_section": 0.90,      # 0.95 is permitted for stiffened compression flanges; 0.90 is used throughout (conservative)
    "bending_member": 0.90,
    "shear": 0.90,
    "screw": 0.50,                # screwed connections: tilting, bearing, pull-out, pull-over
    "bolt_bearing": 0.60,
    "bolt_tearout": 0.70,         # 0.60 when fu/fy < 1.08
    "net_section_bolted": 0.65,
    "block_shear_bolted": 0.65,
}


@dataclass(frozen=True)
class Steel:
    name: str; fy: float; fu: float

    @property
    def ductile(self):               # fu / fy >= 1.08 (clause 1.5.1.4 ductility condition used for some phi factors)
        return self.fu / self.fy >= 1.08


G300 = Steel("G300", 300.0, 340.0)
G450 = Steel("G450", 450.0, 480.0)
G500 = Steel("G500", 500.0, 520.0)
# connection strength for the lift design: 0.75 x 550 MPa (low-ductility rule of AISI S100 for 2 %-elongation steel),
# the lowest reading of the coil likely to be supplied (G550 at 0.95 mm); it is also below G450 fu = 480 MPa
NOTCH_LENGTH = 50.0             # mm, length of a Framer lip notch along the chord (about one web member width)
CONN_LOW = Steel("connections fu 412.5", 450.0, 412.5)
G550 = Steel("G550", 550.0, 550.0)


def g550_design_strengths(t):
    """Clause 1.5.1.4(b): G550 thinner than 0.9 mm uses 90 % of fy and fu (not more than 495 MPa); thinner than 0.6 mm 75 %
    (not more than 410 MPa). At 0.9 mm and above the full 550 MPa applies."""
    if t >= 0.9:
        return Steel("G550", 550.0, 550.0)
    if t >= 0.6:
        return Steel("G550 (0.9 rule)", 495.0, 495.0)
    return Steel("G550 (0.75 rule)", 410.0, 410.0)


# ============================================================================================ elastic plate buckling
def plate_fcr(k, t, b):
    """Elastic local buckling stress of a flat element, clause 2.2.1.2."""
    return k * math.pi ** 2 * E / (12.0 * (1.0 - NU ** 2)) * (t / b) ** 2


def rho_winter(f, fcr):
    """Effective width factor, clause 2.2.1.2: rho = (1 - 0.22 / lambda) / lambda <= 1."""
    lam = math.sqrt(f / fcr)
    return 1.0 if lam <= 0.673 else (1.0 - 0.22 / lam) / lam


# ============================================================================================ lipped channel member
class LippedChannel:
    """C-section member capacities. Geometry out-to-out D (web), B (flange), C (lip); thickness t; inside corner radius ri.
    Flat widths are taken between corner tangent points: D - 2 (ri + t), B - 2 (ri + t), C - (ri + t).
    With ri = 0 (sharp corners) the flats are longest, which is the conservative assumption for local buckling."""

    def __init__(self, t, steel: Steel = G450, D=89.0, B=38.0, C=9.0, ri=0.0, buckling=None):
        self.t, self.steel, self.D, self.B, self.C, self.ri = t, steel, D, B, C, ri
        self.p = S.c89(t, ri, D, B, C)
        self.w_web = D - 2 * (ri + t)
        self.w_flange = B - 2 * (ri + t)
        self.w_lip = C - (ri + t)
        self.buckling = buckling if buckling is not None else load_buckling_table(t)

    # ---------------------------------------------------------------- effective widths
    def _flange_and_lip(self, f):
        """Clause 2.4.2: uniformly compressed flange with a simple lip edge stiffener.
        Returns (effective flange width, effective lip width)."""
        t, b, d = self.t, self.w_flange, self.w_lip
        Sx = 1.28 * math.sqrt(E / f)
        # lip as an unstiffened element (clause 2.3.1, k = 0.43)
        ds_dash = rho_winter(f, plate_fcr(0.43, t, d)) * d
        if b / t <= Sx / 3.0:
            return b, ds_dash
        Ia = min(399.0 * t ** 4 * ((b / t) / Sx - 0.328) ** 3, t ** 4 * (115.0 * (b / t) / Sx + 5.0))
        n = max(0.582 - (b / t) / (4.0 * Sx), 1.0 / 3.0)
        Is = d ** 3 * t / 12.0                                   # lip at 90 degrees to the flange
        RI = min(Is / Ia, 1.0) if Ia > 0 else 1.0
        Dl_b = self.C / b                                        # overall lip depth / flat flange width
        if Dl_b <= 0.25:
            k = min(3.57 * RI ** n + 0.43, 4.0)
        elif Dl_b <= 0.8:
            k = min((4.82 - 5.0 * Dl_b) * RI ** n + 0.43, 4.0)
        else:
            raise ValueError("lip too long for clause 2.4.2")
        be = rho_winter(f, plate_fcr(k, t, b)) * b
        return be, ds_dash * RI

    def area_effective(self, f):
        """Effective area under uniform compression at stress f (clauses 2.2.1, 2.3.1, 2.4.2)."""
        t = self.t
        be_web = rho_winter(f, plate_fcr(4.0, t, self.w_web)) * self.w_web
        be_fl, ds = self._flange_and_lip(f)
        removed = (self.w_web - be_web) + 2.0 * (self.w_flange - be_fl) + 2.0 * (self.w_lip - ds)
        return max(self.p.A - removed * t, 0.0)

    def area_effective_notched(self, f):
        """Effective area at a LIP NOTCH (Framer cuts the lips away over a short length where a truss web joins a chord).
        The lips and the lip corners are gone, each flange becomes an unstiffened element (k = 0.43, clause 2.3.1) whose
        flat runs to the free edge, and the web is as usual (k = 4). Conservative: the swaged web end that sits in the notch
        and restrains the flanges is ignored."""
        t, ri = self.t, self.ri
        be_web = rho_winter(f, plate_fcr(4.0, t, self.w_web)) * self.w_web
        b_fl = self.w_flange + (ri + t)                       # flat flange from the web corner to the cut edge
        # the notch is short (about the width of the web member, NOTCH_LENGTH): over it the flange is a plate simply supported
        # on three sides (web corner and the lipped flange at each end of the notch) and free on the cut edge:
        # k = 0.425 + (b / a)^2 (classical plate buckling), not the 0.43 of an endless free edge
        k = min(0.425 + (b_fl / NOTCH_LENGTH) ** 2, 4.0)
        be_fl = rho_winter(f, plate_fcr(k, t, b_fl)) * b_fl
        lips = 2.0 * (self.w_lip + math.pi / 2.0 * (ri + t / 2.0))
        removed = lips + (self.w_web - be_web) + 2.0 * (b_fl - be_fl)
        return max(self.p.A - removed * t, 0.0)

    def notched_compression_design(self, fn):
        """phi_c x A_eff,notch(fn) x fn: the section at a lip notch, at the member's global buckling stress fn."""
        return PHI["compression"] * self.area_effective_notched(fn) * fn

    # ---------------------------------------------------------------- shear, clause 3.3.4 (AISI S100-16 G2.1 form)
    def shear_design_major(self, kv=5.34):
        """Shear along the web (out-of-plane shear of a panel member): Vv = Aw fv, phi 0.90."""
        t, E_, fy = self.t, E, self.steel.fy
        h = self.w_web; ht = h / t; lim = math.sqrt(E_ * kv / fy)
        if ht <= lim: fv = 0.6 * fy
        elif ht <= 1.51 * lim: fv = 0.6 * math.sqrt(E_ * kv * fy) / ht
        else: fv = math.pi ** 2 * E_ * kv / (12.0 * (1.0 - NU ** 2) * ht ** 2)
        return PHI["shear"] * h * t * fv

    def shear_design_minor(self):
        """Shear across the web (in-plane shear of a panel member), carried by the two flanges: 2 b t 0.6 fy, phi 0.90
        (the flanges are stocky: b/t well under the shear buckling limit)."""
        return PHI["shear"] * 2.0 * self.w_flange * self.t * 0.6 * self.steel.fy

    # ---------------------------------------------------------------- tension, clause 3.2
    def tension_nominal(self, An=None, kt=1.0):
        Ag = self.p.A
        An = Ag if An is None else An
        return min(Ag * self.steel.fy, 0.85 * kt * An * self.steel.fu)

    def tension_design(self, An=None, kt=1.0):
        return PHI["tension"] * self.tension_nominal(An, kt)

    # ---------------------------------------------------------------- compression, clause 3.4 and Section 7
    def elastic_buckling_stress(self, lex, ley, lez):
        """Least elastic buckling stress and its mode for a singly symmetric channel (clauses 3.4.2, 3.4.3).
        lex: effective length for bending about the major (symmetry) axis x; ley: about the minor axis y; lez: twist."""
        p = self.p
        fox = math.pi ** 2 * E / (lex / p.rx) ** 2
        foy = math.pi ** 2 * E / (ley / p.ry) ** 2
        r01 = p.r0
        foz = (G * p.J / (p.A * r01 ** 2)) * (1.0 + math.pi ** 2 * E * p.Cw / (G * p.J * lez ** 2))
        beta = 1.0 - (p.x0 / r01) ** 2
        foxz = ((fox + foz) - math.sqrt((fox + foz) ** 2 - 4.0 * beta * fox * foz)) / (2.0 * beta)
        if foy <= foxz:
            return foy, "flexural (minor axis)", dict(fox=fox, foy=foy, foz=foz, foxz=foxz)
        return foxz, "flexural-torsional", dict(fox=fox, foy=foy, foz=foz, foxz=foxz)

    @staticmethod
    def _fn(fy, foc):
        lam = math.sqrt(fy / foc)
        return (0.658 ** (lam ** 2)) * fy if lam <= 1.5 else (0.877 / lam ** 2) * fy

    def compression_section_nominal(self):
        return self.area_effective(self.steel.fy) * self.steel.fy

    def compression_nominal(self, lex, ley, lez):
        """Returns (Nc, details). Nc = least of the EWM member capacity (3.4.1), the DSM local-global capacity (7.2.1.3)
        and the distortional capacity (7.2.1.4 / 3.4.6)."""
        fy, A = self.steel.fy, self.p.A
        foc, mode, st = self.elastic_buckling_stress(lex, ley, lez)
        fn = self._fn(fy, foc)
        N_ewm = self.area_effective(fn) * fn
        det = dict(foc=foc, global_mode=mode, fn=fn, N_ewm=N_ewm, **st)
        Nce = A * fn
        N_dsm_local = N_dist = None
        b = self.buckling.get("axial") if self.buckling else None
        if b:
            Nol = A * b["f_local"]
            lam_l = math.sqrt(Nce / Nol)
            N_dsm_local = Nce if lam_l <= 0.776 else (1.0 - 0.15 * (Nol / Nce) ** 0.4) * (Nol / Nce) ** 0.4 * Nce
            if b.get("f_dist"):
                Ny, Nod = A * fy, A * b["f_dist"]
                lam_d = math.sqrt(Ny / Nod)
                N_dist = Ny if lam_d <= 0.561 else (1.0 - 0.25 * (Nod / Ny) ** 0.6) * (Nod / Ny) ** 0.6 * Ny
        cands = {"EWM local-global": N_ewm, "DSM local-global": N_dsm_local, "distortional": N_dist}
        gov = min((v, k) for k, v in cands.items() if v is not None)
        det.update(N_dsm_local=N_dsm_local, N_dist=N_dist, governs=gov[1])
        return gov[0], det

    def compression_design(self, lex, ley, lez):
        Nc, det = self.compression_nominal(lex, ley, lez)
        return PHI["compression"] * Nc, det

    # ---------------------------------------------------------------- bending about the major axis, clause 3.3 and Section 7
    def _Ze_major(self, f):
        """Effective section modulus for major-axis bending with the compression flange at stress f (2.2.3, 2.4.2).
        The web is under stress gradient; neutral axis shift from the ineffective flange strip is included by one iteration."""
        t, D = self.t, self.D
        be_fl, ds = self._flange_and_lip(f)
        p = self.p
        # removed strips in the compression flange and lip (taken at the flange level, conservative lever arm)
        y_fl = (D - t) / 2.0
        rem_fl = (self.w_flange - be_fl) * t
        rem_lip = (self.w_lip - ds) * t
        y_lip = y_fl - (self.ri + t) - self.w_lip / 2.0
        # web under stress gradient, psi about -1: k = 24 (clause 2.2.3.2)
        psi = -1.0
        k = 4.0 + 2.0 * (1.0 - psi) ** 3 + 2.0 * (1.0 - psi)
        f_web = f * (self.w_web / 2.0) / (D / 2.0)
        be_w = rho_winter(f_web, plate_fcr(k, t, self.w_web)) * self.w_web
        b1 = be_w / (3.0 - psi)
        b2 = be_w / 2.0
        comp = self.w_web / 2.0
        rem_web = max(comp - (b1 + b2), 0.0) * t
        y_web = comp - b1 - max(comp - (b1 + b2), 0.0) / 2.0     # centroid of the removed web strip above the neutral axis
        A_rem = rem_fl + rem_lip + rem_web
        if A_rem <= 1e-9:
            return p.Ix / (D / 2.0)
        Ae = p.A - A_rem
        ybar = -(rem_fl * y_fl + rem_lip * y_lip + rem_web * y_web) / Ae           # neutral axis moves away from compression
        Ie = p.Ix - (rem_fl * y_fl ** 2 + rem_lip * y_lip ** 2 + rem_web * y_web ** 2) - Ae * ybar ** 2
        return Ie / (D / 2.0 - ybar)                                             # yield first at the compression face

    def moment_major_nominal(self, lb=0.0, Cb=1.0):
        """Major-axis moment capacity: least of section (3.3.2), lateral buckling (3.3.3.2), and DSM local / distortional (7.2.2).
        lb = unbraced length of the compression flange for lateral buckling (0 = fully braced)."""
        fy, p = self.steel.fy, self.p
        Zf = p.Zx()
        My = Zf * fy
        Ms = self._Ze_major(fy) * fy
        det = dict(My=My, Ms_ewm=Ms)
        Mbe = My
        if lb > 0:
            foy = math.pi ** 2 * E / (lb / p.ry) ** 2
            foz = (G * p.J / (p.A * p.r0 ** 2)) * (1.0 + math.pi ** 2 * E * p.Cw / (G * p.J * lb ** 2))
            Mo = Cb * p.A * p.r0 * math.sqrt(foy * foz)
            lam_b = math.sqrt(My / Mo)
            Mc = My if lam_b <= 0.60 else (1.11 * My * (1.0 - 10.0 * lam_b ** 2 / 36.0) if lam_b < 1.336 else My / lam_b ** 2)
            fc = Mc / Zf
            Mb_ewm = self._Ze_major(fc) * fc
            Mbe = Mc
            det.update(Mo=Mo, Mc=Mc, Mb_ewm=Mb_ewm)
        else:
            Mb_ewm = Ms
        M_local = M_dist = None
        b = self.buckling.get("bend_major") if self.buckling else None
        if b:
            Mol = Zf * b["f_local"]
            lam_l = math.sqrt(Mbe / Mol)
            M_local = Mbe if lam_l <= 0.776 else (1.0 - 0.15 * (Mol / Mbe) ** 0.4) * (Mol / Mbe) ** 0.4 * Mbe
            if b.get("f_dist"):
                Mod = Zf * b["f_dist"]
                lam_d = math.sqrt(My / Mod)
                M_dist = My if lam_d <= 0.673 else (1.0 - 0.22 * (Mod / My) ** 0.5) * (Mod / My) ** 0.5 * My
        cands = {"EWM": min(Ms, Mb_ewm), "DSM local": M_local, "distortional": M_dist}
        gov = min((v, k) for k, v in cands.items() if v is not None)
        det.update(M_dsm_local=M_local, M_dist=M_dist, governs=gov[1])
        return gov[0], det

    def moment_major_design(self, lb=0.0, Cb=1.0):
        M, det = self.moment_major_nominal(lb, Cb)
        return PHI["bending_member"] * M, det

    # ---------------------------------------------------------------- bending about the minor axis
    def moment_minor_nominal(self, compression="web"):
        """Minor-axis moment capacity (bending in the plane of a wall panel or truss for a member laid flat).
        compression = 'web' (web in compression, flange tips in tension) or 'lips' (flange tips and lips in compression).
        Yield moment on the first-yield fibre, reduced for local buckling by DSM (7.2.2.3) with the finite strip stress;
        if no finite strip value is available an effective-width estimate is used."""
        fy, p, t = self.steel.fy, self.p, self.t
        Zc = p.Zy_web() if compression == "web" else p.Zy_lip()        # modulus at the compression face
        Zt = p.Zy_lip() if compression == "web" else p.Zy_web()
        My = min(Zc, Zt) * fy                                           # first yield at either face
        key = "bend_minor_web_comp" if compression == "web" else "bend_minor_lips_comp"
        b = self.buckling.get(key) if self.buckling else None
        if b:
            Mol = Zc * b["f_local"]
            lam_l = math.sqrt(My / Mol)
            M = My if lam_l <= 0.776 else (1.0 - 0.15 * (Mol / My) ** 0.4) * (Mol / My) ** 0.4 * My
            return M, dict(My=My, f_local=b["f_local"], method="DSM")
        if compression == "web":
            be = rho_winter(fy, plate_fcr(4.0, t, self.w_web)) * self.w_web
            return My * (0.5 + 0.5 * be / self.w_web), dict(My=My, method="EWM estimate")
        # lips in compression: flanges under stress gradient with the free-edge side in compression (k about 0.57) - take unstiffened
        be = rho_winter(fy, plate_fcr(0.43, t, self.w_lip)) * self.w_lip
        return My * (0.5 + 0.5 * be / self.w_lip), dict(My=My, method="EWM estimate")

    def moment_minor_design(self, compression="web"):
        M, det = self.moment_minor_nominal(compression)
        return PHI["bending_member"] * M, det

    # ---------------------------------------------------------------- shear, clause 3.3.4
    def shear_nominal(self):
        """Shear capacity of the web for shear along the web (major-axis bending), unstiffened web kv = 5.34."""
        d1, t, fy, kv = self.w_web, self.t, self.steel.fy, 5.34
        lim = math.sqrt(E * kv / fy)
        if d1 / t <= lim:
            return 0.64 * fy * d1 * t
        if d1 / t <= 1.415 * lim:
            return 0.64 * t ** 2 * math.sqrt(E * kv * fy)
        return 0.905 * E * kv * t ** 3 / d1

    def shear_design(self):
        return PHI["shear"] * self.shear_nominal()


# ============================================================================================ combined actions, clause 3.5
def combined_compression_bending(N, Mx, My, phiNc, phiNs, phiMbx, phiMby, Nex=None, Ney=None, Cmx=1.0, Cmy=1.0):
    """Clause 3.5.1 (N is the compression magnitude, all values positive). Returns the governing interaction ratio."""
    if phiNc <= 0:
        return float("inf")
    if N / phiNc <= 0.15:
        return N / phiNc + Mx / phiMbx + My / phiMby
    ax = 1.0 - N / Nex if Nex else 1.0
    ay = 1.0 - N / Ney if Ney else 1.0
    if ax <= 0 or ay <= 0:
        return float("inf")
    r1 = N / phiNc + Cmx * Mx / (phiMbx * ax) + Cmy * My / (phiMby * ay)
    r2 = N / phiNs + Mx / phiMbx + My / phiMby
    return max(r1, r2)


def combined_tension_bending(N, Mx, My, phiNt, phiMsx, phiMsy, phiMbx, phiMby):
    """Clause 3.5.2 (N is the tension magnitude). Returns the governing interaction ratio."""
    r1 = Mx / phiMsx + My / phiMsy + N / phiNt
    r2 = Mx / phiMbx + My / phiMby - N / phiNt
    return max(r1, r2)


# ============================================================================================ screwed connections, clause 5.4
def screw_bearing_factor(d, t):
    """Bearing factor C for screws (Table 5.4.2.4): d/t < 6: 2.7; 6 to 13: 3.3 - 0.1 d/t; > 13: 2.0."""
    r = d / t
    return 2.7 if r < 6.0 else (3.3 - 0.1 * r if r <= 13.0 else 2.0)


def screw_shear_nominal(t1, fu1, t2, fu2, d):
    """Clause 5.4.2.4 tilting and hole bearing of ONE screw in single shear.
    t1, fu1: sheet in contact with the screw head; t2, fu2: sheet not in contact with the head; d: nominal screw diameter."""
    bear1 = screw_bearing_factor(d, t1) * t1 * d * fu1
    bear2 = screw_bearing_factor(d, t2) * t2 * d * fu2
    tilt = 4.2 * math.sqrt(t2 ** 3 * d) * fu2
    r = t2 / t1
    if r <= 1.0:
        return min(tilt, bear1, bear2)
    if r >= 2.5:
        return min(bear1, bear2)
    a, b = min(tilt, bear1, bear2), min(bear1, bear2)
    return a + (b - a) * (r - 1.0) / 1.5


def screw_shear_design(t1, fu1, t2, fu2, d, screw_shear_breaking=None):
    """phi x nominal capacity of one screw in shear; if the screw's own single-shear breaking load is given, the
    connection capacity is also limited to phi x that load (clause 5.4.2.6)."""
    v = PHI["screw"] * screw_shear_nominal(t1, fu1, t2, fu2, d)
    if screw_shear_breaking:
        v = min(v, PHI["screw"] * screw_shear_breaking)
    return v


def screw_tearout_design(t, e, steel: Steel):
    """Clause 5.4.2.5: shear limited by end distance e (parallel to the force)."""
    return (0.70 if steel.ductile else 0.60) * t * e * steel.fu


def screw_pullout_design(t2, fu2, d):
    """Clause 5.4.3.1 pull-out from the sheet not in contact with the head."""
    return PHI["screw"] * 0.85 * t2 * d * fu2


def screw_pullover_design(t1, fu1, dw):
    """Clause 5.4.3.1 pull-over (pull-through) of the sheet under the head; dw = larger of head and washer diameter, <= 12.7 mm."""
    return PHI["screw"] * 1.5 * t1 * min(dw, 12.7) * fu1


# ============================================================================================ bolted connections, clause 5.3
def bolt_bearing_factor(d, t):
    """Bearing factor C (Table 5.3.4.2(B)): d/t < 10: 3.0; 10 to 22: 4 - 0.1 d/t; > 22: 1.8."""
    r = d / t
    return 3.0 if r < 10.0 else (4.0 - 0.1 * r if r <= 22.0 else 1.8)


def bolt_bearing_design(t, fu, d, washers=True, inside_sheet=False):
    """Clause 5.3.4.2 bearing without considering bolt-hole deformation: Vb = alpha C d t fu.
    alpha (Table 5.3.4.2(A)): single shear or outside sheets of double shear with washers under head and nut 1.00,
    without washers (or only one) 0.75; inside sheet of a double shear connection 1.33."""
    alpha = 1.33 if inside_sheet else (1.00 if washers else 0.75)
    return PHI["bolt_bearing"] * alpha * bolt_bearing_factor(d, t) * d * t * fu


def bolt_tearout_design(t, e, steel: Steel):
    """Clause 5.3.2: tear-out along two lines through the sheet, Vf = t e fu, e = distance from the hole centre to the end."""
    return (PHI["bolt_tearout"] if steel.ductile else 0.60) * t * e * steel.fu


def flat_tension_design(Ag, An, steel: Steel, kt=1.0):
    """Tension capacity of a flat strap or plate: least of gross yield and net fracture."""
    return min(PHI["tension"] * Ag * steel.fy, PHI["net_section_bolted"] * 0.85 * kt * An * steel.fu)


def block_shear_design(Agv, Anv, Ant, steel: Steel):
    """Clause 5.6.3 block shear rupture: Rn = lesser of 0.6 fy Agv + fu Ant and 0.6 fu Anv + fu Ant."""
    return PHI["block_shear_bolted"] * min(0.6 * steel.fy * Agv + steel.fu * Ant, 0.6 * steel.fu * Anv + steel.fu * Ant)


# bolt shear to AS 4100 (threads in the shear plane), kN -> N : phi 0.8 x 0.62 x fuf x Ac
def bolt_shear_design(d=12.0, fuf=830.0, threads_in_shear_plane=True, n_planes=1):
    core = {12.0: 76.2, 16.0: 144.0, 20.0: 225.0}[d] if threads_in_shear_plane else math.pi * d ** 2 / 4.0
    return 0.8 * 0.62 * fuf * core * n_planes


# ============================================================================================ finite strip table
_TABLE = None


def load_buckling_table(t, corners="sharp", path=None):
    """Elastic buckling stresses for the C89 family from the finite strip table; {} if the table is not there yet."""
    global _TABLE
    path = path or os.path.join(os.path.dirname(__file__), "data", "c89_buckling.json")
    if _TABLE is None:
        if not os.path.exists(path):
            return {}
        _TABLE = json.load(open(path, encoding="utf-8"))
    out = {}
    for r in _TABLE.get("rows", []):
        if abs(r["t"] - t) < 1e-6 and str(r.get("corners", "")).lower().startswith(corners[:5]):
            out[r["action"]] = {"f_local": r["f_local"], "f_dist": r.get("f_dist")}
    return out
