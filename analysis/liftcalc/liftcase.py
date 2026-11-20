"""Lift load cases, member checks and joint checks on a built frame model.

A lift case is: a set of lift points (nodes held vertically, or given sling forces), a gravity load case multiplied by
the lifting factors, and optional horizontal sling components. The model is solved by fea3d; then
  * every member is checked for axial force with bending in both planes (AS/NZS 4600 clause 3.5), and
  * every joint is checked: the force that passes through its fasteners against the fastener capacity.
Units: N, mm.
"""
from __future__ import annotations
import math
from collections import defaultdict
import numpy as np
from . import as4600 as C
from . import notch as NT
from .fea3d import Model

BEARING_TYPES = {"STUD", "KING STUD", "JAMB", "CRIPPLE", "POST"}
PLATE_TYPES = {"BOTTOM TRACK", "TOP TRACK", "HEADER", "SILL"}
GROUP_FACTOR = 0.90
SCREW_D = 4.87          # 10 gauge self-drilling screw, nominal diameter (mm)


# ------------------------------------------------------------------------------------------------ supports
def nearest_node(B, P, kinds=None, types=None, max_dist=None):
    """Model node nearest to point P, optionally restricted to nodes on members of given panel kinds / member types."""
    best = (1e18, None)
    P = np.array(P, float)
    for m in B.members.values():
        if kinds and m["kind"] not in kinds: continue
        if types and m["type"] not in types: continue
        for _, nd in (m.get("nodes") or []):
            d = float(np.linalg.norm(np.array(B.model.xyz[nd]) - P))
            if d < best[0]: best = (d, nd)
    if best[1] is None or (max_dist is not None and best[0] > max_dist):
        raise ValueError(f"no node within {max_dist} mm of {P.tolist()} (nearest {best[0]:.0f} mm)")
    return best[1], best[0]


def hold(model: Model, lift_nodes, mode="rigid", k_sling=None, forces=None):
    """Apply the lift supports to a COPY-free model (call on a fresh support state).
    mode 'rigid': every lift node held vertically; 'springs': vertical springs k_sling (N/mm);
    'forces': the given upward forces are applied as loads by the caller and the model only gets the anti-drift restraints.
    In every mode three horizontal restraints remove rigid-body drift (they carry ~0 under vertical loads)."""
    model.fixed.clear(); model.nspring = list(model.meta.get("permanent_springs", []))
    n = list(lift_nodes)
    if mode == "rigid":
        for nd in n: model.fix(nd, [2])
    elif mode == "springs":
        for nd in n: model.spring(nd, 2, k_sling)
    xyz = np.array([model.xyz[i] for i in n])
    a = int(np.argmin(xyz[:, 0] + xyz[:, 1])); b = int(np.argmax(xyz[:, 0] - xyz[:, 1])); c = int(np.argmax(xyz[:, 1] - xyz[:, 0]))
    model.fix(n[a], [0, 1]); model.fix(n[b], [1])
    if mode == "forces":
        # the applied sling forces must balance the weight; three vertical holds make the support statically determinate,
        # so their reactions are exactly the out-of-balance of the applied forces (reported, and must be ~0)
        for i in {a, b, c}:
            model.fix(n[i], [2])
        model.meta["force_holds"] = [n[i] for i in {a, b, c}]
    if hasattr(model, "K"): del model.K
    return n


# ------------------------------------------------------------------------------------------------ member checks
LINING_RESTRAINT = {             # out-of-plane restraint spacing (mm) that the FINISHED fabric would give. Used only when
    ("roof_truss", "TOP CHORD"): 900.0,       # lining=True (reported as a comparison); the design run takes no credit for it.
    ("roof_truss", "BOTTOM CHORD"): 600.0,
    ("floor_truss", "TOP CHORD"): 300.0,
    ("rim_truss", "TOP CHORD"): 300.0,
}
STRUCTURAL_TAGS = ("LINK", "ATTACH")


def _capacity_cache():
    cache = {}
    def get(t, steel, plies=1):
        key = (round(t, 3), steel.name)
        if key not in cache:
            cache[key] = C.LippedChannel(t, steel)
        return cache[key]
    return get


TWIST = {"mode": "joint"}       # 'joint': twist restrained at every joint (screws through both flanges); 'out': at L_out; 'cap': old 1200 mm cap
NOTCH = {"check": "dsm",        # 'dsm': notched section (no lips) for axial, bending and tension at element ends on a notch; 'old': axial only
         "credit": True,        # True: flange edges held by the nested member (and gusset plates where the joint has a gusset); False: no credit
         "gussets": set()}      # joint ids with a gusset pair (set by run_lift before the checks)
SERVICE_HOLE_D = 32.0           # mm, Framer service hole in the web (taken as a round 32 mm hole)


def member_lengths(m, lining=False, restraint=None):
    """(in-plane buckling length, out-of-plane buckling length, twist length).
    In plane: the largest gap between the member's own stations (joints and links).
    Out of plane: the largest gap between points where ANOTHER PANEL or an added part holds the member (inter-panel links
    and attachments) and its two ends. Sheeting, flooring and lining give no restraint unless lining=True."""
    st = m.get("nodes") or []
    s = [x[0] for x in st]
    if len(s) < 2:
        return m["L"], m["L"], m["L"]
    L_in = max(b - a for a, b in zip(s[:-1], s[1:]))
    held = sorted({s[0], s[-1]} | {x for x, tag in (m.get("tags") or []) if tag in STRUCTURAL_TAGS})
    L_out = max(b - a for a, b in zip(held[:-1], held[1:]))
    if lining and (m["kind"], m["type"]) in LINING_RESTRAINT:
        L_out = min(L_out, LINING_RESTRAINT[(m["kind"], m["type"])])
    key = f'{m["kind"]}|{m["type"]}'
    if restraint and key in restraint:                    # steel restraint lines (bridging) at a stated spacing
        L_out = min(L_out, float(restraint[key]))
    mode = TWIST["mode"]
    L_tw = L_in if mode == "joint" else (L_out if mode == "out" else max(L_in, min(L_out, 1200.0)))
    return L_in, L_out, L_tw


def check_members(B, res, steel=C.G450, lining=False, restraint=None):
    """Utilisation of every member for one solved case. Returns {member id: dict}."""
    get = _capacity_cache()
    F = res["end_forces"]
    out = {}
    for mid, m in B.members.items():
        els = m.get("elements") or []
        if not els or m.get("props") or m["t"] <= 0:
            continue
        sec = get(m["t"], steel)
        n = 2 if m.get("built_up") else m.get("plies", 1)
        L_in, L_out, L_tw = member_lengths(m, lining, restraint)
        ops = {o for o, _ in (m.get("ops") or [])}
        holed = "SERVICE HOLE" in ops
        An = sec.p.A - (SERVICE_HOLE_D * m["t"] if holed else 0.0)
        kh = An / sec.p.A                                            # a web hole: capacities scaled by the net area (conservative)
        phiNt = n * sec.tension_design(An=An)
        phiNc, det = sec.compression_design(L_out, L_in, L_tw)       # lex = major-axis (out-of-plane) length, ley = in-plane
        phiNc *= n * kh
        phiNn = n * kh * sec.notched_compression_design(det["fn"]) if "LIP NOTCH" in ops else None
        zones = NT.notch_zones(m) if ("LIP NOTCH" in ops and NOTCH["check"] == "dsm") else []
        phiVmaj = n * sec.shear_design_major(); phiVmin = n * sec.shear_design_minor()
        phiNs = n * C.PHI["compression"] * sec.compression_section_nominal()
        phiMx, _ = sec.moment_major_design(lb=L_in); phiMx *= n      # out-of-plane bending is about the major axis
        phiMy = n * min(sec.moment_minor_design("web")[0], sec.moment_minor_design("lips")[0])
        Nex = math.pi ** 2 * C.E * n * sec.p.Ix / L_out ** 2
        Ney = math.pi ** 2 * C.E * n * sec.p.Iy / L_in ** 2
        worst = dict(util=0.0)
        Nmax_t = 0.0; Nmax_c = 0.0
        for e in els:
            f = F[e]
            N = f[6]                                                 # tension positive
            for end in (0, 1):
                Min = abs(f[4 + 6 * end]); Mout = abs(f[5 + 6 * end])
                if N >= 0:
                    u = C.combined_tension_bending(N, Mout, Min, phiNt, phiMx, phiMy, phiMx, phiMy); mode = "tension + bending"
                else:
                    u = C.combined_compression_bending(-N, Mout, Min, phiNc, phiNs, phiMx, phiMy, Nex, Ney); mode = "compression + bending (" + det["governs"] + ", " + det["global_mode"] + ")"
                    if phiNn and not zones:                          # the section at a lip notch (truss panel points), axial only (old rule)
                        un = -N / phiNn + Mout / phiMx + Min / phiMy
                        if un > u: u, mode = un, "lip-notch section, compression + bending"
                if zones:                                            # at a notch: the lipless section for every term, in compression and tension
                    el = B.elements[e]; s_end = el["s1"] if end else el["s0"]
                    for z0, z1, a_n in zones:
                        if z0 - 10.0 <= s_end <= z1 + 10.0:
                            fn_ = round(min(det["fn"], sec.steel.fy), 1)
                            gus = NOTCH["credit"] and any(z0 - 10.0 <= p_ <= z1 + 10.0 and j_ in NOTCH["gussets"] for p_, j_ in (m.get("joints") or []))
                            if gus:                                  # the gusset plates cover this section: it is the composite section, not the bare chord
                                cp = NT.gusseted_capacities(round(m["t"], 3), sec.steel.fy, fn_); tag_ = "gusseted lip-notch section"
                                u = 0.0
                            else:
                                cp = NT.notched_capacities(round(m["t"], 3), sec.steel.fy, round(a_n, 0), fn_, bool(NOTCH["credit"]))
                                tag_ = "lip-notch section" + ("" if NOTCH["credit"] else " (no edge credit)")
                                cp = dict(cp, phiNc=min(cp["phiNc"], phiNc / max(n * kh, 1e-9), sec.notched_compression_design(det["fn"])),
                                          phiMx=min(cp["phiMx"], phiMx / n), phiMy=min(cp["phiMy"], phiMy / n), phiNt=min(cp["phiNt"], phiNt / n))
                            k_ = n * kh
                            if N < 0:
                                un = -N / (k_ * cp["phiNc"]) + Mout / (k_ * cp["phiMx"]) + Min / (k_ * cp["phiMy"])
                            else:
                                un = N / (k_ * cp["phiNt"]) + Mout / (k_ * cp["phiMx"]) + Min / (k_ * cp["phiMy"])
                            if un > u: u, mode = un, f"{tag_} (a {a_n:.0f} mm), {'compression' if N < 0 else 'tension'} + bending"
                            break
                Vmaj = abs(f[1 + 6 * end]); Vmin = abs(f[2 + 6 * end])     # shear, and bending with shear (clause 3.3.5)
                uv = max(math.hypot(Mout / phiMx, Vmaj / phiVmaj), math.hypot(Min / phiMy, Vmin / phiVmin))
                if uv > u: u, mode = uv, "bending + shear"
                if u > worst["util"]:
                    worst = dict(util=float(u), N=float(N), M_in=float(Min), M_out=float(Mout), mode=mode + (" (web hole)" if holed else ""), element=e)
            Nmax_t = max(Nmax_t, N); Nmax_c = min(Nmax_c, N)
        worst.update(N_tension_max=float(Nmax_t), N_compression_max=float(Nmax_c), phiNt=phiNt, phiNc=phiNc, phiMx=phiMx, phiMy=phiMy,
                     L_in=L_in, L_out=L_out, plies=n, t=m["t"])
        out[mid] = worst
    return out


# ------------------------------------------------------------------------------------------------ joint checks
SCREW_SHEAR_BREAKING = 5700.0   # N, lowest published characteristic shear of a 10 gauge self-drilling screw (design value 0.5 x 5.7 = 2.85 kN)


def screw_capacity(t1, t2, steel):
    return C.screw_shear_design(t1, steel.fu, t2, steel.fu, SCREW_D, screw_shear_breaking=SCREW_SHEAR_BREAKING)


def check_joints(B, res, steel=C.G450, bearing_ok=True, extra_fasteners=None):
    """Force through each in-panel joint against the capacity of its fasteners.
    The demand is the end force of every member that ENDS at the joint (axial and both shears). When `bearing_ok`, the
    compression of a member that butts square onto the member it joins is taken in bearing and not through the screws."""
    F = res["end_forces"]
    M = B.model
    extra = extra_fasteners or {}
    end_at = defaultdict(list)                       # node -> [(member id, element, end)]
    for mid, m in B.members.items():
        els = m.get("elements") or []
        if not els: continue
        e0, e1 = els[0], els[-1]
        end_at[M.el[e0]["i"]].append((mid, e0, 0)); end_at[M.el[e1]["j"]].append((mid, e1, 1))
    out = {}
    for jid, j in B.joints.items():
        nd = j["node"]; mids = j["members"]
        if len(mids) < 2: continue
        ts = [B.members[x]["t"] for x in mids]
        n_fr = j["fasteners"]; n_ex = max(0, extra.get(jid, 0)); nf = n_fr + n_ex
        c1 = screw_capacity(min(ts), min(ts), steel); gf = GROUP_FACTOR if nf >= 3 else 1.0
        demand = 0.0; who = None; cap = 0.0
        for (mid, e, end) in end_at.get(nd, []):
            if mid not in mids: continue
            f = F[e]
            N = f[6]                                 # tension positive (same sign at both ends of an element without span load)
            Vy, Vz = f[1 + 6 * end], f[2 + 6 * end]
            other = [x for x in mids if x != mid]
            mm_ = B.members[mid]
            # bearing credit ONLY for a wall stud standing square on a wall plate (its cut end seats on the plate web);
            # truss webs and every other member end pass their full force through the screws
            square = (other and mm_["kind"] == "wall" and mm_["type"] in BEARING_TYPES and B.members[other[0]]["type"] in PLATE_TYPES
                      and abs(float(np.dot(mm_["dir"], B.members[other[0]]["dir"]))) < 0.09)
            Nj = 0.0 if (bearing_ok and N < 0 and square) else abs(N)
            d = math.sqrt(Nj ** 2 + Vy ** 2 + Vz ** 2)
            # Framer's screws sit at the dimple, e from the member end: end rupture may govern (lower of 0.5 t e fu and
            # 0.6 t (e - d/2) fu); the extra screws of this design are placed at least 15 mm from the end (full capacity)
            e = (j.get("edist") or {}).get(mid, 99.0)
            er = min(0.5 * min(ts) * e * steel.fu, 0.6 * min(ts) * max(e - SCREW_D / 2.0, 0.0) * steel.fu)
            cap_m = (n_fr * min(c1, er) + n_ex * c1) * gf
            if cap == 0.0 or d / max(cap_m, 1e-9) > demand / max(cap, 1e-9):
                demand, who, cap = d, mid, cap_m
        if cap == 0.0:
            cap = nf * c1 * gf
        out[jid] = dict(node=nd, demand=float(demand), capacity=float(cap), util=float(demand / cap) if cap > 0 else float("inf"),
                        fasteners=nf, member=who, validated=j["validated"], panel=j["panel"])
    return out


def check_links(B, res, steel=C.G450, screws_per_link=2, t=0.95, screws_by_rule=None):
    """Inter-panel links: shear through the screws (compression goes in bearing). Tension across a link would rely on screw
    pull-out, which the design basis does not allow on the lift path: `needs_tie` marks every link whose tension exceeds 10 %
    of the pull-out value, and those need a positive tie (strap or bracket in shear) in the design."""
    F = res["end_forces"]
    one_v = screw_capacity(t, t, steel); one_t = C.screw_pullout_design(t, steel.fu, SCREW_D)
    out = []
    for lk in B.links:
        n_s = (screws_by_rule or {}).get(lk["rule"], screws_per_link)
        gf = GROUP_FACTOR if n_s >= 3 else 1.0
        v_cap = n_s * one_v * gf; t_cap = n_s * one_t * gf
        f = F[lk["element"]]
        N = f[6]; V = math.hypot(f[7], f[8])
        if lk.get("diag"):                      # a truss-end reaction tie: its axial force is a shear on the screws
            V = abs(N); N = 0.0
        ut = (N / t_cap) if N > 0 else 0.0
        uv = V / v_cap
        out.append(dict(rule=lk["rule"], a=lk["a"], b=lk["b"], N=float(N), V=float(V), util=float(max(uv, ut, math.hypot(uv, ut))),
                        util_shear=float(uv), util_tension=float(ut), needs_tie=bool(ut > 0.10), na=lk["na"], nb=lk["nb"]))
    return out


# ------------------------------------------------------------------------------------------------ summary helpers
def reactions(res, lift_nodes):
    return [float(res["reactions"].get(nd, [0, 0, 0])[2]) for nd in lift_nodes]


def total_vertical_load(model: Model, case):
    return -sum(v for (nd, d), v in model.loads[case].items() if d == 2)


def added_forces(B, res):
    """Largest tension, compression and end shear in every added (non-Framer) member for one solved case."""
    F = res["end_forces"]; out = {}
    for mid, m in B.members.items():
        if not m.get("added") or not m.get("elements"): continue
        N = [F[e][6] for e in m["elements"]]
        V = [max(math.hypot(F[e][1], F[e][2]), math.hypot(F[e][7], F[e][8])) for e in m["elements"]]
        Mm = [max(abs(F[e][4]), abs(F[e][5]), abs(F[e][10]), abs(F[e][11])) for e in m["elements"]]
        out[mid] = dict(N_max=float(max(N)), N_min=float(min(N)), V=float(max(V)), M=float(max(Mm)), type=m["type"], role=m.get("role", ""))
    return out
