"""2D beam statics used for the hand checks (independent of the 3D model).

A prismatic Euler-Bernoulli beam on point supports under distributed and point loads, solved by the direct
stiffness method with a fine mesh. Supports can be rigid, elastic (springs) or replaced by known forces
(an equalising rig: forces are prescribed, the beam floats, three-two-one style restraint by two soft points).

Units: m, kN, kNm. Positive load = downward. Positive reaction = upward. Sagging moment positive.
"""
from __future__ import annotations
import numpy as np


def solve(L, EI, supports, w_segments=(), points=(), n=1200, springs=None, prescribed=None):
    """Return dict(x, M, V, defl, reactions).

    L          beam length (m)
    EI         flexural rigidity (kNm2); a float or a function EI(x)
    supports   x positions of rigid vertical supports (ignored where `prescribed` is given)
    w_segments iterable of (x0, x1, w) downward line loads kN/m
    points     iterable of (x, P) downward point loads kN
    springs    optional dict {x: k (kN/m)} elastic supports instead of rigid at those x
    prescribed optional dict {x: F (kN, upward)}: forces applied instead of supports (equalising rig).
               The beam is then held by two very soft springs at its ends; their reactions must be ~0
               when the prescribed forces balance the load (reported as 'unbalance').
    """
    xs = np.linspace(0.0, L, n + 1)
    # make sure every support / load position is a node
    extra = [s for s in supports] + [p[0] for p in points] + [a for seg in w_segments for a in seg[:2]]
    if springs: extra += list(springs)
    if prescribed: extra += list(prescribed)
    xs = np.unique(np.round(np.concatenate([xs, np.array(extra, float)]), 9))   # round first: 1.2 and 1.2000000000000002 must be one node
    xs.sort()
    nn = len(xs)
    K = np.zeros((2 * nn, 2 * nn)); F = np.zeros(2 * nn)
    ei = EI if callable(EI) else (lambda x: EI)
    for e in range(nn - 1):
        a, b = xs[e], xs[e + 1]; le = b - a
        if le <= 0: continue
        k = ei(0.5 * (a + b)) / le ** 3 * np.array([[12, 6 * le, -12, 6 * le], [6 * le, 4 * le * le, -6 * le, 2 * le * le],
                                                     [-12, -6 * le, 12, -6 * le], [6 * le, 2 * le * le, -6 * le, 4 * le * le]])
        dof = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        K[np.ix_(dof, dof)] += k
        # consistent nodal loads for the distributed load on this element (downward = negative v)
        w = sum(ws for (x0, x1, ws) in w_segments if x0 <= 0.5 * (a + b) <= x1)
        if w:
            F[dof] += -w * le / 2 * np.array([1, le / 6, 1, -le / 6])
    idx = lambda x: int(np.argmin(np.abs(xs - x)))
    for (x, P) in points:
        F[2 * idx(x)] += -P
    fixed = []
    spring_nodes = {}
    if prescribed:
        for x, f in prescribed.items():
            F[2 * idx(x)] += f
        ksoft = 1e-6 * (ei(L / 2) / L ** 3)
        spring_nodes = {idx(0.0): ksoft, idx(L): ksoft}
    else:
        for s in supports:
            if springs and s in springs: spring_nodes[idx(s)] = springs[s]
            else: fixed.append(2 * idx(s))
    for nd, ks in spring_nodes.items():
        K[2 * nd, 2 * nd] += ks
    free = [d for d in range(2 * nn) if d not in fixed]
    u = np.zeros(2 * nn)
    u[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
    R = K @ u - F
    reactions = {}
    if prescribed:
        reactions = dict(prescribed)
        unbalance = sum(spring_nodes[nd] * u[2 * nd] for nd in spring_nodes)
    else:
        for s in supports:
            nd = idx(s)
            reactions[s] = float(spring_nodes[nd] * -u[2 * nd]) if nd in spring_nodes else float(R[2 * nd])
        unbalance = 0.0
    # shear and moment by statics from the left (exact for the applied loads + reactions)
    V = np.zeros(nn); M = np.zeros(nn)
    up = {idx(s): r for s, r in reactions.items()}
    pt = {}
    for (x, P) in points: pt[idx(x)] = pt.get(idx(x), 0.0) + P
    v = 0.0; m = 0.0
    for i in range(nn):
        if i > 0:
            le = xs[i] - xs[i - 1]; xm = 0.5 * (xs[i] + xs[i - 1])
            w = sum(ws for (x0, x1, ws) in w_segments if x0 <= xm <= x1)
            m += v * le - w * le * le / 2
            v += -w * le
        M[i] = m                     # moment just at the node (before the node's point actions change the shear)
        v += up.get(i, 0.0) - pt.get(i, 0.0)
        V[i] = v                     # shear just right of the node
    return {"x": xs, "M": M, "V": V, "defl": -u[0::2], "reactions": reactions, "unbalance": float(unbalance),
            "total_load": float(sum(w * (x1 - x0) for (x0, x1, w) in w_segments) + sum(P for _, P in points))}


def summary(res, label=""):
    M, V, x = res["M"], res["V"], res["x"]
    i_s, i_h = int(np.argmax(M)), int(np.argmin(M))
    out = {"label": label, "M_sag": float(M[i_s]), "x_sag": float(x[i_s]), "M_hog": float(M[i_h]), "x_hog": float(x[i_h]),
           "V_max": float(np.max(np.abs(V))), "reactions": {round(k, 3): round(v, 3) for k, v in res["reactions"].items()},
           "sum_R": float(sum(res["reactions"].values())), "total_load": res["total_load"], "defl_max": float(np.max(np.abs(res["defl"])))}
    return out
