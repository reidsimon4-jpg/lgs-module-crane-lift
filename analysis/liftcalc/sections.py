"""Thin-walled section properties for the C89 lipped channel family (independent implementation).

General method: the section is a single open branch of straight centreline segments (corners may be rounded and
are then meshed as short chords). Area, centroid and second moments are exact for straight segments; the shear
centre and warping constant come from the sectorial-coordinate method.

Axes for a single channel:
  origin at the middle of the web centreline; +x points from the web towards the flange tips; y runs along the web.
  x-x (through the centroid, parallel to the flanges) is the MAJOR axis: Ix = integral of y^2 dA.
  y-y (through the centroid, parallel to the web)     is the MINOR axis: Iy = integral of (x - xc)^2 dA.
  The shear centre lies on the x axis on the far side of the web from the centroid; x0 = distance between them.
Units: mm.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field

STEEL_DENSITY = 7850.0   # kg/m3


def lipped_channel_nodes(D=89.0, B=38.0, C=9.0, t=0.95, ri=0.0, n_arc=6):
    """Centreline nodes of a lipped channel, starting at the tip of the bottom lip and ending at the tip of the top lip.
    D, B, C are out-to-out; t = base metal thickness; ri = inside corner radius (0 = sharp corners)."""
    h = D - t                 # centreline web height
    b = B - t                 # centreline flange width
    c = C - t / 2.0           # centreline lip length
    r = (ri + t / 2.0) if ri > 0 else 0.0
    if r <= 0:
        return [(b, -h / 2 + c), (b, -h / 2), (0.0, -h / 2), (0.0, h / 2), (b, h / 2), (b, h / 2 - c)]
    if r > min(c, b / 2, h / 2):
        raise ValueError("corner radius too large for the section")
    pts = []

    def arc(cx, cy, a0, a1):
        for k in range(1, n_arc):
            a = a0 + (a1 - a0) * k / n_arc
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))

    # bottom lip tip, going down to the bottom-right corner
    pts.append((b, -h / 2 + c))
    pts.append((b, -h / 2 + r)); arc(b - r, -h / 2 + r, 0.0, -math.pi / 2); pts.append((b - r, -h / 2))
    pts.append((r, -h / 2)); arc(r, -h / 2 + r, -math.pi / 2, -math.pi); pts.append((0.0, -h / 2 + r))
    pts.append((0.0, h / 2 - r)); arc(r, h / 2 - r, math.pi, math.pi / 2); pts.append((r, h / 2))
    pts.append((b - r, h / 2)); arc(b - r, h / 2 - r, math.pi / 2, 0.0); pts.append((b, h / 2 - r))
    pts.append((b, h / 2 - c))
    return pts


@dataclass
class Props:
    A: float; xc: float; yc: float; Ix: float; Iy: float; Ixy: float; J: float
    xs: float; ys: float; Cw: float           # shear centre (absolute coordinates) and warping constant
    t: float
    nodes: list = field(repr=False, default_factory=list)

    @property
    def rx(self): return math.sqrt(self.Ix / self.A)
    @property
    def ry(self): return math.sqrt(self.Iy / self.A)
    @property
    def x0(self): return abs(self.xs - self.xc)       # shear centre to centroid along the axis of symmetry
    @property
    def r0(self): return math.sqrt(self.rx ** 2 + self.ry ** 2 + (self.xs - self.xc) ** 2 + (self.ys - self.yc) ** 2)
    @property
    def kg_per_m(self): return self.A * 1e-6 * STEEL_DENSITY

    def extreme(self):
        """Distances from the centroid to the extreme fibres (outer faces): +x side, -x side, +/-y."""
        xs = [p[0] for p in self.nodes]; ys = [p[1] for p in self.nodes]
        return {"x_pos": max(xs) - self.xc + self.t / 2, "x_neg": self.xc - min(xs) + self.t / 2,
                "y": max(max(ys) - self.yc, self.yc - min(ys)) + self.t / 2}

    def Zx(self): return self.Ix / self.extreme()["y"]
    def Zy_web(self): return self.Iy / self.extreme()["x_neg"]     # modulus at the web face (minor-axis bending)
    def Zy_lip(self): return self.Iy / self.extreme()["x_pos"]     # modulus at the lip / flange-tip side


def open_section_props(nodes, t):
    """Properties of an open single-branch thin-walled section through centreline `nodes` with thickness t."""
    segs = [(nodes[i][0], nodes[i][1], nodes[i + 1][0], nodes[i + 1][1]) for i in range(len(nodes) - 1)]
    A = Sx = Sy = 0.0
    for (x1, y1, x2, y2) in segs:
        L = math.hypot(x2 - x1, y2 - y1); a = t * L
        A += a; Sx += a * (y1 + y2) / 2; Sy += a * (x1 + x2) / 2
    xc, yc = Sy / A, Sx / A
    Ix = Iy = Ixy = J = 0.0
    for (x1, y1, x2, y2) in segs:
        L = math.hypot(x2 - x1, y2 - y1)
        a1, a2, b1, b2 = x1 - xc, x2 - xc, y1 - yc, y2 - yc
        Ix += t * L * (b1 * b1 + b1 * b2 + b2 * b2) / 3
        Iy += t * L * (a1 * a1 + a1 * a2 + a2 * a2) / 3
        Ixy += t * L * (2 * a1 * b1 + a1 * b2 + a2 * b1 + 2 * a2 * b2) / 6
        J += L * t ** 3 / 3
    # sectorial coordinate with pole at the centroid, origin at the first node
    w = [0.0]
    for (x1, y1, x2, y2) in segs:
        w.append(w[-1] + (x1 - xc) * (y2 - yc) - (x2 - xc) * (y1 - yc))
    Iwx = Iwy = 0.0                      # integrals of w*x and w*y
    for i, (x1, y1, x2, y2) in enumerate(segs):
        L = math.hypot(x2 - x1, y2 - y1)
        a1, a2, b1, b2 = x1 - xc, x2 - xc, y1 - yc, y2 - yc
        w1, w2 = w[i], w[i + 1]
        Iwx += t * L * (2 * w1 * a1 + w1 * a2 + w2 * a1 + 2 * w2 * a2) / 6
        Iwy += t * L * (2 * w1 * b1 + w1 * b2 + w2 * b1 + 2 * w2 * b2) / 6
    den = Ix * Iy - Ixy * Ixy
    # shear centre relative to the centroid (standard result for the pole shift that makes Iwx = Iwy = 0)
    ex = (Iwy * Iy - Iwx * Ixy) / den
    ey = -(Iwx * Ix - Iwy * Ixy) / den
    # sectorial coordinate about the shear centre, normalised to zero mean
    ws = [w[i] - ex * (nodes[i][1] - yc) + ey * (nodes[i][0] - xc) for i in range(len(nodes))]
    Sw = sum(t * math.hypot(s[2] - s[0], s[3] - s[1]) * (ws[i] + ws[i + 1]) / 2 for i, s in enumerate(segs))
    wn = [v - Sw / A for v in ws]
    Cw = sum(t * math.hypot(s[2] - s[0], s[3] - s[1]) * (wn[i] ** 2 + wn[i] * wn[i + 1] + wn[i + 1] ** 2) / 3 for i, s in enumerate(segs))
    return Props(A=A, xc=xc, yc=yc, Ix=Ix, Iy=Iy, Ixy=Ixy, J=J, xs=xc + ex, ys=yc + ey, Cw=Cw, t=t, nodes=list(nodes))


def c89(t=0.95, ri=0.0, D=89.0, B=38.0, C=9.0):
    """Single C89 lipped channel."""
    return open_section_props(lipped_channel_nodes(D, B, C, t, ri), t)


@dataclass
class BuiltUp:
    """Two channels acting together. kind = 'b2b' (webs together) or 'boxed' (flange tips together).
    Second moments assume the two channels are fastened so they bend as one about the y axis."""
    kind: str; single: Props; gap: float = 0.0

    @property
    def A(self): return 2 * self.single.A
    @property
    def Ix(self): return 2 * self.single.Ix
    @property
    def Iy(self):
        s = self.single
        if self.kind == "b2b":
            d = s.xc + s.t / 2 + self.gap / 2           # centroid of one channel from the common web contact plane
        else:
            d = s.extreme()["x_pos"] + self.gap / 2      # centroid from the plane where the lips meet
        return 2 * (s.Iy + s.A * d * d)
    @property
    def J(self): return 2 * self.single.J              # open-section torsion (conservative: no closed-cell action)
    @property
    def rx(self): return math.sqrt(self.Ix / self.A)
    @property
    def ry(self): return math.sqrt(self.Iy / self.A)
    @property
    def kg_per_m(self): return 2 * self.single.kg_per_m


def closed_form_lipped_channel(D, B, C, t):
    """Textbook closed-form area, centroid and second moments of a sharp-cornered lipped channel (centreline
    dimensions a = D - t, b = B - t, c = C - t/2). Used only to test the general routine."""
    a, b, c = D - t, B - t, C - t / 2
    A = t * (a + 2 * b + 2 * c)
    xbar = t * (2 * b * b / 2 + 2 * c * b) / A                     # from the web centreline
    Ix = t * (a ** 3 / 12 + 2 * b * (a / 2) ** 2 + 2 * (c ** 3 / 12 + c * (a / 2 - c / 2) ** 2))
    Iy = t * (a * xbar ** 2 + 2 * (b ** 3 / 12 + b * (b / 2 - xbar) ** 2) + 2 * c * (b - xbar) ** 2)
    return {"A": A, "xbar": xbar, "Ix": Ix, "Iy": Iy}
