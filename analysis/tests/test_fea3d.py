"""Checks of the independent 3D frame solver against closed-form results and against PyNite."""
import sys, os, math
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from liftcalc.fea3d import Model

E, G = 200000.0, 200000.0 / 2.6


def test_cantilever_two_axes():
    L, P, Iy, Iz = 1500.0, 1000.0, 2.2e5, 3.3e4
    m = Model(); a = m.node(0, 0, 0); b = m.node(L, 0, 0)
    m.beam(a, b, 170.0, Iy, Iz, 50.0, ref=(0, 1, 0))        # local y = global Y, local z = global Z
    m.fix(a, range(6))
    m.load("z", b, 2, -P)                                   # load along global Z -> bending in x-z plane -> uses Iy
    m.load("y", b, 1, -P)                                   # load along global Y -> bending in x-y plane -> uses Iz
    r = m.solve()
    assert abs(r["z"]["u"][b, 2] + P * L ** 3 / (3 * E * Iy)) < 1e-6 * abs(P * L ** 3 / (3 * E * Iy))
    assert abs(r["y"]["u"][b, 1] + P * L ** 3 / (3 * E * Iz)) < 1e-6 * abs(P * L ** 3 / (3 * E * Iz))
    # support reaction and moment
    assert abs(r["z"]["reactions"][a][2] - P) < 1e-6 and abs(abs(r["z"]["reactions"][a][4]) - P * L) < 1e-3


def test_axial_and_torsion():
    L, A, J = 2000.0, 170.0, 60.0
    m = Model(); a = m.node(0, 0, 0); b = m.node(0, 0, L)   # vertical member, ref falls back automatically
    m.beam(a, b, A, 1e5, 1e5, J, ref=(1, 0, 0)); m.fix(a, range(6))
    m.load("n", b, 2, 5000.0); m.load("t", b, 5, 1.0e4)
    r = m.solve()
    assert abs(r["n"]["u"][b, 2] - 5000.0 * L / (E * A)) < 1e-9
    assert abs(Model.axial(r["n"]["end_forces"])[0] - 5000.0) < 1e-6          # tension positive
    assert abs(r["t"]["u"][b, 5] - 1.0e4 * L / (G * J)) < 1e-9


def test_semi_rigid_limits():
    # fixed-fixed beam with a central point load, modelled with two elements; end fixity r at the supports
    L, P, I = 3000.0, 2000.0, 2.0e5
    def mid_defl(r):
        m = Model(); a = m.node(0, 0, 0); c = m.node(L / 2, 0, 0); b = m.node(L, 0, 0)
        m.beam(a, c, 200.0, 1e5, I, 50.0, ref=(0, 1, 0), rz=(r, 1.0)); m.beam(c, b, 200.0, 1e5, I, 50.0, ref=(0, 1, 0), rz=(1.0, r))
        m.fix(a, range(6)); m.fix(b, range(6)); m.load("p", c, 1, -P)
        return -m.solve()["p"]["u"][c, 1]
    assert abs(mid_defl(1.0) - P * L ** 3 / (192 * E * I)) < 1e-6 * P * L ** 3 / (192 * E * I)      # fixed ends
    assert abs(mid_defl(0.0) - P * L ** 3 / (48 * E * I)) < 1e-6 * P * L ** 3 / (48 * E * I)        # pinned ends
    assert P * L ** 3 / (192 * E * I) < mid_defl(0.5) < P * L ** 3 / (48 * E * I)


def test_pratt_truss_forces():
    # 4-panel Pratt truss, pinned webs, unit loads at the three interior bottom nodes: chord and diagonal forces by statics.
    # (With stiff continuous chords the same truss carries about 3 % of the shear in chord bending: that is physics, not error.)
    a, h, P = 1000.0, 1000.0, 1000.0
    m = Model()
    bot = [m.node(i * a, 0, 0) for i in range(5)]; top = [m.node(i * a, 0, h) for i in range(1, 4)]
    # The truss lies in the global x-z plane and ref = global Y, so local y' is OUT of the truss plane:
    # Iy (bending in the x'-z' plane) is the IN-plane stiffness. Keep it negligible so the truss is an ideal pin truss.
    big = dict(A=500.0, Iy=50.0, Iz=1e6, J=1e4, ref=(0, 1, 0))
    for i in range(4): m.beam(bot[i], bot[i + 1], **big)
    for i in range(2): m.beam(top[i], top[i + 1], **big)
    pin = dict(A=200.0, Iy=1e3, Iz=1e3, J=10.0, ref=(0, 1, 0), rz=(0.0, 0.0), ry=(0.0, 0.0))
    d_end = m.beam(bot[0], top[0], **pin); m.beam(top[2], bot[4], **pin)
    for i in range(3): m.beam(bot[i + 1], top[i], **pin)                 # verticals
    d_in = m.beam(top[0], bot[2], **pin); m.beam(top[2], bot[2], **pin)   # inner diagonals
    m.fix(bot[0], [0, 1, 2, 3]); m.fix(bot[4], [1, 2])
    for n in bot + top: m.fix(n, [1])                                   # plane truss: hold out of plane
    for n in bot[1:4]: m.load("g", n, 2, -P)
    r = m.solve()["g"]
    N = Model.axial(r["end_forces"])
    assert abs(N[d_end] + 1.5 * P * math.sqrt(2)) < 1.0                 # end diagonal in compression 1.5 P sqrt2
    assert abs(N[d_in] - 0.5 * P * math.sqrt(2)) < 1.0                  # inner diagonal in tension 0.5 P sqrt2
    assert abs(N[4] + 2.0 * P) < 1.0                                    # top chord at midspan: -M/h = -2P
    assert abs(sum(v[2] for v in r["reactions"].values()) - 3 * P) < 1e-6


def test_random_frame_against_pynite():
    from Pynite import FEModel3D
    rng = np.random.default_rng(7)
    pts = [(x * 1200.0 + rng.uniform(-80, 80), y * 900.0 + rng.uniform(-60, 60), z * 1100.0) for z in range(3) for y in range(2) for x in range(3)]
    A, I, J = 300.0, 4.0e5, 3.0e3                                         # Iy = Iz so local-axis conventions cannot differ
    m = Model(); ids = [m.node(*p) for p in pts]
    pn = FEModel3D(); pn.add_material("s", E, G, 0.3, 7.85e-9); pn.add_section("c", A, I, I, J)
    for i, p in enumerate(pts): pn.add_node(f"N{i}", *p)
    pairs = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = np.linalg.norm(np.array(pts[i]) - np.array(pts[j]))
            if d < 1500.0: pairs.append((i, j))
    for k, (i, j) in enumerate(pairs):
        m.beam(ids[i], ids[j], A, I, I, J); pn.add_member(f"M{k}", f"N{i}", f"N{j}", "s", "c")
    for i in range(6):
        m.fix(ids[i], range(6)); pn.def_support(f"N{i}", True, True, True, True, True, True)
    for i in range(6, len(pts)):
        f = rng.uniform(-3000, 3000, 3)
        for d, name in enumerate(("FX", "FY", "FZ")):
            m.load("c", ids[i], d, f[d]); pn.add_node_load(f"N{i}", name, float(f[d]), "c")
    pn.add_load_combo("c", {"c": 1.0}); pn.analyze_linear()
    r = m.solve()["c"]
    umax = np.abs(r["u"][:, :3]).max()
    for i in range(len(pts)):
        ref = np.array([pn.nodes[f"N{i}"].DX["c"], pn.nodes[f"N{i}"].DY["c"], pn.nodes[f"N{i}"].DZ["c"]])
        assert np.abs(r["u"][i, :3] - ref).max() < 1e-6 * umax + 1e-9
    # axial forces: PyNite reports compression positive along the member
    N = Model.axial(r["end_forces"])
    for k in range(len(pairs)):
        assert abs(N[k] + pn.members[f"M{k}"].axial(0.0, "c")) < 1e-3 * max(1.0, np.abs(N).max())
