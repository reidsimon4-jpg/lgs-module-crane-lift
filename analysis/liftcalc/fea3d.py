"""Independent linear-elastic 3D frame solver (direct stiffness method).

Written for this project; it does not use any code from Infinity Framer. Cross-checked against PyNite
(see analysis/tests/test_fea3d.py and verification/solver_crosscheck).

Units: N, mm, MPa (N/mm2). Rotations in radians.

Element: 2-node Euler-Bernoulli space frame element, 6 degrees of freedom per node
(ux, uy, uz, rx, ry, rz in GLOBAL axes). Local axes: x' along the member from node i to node j;
y' is the component of the element's reference vector `ref` perpendicular to x'; z' = x' cross y'.
  Iz = second moment for bending in the local x'-y' plane (bending about z')
  Iy = second moment for bending in the local x'-z' plane (bending about y')
End fixity for bending about z' (the "in-plane" bending of a panel member) is set per end by a fixity factor
r in [0, 1]: 1 = rigid, 0 = pinned, between = semi-rigid (r = 1 / (1 + 3 E Iz / (k_theta L))). The same can be
set for bending about y' (ry_i, ry_j). Torsion can be released at end j.

Sign convention of reported member forces (local axes, acting ON the member ends, "end actions"):
  N > 0 is TENSION. Moments and shears are reported as end actions at i and j in local axes.
"""
from __future__ import annotations
import numpy as np
from scipy.sparse import coo_matrix, csc_matrix
from scipy.sparse.linalg import splu


class Model:
    def __init__(self):
        self.xyz = []                 # node coordinates
        self.el = []                  # element dicts
        self.fixed = {}               # node -> set of dofs (0..5)
        self.nspring = []             # (node, dof, k)
        self.loads = {}               # case name -> {(node, dof): value}
        self.meta = {}

    # ------------------------------------------------------------------ building
    def node(self, x, y, z):
        self.xyz.append((float(x), float(y), float(z)))
        return len(self.xyz) - 1

    def beam(self, i, j, A, Iy, Iz, J, E=200000.0, G=None, ref=(0.0, 0.0, 1.0), rz=(1.0, 1.0), ry=(1.0, 1.0),
             torsion_release=False, tag=None):
        if i == j:
            raise ValueError("zero-length element (same node)")
        G = E / 2.6 if G is None else G
        self.el.append(dict(i=i, j=j, A=float(A), Iy=float(Iy), Iz=float(Iz), J=float(J), E=float(E), G=float(G),
                            ref=tuple(float(v) for v in ref), rz=(float(rz[0]), float(rz[1])), ry=(float(ry[0]), float(ry[1])),
                            tr=bool(torsion_release), tag=tag))
        return len(self.el) - 1

    def fix(self, node, dofs):
        self.fixed.setdefault(node, set()).update(dofs)

    def spring(self, node, dof, k):
        self.nspring.append((node, int(dof), float(k)))

    def load(self, case, node, dof, value):
        d = self.loads.setdefault(case, {})
        d[(node, dof)] = d.get((node, dof), 0.0) + float(value)

    # ------------------------------------------------------------------ element matrices
    @staticmethod
    def _bend(EI, L, ri, rj):
        """4x4 bending stiffness [v_i, th_i, v_j, th_j] of a beam with end fixity factors ri, rj
        (Monforton and Wu 1963 form). ri = rj = 1 gives the classic rigid matrix; 0 gives a pin."""
        d = 4.0 - ri * rj
        if abs(d) < 1e-14:
            d = 1e-14
        a = EI / L ** 3
        k11 = 12.0 * a * (ri + rj + ri * rj) / d
        k12 = 6.0 * a * L * ri * (2.0 + rj) / d
        k14 = 6.0 * a * L * rj * (2.0 + ri) / d
        k22 = 12.0 * a * L * L * ri / d
        k24 = 6.0 * a * L * L * ri * rj / d
        k44 = 12.0 * a * L * L * rj / d
        return np.array([[k11, k12, -k11, k14],
                         [k12, k22, -k12, k24],
                         [-k11, -k12, k11, -k14],
                         [k14, k24, -k14, k44]])

    def _local(self, e):
        xi, xj = np.array(self.xyz[e["i"]]), np.array(self.xyz[e["j"]])
        d = xj - xi
        L = float(np.linalg.norm(d))
        if L < 1e-9:
            raise ValueError("zero-length element")
        ex = d / L
        ref = np.array(e["ref"], float)
        ey = ref - ref.dot(ex) * ex
        if np.linalg.norm(ey) < 1e-8 * max(1.0, np.linalg.norm(ref)):
            # reference vector parallel to the member: fall back to a global axis that is not
            alt = np.array([1.0, 0.0, 0.0]) if abs(ex[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
            ey = alt - alt.dot(ex) * ex
        ey /= np.linalg.norm(ey)
        ez = np.cross(ex, ey)
        R = np.vstack([ex, ey, ez])                      # rows = local axes in global components
        k = np.zeros((12, 12))
        EA_L = e["E"] * e["A"] / L
        k[0, 0] = k[6, 6] = EA_L; k[0, 6] = k[6, 0] = -EA_L
        GJ_L = 0.0 if e["tr"] else e["G"] * e["J"] / L
        k[3, 3] = k[9, 9] = GJ_L; k[3, 9] = k[9, 3] = -GJ_L
        # bending about z' : dofs v (1, 7) and theta_z (5, 11)
        kz = self._bend(e["E"] * e["Iz"], L, e["rz"][0], e["rz"][1])
        iz = [1, 5, 7, 11]
        for a in range(4):
            for b in range(4):
                k[iz[a], iz[b]] += kz[a, b]
        # bending about y' : dofs w (2, 8) and theta_y (4, 10); note theta_y = -dw/dx
        ky = self._bend(e["E"] * e["Iy"], L, e["ry"][0], e["ry"][1])
        S = np.diag([1.0, -1.0, 1.0, -1.0])
        ky = S @ ky @ S
        iy = [2, 4, 8, 10]
        for a in range(4):
            for b in range(4):
                k[iy[a], iy[b]] += ky[a, b]
        T = np.zeros((12, 12))
        for b in range(4):
            T[3 * b:3 * b + 3, 3 * b:3 * b + 3] = R
        return k, T, L

    # ------------------------------------------------------------------ assembly and solve
    def assemble(self):
        n = len(self.xyz)
        rows, cols, vals = [], [], []
        self._ke = []
        for e in self.el:
            k, T, L = self._local(e)
            kg = T.T @ k @ T
            dof = [6 * e["i"] + a for a in range(6)] + [6 * e["j"] + a for a in range(6)]
            self._ke.append((k, T, L, dof))
            rr, cc = np.meshgrid(dof, dof, indexing="ij")
            rows.append(rr.ravel()); cols.append(cc.ravel()); vals.append(kg.ravel())
        for (nd, d, ks) in self.nspring:
            rows.append(np.array([6 * nd + d])); cols.append(np.array([6 * nd + d])); vals.append(np.array([ks]))
        K = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(6 * n, 6 * n)).tocsc()
        self.K = K
        return K

    def solve(self, cases=None, check=True):
        """Solve all (or the named) load cases. Returns {case: result dict}."""
        if not hasattr(self, "K"):
            self.assemble()
        n = len(self.xyz)
        fixed = sorted(6 * nd + d for nd, ds in self.fixed.items() for d in ds)
        mask = np.ones(6 * n, bool); mask[fixed] = False
        free = np.nonzero(mask)[0]
        Kff = self.K[free][:, free].tocsc()
        # degrees of freedom with no stiffness at all (a node touched by nothing) make the matrix singular: report them
        diag = Kff.diagonal()
        dead = free[np.abs(diag) < 1e-9]
        if len(dead):
            raise RuntimeError("unrestrained degrees of freedom with zero stiffness: %s" % [(int(d // 6), int(d % 6)) for d in dead[:20]])
        lu = splu(Kff)
        out = {}
        for case in (cases or list(self.loads)):
            F = np.zeros(6 * n)
            for (nd, d), v in self.loads[case].items():
                F[6 * nd + d] += v
            u = np.zeros(6 * n)
            u[free] = lu.solve(F[free])
            if check:
                res = Kff @ u[free] - F[free]
                scale = max(1.0, float(np.abs(F).max()))
                if float(np.abs(res).max()) > 1e-5 * scale:
                    raise RuntimeError("solution residual too large in case %s: %.3e (mechanism or ill-conditioning)" % (case, np.abs(res).max()))
            R = self.K @ u - F                             # reactions (support + spring forces come out at their dofs)
            react = {}
            for nd, ds in self.fixed.items():
                react[nd] = [float(R[6 * nd + d]) if d in ds else 0.0 for d in range(6)]
            spring_forces = [(nd, d, -ks * float(u[6 * nd + d])) for (nd, d, ks) in self.nspring]
            forces = np.zeros((len(self.el), 12))
            for a, (k, T, L, dof) in enumerate(self._ke):
                forces[a] = k @ (T @ u[dof])               # local end actions on the member
            out[case] = dict(u=u.reshape(n, 6), reactions=react, spring_forces=spring_forces, end_forces=forces,
                             applied=F.reshape(n, 6))
        return out

    # ------------------------------------------------------------------ helpers on results
    @staticmethod
    def axial(end_forces):
        """Axial force per element, tension positive (from the end action at j along local x)."""
        return end_forces[:, 6]

    @staticmethod
    def moments_z(end_forces):
        """In-plane bending moment (about local z) at i and j as internal sagging-convention magnitudes |M|."""
        return np.abs(end_forces[:, 5]), np.abs(end_forces[:, 11])

    @staticmethod
    def moments_y(end_forces):
        return np.abs(end_forces[:, 4]), np.abs(end_forces[:, 10])


def mechanisms(model: "Model", k=8, tol=1e-6):
    """Diagnostic: the lowest stiffness modes of the supported structure. A (near-)zero eigenvalue is a mechanism.
    Returns [(eigenvalue, [(node, max translation component)...top nodes])]. Uses shift-invert just below zero."""
    from scipy.sparse.linalg import eigsh
    if not hasattr(model, "K"):
        model.assemble()
    n = len(model.xyz)
    fixed = sorted(6 * nd + d for nd, ds in model.fixed.items() for d in ds)
    mask = np.ones(6 * n, bool); mask[fixed] = False
    free = np.nonzero(mask)[0]
    Kff = model.K[free][:, free].tocsc()
    scale = float(abs(Kff.diagonal()).mean())
    vals, vecs = eigsh(Kff, k=k, sigma=-1e-9 * scale, which="LM")
    out = []
    for a in np.argsort(vals):
        v = np.zeros(6 * n); v[free] = vecs[:, a]
        amp = np.abs(v.reshape(n, 6)[:, :3]).max(axis=1) + np.abs(v.reshape(n, 6)[:, 3:]).max(axis=1) * 100.0
        top = np.argsort(-amp)[:8]
        out.append((float(vals[a]), [(int(t), float(amp[t])) for t in top], float(vals[a] / scale)))
    return out
