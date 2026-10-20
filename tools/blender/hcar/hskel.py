"""Hellcat physics skeleton (P2): nodes, beams, collision / pressure triangles, break groups, torsion
bars, wheels, camera mounts and part -> visual links, written as sim/vehicle/hellcat/geometry.json
(format hellcat-softbody v1, tools/blender/hcar/sk.py) for the Unity solver.

Layout (BeamNG-style, see docs/P2_report.md):
- a load-carrying cage of few heavy nodes: sills, floor and tunnel, hinge pillars, cowl, firewall,
  dash bar, A/B/C pillars and roof rails (triangular sections), roof bows, front rails with crush
  cans and a bumper beam, core support, aprons and strut towers, rear rails, wheel houses, rear
  panel, rear bumper beam, parcel shelf;
- panels sampled from the visual panel grids (doors, fenders, quarters, roof, hood, deck lid,
  fascia, rear bumper, glass): welded, bolted, clipped or hinged to the cage; closures are double
  layers (outer skin + inner frame) with 3-beam pins at each hinge and latch beams;
- chassis: engine, gearbox, shafts, differential, rear subframe, SLA front suspension with a
  rack (HYDRO-driven rack ends + tie rods), 5-link rear, coil springs, dampers, bump stops,
  anti-roll bars (torsion bars), wheels (rim rings + 24-section pressurized tire), exhaust, tank,
  battery, radiator, seats, steering column.

Run in Blender (with the debug view): call hcar.hskel:main ; plain python: hskel.build()
"""
import itertools
import math
import os

import numpy as np

from . import PROJECT_ROOT
from . import hskel_tables as T
from . import sk as S

OUT_SIM = os.path.join(PROJECT_ROOT, "sim", "vehicle", "hellcat", "geometry.json")
OUT_UNITY = os.path.join(PROJECT_ROOT, "Unity", "HellcatSandbox", "Assets", "StreamingAssets", "Vehicles", "hellcat",
                         "geometry.json")
F_TIRE = S.DEFAULT_FLAGS | S.TIRE
F_NOCOL = 0                                        # internal nodes: no collision
# small detachable assemblies (headlamps, mirrors, radiator) also collide with the car's other parts (D-058): torn off,
# they went through the body and landed behind the car; no other part's triangle lies within 5 cm of them at rest
F_DETACH = S.DEFAULT_FLAGS | S.SELF_COLLISION
HINGE_MIN_ASPECT = 0.25                            # no shell hinge where a wing triangle is flatter than this (h / |e|)


class Build:
    """Skeleton under construction: nodes carry a mass group and a weight; masses are assigned at the end."""

    def __init__(self):
        self.sk = S.Skeleton("hellcat")
        self.mgroup, self.weight = {}, {}
        self.cage = []                     # indices of load-carrying body nodes (weld / bolt targets)
        self.tags = {}                     # name -> node index for lookups

    # ---- nodes and beams
    def node(self, name, p, group, part, cmat="body", flags=S.DEFAULT_FLAGS, w=1.0, cage=False):
        i = self.sk.node(name, [float(v) for v in p], 1.0, flags=flags, cmat=cmat, group=part, part=part)
        self.mgroup[i], self.weight[i] = group, w
        self.tags[name] = i
        if cage:
            self.cage.append(i)
        return i

    def pair(self, name, p, group, part, side_parts=False, **kw):
        """Right and left node (x mirrored). Returns (R, L)."""
        x, y, z = p
        gr = group.format(s="R") if "{s}" in group else group
        gl = group.format(s="L") if "{s}" in group else group
        pr = part.format(s="R") if side_parts else part
        pl = part.format(s="L") if side_parts else part
        return (self.node(f"{name}_R", (x, y, z), gr, pr, **kw), self.node(f"{name}_L", (-x, y, z), gl, pl, **kw))

    def beam(self, a, b, mat, **kw):
        return self.sk.beam(a, b, mat, **kw)

    def P(self, i):
        return np.array(self.sk.nodes[i]["p"])

    def nearest(self, p, pool, k=1, max_d=9.0, exclude=(), min_d=0.0):
        """k nearest pool nodes within max_d; min_d skips nodes closer than that (a beam of a few mm
        across a shut line flips direction as soon as its nodes cross)."""
        pool = [i for i in pool if i not in exclude]
        d = [(float(np.linalg.norm(self.P(i) - p)), i) for i in pool]
        d = sorted(x for x in d if x[0] >= min_d)
        return [i for dd, i in d[:k] if dd <= max_d]

    def chain(self, ids, mat, **kw):
        for a, b in zip(ids[:-1], ids[1:]):
            self.beam(a, b, mat, **kw)

    def brace(self, A, B, mat_long, mat_diag, full=False):
        """Connect two node sections (equal length lists, closed loops) with longitudinal beams and
        one face diagonal per face (alternating), or both diagonals (full)."""
        n = len(A)
        for k in range(n):
            self.beam(A[k], B[k], mat_long)
            k1 = (k + 1) % n
            if n == 2 and k == 1:
                break
            if full or k % 2 == 0:
                self.beam(A[k], B[k1], mat_diag)
            if full or k % 2 == 1:
                self.beam(A[k1], B[k], mat_diag)

    def section(self, ids, mat, diag=True):
        """Close a section loop (and its diagonals for 4-node sections)."""
        n = len(ids)
        for k in range(n):
            self.beam(ids[k], ids[(k + 1) % n], mat)
        if diag and n == 4:
            self.beam(ids[0], ids[2], mat)
            self.beam(ids[1], ids[3], mat)

    def pin(self, a, targets, mat, bg="", bgt=0):
        """Pin node a to 3 (non-collinear) target nodes: a ball joint."""
        for t in targets[:3]:
            self.beam(a, t, mat, bg=bg, bgt=bgt)

    def anchor(self, a, pool, mat, k=3, max_d=0.6, min_d=0.03, bg="", bgt=0, exclude=()):
        """Tie node a to the nearest pool nodes whose directions span 3D (no collinear pair, no coplanar
        triple): a node held by three non-coplanar beams has no mechanism (P3 finding, D-030)."""
        pa = self.P(a)
        cand = []
        for i in pool:
            if i == a or i in exclude:
                continue
            d = self.P(i) - pa
            L = float(np.linalg.norm(d))
            if min_d <= L <= max_d:
                cand.append((L, i, d / L))
        cand.sort(key=lambda c: c[0])
        chosen = []
        for L, i, u in cand:
            if not chosen:
                chosen.append((i, u))
            elif len(chosen) == 1:
                if abs(float(np.dot(u, chosen[0][1]))) < 0.9:
                    chosen.append((i, u))
            else:
                n = np.cross(chosen[0][1], chosen[1][1])
                n /= np.linalg.norm(n)
                if abs(float(np.dot(u, n))) > 0.35:
                    chosen.append((i, u))
            if len(chosen) >= k:
                break
        for i, _ in chosen:
            self.beam(a, i, mat, bg=bg, bgt=bgt)
        return [i for i, _ in chosen]

    def joint(self, a, pool, mat, bg="", bgt=0, **kw):
        """Hold node a with 3 beams to the pool nodes of joint_targets: a closure hinge (D-063)."""
        ids = self.joint_targets(a, pool, **kw)
        for i in ids:
            self.beam(a, i, mat, bg=bg, bgt=bgt)
        return ids

    def joint_targets(self, a, pool, max_d=0.45, min_d=0.08, ncand=16):
        """Three pool nodes whose directions from node a span 3D as evenly as possible (D-063): of the triples among the
        ncand nearest candidates, the one with the largest smallest singular value of its beam directions, shorter
        beams preferred. Pins to three targets in one row (the hinge pillar, the core support's top bar, the rear
        panel's top) left the node free across their plane: the door hinges along the car, the door latches
        outward-forward (the rear edge of a door swung out in a frontal crash), the hood latch upward (P4)."""
        pa = self.P(a)
        cand = []
        for i in dict.fromkeys(pool):
            if i == a:
                continue
            d = self.P(i) - pa
            L = float(np.linalg.norm(d))
            if min_d <= L <= max_d:
                cand.append((L, i, d / L))
        cand.sort(key=lambda c: (c[0], c[1]))
        cand = cand[:ncand]
        best, score = None, -1.0
        for tri in itertools.combinations(range(len(cand)), 3):
            sv = float(np.linalg.svd(np.array([cand[k][2] for k in tri]), compute_uv=False)[-1])
            s = sv / (1.0 + sum(cand[k][0] for k in tri) / (3.0 * max_d))
            if s > score + 1e-9:
                best, score = tri, s
        if best is None:
            raise ValueError(f"joint: fewer than 3 candidates within {max_d} m of {self.sk.nodes[a]['name']}")
        return [cand[k][1] for k in best]

    def support_surface(self, ids, mat, k=2, max_d=0.45, bg="", bgt=0, min_cos=0.35, pool=None):
        """Out-of-plane support of a single-layer panel grid: each node gets up to k beams to cage nodes
        behind it (within ~70 deg of its inward normal, nearest and steepest first). Without them a flat
        beam grid has no stiffness across its plane (modes below 1 Hz, sag under gravity). pool: candidate
        nodes (default: the whole cage)."""
        G = np.array([[self.P(q) for q in row] for row in ids])
        du = np.gradient(G, axis=0)
        dv = np.gradient(G, axis=1)
        N = np.cross(du, dv)
        N /= np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-12)
        pool = list(self.cage) if pool is None else list(pool)
        cage = np.array([self.P(c) for c in pool])
        added = 0
        for i in range(ids.shape[0]):
            for j in range(ids.shape[1]):
                a = ids[i, j]
                p = G[i, j]
                n = N[i, j]
                if np.dot(n, inside_point(p) - p) < 0:
                    n = -n
                d = cage - p
                L = np.linalg.norm(d, axis=1)
                ok = (L > 0.03) & (L < max_d)
                cosv = np.where(ok, np.sum(d * n, axis=1) / np.maximum(L, 1e-9), -1.0)
                order = [c for c in np.argsort(L / np.maximum(cosv, 1e-3)) if cosv[c] >= min_cos]
                picked = []
                for c in order:
                    u = d[c] / L[c]
                    if all(abs(float(np.dot(u, d[q] / L[q]))) < 0.94 for q in picked):
                        picked.append(c)
                    if len(picked) >= k:
                        break
                for c in picked:
                    if pool[c] != a:
                        self.beam(a, pool[c], mat, bg=bg, bgt=bgt)
                        added += 1
        return added

    def mount(self, a, mat="subframe_mount", k=3, max_d=0.45, bg="", bgt=0):
        """Stiffen a body-side pick-up (suspension pivot, rack end, bar axis): k extra beams to the nearest structural
        nodes with diverse directions. The pick-ups sat on 2-3 beams, so the knuckles wound up fore-aft at 3 kN m/rad
        (a real corner is 50-300) and the parked car rocked on its wheels at ~0.9 Hz (D-035)."""
        pool = [i for i in self.cage if i != a]
        return self.anchor(a, pool, mat, k=k, max_d=max_d, min_d=0.03, bg=bg, bgt=bgt)

    def stops(self, nodes, pool, mat="stop", max_d=0.30, min_cos=0.5, inward=None):
        """Rubber stops (compression-only SUPPORT beams) under the perimeter of a closure: each node to the pool
        node most nearly straight below it along `inward` (unit vector, default -z), nearest first."""
        inward = np.array([0.0, 0.0, -1.0]) if inward is None else np.asarray(inward, float)
        n = 0
        for a in nodes:
            pa = self.P(a)
            best = None
            for c in pool:
                d = self.P(c) - pa
                L = float(np.linalg.norm(d))
                if L < 0.02 or L > max_d:
                    continue
                cs = float(np.dot(d, inward)) / L
                if cs >= min_cos and (best is None or L / cs < best[0]):
                    best = (L / cs, c)
            if best is not None:
                self.beam(a, best[1], mat, type="SUPPORT")
                n += 1
        return n

    # ---- grids
    def grid(self, name, G, group, part, cmat, flags=S.DEFAULT_FLAGS, w=1.0):
        ni, nj = G.shape[:2]
        ids = np.zeros((ni, nj), int)
        for i in range(ni):
            for j in range(nj):
                ids[i, j] = self.node(f"{name}_{i}_{j}", G[i, j], group, part, cmat=cmat, flags=flags, w=w)
        return ids

    def grid_beams(self, ids, mat, mat_diag, skip=True, bg=""):
        ni, nj = ids.shape
        for i in range(ni):
            for j in range(nj):
                if i + 1 < ni:
                    self.beam(ids[i, j], ids[i + 1, j], mat, bg=bg, bgt=1)
                if j + 1 < nj:
                    self.beam(ids[i, j], ids[i, j + 1], mat, bg=bg, bgt=1)
                if i + 1 < ni and j + 1 < nj:
                    self.beam(ids[i, j], ids[i + 1, j + 1], mat_diag, bg=bg, bgt=1)
                    self.beam(ids[i + 1, j], ids[i, j + 1], mat_diag, bg=bg, bgt=1)
                if skip and i + 2 < ni:
                    self.beam(ids[i, j], ids[i + 2, j], mat_diag, bg=bg, bgt=1)
                if skip and j + 2 < nj:
                    self.beam(ids[i, j], ids[i, j + 2], mat_diag, bg=bg, bgt=1)

    def grid_tris(self, ids, group, centre_fn, bg="", ttype="COLLIDE", hinge=""):
        """Two triangles per cell with one winding for the whole grid (a grid is one continuous surface, so a
        per-cell choice flips cells where the panel wraps round, e.g. fender lips at the wheel arch). Outward
        is the side the area-weighted majority of cells faces away from centre_fn(cell centre). hinge: shell
        bending material for the grid's interior edges (D-032)."""
        t0 = len(self.sk.tris)
        self._grid_tris(ids, group, centre_fn, bg, ttype)
        if hinge:
            self.hinge_tris(self.sk.tris[t0:], hinge)

    def hinge_tris(self, tris, mat):
        """Shell bending hinges on every edge shared by exactly two of the given triangles (D-032): a single-layer
        panel grid has no bending stiffness of its own, so flat panels sagged into a hanging net under gravity."""
        edges = {}
        for t in tris:
            v = (t["a"], t["b"], t["c"])
            for k in range(3):
                a, b, c = v[k], v[(k + 1) % 3], v[(k + 2) % 3]
                edges.setdefault((min(a, b), max(a, b)), []).append(c)
        n = 0
        for (a, b), opp in sorted(edges.items()):
            if len(opp) == 2 and opp[0] != opp[1]:
                pa, pb = self.P(a), self.P(b)
                ev = pb - pa
                e = float(np.linalg.norm(ev))
                hw = min(float(np.linalg.norm(np.cross(ev, self.P(o) - pa))) / max(e, 1e-9) for o in opp)
                tw = [float(np.dot(self.P(o) - pa, ev)) / max(e * e, 1e-12) for o in opp]
                # sliver or very obtuse cells (grid rows squeezed at the wheel arches): the dihedral gradient of the
                # edge nodes grows with the wing's lever along the edge, so such a hinge is far stiffer than useful
                if hw < HINGE_MIN_ASPECT * e or min(tw) < -0.5 or max(tw) > 1.5:
                    continue
                self.sk.hinge(opp[0], a, b, opp[1], mat)
                n += 1
        return n

    def _grid_tris(self, ids, group, centre_fn, bg="", ttype="COLLIDE"):
        ni, nj = ids.shape
        cells, score = [], 0.0
        for i in range(ni - 1):
            for j in range(nj - 1):
                a, b, c, d = ids[i, j], ids[i + 1, j], ids[i + 1, j + 1], ids[i, j + 1]
                pa, pb, pc, pd = self.P(a), self.P(b), self.P(c), self.P(d)
                cen = (pa + pb + pc + pd) / 4
                out = cen - centre_fn(cen)
                score += np.dot(np.cross(pc - pa, pd - pb), out / (np.linalg.norm(out) + 1e-12))
                cells.append((a, b, c, d))
        for a, b, c, d in cells:
            if score >= 0:
                self.sk.tri(a, b, c, type=ttype, group=group, bg=bg)
                self.sk.tri(a, c, d, type=ttype, group=group, bg=bg)
            else:
                self.sk.tri(a, c, b, type=ttype, group=group, bg=bg)
                self.sk.tri(a, d, c, type=ttype, group=group, bg=bg)


def inside_point(p):
    """A point inside the body for outward-winding tests (on the car's axis, at mid height)."""
    return np.array([0.0, float(np.clip(p[1], -1.9, 1.7)), 0.62])


def samp(P, ni, nj, i0=0.0, i1=1.0, j0=0.0, j1=1.0):
    nu, nv = P.shape[:2]
    ii = np.round(np.linspace(i0 * (nu - 1), i1 * (nu - 1), ni)).astype(int)
    jj = np.round(np.linspace(j0 * (nv - 1), j1 * (nv - 1), nj)).astype(int)
    return P[ii][:, jj]


def full_from_half(G):
    """Centre panel: G (n_half, nj, 3) with column 0 on the centreline -> full grid (2 n_half - 1, nj, 3)."""
    L = G[1:][::-1].copy()
    L[..., 0] *= -1
    out = np.concatenate([L, G], axis=0)
    out[len(G) - 1, :, 0] = 0.0
    return out


def visual_grids():
    from .body import model
    from .body_panels import bumper_panels, side_panels
    from .gh_panels import cap_panels, glass_patch, greenhouse_panels
    m = model()
    out = {}
    for d in (side_panels(m), bumper_panels(m), greenhouse_panels(m), cap_panels(m)):
        for k, p in d.items():
            out[k] = p.mesh()["P"]
    out["glass_front"] = glass_patch(m, "front")
    out["glass_rear"] = glass_patch(m, "rear")
    return out


def offset_in(G, d):
    """Offset a grid (ni, nj, 3) by d towards the inside of the car (along its numeric normal)."""
    du = np.gradient(G, axis=0)
    dv = np.gradient(G, axis=1)
    N = np.cross(du, dv)
    N /= np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-12)
    ref = np.array([[inside_point(p) for p in row] for row in G])
    sgn = np.sign(np.sum(N * (ref - G), axis=-1, keepdims=True))
    sgn[sgn == 0] = 1.0
    return G + sgn * N * d


# =================================================================================================
# body cage
# =================================================================================================
def build_cage(B, V):
    sides = ("R", "L")
    st = {}
    # ---- sills (4-node box per cabin station) and floor
    sill = {s: [] for s in sides}
    floor = {s: [] for s in sides}
    tunnel = []
    from .mechanics import floor_z
    for k, y in enumerate(T.CABIN_Y):
        zf = float(floor_z(T.FLOOR_X, y))
        for si, sx in ((0, 1), (1, -1)):
            s = sides[si]
            ids = [B.node(f"sill{k}_{n}_{s}", (sx * x, y, z), "cell", "body", w=1.6, cage=True)
                   for n, (x, z) in enumerate(((T.SILL["x_out"], T.SILL["z_lo"]), (T.SILL["x_in"], T.SILL["z_lo"]),
                                               (T.SILL["x_in"], T.SILL["z_hi"]), (T.SILL["x_out"], T.SILL["z_hi"])))]
            sill[s].append(ids)
            floor[s].append(B.node(f"floor{k}_{s}", (sx * T.FLOOR_X, y, zf + 0.004), "cell", "body", w=1.7, cage=True))
        tunnel.append(B.node(f"tunnel{k}", (0.0, y, float(floor_z(0.0, y)) + 0.01), "cell", "body", w=1.7, cage=True))
    for s in sides:
        for k in range(len(T.CABIN_Y)):
            B.section(sill[s][k], "cell_brace")
            if k + 1 < len(T.CABIN_Y):
                B.brace(sill[s][k], sill[s][k + 1], "cell", "cell_brace")
                B.beam(floor[s][k], floor[s][k + 1], "floor")
                B.beam(floor[s][k], sill[s][k + 1][1], "floor_brace")
                B.beam(floor[s][k + 1], tunnel[k], "floor_brace")
            B.beam(floor[s][k], sill[s][k][1], "floor")
            B.beam(floor[s][k], sill[s][k][2], "floor_brace")
            B.beam(floor[s][k], tunnel[k], "floor")
    B.chain(tunnel, "floor")
    st["sill"], st["floor"], st["tunnel"] = sill, floor, tunnel
    # ---- roof rail / pillar line from the visual pillar strip (C base -> roof -> A base)
    Pil = V["CH_Pillars"]
    mid = Pil[:, Pil.shape[1] // 2]
    ys_rail = T.RAIL_Y
    rail = {s: [] for s in sides}
    for k, yt in enumerate(ys_rail):
        i = int(np.argmin(np.abs(mid[:, 1] - yt)))
        p = mid[i].copy()
        # tangent of the strip and its inward direction (towards the car's axis, horizontally)
        t = mid[min(i + 1, len(mid) - 1)] - mid[max(i - 1, 0)]
        t /= np.linalg.norm(t)
        inward = np.array([-1.0, 0.0, 0.0])
        down = np.cross(t, inward)
        if down[2] > 0:
            down = -down
        pts = [p + inward * 0.015 + down * 0.012, p + inward * 0.075 + down * 0.020, p + inward * 0.030 + down * 0.070]
        for si, sx in ((0, 1), (1, -1)):
            s = sides[si]
            ids = [B.node(f"rail{k}_{n}_{s}", q * [sx, 1, 1], "cell", "body", w=(2.2 if yt < -1.0 else 1.3), cage=True)
                   for n, q in enumerate(pts)]
            rail[s].append(ids)
    for s in sides:
        for k in range(len(ys_rail)):
            B.section(rail[s][k], "pillar", diag=False)
            if k + 1 < len(ys_rail):
                B.brace(rail[s][k], rail[s][k + 1], "pillar", "pillar_brace", full=True)
    st["rail"] = rail
    rk = {y: k for k, y in enumerate(ys_rail)}
    # ---- hinge pillars (A lower), cowl, firewall, dash bar
    hinge = {s: [] for s in sides}
    for n, p in enumerate(T.A_HINGE):
        r, l = B.pair(f"hinge{n}", p, "cell", "body", w=1.8, cage=True)
        hinge["R"].append(r)
        hinge["L"].append(l)
    for si, s in enumerate(sides):
        h = hinge[s]
        B.chain(h, "cell")
        S0, S1 = sill[s][0], sill[s][1]          # hinge pillar (y 0.80) between sill stations 0.92 and 0.66
        B.beam(h[0], S0[0], "cell")
        B.beam(h[0], S0[3], "cell")
        B.beam(h[0], S0[2], "cell_brace")
        B.beam(h[0], S1[0], "cell")
        B.beam(h[0], S1[3], "cell")
        B.beam(h[0], S1[2], "cell_brace")
        B.beam(h[1], S0[3], "cell_brace")
        B.beam(h[1], S1[3], "cell_brace")
        B.beam(h[1], S0[2], "cell_brace")
        a0 = rail[s][0]
        for q in a0:
            B.beam(h[2], q, "cell")
        B.beam(h[1], a0[1], "cell_brace")
        B.beam(h[1], a0[2], "cell_brace")
        B.beam(h[2], sill[s][1][3], "cell_brace")
    cowl = []
    for x in T.COWL["x"]:
        if x == 0:
            cowl.append(B.node("cowl_C", (0.0, T.COWL["y"], T.COWL["z"]), "cell", "body", w=1.8, cage=True))
        else:
            cowl.extend(B.pair(f"cowl{int(x * 100)}", (x, T.COWL["y"], T.COWL["z"]), "cell", "body", w=1.8, cage=True))
    cR, cL = [cowl[0], cowl[1], cowl[3]], [cowl[0], cowl[2], cowl[4]]      # centre, inner, outer per side
    fw = {}
    for z in T.FIREWALL["z"]:
        fw[("C", z)] = B.node(f"fw_C_{int(z * 100)}", (0.0, T.FIREWALL["y"], z), "cell", "body", w=1.8, cage=True)
        fw[("R", z)], fw[("L", z)] = B.pair(f"fw_{int(z * 100)}", (0.38, T.FIREWALL["y"], z), "cell", "body", w=1.8,
                                            cage=True)
    for s, cc in (("R", cR), ("L", cL)):
        B.chain([cc[0], cc[1], cc[2]], "cell")
        B.beam(cc[2], rail[s][0][0], "cell")
        B.beam(cc[2], rail[s][0][1], "cell_brace")
        B.beam(cc[2], hinge[s][2], "cell")
        B.beam(cc[1], rail[s][0][1], "cell_brace")
        lo, hi = fw[(s, T.FIREWALL["z"][0])], fw[(s, T.FIREWALL["z"][1])]
        B.beam(lo, hi, "cell")
        B.beam(hi, cc[1], "cell")
        B.beam(hi, cc[0], "cell_brace")
        B.beam(hi, cc[2], "cell_brace")
        B.beam(lo, floor[s][0], "cell")
        B.beam(lo, sill[s][0][1], "cell_brace")
        B.beam(hi, hinge[s][1], "cell_brace")
        B.beam(lo, hinge[s][0], "cell_brace")
        B.beam(lo, fw[("C", T.FIREWALL["z"][0])], "cell")
        B.beam(hi, fw[("C", T.FIREWALL["z"][1])], "cell")
        B.beam(lo, fw[("C", T.FIREWALL["z"][1])], "cell_brace")
    B.beam(fw[("C", T.FIREWALL["z"][0])], fw[("C", T.FIREWALL["z"][1])], "cell")
    B.beam(fw[("C", T.FIREWALL["z"][0])], tunnel[0], "cell")
    B.beam(fw[("C", T.FIREWALL["z"][1])], cowl[0], "cell")
    st["hinge"], st["cowl"], st["fw"] = hinge, cowl, fw
    dash = [B.node("dash_C", (0.0, T.DASH_BAR["y"], T.DASH_BAR["z"]), "dash", "body", flags=F_NOCOL)]
    for x in T.DASH_BAR["x"][1:]:
        dash.extend(B.pair(f"dash{int(x * 100)}", (x, T.DASH_BAR["y"], T.DASH_BAR["z"]), "dash", "body", flags=F_NOCOL))
    for s, d in (("R", [dash[0], dash[1], dash[3]]), ("L", [dash[0], dash[2], dash[4]])):
        B.chain(d, "dash")
        B.beam(d[2], hinge[s][1], "dash")
        B.beam(d[2], hinge[s][2], "dash")
        B.beam(d[1], cowl[1 if s == "R" else 2], "dash")
        B.beam(d[1], fw[(s, T.FIREWALL["z"][1])], "dash")
        B.beam(d[2], cowl[3 if s == "R" else 4], "dash")
    B.beam(dash[0], tunnel[1], "dash")
    B.beam(dash[0], cowl[0], "dash")
    B.beam(dash[0], fw[("C", T.FIREWALL["z"][1])], "dash")
    st["dash"] = dash
    # ---- B and C pillars (two nodes per level, fore / aft)
    for s, sx in (("R", 1), ("L", -1)):
        kb = T.CABIN_Y.index(T.B_PILLAR_Y)
        kc = T.CABIN_Y.index(T.C_PILLAR_Y)
        for (py, levels, kk, ry, tag) in ((T.B_PILLAR_Y, T.B_PILLAR, kb, -0.60, "bp"), (T.C_PILLAR_Y, T.C_PILLAR, kc, -1.06, "cp")):
            col = []
            for n, (x, z) in enumerate(levels[1:], 1):
                col.append((B.node(f"{tag}{n}f_{s}", (sx * x, py + 0.04, z), "cell", "body", w=2.2, cage=True),
                            B.node(f"{tag}{n}a_{s}", (sx * x, py - 0.04, z), "cell", "body", w=2.2, cage=True)))
            S_ = sill[s][kk]
            for f, a in col:
                B.beam(f, a, "cell")
            B.beam(col[0][0], S_[3], "cell")
            B.beam(col[0][1], S_[3], "cell")
            B.beam(col[0][0], S_[2], "cell_brace")
            B.beam(col[0][1], S_[0], "cell_brace")
            B.beam(col[0][0], sill[s][kk - 1][3], "cell_brace")
            B.beam(col[0][1], sill[s][kk + 1][3] if kk + 1 < len(T.CABIN_Y) else S_[2], "cell_brace")
            for (f0, a0), (f1, a1) in zip(col[:-1], col[1:]):
                B.beam(f0, f1, "cell")
                B.beam(a0, a1, "cell")
                B.beam(f0, a1, "cell_brace")
            top = rail[s][rk[ry]]
            ft, at = col[-1]
            for q in top:
                B.beam(ft, q, "cell")
                B.beam(at, q, "cell_brace")
            st[f"{tag}_{s}"] = col
    # ---- roof bows (front header, B bow, rear header)
    for ry, tag in ((0.29, "hdrF"), (-0.60, "bowB"), (-1.24, "hdrR")):
        kr = rk[ry]
        R0, L0 = rail["R"][kr][1], rail["L"][kr][1]
        pR, pL = B.P(R0), B.P(L0)
        zc = max(pR[2], pL[2]) + 0.055
        cen = B.node(f"{tag}_C", (0.0, ry, zc), "cell", "body", w=1.3, cage=True)
        mR = B.node(f"{tag}_m_R", (pR[0] * 0.5, ry, zc - 0.012), "cell", "body", w=1.3, cage=True)
        mL = B.node(f"{tag}_m_L", (pL[0] * 0.5, ry, zc - 0.012), "cell", "body", w=1.3, cage=True)
        for s, m_, rr in (("R", mR, rail["R"][kr]), ("L", mL, rail["L"][kr])):
            B.beam(m_, cen, "pillar")
            B.beam(m_, rr[0], "pillar")
            B.beam(m_, rr[1], "pillar")
            B.beam(m_, rr[2], "pillar_brace")
            nb = rail[s][kr + 1] if kr + 1 < len(ys_rail) else rail[s][kr - 1]
            B.beam(m_, nb[1], "pillar_brace")
            pb = rail[s][kr - 1] if kr > 0 else rail[s][kr + 1]
            B.beam(m_, pb[1], "pillar_brace")
        # the bow centre sits on a nearly straight line between its mid nodes: brace it fore and aft
        for s in ("R", "L"):
            for kk in (kr - 1, kr + 1):
                if 0 <= kk < len(ys_rail):
                    B.beam(cen, rail[s][kk][1], "pillar_brace")
        st[tag] = (mL, cen, mR)
    # header to cowl through the windshield frame is the A-pillar itself; B bow to B pillars done via rails
    # ---- parcel shelf, rear seat bulkhead
    shelf = [B.node("shelf_C", (0.0, T.SHELF_Y, T.SHELF_Z), "cell", "body", w=1.6, cage=True)]
    shelf.extend(B.pair("shelf35", (0.35, T.SHELF_Y, T.SHELF_Z), "cell", "body", w=1.6, cage=True))
    shelf.extend(B.pair("shelf68", (0.68, T.SHELF_Y + 0.02, T.SHELF_Z + 0.01), "cell", "body", w=2.5, cage=True))
    bulk = [B.node("bulk_C", (0.0, -1.24, 0.72), "cell", "body", w=1.6, cage=True)]
    bulk.extend(B.pair("bulk40", (0.40, -1.24, 0.72), "cell", "body", w=1.6, cage=True))
    for s, (c, m_, o), (bc, bm) in (("R", (shelf[0], shelf[1], shelf[3]), (bulk[0], bulk[1])),
                                     ("L", (shelf[0], shelf[2], shelf[4]), (bulk[0], bulk[2]))):
        B.chain([c, m_, o], "cell")
        B.beam(bc, bm, "cell")
        B.beam(m_, bm, "cell")
        B.beam(c, bc, "cell")
        B.beam(m_, bc, "cell_brace")
        for q in rail[s][rk[-1.42]] + rail[s][rk[-1.60]]:
            B.beam(o, q, "pillar")
        B.beam(o, rail[s][rk[-1.24]][2], "cell_brace")
        B.beam(bm, st[f"cp_{s}"][1][1], "cell")
        B.beam(bm, st[f"cp_{s}"][0][1], "cell_brace")
        B.beam(bm, floor[s][-1], "cell")
        B.beam(bc, tunnel[-1], "cell")
        B.beam(bm, tunnel[-1], "cell_brace")
        # shelf centre and the bulkhead out of the shelf plane: to the rear header and the C pillars
        B.beam(c, st["hdrR"][1], "cell_brace")
        B.beam(m_, st["hdrR"][2 if s == "R" else 0], "cell_brace")
        B.beam(c, st[f"cp_{s}"][-1][1], "cell_brace")
    B.anchor(bulk[0], B.cage, "cell_brace", k=3, max_d=0.6)
    st["shelf"], st["bulk"] = shelf, bulk
    return st


def build_front(B, st):
    sides = ("R", "L")
    rails = {s: [] for s in sides}
    fr = T.FRONT_RAIL
    from .mechanics import floor_z  # noqa: F401
    for k, y in enumerate(T.FRONT_RAIL_Y + [T.CRUSH_CAN_Y]):
        mat_w = (1.8, 2.8, 2.8, 2.4, 1.4, 1.4, 1.4)[k]       # suspension / engine mount stations heavier
        for s, sx in (("R", 1), ("L", -1)):
            ids = [B.node(f"frail{k}_{n}_{s}", (sx * x, y, z), "cell", "body", w=mat_w, cage=True)
                   for n, (x, z) in enumerate(((fr["x_out"], fr["z_lo"]), (fr["x_in"], fr["z_lo"]),
                                               (fr["x_in"], fr["z_hi"]), (fr["x_out"], fr["z_hi"])))]
            rails[s].append(ids)
    nfr = len(T.FRONT_RAIL_Y)
    for s in sides:
        for k in range(len(rails[s])):
            B.section(rails[s][k], "rail_f_brace")
            if k + 1 < len(rails[s]):
                crush = k + 1 == len(rails[s]) - 1        # last bay = crush can
                B.brace(rails[s][k], rails[s][k + 1], "crush_can" if crush else "rail_f",
                        "crush_can" if crush else "rail_f_brace")
        # rail root: torque box into the sill front, floor and firewall
        r0 = rails[s][0]
        S0 = st["sill"][s][0]
        fwlo = st["fw"][(s, T.FIREWALL["z"][0])]
        for q in r0:
            B.beam(q, fwlo, "cell")
        B.beam(r0[0], S0[1], "cell")
        B.beam(r0[3], S0[2], "cell_brace")
        B.beam(r0[0], st["floor"][s][0], "cell")
        B.beam(r0[1], st["floor"][s][0], "cell_brace")
        B.beam(r0[2], st["fw"][(s, T.FIREWALL["z"][1])], "cell_brace")
        B.beam(r0[3], st["hinge"][s][0], "cell_brace")
        B.beam(r0[1], st["tunnel"][0], "cell_brace")
    st["frail"] = rails
    # subframe cross members under the engine
    for y, z, tag in ((1.32, 0.255, "xm1"), (1.85, 0.290, "xm2")):
        c = B.node(f"{tag}_C", (0.0, y, z), "cell", "body", cage=True)
        k = int(np.argmin([abs(v - y) for v in T.FRONT_RAIL_Y]))
        for s in sides:
            B.beam(c, rails[s][k][1], "rail_f")
            B.beam(c, rails[s][k][2], "rail_f_brace")
            kk = k + 1 if T.FRONT_RAIL_Y[k] < y else k - 1
            B.beam(c, rails[s][kk][1], "rail_f_brace")
        st[tag] = c
    # bumper beam (two rows) and crush can attachment
    bb = T.BUMPER_F
    front_row, back_row = [], []
    for x in bb["x"]:
        yb = bb["y"] - 0.10 * (x / 0.76) ** 2
        if x == 0:
            front_row.append([B.node("bbF_f_C", (0.0, yb, bb["z"]), "cell", "body", w=2.6, cage=True)] * 2)
            back_row.append([B.node("bbF_b_C", (0.0, yb - bb["depth"], bb["z"]), "cell", "body", w=2.6, cage=True)] * 2)
        else:
            front_row.append(list(B.pair(f"bbF_f{int(x * 100)}", (x, yb, bb["z"]), "cell", "body", w=2.6, cage=True)))
            back_row.append(list(B.pair(f"bbF_b{int(x * 100)}", (x, yb - bb["depth"], bb["z"]), "cell", "body", w=2.6,
                                        cage=True)))
    # top row behind the beam: a triangular section, so the beam is a 3D truss (two rows in one horizontal
    # plane were a vertical mechanism, D-030)
    top_row = []
    for x in bb["x"]:
        yb = bb["y"] - 0.10 * (x / 0.76) ** 2 - bb["depth"]
        if x == 0:
            top_row.append([B.node("bbF_t_C", (0.0, yb, bb["z"] + 0.08), "cell", "body", w=2.6, cage=True)] * 2)
        else:
            top_row.append(list(B.pair(f"bbF_t{int(x * 100)}", (x, yb, bb["z"] + 0.08), "cell", "body", w=2.6, cage=True)))
    for si in (0, 1):
        f = [r[si] for r in front_row]
        b = [r[si] for r in back_row]
        t = [r[si] for r in top_row]
        B.chain(f, "bumper_beam")
        B.chain(b, "bumper_beam")
        B.chain(t, "bumper_beam")
        for k in range(len(f)):
            B.beam(f[k], b[k], "bumper_beam")
            B.beam(t[k], b[k], "bumper_beam")
            B.beam(t[k], f[k], "bumper_beam")
            if k + 1 < len(f):
                B.beam(f[k], b[k + 1], "bumper_beam")
                B.beam(b[k], f[k + 1], "bumper_beam")
                B.beam(t[k], b[k + 1], "bumper_beam")
                B.beam(t[k], f[k + 1], "bumper_beam")
        s = ("R", "L")[si]
        can = rails[s][-1]
        ki = bb["x"].index(0.42)
        for q in can:
            B.beam(q, b[ki], "crush_can")
            B.beam(q, f[ki], "crush_can")
        B.beam(can[0], b[ki + 1], "crush_can")
        B.beam(can[1], b[ki - 1], "crush_can")
        B.beam(can[2], t[ki], "crush_can")
        B.beam(can[3], t[ki], "crush_can")
        B.beam(can[2], t[ki - 1], "crush_can")
    st["bbF"] = (front_row, back_row, top_row)
    # core support
    co = T.CORE
    core = {}
    for z, tag in ((co["z_lo"], "lo"), (co["z_hi"], "hi")):
        core[(tag, "C")] = B.node(f"core_{tag}_C", (0.0, co["y"], z), "cell", "body", w=2.2, cage=True)
        for x in co["x"][1:]:
            r, l = B.pair(f"core_{tag}{int(x * 100)}", (x, co["y"], z), "cell", "body", w=2.2, cage=True)
            core[(tag, "R", x)], core[(tag, "L", x)] = r, l
    xin, xout = co["x"][1], co["x"][2]
    for tag in ("lo", "hi"):
        for s in sides:
            B.chain([core[(tag, "C")], core[(tag, s, xin)], core[(tag, s, xout)]], "core")
    for s in sides:
        B.beam(core[("lo", s, xout)], core[("hi", s, xout)], "core")
        B.beam(core[("lo", s, xin)], core[("hi", s, xin)], "core")
        B.beam(core[("lo", s, xin)], core[("hi", s, xout)], "core")
        B.beam(core[("lo", s, xout)], core[("hi", s, xin)], "core")
        r5 = rails[s][nfr - 1]               # rail station at the core support (y 2.08)
        for q in r5:
            B.beam(core[("lo", s, xin)], q, "core")
        B.beam(core[("lo", s, xout)], r5[0], "core")
        B.beam(core[("lo", s, xout)], r5[3], "core")
    B.beam(core[("lo", "C")], core[("hi", "C")], "core")
    B.beam(core[("lo", "C")], core[("hi", "R", xin)], "core")
    B.beam(core[("lo", "C")], core[("hi", "L", xin)], "core")
    # the core support is one plane (y const): tie its centre nodes out of that plane (bumper beam, cross member)
    off = [n for row in st["bbF"][1] + st["bbF"][2] for n in row] + [st["xm2"]]
    for tag in ("lo", "hi"):
        B.anchor(core[(tag, "C")], off, "core", k=3, max_d=0.7)
    st["core"] = core
    # aprons (upper rails) and wheel-house inner tops / strut towers
    for s, sx in (("R", 1), ("L", -1)):
        ap = [B.node(f"apron{n}_{s}", (sx * x, y, z), "cell", "body", w=2.0, cage=True) for n, (x, y, z) in enumerate(T.APRON)]
        lo = [B.node(f"aplo{n}_{s}", (sx * x, y, z), "cell", "body", w=(9.0 if n == 1 else 3.5), cage=True) for n, (x, y, z) in enumerate(T.APRON_LO)]
        B.chain(ap, "apron")
        B.chain(lo, "apron")
        h = st["hinge"][s]
        B.beam(ap[0], h[2], "apron")
        B.beam(ap[0], h[1], "apron")
        B.beam(ap[0], st["rail"][s][0][0], "apron")
        B.beam(ap[0], st["cowl"][3 if s == "R" else 4], "apron")
        B.beam(ap[-1], core[("hi", s, xout)], "apron")
        B.beam(ap[-1], core[("lo", s, xout)], "apron")
        B.beam(ap[-2], core[("hi", s, xout)], "apron")
        B.beam(ap[-1], core[("hi", s, xin)], "apron")
        # wheel house: apron <-> inner top <-> rail
        B.beam(lo[0], ap[0], "apron")
        B.beam(lo[0], ap[1], "apron")
        B.beam(lo[0], h[1], "apron")
        B.beam(lo[0], st["fw"][(s, T.FIREWALL["z"][1])], "apron")
        B.beam(lo[1], ap[1], "apron")
        B.beam(lo[1], ap[2], "apron")
        B.beam(lo[1], ap[3], "apron")
        B.beam(lo[2], ap[3], "apron")
        B.beam(lo[2], ap[4], "apron")
        B.beam(lo[2], core[("hi", s, xout)], "apron")
        B.beam(lo[0], lo[2], "apron_brace")
        k1 = 1
        for q in rails[s][k1]:
            B.beam(lo[0], q, "apron")
        for q in rails[s][2]:
            B.beam(lo[1], q, "apron")
        for q in rails[s][4]:
            B.beam(lo[2], q, "apron")
        B.beam(lo[1], rails[s][1][2], "apron_brace")
        B.beam(lo[1], rails[s][3][2], "apron_brace")
        B.beam(ap[2], rails[s][2][3], "apron_brace")
        st[f"apron_{s}"], st[f"aplo_{s}"] = ap, lo
    # cowl to strut towers (strut-tower brace)
    B.beam(st["aplo_R"][1], st["cowl"][1], "apron_brace")
    B.beam(st["aplo_L"][1], st["cowl"][2], "apron_brace")
    return st


def build_rear(B, st):
    sides = ("R", "L")
    rr = T.REAR_RAIL
    rails = {s: [] for s in sides}
    for k, y in enumerate(T.REAR_RAIL_Y):
        # stations 1, 3 and 4 carry the subframe mounts and the upper-link brackets (reinforced, heavier)
        wk = 2.0 if k in (1, 3, 4) else 1.4
        for s, sx in (("R", 1), ("L", -1)):
            ids = [B.node(f"rrail{k}_{n}_{s}", (sx * x, y, z), "cell", "body", w=wk, cage=True)
                   for n, (x, z) in enumerate(((rr["x_out"], rr["z_lo"][k]), (rr["x_in"], rr["z_lo"][k]),
                                               (rr["x_in"], rr["z_hi"][k]), (rr["x_out"], rr["z_hi"][k])))]
            rails[s].append(ids)
    for s in sides:
        for k in range(len(rails[s])):
            B.section(rails[s][k], "rail_r_brace")
            if k + 1 < len(rails[s]):
                crush = k + 1 == len(rails[s]) - 1
                B.brace(rails[s][k], rails[s][k + 1], "crush_can" if crush else "rail_r",
                        "crush_can" if crush else "rail_r_brace")
        r0 = rails[s][0]
        S_ = st["sill"][s][-1]
        for q in r0:
            B.beam(q, st["floor"][s][-1], "cell")
        B.beam(r0[0], S_[1], "cell")
        B.beam(r0[3], S_[2], "cell")
        B.beam(r0[2], st["bulk"][1 if s == "R" else 2], "cell")
        B.beam(r0[1], st["tunnel"][-1], "cell_brace")
    st["rrail"] = rails
    # trunk floor: centre nodes between the rails
    tf = []
    for k, y in enumerate(T.REAR_RAIL_Y[1:-1], 1):
        z = rr["z_lo"][k] + 0.02
        c = B.node(f"tfloor{k}_C", (0.0, y, z), "cell", "body", w=1.6, cage=True)
        for s in sides:
            B.beam(c, rails[s][k][1], "floor")
            B.beam(c, rails[s][k][2], "floor_brace")
        if tf:
            B.beam(c, tf[-1], "floor")
            for s in sides:
                B.beam(c, rails[s][k - 1][1], "floor_brace")
        tf.append(c)
    B.beam(tf[0], st["tunnel"][-1], "floor")
    st["tfloor"] = tf
    # wheel houses and rear towers
    kc = T.CABIN_Y.index(T.C_PILLAR_Y)
    for s, sx in (("R", 1), ("L", -1)):
        wh = [B.node(f"whouse{n}_{s}", (sx * x, y, z), "cell", "body", w=1.2, cage=True) for n, (x, y, z) in enumerate(T.WHEELHOUSE_R)]
        tw = B.node(f"rtower_{s}", (sx * T.REAR_TOWER[0], T.REAR_TOWER[1], T.REAR_TOWER[2]), "cell", "body", w=8.0, cage=True)
        B.chain(wh, "rail_r")
        for q in wh[1:4]:
            B.beam(tw, q, "rail_r")
        B.beam(tw, wh[0], "rail_r_brace")
        B.beam(tw, wh[4], "rail_r_brace")
        # to the rails (inner) and the C pillar / shelf (upper)
        B.beam(wh[0], rails[s][0][0], "rail_r")
        B.beam(wh[0], rails[s][0][3], "rail_r")
        B.beam(wh[0], st["sill"][s][kc][2], "rail_r")
        B.beam(wh[0], st["cp_" + s][0][1], "rail_r")
        B.beam(wh[1], st["cp_" + s][0][1], "rail_r")
        B.beam(wh[1], st["cp_" + s][1][1], "rail_r_brace")
        B.beam(wh[1], rails[s][1][3], "rail_r")
        B.beam(wh[2], rails[s][2][3], "rail_r")
        B.beam(wh[2], rails[s][2][2], "rail_r_brace")
        B.beam(wh[3], rails[s][3][3], "rail_r")
        B.beam(wh[4], rails[s][3][0], "rail_r")
        B.beam(wh[4], rails[s][4][3], "rail_r")
        B.beam(tw, rails[s][2][3], "rail_r")
        B.beam(tw, st["shelf"][3 if s == "R" else 4], "rail_r")
        B.beam(tw, st["bulk"][1 if s == "R" else 2], "rail_r_brace")
        B.beam(wh[2], st["shelf"][3 if s == "R" else 4], "rail_r_brace")
        st[f"whouse_{s}"], st[f"rtower_{s}"] = wh, tw
    # rear panel and rear bumper beam
    rp = T.REAR_PANEL
    panel = {}
    for z, tag in ((rp["z_lo"], "lo"), (rp["z_hi"], "hi")):
        panel[(tag, "C")] = B.node(f"rpanel_{tag}_C", (0.0, rp["y"], z), "cell", "body", w=1.2, cage=True)
        for x in rp["x"][1:]:
            r, l = B.pair(f"rpanel_{tag}{int(x * 100)}", (x, rp["y"], z), "cell", "body", w=1.8, cage=True)
            panel[(tag, "R", x)], panel[(tag, "L", x)] = r, l
    xi, xo = rp["x"][1], rp["x"][2]
    for tag in ("lo", "hi"):
        for s in sides:
            B.chain([panel[(tag, "C")], panel[(tag, s, xi)], panel[(tag, s, xo)]], "rail_r")
    for s in sides:
        B.beam(panel[("lo", s, xi)], panel[("hi", s, xi)], "rail_r")
        B.beam(panel[("lo", s, xo)], panel[("hi", s, xo)], "rail_r")
        B.beam(panel[("lo", s, xi)], panel[("hi", s, xo)], "rail_r_brace")
        B.beam(panel[("lo", "C")], panel[("hi", s, xi)], "rail_r_brace")
        last = rails[s][-2]
        for q in last:
            B.beam(panel[("lo", s, xo)], q, "rail_r")
        B.beam(panel[("lo", s, xi)], last[1], "rail_r")
        B.beam(panel[("lo", s, xi)], last[2], "rail_r_brace")
        B.beam(panel[("hi", s, xo)], last[3], "rail_r_brace")
        B.beam(panel[("hi", s, xo)], st[f"whouse_{s}"][4], "rail_r_brace")
    B.beam(panel[("lo", "C")], panel[("hi", "C")], "rail_r")
    B.beam(panel[("lo", "C")], st["tfloor"][-1], "rail_r")
    st["rpanel"] = panel
    bb = T.BUMPER_R
    front_row, back_row = [], []
    for x in bb["x"]:
        yb = bb["y"] + 0.12 * (x / 0.78) ** 2
        if x == 0:
            back_row.append([B.node("bbR_b_C", (0.0, yb, bb["z"]), "cell", "body", w=2.0, cage=True)] * 2)
            front_row.append([B.node("bbR_f_C", (0.0, yb + bb["depth"], bb["z"]), "cell", "body", w=2.0, cage=True)] * 2)
        else:
            back_row.append(list(B.pair(f"bbR_b{int(x * 100)}", (x, yb, bb["z"]), "cell", "body", w=3.2 if x == 0.45 else 2.0, cage=True)))
            front_row.append(list(B.pair(f"bbR_f{int(x * 100)}", (x, yb + bb["depth"], bb["z"]), "cell", "body", w=3.2 if x == 0.45 else 2.0,
                                         cage=True)))
    top_row = []                                   # triangular section (see the front beam)
    for x in bb["x"]:
        yb = bb["y"] + 0.12 * (x / 0.78) ** 2 + bb["depth"]
        if x == 0:
            top_row.append([B.node("bbR_t_C", (0.0, yb, bb["z"] + 0.08), "cell", "body", w=2.6, cage=True)] * 2)
        else:
            top_row.append(list(B.pair(f"bbR_t{int(x * 100)}", (x, yb, bb["z"] + 0.08), "cell", "body", w=2.6, cage=True)))
    for si in (0, 1):
        f = [r[si] for r in front_row]
        b = [r[si] for r in back_row]
        t = [r[si] for r in top_row]
        B.chain(f, "bumper_beam")
        B.chain(b, "bumper_beam")
        B.chain(t, "bumper_beam")
        for k in range(len(f)):
            B.beam(f[k], b[k], "bumper_beam")
            B.beam(t[k], b[k], "bumper_beam")
            B.beam(t[k], f[k], "bumper_beam")
            if k + 1 < len(f):
                B.beam(f[k], b[k + 1], "bumper_beam")
                B.beam(b[k], f[k + 1], "bumper_beam")
                B.beam(t[k], b[k + 1], "bumper_beam")
                B.beam(t[k], f[k + 1], "bumper_beam")
        s = ("R", "L")[si]
        end = rails[s][-1]
        ki = bb["x"].index(0.45)
        for q in end:
            B.beam(q, f[ki], "crush_can")
            B.beam(q, b[ki], "crush_can")
        B.beam(end[0], f[ki + 1], "crush_can")
        B.beam(end[1], f[ki - 1], "crush_can")
        B.beam(end[2], t[ki], "crush_can")
        B.beam(end[3], t[ki], "crush_can")
        B.beam(end[2], t[ki - 1], "crush_can")
    st["bbR"] = (front_row, back_row, top_row)
    return st


# =================================================================================================
# panels
# =================================================================================================
def side_grid(V, key, res):
    return samp(V[key], *res)


def weld_edges(B, ids, mat, edges=("all",), k=2, max_d=0.30, bg=""):
    """Connect the border nodes of a panel grid to their k nearest cage nodes."""
    ni, nj = ids.shape
    border = set()
    if "all" in edges or "bottom" in edges:
        border |= {ids[i, 0] for i in range(ni)}
    if "all" in edges or "top" in edges:
        border |= {ids[i, nj - 1] for i in range(ni)}
    if "all" in edges or "start" in edges:
        border |= {ids[0, j] for j in range(nj)}
    if "all" in edges or "end" in edges:
        border |= {ids[ni - 1, j] for j in range(nj)}
    n = 0
    for a in sorted(border):
        for t in B.nearest(B.P(a), B.cage, k=k, max_d=max_d):
            B.beam(a, t, mat, bg=bg)
            n += 1
    return n


def seal_edges(B, ids, pool, mat, bg, edges=("start", "end", "bottom", "top"), max_d=0.16):
    """Weatherstrip of a closed closure: each perimeter node of the outer skin to the nearest body node. The
    seals belong to the latch group (passive), so they let go when the latch breaks (D-030)."""
    ni, nj = ids.shape
    border = set()
    if "bottom" in edges:
        border |= {ids[i, 0] for i in range(ni)}
    if "top" in edges:
        border |= {ids[i, nj - 1] for i in range(ni)}
    if "start" in edges:
        border |= {ids[0, j] for j in range(nj)}
    if "end" in edges:
        border |= {ids[ni - 1, j] for j in range(nj)}
    n = 0
    for a in sorted(border):
        for t in B.nearest(B.P(a), pool, k=1, max_d=max_d, min_d=0.02):
            B.beam(a, t, mat, bg=bg, bgt=1)
            n += 1
    return n


def build_panels(B, V, st):
    R = T.PANEL_RES
    out = {}
    sides = (("R", 1), ("L", -1))
    # ---- quarters (welded body panels)
    for s, sx in sides:
        G = side_grid(V, "CH_Quarter", R["quarter"]) * [sx, 1, 1]
        ids = B.grid(f"quarter_{s}", G, "cell", "body", "body", w=0.35)
        B.grid_beams(ids, "panel", "panel_brace")
        B.grid_tris(ids, "body", inside_point, hinge="skin_side")
        weld_edges(B, ids, "weld", k=2, max_d=0.32)
        B.support_surface(ids, "panel_support", k=2)
        out[f"quarter_{s}"] = ids
    # ---- roof (welded)
    P = V["CH_Roof"].transpose(1, 0, 2)[::-1]                     # columns centre -> edge, rows rear -> front
    G = full_from_half(samp(P, R["roof"][0], R["roof"][1], i0=0.0, i1=0.97))
    ids = B.grid("roof", G, "cell", "body", "body", w=0.35)
    B.grid_beams(ids, "panel", "panel_brace")
    B.grid_tris(ids, "body", inside_point, hinge="skin_roof")
    weld_edges(B, ids, "weld", k=2, max_d=0.30)
    for tag in ("hdrF", "bowB", "hdrR"):                           # roof bows support the skin
        for q in st[tag]:
            for t in B.nearest(B.P(q), list(ids.ravel()), k=2, max_d=0.20):
                B.beam(q, t, "weld")
    B.support_surface(ids, "panel_support", k=2, max_d=0.55)
    out["roof"] = ids
    # ---- fenders (bolted to apron, hinge pillar, core support / fascia)
    for s, sx in sides:
        side = "R" if sx > 0 else "L"
        G = side_grid(V, "CH_Fender", R["fender"]) * [sx, 1, 1]
        ids = B.grid(f"fender_{side}", G, f"fender_{side}", f"fender_{side}", "body", w=1.0)
        B.grid_beams(ids, "panel", "panel_brace")
        B.grid_tris(ids, f"fender_{side}", inside_point, hinge="skin_side")
        weld_edges(B, ids, "bolt", edges=("top", "start"), k=2, max_d=0.25)
        B.support_surface(ids, "panel_support_bolt", k=2)
        out[f"fender_{side}"] = ids
    # ---- doors: outer skin + inner frame; hinges (pins) on the hinge pillar, latch on the B pillar
    for s, sx in sides:
        side = "FR" if sx > 0 else "FL"
        part = f"door_{side}"
        G = side_grid(V, "CH_Door", R["door"]) * [sx, 1, 1]
        outer = B.grid(f"{part}_o", G, part, part, "body", w=0.8)
        Gi = offset_in(samp(V["CH_Door"], *R["door_inner"], i0=0.04, i1=0.96, j0=0.05, j1=0.95) * [sx, 1, 1], 0.10)
        inner = B.grid(f"{part}_i", Gi, part, part, "body", flags=F_NOCOL, w=1.6)
        B.grid_beams(outer, "panel", "panel_brace")
        B.grid_beams(inner, "panel_inner", "panel_inner", skip=False)
        for q in inner.ravel():
            for t in B.nearest(B.P(q), list(outer.ravel()), k=4, max_d=0.25):
                B.beam(q, t, "panel_link")
        # door edge (front, rear, bottom, top) of the outer skin to the inner frame for torsion
        B.grid_tris(outer, part, inside_point, hinge="skin_side")
        ni, nj = outer.shape
        front_col = [outer[ni - 1, j] for j in range(nj)]
        # hinges and latch as 3D joints on the hinge pillar / B pillar region of the cage (D-063): pinned to the three
        # hinge pillar nodes in a line, the upper hinge was free along the car; latched by two beams to the B pillar,
        # the door's rear edge swung out and forward under the frontal pulse
        for zt in (0.45, 0.82):
            h = min(front_col, key=lambda q: abs(B.P(q)[2] - zt))
            B.joint(h, B.cage, "hinge", bg=part)
            hi_ = B.nearest(B.P(h), list(inner.ravel()), k=1)[0]
            B.joint(hi_, B.cage, "hinge", bg=part, bgt=1)
            B.weight[h] = B.weight[hi_] = 5.0           # hinge hardware: heavier nodes carry the stiff pins
        rear_col = [outer[0, j] for j in range(nj)]
        latch = min(rear_col, key=lambda q: abs(B.P(q)[2] - 0.72))
        B.weight[latch] = 4.0
        # the latch on the B pillar; a target off the pillar (the C pillar's front) is a passive, ductile tie (latch_tie):
        # as a latch beam it tore the latch off when the body side buckled at 120 km/h and the door flew open
        for t in B.joint_targets(latch, B.cage):
            if B.sk.nodes[t]["name"].startswith("bp"):
                B.beam(latch, t, "latch", bg=f"{part}_latch")
            else:
                B.beam(latch, t, "latch_tie", bg=f"{part}_latch", bgt=1)
        seal_edges(B, outer, B.cage, "seal", f"{part}_latch", edges=("start", "end", "bottom"))
        out[part] = (outer, inner)
    # ---- hood: outer + inner; hinges at the rear corners, latch at the front centre
    P = V["CH_Hood"]
    G = full_from_half(samp(P, *R["hood"]))
    outer = B.grid("hood_o", G, "hood", "hood", "body", w=0.8)
    Gi = offset_in(full_from_half(samp(P, *R["hood_inner"], i1=0.85, j0=0.06, j1=0.94)), 0.045)
    inner = B.grid("hood_i", Gi, "hood", "hood", "body", flags=F_NOCOL, w=1.5)
    B.grid_beams(outer, "panel", "panel_brace")
    B.grid_beams(inner, "panel_inner", "panel_inner", skip=False)
    for q in inner.ravel():
        for t in B.nearest(B.P(q), list(outer.ravel()), k=4, max_d=0.30):
            B.beam(q, t, "panel_link")
    B.grid_tris(outer, "hood", inside_point, hinge="skin_hood")
    ni, nj = outer.shape
    for i_c, s in ((ni - 1, "R"), (0, "L")):
        h = outer[i_c, 1]
        B.joint(h, B.cage, "hinge", bg="hood")                              # D-063
        B.joint(outer[i_c, 0], B.cage, "hinge", bg="hood", bgt=1)
        B.weight[h] = B.weight[outer[i_c, 0]] = 4.0
    lt = outer[ni // 2, nj - 1]
    B.weight[lt] = 3.0
    # the hood latch carries the core support's push when the front crushes; at the door latches' 12 kN it let go in a
    # 50 km/h frontal and the hood folded over the windshield instead of crumpling (D-059). The core support's lower
    # centre holds it down (D-063): tied to the top bar alone, in one row with it, the hood's front edge was free to
    # lift and rose 0.4-0.5 m in the frontal crashes. That tie is ductile and passive (latch_tie): as a plain latch
    # beam it tore the latch off when the crushing core support turned
    for t in (st["core"][("hi", "C")], st["core"][("hi", "R", T.CORE["x"][1])], st["core"][("hi", "L", T.CORE["x"][1])]):
        B.beam(lt, t, "latch_hood", bg="hood_latch")
    B.beam(lt, st["core"][("lo", "C")], "latch_tie", bg="hood_latch", bgt=1)
    # cowl lip: the plenum flange the hood's rear edge rests on (the edge runs up to 24 cm ahead of the cowl
    # bar, D-034), triangulated to the cowl and the firewall top
    lips = []
    for i in range(1, ni - 1):
        lips.append(B.node(f"cowllip{i}", B.P(outer[i, 0]) + np.array([0.0, -0.02, -0.045]), "cell", "body", w=1.0,
                           cage=True))
    B.chain(lips, "lip")
    fwp = list(st["cowl"]) + [st["fw"][k] for k in st["fw"]]
    for q in lips:
        B.anchor(q, fwp, "lip", k=3, max_d=0.45)
    st["cowl_lip"] = lips
    # rubber stops round the perimeter on the lip, the aprons and the core support (compression only, D-034)
    rim = [outer[i, j] for i in range(ni) for j in range(nj) if i in (0, ni - 1) or j in (0, nj - 1)]
    rim = [q for q in rim if B.weight.get(q, 1.0) < 2.5]                 # not the hinge / latch hardware
    B.stops(rim, lips + st["apron_R"] + st["apron_L"] + [st["core"][k] for k in st["core"]], "stop_closure",
            max_d=0.25, min_cos=0.55)
    seal_edges(B, outer, B.cage, "seal", "hood_latch", max_d=0.20)
    out["hood"] = (outer, inner)
    # ---- deck lid: outer + inner; hinges at the front corners, latch at the rear centre
    P = V["CH_DeckLid"]
    G = full_from_half(samp(P, *R["trunk"]))
    outer = B.grid("trunk_o", G, "trunk", "trunk", "body", w=0.8)
    Gi = offset_in(full_from_half(samp(P, *R["trunk_inner"], i1=0.85, j0=0.08, j1=0.92)), 0.04)
    inner = B.grid("trunk_i", Gi, "trunk", "trunk", "body", flags=F_NOCOL, w=1.5)
    B.grid_beams(outer, "panel", "panel_brace")
    B.grid_beams(inner, "panel_inner", "panel_inner", skip=False)
    for q in inner.ravel():
        for t in B.nearest(B.P(q), list(outer.ravel()), k=4, max_d=0.30):
            B.beam(q, t, "panel_link")
    B.grid_tris(outer, "trunk", inside_point, hinge="skin_hood")
    ni, nj = outer.shape
    for i_c, s in ((ni - 1, "R"), (0, "L")):
        h = outer[i_c, nj - 2]
        # D-063: the three nodes of one roof rail section ahead of the hinge gave a pin free up / down and sideways;
        # within 0.5 m the shelf and the shock tower close it (not the wheel house top: at 1.1 kg the stiff hinge
        # beam on it set the skeleton's largest S)
        B.joint(h, [q for q in B.cage if not B.sk.nodes[q]["name"].startswith("whouse")], "hinge", bg="trunk",
                max_d=0.50)
        B.weight[h] = 4.0
    lt = outer[ni // 2, 0]
    B.weight[lt] = 3.0
    # rear panel top row + a passive, ductile tie to its lower centre (D-063): the top row alone left the lid's rear
    # edge free to lift
    for t in (st["rpanel"][("hi", "C")], st["rpanel"][("hi", "R", T.REAR_PANEL["x"][1])],
              st["rpanel"][("hi", "L", T.REAR_PANEL["x"][1])]):
        B.beam(lt, t, "latch", bg="trunk_latch")
    B.beam(lt, st["rpanel"][("lo", "C")], "latch_tie", bg="trunk_latch", bgt=1)
    # tray lip: the rear window's lower flange under the lid's front edge (D-034), triangulated to the shelf,
    # the roof rail ends and the rear bulkhead / wheel houses
    lips = []
    for i in range(1, ni - 1):
        lips.append(B.node(f"traylip{i}", B.P(outer[i, nj - 1]) + np.array([0.0, 0.02, -0.045]), "cell", "body", w=1.0,
                           cage=True))
    B.chain(lips, "lip")
    pool = st["shelf"] + [n for s_ in ("R", "L") for sec in st["rail"][s_][-3:] for n in sec] + st["bulk"] +         [n for n in B.cage if B.sk.nodes[n]["name"].startswith(("whouse", "rtower"))]
    for q in lips:
        B.anchor(q, pool, "lip", k=3, max_d=0.6)
    st["tray_lip"] = lips
    quarters = list(out["quarter_R"].ravel()) + list(out["quarter_L"].ravel())
    rim = [outer[i, j] for i in range(ni) for j in range(nj) if i in (0, ni - 1) or j in (0, nj - 1)]
    rim = [q for q in rim if B.weight.get(q, 1.0) < 2.5]
    B.stops(rim, lips + quarters + [st["rpanel"][k] for k in st["rpanel"]], "stop_closure", max_d=0.25, min_cos=0.55)
    seal_edges(B, outer, B.cage + quarters, "seal", "trunk_latch", max_d=0.20)
    out["trunk"] = (outer, inner)
    # ---- fascia (front bumper cover) and rear bumper cover: plastic, clipped
    P = V["CH_Fascia"][::-1]                                       # columns centre -> side
    G = full_from_half(samp(P, *R["fascia"]))
    ids = B.grid("fascia", G, "bumper_F", "bumper_F", "plastic", w=1.0)
    B.grid_beams(ids, "plastic", "plastic_brace")
    B.grid_tris(ids, "bumper_F", inside_point, hinge="skin_plastic")
    fb = [n for row in st["bbF"][0] for n in row] + [st["core"][k] for k in st["core"]]
    for q in ids.ravel():
        for t in B.nearest(B.P(q), fb, k=1, max_d=0.12):
            B.beam(q, t, "clip", bg="bumper_F")
    for q in ids[[0, -1]].ravel():                                 # wrap-around ends to the fenders
        for f in ("fender_R", "fender_L"):
            for t in B.nearest(B.P(q), list(out[f].ravel()), k=1, max_d=0.14, min_d=0.03):
                B.beam(q, t, "clip", bg="bumper_F")
    B.support_surface(ids, "plastic_support", k=2, bg="bumper_F", bgt=1)
    out["fascia"] = ids
    P = V["CH_RearBumper"]
    G = full_from_half(samp(P, *R["bumper_r"]))
    ids = B.grid("rbumper", G, "bumper_R", "bumper_R", "plastic", w=1.0)
    B.grid_beams(ids, "plastic", "plastic_brace")
    B.grid_tris(ids, "bumper_R", inside_point, hinge="skin_plastic")
    rb = [n for row in st["bbR"][1] for n in row] + [st["rpanel"][k] for k in st["rpanel"]]
    for q in ids.ravel():
        for t in B.nearest(B.P(q), rb, k=1, max_d=0.12):
            B.beam(q, t, "clip", bg="bumper_R")
    for q in ids[[0, -1]].ravel():
        for f in ("quarter_R", "quarter_L"):
            for t in B.nearest(B.P(q), list(out[f].ravel()), k=1, max_d=0.14, min_d=0.03):
                B.beam(q, t, "clip", bg="bumper_R")
    B.support_surface(ids, "plastic_support", k=2, bg="bumper_R", bgt=1)
    out["rbumper"] = ids
    return out


GLASS_GAP = 0.02   # m between the two layers of a glass pane


def glass_pane(B, G, part, mat, hinge="glass_side"):
    """A pane as two layers 2 cm apart, so it has bending stiffness across its plane like curved glass (a single
    layer has none, D-030): the outer layer (collision, skinning) and a coarser inner layer (every second node, no
    collision) linked to the outer nodes around each inner node. Returns (outer, inner) node grids."""
    outer = B.grid(part, G, part, part, "glass", w=1.0)
    Gi = offset_in(G, GLASS_GAP)[::2, ::2]
    inner = B.grid(f"{part}_in", Gi, part, part, "glass", flags=F_NOCOL, w=1.0)
    B.grid_beams(outer, mat, mat, skip=False, bg=part)
    B.grid_beams(inner, mat, mat, skip=False, bg=part)
    ni, nj = outer.shape
    for I in range(inner.shape[0]):
        for J in range(inner.shape[1]):
            for i in range(2 * I - 1, 2 * I + 2):
                for j in range(2 * J - 1, 2 * J + 2):
                    if 0 <= i < ni and 0 <= j < nj:
                        B.beam(outer[i, j], inner[I, J], mat, bg=part, bgt=1)
    B.grid_tris(outer, part, inside_point, bg=part, hinge=hinge)
    return outer, inner


def build_glass(B, V, st, panels):
    R = T.PANEL_RES
    for key, res, part, mat in (("glass_front", R["windshield"], "glass_windshield", "glass"),
                                ("glass_rear", R["rear_glass"], "glass_rear", "glass")):
        G = full_from_half(samp(V[key], *res))
        ids, inner = glass_pane(B, G, part, mat, hinge="glass_laminated" if part == "glass_windshield" else "glass_side")
        weld_edges(B, ids, "glass_mount", k=2, max_d=0.20, bg=part)
        weld_edges(B, inner, "glass_mount", k=2, max_d=0.20, bg=part)
        st[part] = ids
    for s, sx in (("R", 1), ("L", -1)):
        side = "FR" if sx > 0 else "FL"
        G = samp(V["CH_Glass_Door"], *R["door_glass"], i0=0.02, i1=0.9) * [sx, 1, 1]
        part = f"glass_side_{side}"
        ids, gin = glass_pane(B, G, part, "glass_side")
        outer, inner = panels[f"door_{side}"]
        top_o = [outer[i, outer.shape[1] - 1] for i in range(outer.shape[0])]
        top_i = [inner[i, inner.shape[1] - 1] for i in range(inner.shape[0])]
        for i in range(ids.shape[0]):
            for t in (B.nearest(B.P(ids[i, 0]), top_o, k=2, max_d=0.25, min_d=0.03)
                      + B.nearest(B.P(ids[i, 0]), top_i, k=1, max_d=0.30, min_d=0.03)):
                B.beam(ids[i, 0], t, "glass_mount", bg=part)
            for t in B.nearest(B.P(ids[i, 1]), top_i, k=1, max_d=0.40):
                B.beam(ids[i, 1], t, "glass_mount", bg=part)
        for i in range(gin.shape[0]):
            for t in B.nearest(B.P(gin[i, 0]), top_i + top_o, k=2, max_d=0.30, min_d=0.03):
                B.beam(gin[i, 0], t, "glass_mount", bg=part)
        rails = [n for sec in st["rail"][s] for n in sec]
        for i in range(ids.shape[0]):           # frameless glass: top edge sealed against the roof rail
            for t in B.nearest(B.P(ids[i, ids.shape[1] - 1]), rails, k=1, max_d=0.16, min_d=0.02):
                B.beam(ids[i, ids.shape[1] - 1], t, "seal", bg=f"door_{side}_latch", bgt=1)
        st[part] = ids
        G = samp(V["CH_Glass_Quarter"], *R["quarter_glass"], i0=0.15) * [sx, 1, 1]   # skip the pointed rear tip
        part = f"glass_quarter_{s}"
        ids, gin = glass_pane(B, G, part, "glass_side")
        weld_edges(B, ids, "glass_mount", k=2, max_d=0.22, bg=part)
        weld_edges(B, gin, "glass_mount", k=2, max_d=0.22, bg=part)
        st[part] = ids


# =================================================================================================
# chassis: powertrain, suspension, steering, wheels
# =================================================================================================
def build_powertrain(B, st):
    eng = []
    for n, (x, y, z) in enumerate([(0.20, 1.12, 0.40), (-0.20, 1.12, 0.40), (0.20, 1.64, 0.40), (-0.20, 1.64, 0.40),
                                   (0.27, 1.12, 0.70), (-0.27, 1.12, 0.70), (0.27, 1.64, 0.70), (-0.27, 1.64, 0.70),
                                   (0.0, 1.20, 0.93), (0.0, 1.55, 0.93)]):
        eng.append(B.node(f"eng{n}", (x, y, z), "engine", "engine", cmat="metal"))
    for a in range(len(eng)):
        for b in range(a + 1, len(eng)):
            B.beam(eng[a], eng[b], "engine")
    tr = []
    for n, (x, y, z) in enumerate([(0.0, 1.00, 0.24), (0.13, 1.00, 0.40), (-0.13, 1.00, 0.40), (0.0, 0.62, 0.26),
                                   (0.0, 0.62, 0.46), (0.0, 0.36, 0.33)]):
        tr.append(B.node(f"trans{n}", (x, y, z), "transmission", "engine", cmat="metal"))
    for a in range(len(tr)):
        for b in range(a + 1, len(tr)):
            B.beam(tr[a], tr[b], "engine")
    for a in tr[:3]:
        for b in eng[:2] + eng[4:6]:
            B.beam(a, b, "engine")
    # engine mounts on the front rails (inner upper nodes at y 1.20 / 1.45), gearbox mount on the tunnel
    fr = st["frail"]
    for s, e_lo, e_hi in (("R", eng[0], eng[2]), ("L", eng[1], eng[3])):
        for q in (fr[s][1][2], fr[s][1][1], fr[s][2][2]):
            B.beam(e_lo, q, "mount_engine", bg="engine_mount")
        for q in (fr[s][2][2], fr[s][2][1], fr[s][3][2]):
            B.beam(e_hi, q, "mount_engine", bg="engine_mount")
    for q in (st["tunnel"][1], st["tunnel"][2], st["floor"]["R"][1], st["floor"]["L"][1]):
        B.beam(tr[5], q, "mount_trans", bg="engine_mount")
    B.beam(tr[3], st["xm1"], "mount_trans", bg="engine_mount")
    # drive shaft and differential
    ds = [tr[5], B.node("dshaft0", (0.0, -0.30, 0.33), "driveshaft", "body", cmat="metal", flags=F_NOCOL),
          B.node("dshaft1", (0.0, -0.95, 0.325), "driveshaft", "body", cmat="metal", flags=F_NOCOL)]
    B.chain(ds, "driveshaft")
    for q in (st["tunnel"][4], st["tunnel"][5]):
        B.beam(ds[1], q, "mount_trans")
    # centre bearing and the rear shaft node held in 3D (a straight chain is a mechanism, D-030)
    pool = st["tunnel"] + st["floor"]["R"] + st["floor"]["L"]
    for q in ds[1:]:
        B.anchor(q, pool, "center_bearing", k=3, max_d=0.7)
    st["eng"], st["trans"], st["dshaft"] = eng, tr, ds
    return st


def build_rear_subframe(B, st):
    yr = -T.WHEELBASE / 2
    sub = {}
    pts = {"f": (0.40, yr + 0.36, 0.27), "m": (0.40, yr, 0.30), "a": (0.40, yr - 0.38, 0.27)}
    for k, p in pts.items():
        sub[("R", k)], sub[("L", k)] = B.pair(f"rsub_{k}", p, "subframe_rear", "body", cmat="metal")
    sub["cf"] = B.node("rsub_cf", (0.0, yr + 0.30, 0.235), "subframe_rear", "body", cmat="metal")
    sub["ca"] = B.node("rsub_ca", (0.0, yr - 0.30, 0.235), "subframe_rear", "body", cmat="metal")
    for s in ("R", "L"):
        B.chain([sub[(s, "f")], sub[(s, "m")], sub[(s, "a")]], "subframe")
        B.beam(sub[(s, "f")], sub["cf"], "subframe")
        B.beam(sub[(s, "a")], sub["ca"], "subframe")
        B.beam(sub[(s, "m")], sub["cf"], "subframe")
        B.beam(sub[(s, "m")], sub["ca"], "subframe")
        B.beam(sub[(s, "f")], sub["ca"], "subframe")
    B.beam(sub["cf"], sub["ca"], "subframe")
    B.beam(sub[("R", "m")], sub[("L", "m")], "subframe")
    for s in ("R", "L"):                    # the subframe frame is nearly flat: cross it vertically
        B.beam(sub[(s, "f")], sub[("L" if s == "R" else "R", "m")], "subframe")
    # bushings to the body rails (4 mounts)
    rr = st["rrail"]
    for s in ("R", "L"):
        for q in (rr[s][0][1], rr[s][0][0], rr[s][1][1]):
            B.beam(sub[(s, "f")], q, "subframe_mount", bg=f"subframe_{s}")
        for q in (rr[s][3][1], rr[s][3][0], rr[s][4][1]):
            B.beam(sub[(s, "a")], q, "subframe_mount", bg=f"subframe_{s}")
    # differential
    diff = []
    for n, (x, y, z) in enumerate([(0.12, yr + 0.12, 0.33), (-0.12, yr + 0.12, 0.33), (0.0, yr - 0.12, 0.30),
                                   (0.0, yr, 0.44)]):
        diff.append(B.node(f"diff{n}", (x, y, z), "differential", "body", cmat="metal"))
    for a in range(4):
        for b in range(a + 1, 4):
            B.beam(diff[a], diff[b], "engine")
    for q in diff:
        for t in (sub[("R", "m")], sub[("L", "m")], sub["cf"], sub["ca"]):
            B.beam(q, t, "subframe_mount", bg="differential")
    for c in (sub["cf"], sub["ca"]):
        B.anchor(c, diff + [sub[(s_, k_)] for s_ in ("R", "L") for k_ in ("f", "m", "a")], "subframe", k=3, max_d=0.7)
    B.beam(st["dshaft"][-1], diff[0], "driveshaft")
    B.beam(st["dshaft"][-1], diff[1], "driveshaft")
    st["rsub"], st["diff"] = sub, diff
    return st


def wheel_ids(B, name, centre, side, front, st):
    """Wheel with a 24-section tire: axle nodes (part of the knuckle), rim rings (2 x 24), tread
    (3 x 24). Returns dict of node lists."""
    cx, cy, cz = centre
    n = T.TIRE_SECTIONS
    part = f"wheel_{name}"
    knuckle_group = "knuckle_front" if front else "knuckle_rear"
    ax_in = B.node(f"{name}_axle_in", (cx - side * T.AXLE_IN, cy, cz), f"{knuckle_group}_{name}", part, cmat="metal",
                   flags=F_NOCOL)
    ax_out = B.node(f"{name}_axle_out", (cx + side * T.AXLE_OUT, cy, cz), f"{knuckle_group}_{name}", part, cmat="metal",
                    flags=F_NOCOL)
    rim_i, rim_o, tr_i, tr_c, tr_o = [], [], [], [], []
    for k in range(n):
        a = 2 * math.pi * k / n
        ca, sa = math.cos(a), math.sin(a)
        def P(dx, r):  # noqa: E306
            return (cx + side * dx, cy + r * sa, cz - r * ca)
        rg = f"rim_{'front' if front else 'rear'}_{name}"
        rim_i.append(B.node(f"{name}_rimI{k}", P(-T.RIM_HALF_W, T.RIM_R), rg, part, cmat="metal", flags=F_NOCOL))
        rim_o.append(B.node(f"{name}_rimO{k}", P(T.RIM_HALF_W, T.RIM_R), rg, part, cmat="metal", flags=S.DEFAULT_FLAGS))
        rt = T.TIRE_R_OUT - 0.012
        tr_i.append(B.node(f"{name}_trI{k}", P(-T.TREAD_HALF_W, rt), f"tire_{name}", part, cmat="tire", flags=F_TIRE))
        tr_c.append(B.node(f"{name}_trC{k}", P(0.0, T.TIRE_R_OUT), f"tire_{name}", part, cmat="tire", flags=F_TIRE))
        tr_o.append(B.node(f"{name}_trO{k}", P(T.TREAD_HALF_W, rt), f"tire_{name}", part, cmat="tire", flags=F_TIRE))
    B.beam(ax_in, ax_out, "knuckle_f" if front else "knuckle")
    for k in range(n):
        k1 = (k + 1) % n
        # rim: rings, cross bracing, spokes to both axle nodes
        B.beam(rim_i[k], rim_i[k1], "rim")
        B.beam(rim_o[k], rim_o[k1], "rim")
        B.beam(rim_i[k], rim_o[k], "rim")
        B.beam(rim_i[k], rim_o[k1], "rim")
        for ax in (ax_in, ax_out):
            B.beam(rim_i[k], ax, "rim_spoke")
            B.beam(rim_o[k], ax, "rim_spoke")
        # tire: sidewalls (bead -> shoulder), tread (circumferential, lateral, diagonals)
        B.beam(rim_i[k], tr_i[k], "tire_side", bg=f"tire_{name}", bgt=1)
        B.beam(rim_o[k], tr_o[k], "tire_side", bg=f"tire_{name}", bgt=1)
        B.beam(rim_i[k], tr_i[k1], "tire_side_diag")
        B.beam(rim_i[k1], tr_i[k], "tire_side_diag")
        B.beam(rim_o[k], tr_o[k1], "tire_side_diag")
        B.beam(rim_o[k1], tr_o[k], "tire_side_diag")
        B.beam(rim_i[k], tr_c[k], "tire_side_diag")
        B.beam(rim_o[k], tr_c[k], "tire_side_diag")
        for row in (tr_i, tr_c, tr_o):
            B.beam(row[k], row[k1], "tire_tread")
        B.beam(tr_i[k], tr_c[k], "tire_tread_lat")
        B.beam(tr_c[k], tr_o[k], "tire_tread_lat")
        B.beam(tr_i[k], tr_c[k1], "tire_tread_diag")
        B.beam(tr_c[k], tr_i[k1], "tire_tread_diag")
        B.beam(tr_c[k], tr_o[k1], "tire_tread_diag")
        B.beam(tr_o[k], tr_c[k1], "tire_tread_diag")
    # belt: circumferential bending of the tread band, a hinge across every lateral edge of the two tread strips (D-043).
    # The tread nodes then curve gradually into the contact patch instead of dropping onto the ground one 24-gon corner
    # at a time (impacts at v sin(7.5 deg) made the rolling losses grow with v^2)
    # (wings mirrored about the centre row: the two strips have opposite diagonals, so the band has no handedness)
    for ra, rb in ((tr_i, tr_c), (tr_o, tr_c)):
        for k in range(n):
            km, kp = (k - 1) % n, (k + 1) % n
            B.sk.hinge(ra[km], ra[k], rb[k], rb[kp], "tire_belt")
    # air volume: closed surface rim barrel -> inner sidewall -> tread -> outer sidewall, wound out of
    # the cavity (away from the torus core circle at the mid radius); tread bands also collide
    tri0 = len(B.sk.tris)
    c = np.array(centre)
    r_mid = 0.5 * (T.RIM_R + T.TIRE_R_OUT)
    rings = [rim_i, tr_i, tr_c, tr_o, rim_o, rim_i]
    for r in range(len(rings) - 1):
        for k in range(n):
            k1 = (k + 1) % n
            a, b, cc, d = rings[r][k], rings[r][k1], rings[r + 1][k1], rings[r + 1][k]
            if r in (2, 3):
                # outer half split along the mirrored diagonal: the pressure load pattern has no handedness either
                a, b, cc, d = b, cc, d, a
            pa, pb, pc = B.P(a), B.P(b), B.P(cc)
            cen = (pa + pb + pc + B.P(d)) / 4
            rad = cen - c
            rad[0] = 0.0
            core = c + rad / max(np.linalg.norm(rad), 1e-9) * r_mid
            nn = np.cross(pb - pa, pc - pa)
            ttype = "COLLIDE" if r in (1, 2, 3) else "PRESSURE"      # tread and outer sidewall collide
            if np.dot(nn, cen - core) >= 0:
                B.sk.tri(a, b, cc, type=ttype, group=part)
                B.sk.tri(a, cc, d, type=ttype, group=part)
            else:
                B.sk.tri(a, cc, b, type=ttype, group=part)
                B.sk.tri(a, d, cc, type=ttype, group=part)
    tris = list(range(tri0, len(B.sk.tris)))
    B.sk.pressure_groups.append({"name": f"tire_{name}", "tris": tris, "pressure": T.TIRE_PRESSURE_PA, "wheel": name})
    return {"ax_in": ax_in, "ax_out": ax_out, "rim_i": rim_i, "rim_o": rim_o, "tread": tr_i + tr_c + tr_o,
            "tr_c": tr_c}


def build_front_suspension(B, st):
    W = {"R": (0.8335, 1.4755, 0.352), "L": (-0.8335, 1.4755, 0.352)}
    fr = st["frail"]
    rack = {}
    # steering rack housing on the front cross member (front steer: tie rods ahead of the axle). The
    # rack ends are pinned to the housing; the tie rods are HYDRO beams whose length follows the
    # steering input (lengthening the right one and shortening the left one moves both steering arms
    # to the right = steer right), which is the rack's kinematics without a sliding joint (D-023).
    # rack height: the tie rods point at the front-view instant centre, which nulls the bump steer
    # (tools/skeleton/suspension_design.py, D-025)
    yrk, zrk = 1.62, 0.257
    rack_c = B.node("rack_C", (0.0, yrk, zrk), "rack", "body", cmat="metal", flags=F_NOCOL)
    for q in (fr["R"][3][1], fr["L"][3][1], fr["R"][2][1], fr["L"][2][1], st["xm2"]):
        B.beam(rack_c, q, "subframe")
    wheels = {}
    for s, sx in (("R", 1), ("L", -1)):
        name = "FR" if sx > 0 else "FL"
        cx, cy, cz = W[s]
        w = wheel_ids(B, name, (cx, cy, cz), sx, True, st)
        part = f"wheel_{name}"
        kg = f"knuckle_front_{name}"
        # the lower ball joint carries the spring, the damper and the anti-roll-bar link: heavier in the knuckle group
        # (exact stability, D-051)
        lbj = B.node(f"{name}_lbj", (sx * 0.745, cy, 0.165), kg, part, cmat="metal", flags=F_NOCOL, w=1.25)
        ubj = B.node(f"{name}_ubj", (sx * 0.715, cy - 0.02, 0.575), kg, part, cmat="metal", flags=F_NOCOL)
        # steering arm: tie-rod end 0.135 m ahead of the axle and 40 mm outboard of the kingpin, so the arms' extensions
        # meet behind the axle - about 50 % Ackermann for the front-mounted rack (D-051; inboard it was anti-Ackermann)
        tre = B.node(f"{name}_tre", (sx * 0.775, cy + 0.135, 0.255), kg, part, cmat="metal", flags=F_NOCOL)
        kn = [w["ax_in"], w["ax_out"], lbj, ubj, tre]
        for a in range(len(kn)):
            for b in range(a + 1, len(kn)):
                B.beam(kn[a], kn[b], "knuckle_f")
        # lower A-arm (two inner pivots under the rail, ball joint) and the anti-roll-bar pick-up node. The
        # inner pivot heights put the front-view instant centre 2.5 m inboard of the contact patch at 0.27 m
        # height: roll centre ~0.09 m, camber gain ~-23 deg/m (D-025)
        li_f = B.node(f"{name}_lca_f", (sx * 0.38, cy + 0.20, 0.181), f"susp_front_arms_{s}", "body", cmat="metal", flags=F_NOCOL)
        li_r = B.node(f"{name}_lca_r", (sx * 0.38, cy - 0.20, 0.181), f"susp_front_arms_{s}", "body", cmat="metal", flags=F_NOCOL)
        lsh = B.node(f"{name}_lca_sh", (sx * 0.650, cy, 0.215), f"susp_front_arms_{s}", part, cmat="metal", flags=F_NOCOL)
        for a in (li_f, li_r):
            B.beam(a, lbj, "arm", bg=part)
            B.beam(a, lsh, "arm")
        B.beam(li_f, li_r, "arm")
        B.beam(lsh, lbj, "arm")
        for q in (fr[s][2][1], fr[s][2][0], fr[s][3][1]):
            B.beam(li_f, q, "subframe")
        for q in (fr[s][1][1], fr[s][1][0], fr[s][2][1]):
            B.beam(li_r, q, "subframe")
        B.mount(li_f, "subframe_mount", k=3, max_d=0.45)
        B.mount(li_r, "subframe_mount", k=3, max_d=0.45)
        # upper A-arm (pivots on the apron / tower), ball joint
        ui_f = B.node(f"{name}_uca_f", (sx * 0.50, cy + 0.20, 0.548), f"susp_front_arms_{s}", "body", cmat="metal", flags=F_NOCOL)
        ui_r = B.node(f"{name}_uca_r", (sx * 0.50, cy - 0.20, 0.548), f"susp_front_arms_{s}", "body", cmat="metal", flags=F_NOCOL)
        for a in (ui_f, ui_r):
            B.beam(a, ubj, "arm", bg=part)
        B.beam(ui_f, ui_r, "arm")
        lo = st[f"aplo_{s}"]
        for a, ks in ((ui_f, (1, 2)), (ui_r, (0, 1))):
            for kk in ks:
                B.beam(a, lo[kk], "subframe")
            B.beam(a, fr[s][2][2], "subframe")
            B.mount(a, "subframe_mount", k=3, max_d=0.45)
        # coil-over: lower ball joint (heavy knuckle node) -> strut top (tower = APRON_LO[1]); the real
        # spring sits on the arm just inboard, so the rates are wheel rates (motion ratio 1); bump stop
        top = lo[1]
        B.beam(lbj, top, "spring_f", pre=1.0)
        B.beam(lbj, top, "damper_f", allow_duplicate=True)
        B.beam(lbj, top, "bumpstop_f", type="BOUNDED", allow_duplicate=True)
        # rack end (pinned to the housing and the rail), HYDRO tie rod to the steering arm: +-20 % of the 0.375 m tie
        # rod turns the inner wheel 34 deg and the outer 30 deg at full lock (tools/p3b/steer_kinematics.py, D-051)
        rk = B.node(f"rack_{s}", (sx * 0.40, yrk, zrk), "rack", "body", cmat="metal", flags=F_NOCOL)
        B.pin(rk, [rack_c, fr[s][3][1], fr[s][3][2]], "subframe")
        B.beam(rk, fr[s][2][1], "subframe")
        B.mount(rk, "subframe_mount", k=3, max_d=0.45, bg=f"tierod_{name}", bgt=1)
        B.beam(rk, tre, "tierod", type="HYDRO", hydro="steering", hf=(0.20 if sx > 0 else -0.20), bg=f"tierod_{name}")
        rack[s] = rk
        # anti-roll-bar drop link on the lower ball joint: on the arm's shock node it bent the (nearly flat) arm and the
        # bar worked at half its rate (D-051)
        wheels[name] = dict(w, arm=tre, lsh=lbj, arb_pick=lbj, part=part, lca=(li_f, li_r), kingpin=(lbj, ubj))
    st["rack"] = rack
    st["wheels_front"] = wheels
    # K-member: the lower-arm pivots tied across the car (and crosswise), the rack housing tied to them, so the pivots and
    # the rack move as one cradle - before, the pivots hung on the rails alone and the arms yawed under brake and side
    # forces (front compliance steer 1.1 deg/kN, D-051)
    (rf, rr), (lf, lr) = wheels["FR"]["lca"], wheels["FL"]["lca"]
    for a, b in ((rf, lf), (rr, lr), (rf, lr), (rr, lf), (rack["R"], rf), (rack["R"], rr), (rack["L"], lf), (rack["L"], lr),
                 (rack_c, rr), (rack_c, lr)):
        B.beam(a, b, "kmember")
    # anti-roll bar: axis nodes on the rails, lever tips 0.20 m behind the bar axis, drop links down to
    # the lower-arm nodes
    axR = B.node("arbF_axis_R", (0.30, 1.72, 0.31), "rack", "body", cmat="metal", flags=F_NOCOL)
    axL = B.node("arbF_axis_L", (-0.30, 1.72, 0.31), "rack", "body", cmat="metal", flags=F_NOCOL)
    for a, s in ((axR, "R"), (axL, "L")):
        for q in (fr[s][3][1], fr[s][3][0], fr[s][2][1]):
            B.beam(a, q, "subframe")
        B.mount(a, "subframe_mount", k=3, max_d=0.45)
    B.beam(axR, axL, "subframe")
    # lever tips at x 0.62: further out (0.70, a more vertical link) the two levers lay almost along the bar and left the
    # 1.7 kg tips a fore-aft pendulum mode at 30 Hz that rang for seconds after a drop (D-054)
    tips = anti_roll_levers(B, "arbF", axR, axL, {"R": (0.62, 1.52, 0.31), "L": (-0.62, 1.52, 0.31)}, "rack",
                            {"R": wheels["FR"]["arb_pick"], "L": wheels["FL"]["arb_pick"]})
    B.sk.torsion_bars.append({"n": [tips["R"], axR, axL, tips["L"]], "mat": "arb_front", "bg": ""})
    return st


def anti_roll_levers(B, prefix, axR, axL, tip_pos, group, pick):
    """Lever tips of an anti-roll bar: each tip is tied to both bar-axis nodes, so it can only rotate
    about the bar axis, and a drop link connects it to the suspension (pick node). The torsion bar
    [tip_R, axis_R, axis_L, tip_L] resists the difference of the two lever angles. A lever of its own
    keeps the bar out of the suspension kinematics: a beam from the bar axis straight to the arm would
    act as an extra suspension spring and fight the arm's arc."""
    tips = {}
    for s in ("R", "L"):
        tip = B.node(f"{prefix}_tip_{s}", tip_pos[s], group, "body", cmat="metal", flags=F_NOCOL)
        B.beam(tip, axR, "arb_lever")
        B.beam(tip, axL, "arb_lever")
        B.beam(tip, pick[s], "arb_link")
        tips[s] = tip
    return tips


def build_rear_suspension(B, st):
    yr = -T.WHEELBASE / 2
    sub = st["rsub"]
    wheels = {}
    for s, sx in (("R", 1), ("L", -1)):
        name = "RR" if sx > 0 else "RL"
        c = (sx * 0.8345, yr, 0.352)
        w = wheel_ids(B, name, c, sx, False, st)
        part = f"wheel_{name}"
        kg = f"knuckle_rear_{name}"
        k_lo_f = B.node(f"{name}_klf", (sx * 0.735, yr + 0.10, 0.255), kg, part, cmat="metal", flags=F_NOCOL)
        k_lo_r = B.node(f"{name}_klr", (sx * 0.735, yr - 0.10, 0.255), kg, part, cmat="metal", flags=F_NOCOL, w=1.75)
        k_up = B.node(f"{name}_kup", (sx * 0.720, yr - 0.02, 0.475), kg, part, cmat="metal", flags=F_NOCOL)
        kn = [w["ax_in"], w["ax_out"], k_lo_f, k_lo_r, k_up]
        for a in range(len(kn)):
            for b in range(a + 1, len(kn)):
                B.beam(kn[a], kn[b], "knuckle")
        # five links: inner pivots on the subframe / body, outer on the knuckle. Lower links and the toe
        # link (last) on one line with the front-view instant centre 2.5 m inboard at 0.30 m height, upper
        # links rising outward to it: roll centre ~0.10 m, camber gain ~-23 deg/m, no bump steer (D-025)
        inner_pts = [(0.36, yr + 0.20, 0.262), (0.36, yr - 0.20, 0.262), (0.40, yr + 0.15, 0.452),
                     (0.40, yr - 0.28, 0.452), (0.36, yr + 0.32, 0.262)]
        outer = [k_lo_f, k_lo_r, k_up, k_up, k_lo_f]
        for n_, (p, o) in enumerate(zip(inner_pts, outer)):
            ip = B.node(f"{name}_link{n_}", (sx * p[0], p[1], p[2]), f"susp_rear_links_{s}", "body", cmat="metal", flags=F_NOCOL)
            B.beam(ip, o, "link", bg=part)
            # inner pivot: pinned to the subframe (low ones) or the body rail (upper ones)
            pool = [sub[(s, "f")], sub[(s, "m")], sub[(s, "a")], sub["cf"], sub["ca"]] if p[2] < 0.40 else \
                list(st["rrail"][s][1]) + list(st["rrail"][s][2]) + list(st["rrail"][s][3])
            B.pin(ip, B.nearest(B.P(ip), pool, k=3), "subframe")
            B.mount(ip, "subframe_mount", k=3, max_d=0.40)
        # coil-over: lower link (rear lower knuckle point) -> rear tower
        B.beam(k_lo_r, st[f"rtower_{s}"], "spring_r", pre=1.0)
        B.beam(k_lo_r, st[f"rtower_{s}"], "damper_r", allow_duplicate=True)
        B.beam(k_lo_r, st[f"rtower_{s}"], "bumpstop_r", type="BOUNDED", allow_duplicate=True)
        wheels[name] = dict(w, arm=k_up, lsh=k_lo_r, part=part)
    st["wheels_rear"] = wheels
    # anti-roll bar: axis nodes on the subframe, lever tips inboard of the rims, drop links to the knuckles
    axR = B.node("arbR_axis_R", (0.30, yr - 0.30, 0.30), "subframe_rear", "body", cmat="metal", flags=F_NOCOL)
    axL = B.node("arbR_axis_L", (-0.30, yr - 0.30, 0.30), "subframe_rear", "body", cmat="metal", flags=F_NOCOL)
    for a, s in ((axR, "R"), (axL, "L")):
        B.pin(a, [sub[(s, "a")], sub[(s, "m")], sub["ca"]], "subframe")
        B.mount(a, "subframe_mount", k=3, max_d=0.40)
    B.beam(axR, axL, "subframe")
    tips = anti_roll_levers(B, "arbR", axR, axL, {"R": (0.62, yr - 0.12, 0.38), "L": (-0.62, yr - 0.12, 0.38)},
                            "subframe_rear", {"R": wheels["RR"]["lsh"], "L": wheels["RL"]["lsh"]})
    B.sk.torsion_bars.append({"n": [tips["R"], axR, axL, tips["L"]], "mat": "arb_rear", "bg": ""})
    return st


# =================================================================================================
# auxiliaries: exhaust, tank, battery, radiator, seats, column, mirrors, lamps
# =================================================================================================
def build_aux(B, st, panels):
    sides = (("R", 1), ("L", -1))
    # exhaust: two chains under the floor, hangers to the floor / rear rails (break group "exhaust")
    path = [(0.27, 1.06, 0.17), (0.22, 0.60, 0.155), (0.22, 0.0, 0.155), (0.22, -0.60, 0.155), (0.25, -1.20, 0.155),
            (0.32, -1.85, 0.16), (0.46, -2.10, 0.235), (0.54, -2.38, 0.241)]
    for s, sx in sides:
        ids = [B.node(f"exh{k}_{s}", (sx * x, y, z), "exhaust", "exhaust", cmat="metal") for k, (x, y, z) in enumerate(path)]
        B.chain(ids, "exhaust")
        for a, b in zip(ids[:-2], ids[2:]):
            B.beam(a, b, "exhaust")
        B.beam(ids[0], st["eng"][0 if sx > 0 else 1], "exhaust")             # manifold
        B.beam(ids[0], st["eng"][4 if sx > 0 else 5], "exhaust")
        for k in range(1, len(ids)):                     # every node hung in 3D (the pipe is nearly straight)
            B.anchor(ids[k], B.cage, "exhaust_hanger", k=3, max_d=0.6, bg="exhaust", bgt=1)   # rubber hangers, passive
        st[f"exh_{s}"] = ids
    # fuel tank (saddle) on the floor, straps
    tk = []
    for n, (x, y, z) in enumerate([(0.21, -0.75, 0.30), (-0.21, -0.75, 0.30), (0.21, -1.10, 0.30), (-0.21, -1.10, 0.30),
                                   (0.30, -0.92, 0.36), (-0.30, -0.92, 0.36)]):
        tk.append(B.node(f"tank{n}", (x, y, z), "fuel_tank", "fuel_tank", cmat="metal"))
    for a in range(len(tk)):
        for b in range(a + 1, len(tk)):
            B.beam(tk[a], tk[b], "tank")
    for q in tk:
        for t in B.nearest(B.P(q), B.cage, k=2, max_d=0.40):
            B.beam(q, t, "tank_strap", bg="fuel_tank")
    # battery in the trunk (right side)
    bt = [B.node(f"batt{n}", p, "battery", "body", cmat="metal", flags=F_NOCOL)
          for n, p in enumerate([(0.30, -2.05, 0.42), (0.52, -2.05, 0.42), (0.30, -2.25, 0.42), (0.41, -2.15, 0.60)])]
    for a in range(4):
        for b in range(a + 1, 4):
            B.beam(bt[a], bt[b], "tank")
    for q in bt:
        for t in B.nearest(B.P(q), B.cage, k=2, max_d=0.35):
            B.beam(q, t, "tank_strap")
    # radiator (with condenser, fan and shroud) on the core support: its own part and break group, so its meshes bind to
    # it alone and it comes away as a unit (D-058: on the body part, torn-off lamp mounts left it at the wall and the
    # shroud and liner meshes stretched 1.4 m); it collides, so it cannot pass through a wall
    core = st["core"]
    rad = [B.node(f"rad{n}", p, "radiator", "radiator", cmat="metal", flags=F_DETACH)
           for n, p in enumerate([(0.55, 2.02, 0.40), (-0.55, 2.02, 0.40), (0.55, 2.02, 0.74), (-0.55, 2.02, 0.74)])]
    B.section([rad[0], rad[1], rad[3], rad[2]], "tank")
    pool = [core[k] for k in core] + [n for s_ in ("R", "L") for sec in st["frail"][s_][3:] for n in sec] + [st["xm2"]]
    for q in rad:
        B.anchor(q, pool, "radiator_mount", k=3, max_d=0.6, bg="radiator")
    st["radiator"] = rad
    # seats: frames on the floor (front) and the rear kick-up, breakable mounts
    from .interior_tables import H_POINT, TORSO_DEG
    a = math.radians(TORSO_DEG)
    for s, sx in sides:
        side = "FR" if sx > 0 else "FL"
        xc = sx * abs(H_POINT[0])
        yb = H_POINT[1] - 0.135
        base = [B.node(f"seat{side}_{n}", (xc + dx, y, 0.25), f"seat_{side}", f"seat_{side}", flags=F_NOCOL)
                for n, (dx, y) in enumerate(((-0.17, yb - 0.05), (0.17, yb - 0.05), (-0.17, yb + 0.40), (0.17, yb + 0.40)))]
        top = [B.node(f"seat{side}_t{n}", (xc + dx, yb - 0.78 * math.sin(a), 0.42 + 0.78 * math.cos(a)), f"seat_{side}",
                      f"seat_{side}", flags=F_NOCOL, w=0.4) for n, dx in enumerate((-0.16, 0.16))]   # back mass sits low
        allp = base + top
        for i in range(len(allp)):
            for j in range(i + 1, len(allp)):
                B.beam(allp[i], allp[j], "seat")
        for q in base:
            # one mount each to the floor, the tunnel side and the sill top: three directions with vertical
            # components (mounts only to the floor plane left the seat a 3.4 Hz pitch mode, D-034)
            for pool in (st["floor"][s], st["tunnel"], [sec[2] for sec in st["sill"][s]] + [sec[3] for sec in st["sill"][s]]):
                for t in B.nearest(B.P(q), pool, k=1, max_d=0.6):
                    B.beam(q, t, "seat_mount", bg=f"seat_{side}")
            B.anchor(q, st["floor"][s] + st["tunnel"] + [n_ for sec in st["sill"][s] for n_ in sec], "seat_mount", k=3,
                     max_d=0.5, bg=f"seat_{side}")
        st[f"seat_{side}"] = allp
    rs = [B.node(f"seatR_{n}", p, "seat_rear", "seat_rear", flags=F_NOCOL)
          for n, p in enumerate([(0.40, -0.85, 0.50), (-0.40, -0.85, 0.50), (0.40, -1.25, 0.60), (-0.40, -1.25, 0.60)])]
    for i in range(4):
        for j in range(i + 1, 4):
            B.beam(rs[i], rs[j], "seat")
    for q in rs:
        B.anchor(q, B.cage, "seat_mount", k=3, max_d=0.6)
    # steering column: dash bar -> wheel hub (collapsible)
    from .interior_tables import WHEEL_CENTRE, column_axis
    ca = np.array(column_axis())
    c_top = B.node("column_top", WHEEL_CENTRE, "column", "body", flags=F_NOCOL)
    c_mid = B.node("column_mid", np.array(WHEEL_CENTRE) + ca * 0.28, "column", "body", flags=F_NOCOL)
    B.beam(c_top, c_mid, "column")
    for t in (st["dash"][2], st["dash"][0], st["dash"][4]):                # left (driver) side bar nodes
        B.beam(c_mid, t, "dash")
    for t in (st["dash"][2], st["dash"][4]):
        B.beam(c_top, t, "column")
    B.beam(c_top, st["fw"][("L", T.FIREWALL["z"][1])], "column")
    pool = st["dash"] + list(st["cowl"]) + st["hinge"]["L"] + [st["fw"][k] for k in st["fw"]]
    B.anchor(c_mid, pool, "dash", k=3, max_d=0.7)
    B.anchor(c_top, pool, "column", k=3, max_d=0.8)
    st["column"] = (c_top, c_mid)
    # side mirrors on the doors (break groups)
    for s, sx in sides:
        side = "FR" if sx > 0 else "FL"
        mside = "R" if sx > 0 else "L"
        outer, inner = panels[f"door_{side}"]
        base = [outer[outer.shape[0] - 1, outer.shape[1] - 1], outer[outer.shape[0] - 2, outer.shape[1] - 1],
                inner[inner.shape[0] - 1, inner.shape[1] - 1]]
        m = [B.node(f"mirror_{mside}_{n}", p, f"mirror_{mside}", f"mirror_{mside}", cmat="plastic", flags=F_DETACH)
             for n, p in enumerate([(sx * 1.040, 0.390, 1.050), (sx * 1.060, 0.330, 1.090), (sx * 0.960, 0.400, 1.020)])]
        B.section(m, "mirror", diag=False)
        top = [q for q in list(outer.ravel()) + list(inner.ravel()) if B.P(q)[2] > 0.80]
        for q in m:
            for t in base:
                B.beam(q, t, "mirror_mount", bg=f"mirror_{mside}")
            # nearest door-top nodes spanning 3D (three long, nearly parallel struts let it rock at 3.3 Hz, D-034)
            B.anchor(q, top, "mirror_mount", k=3, max_d=0.40, bg=f"mirror_{mside}")
        B.sk.tri(m[0], m[1], m[2], group=f"mirror_{mside}")
        B.sk.tri(m[0], m[2], m[1], group=f"mirror_{mside}")
    # headlamp clusters on the core support / fascia
    for s, sx in sides:
        hs = "R" if sx > 0 else "L"
        h = [B.node(f"headlight_{hs}_{n}", p, f"headlight_{hs}", f"headlight_{hs}", cmat="plastic", flags=F_DETACH)
             for n, p in enumerate([(sx * 0.58, 2.25, 0.70), (sx * 0.74, 2.20, 0.70), (sx * 0.66, 2.16, 0.76)])]
        B.section(h, "lamp", diag=False)
        for q in h:
            for t in B.nearest(B.P(q), [core[k] for k in core] + list(panels["fascia"].ravel()), k=3, max_d=0.25):
                B.beam(q, t, "lamp_mount", bg=f"headlight_{hs}")
    return st


# =================================================================================================
# masses, wheels, cameras, parts
# =================================================================================================
def group_target(g):
    if g in T.GROUP_MASS:
        return T.GROUP_MASS[g]
    base = g.rsplit("_", 1)[0]
    for key in (base, g.split("_")[0], "_".join(g.split("_")[:2])):
        if key in T.GROUP_MASS:
            return T.GROUP_MASS[key]
    return None


def cell_stiffness(B, cell):
    """Sum of the spring constants (params.json) of the beams at each cell node."""
    import json
    import re
    path = os.path.join(PROJECT_ROOT, "sim", "vehicle", "hellcat", "params.json")
    text = re.sub(r"//[^\n]*", "", open(path, encoding="utf-8").read())
    k = {m["name"]: max(m.get("spring", 0.0), 0.0) for m in json.loads(text)["materials"]}
    tot = {}
    for bm in B.sk.beams:
        kb = k.get(bm["mat"], 0.0)
        tot[bm["a"]] = tot.get(bm["a"], 0.0) + kb
        tot[bm["b"]] = tot.get(bm["b"], 0.0) + kb
    return np.array([tot.get(i, 0.0) for i in cell])


def distribute_mass(B):
    sk = B.sk
    groups = {}
    for i, g in B.mgroup.items():
        groups.setdefault(g, []).append(i)
    fixed_total = 0.0
    for g, ids in groups.items():
        if g == "cell":
            continue
        tgt = group_target(g)
        if tgt is None:
            raise ValueError(f"no mass for group {g}")
        wsum = sum(B.weight[i] for i in ids)
        for i in ids:
            sk.nodes[i]["m"] = tgt * B.weight[i] / wsum
        # panels: minimum node mass for stability (the extra comes out of the body cell)
        for i in ids:
            if sk.nodes[i]["m"] < T.PANEL_NODE_MIN_MASS:
                sk.nodes[i]["m"] = T.PANEL_NODE_MIN_MASS
        fixed_total += sum(sk.nodes[i]["m"] for i in ids)
    cell = groups["cell"]
    rest = T.MASS_TOTAL - fixed_total
    if rest <= 0:
        raise ValueError(f"fixed groups exceed the total mass: {fixed_total:.1f} kg")
    # cell mass: weights scaled by the attached stiffness (D-031: a node carrying stiffer beams gets more mass, so the
    # local frequencies sqrt(sum k / m) even out and the stability measure S drops), then a linear tilt along y so
    # the centre of mass hits the 57 / 43 split
    ks = cell_stiffness(B, cell)
    cage = set(B.cage)
    med = float(np.median([k for i, k in zip(cell, ks) if i in cage]))
    boost = np.array([(max(k, 0.3 * med) / med) ** T.CELL_STIFFNESS_EXP if i in cage else 1.0 for i, k in zip(cell, ks)])
    # per-node multipliers from tools/skeleton/mass_balance.py (exact modes above the stability target, D-031)
    mb = os.path.join(os.path.dirname(__file__), "hskel_mass_boost.json")
    if os.path.exists(mb):
        import json
        extra = json.load(open(mb, encoding="utf-8"))
        names = [sk.nodes[i]["name"] for i in cell]
        boost = boost * np.array([extra.get(nm, 1.0) for nm in names])
    w = np.array([B.weight[i] for i in cell]) * boost      # panels in the cell group (quarters, roof) keep their weights
    y = np.array([sk.nodes[i]["p"][1] for i in cell])
    other_m = sum(sk.nodes[i]["m"] for g, ids in groups.items() if g != "cell" for i in ids)
    other_my = sum(sk.nodes[i]["m"] * sk.nodes[i]["p"][1] for g, ids in groups.items() if g != "cell" for i in ids)
    target_my = T.COM_Y_TARGET * T.MASS_TOTAL - other_my
    # m_i = rest * w_i (1 + a (y_i - ybar)) / sum(...): solve a for sum(m_i y_i) = target_my
    ybar = float(np.sum(w * y) / np.sum(w))
    wy = w * (y - ybar)
    a_num = target_my / rest * np.sum(w) - np.sum(w * y)
    a_den = np.sum(wy * y) - target_my / rest * np.sum(wy)
    a = float(a_num / a_den) if abs(a_den) > 1e-9 else 0.0
    a = float(np.clip(a, -0.2, 0.2))       # widened for the rigidifier mass boosts (D-040), which load the rear rails
    m = rest * w * (1 + a * (y - ybar))
    m = np.maximum(m, 0.5)
    m *= rest / m.sum()
    for i, mi in zip(cell, m):
        sk.nodes[i]["m"] = float(mi)
    return {"fixed_kg": round(fixed_total, 1), "cell_kg": round(rest, 1), "tilt": round(a, 4), "other_kg": round(other_m, 1)}


def windup_body(B, name):
    """Body nodes of a wheel's wind-up element (D-036): the inner pivots of its links (body-side ends of the arm, link and
    tie-rod beams from the knuckle nodes), the body nodes those pivots are mounted on, and the spring tower."""
    sk = B.sk
    names = [n["name"] for n in sk.nodes]
    knuckle = {sk.node_index[f"{name}_{k}"] for k in (("lbj", "ubj", "tre") if name[0] == "F" else ("klf", "klr", "kup"))}
    adj = {}
    for bm in sk.beams:
        adj.setdefault(bm["a"], []).append(bm)
        adj.setdefault(bm["b"], []).append(bm)
    body = lambda i: sk.nodes[i]["part"] == "body"
    other = lambda bm, i: bm["b"] if bm["a"] == i else bm["a"]
    pivots, mounts, tower = set(), set(), set()
    for k in knuckle:
        for bm in adj.get(k, []):
            j = other(bm, k)
            if body(j) and bm["mat"] in ("arm", "link", "tierod"):
                pivots.add(j)
            if body(j) and bm["mat"].startswith("spring_"):
                tower.add(j)
    for p in pivots:
        for bm in adj.get(p, []):
            j = other(bm, p)
            if body(j) and j not in pivots and bm["mat"] in ("subframe", "subframe_mount"):
                mounts.add(j)
    ids = sorted(pivots | mounts | tower)
    assert len(ids) >= 6, (name, [names[i] for i in ids])
    return ids


def register_wheels(B, st):
    for name, w in list(st["wheels_front"].items()) + list(st["wheels_rear"].items()):
        front = name[0] == "F"
        B.sk.wheel(name, w["ax_in"], w["ax_out"], w["rim_i"] + w["rim_o"], w["tread"], w["arm"], driven=not front,
                   steered=front, brake="front" if front else "rear", radius=0.352, pressure_group=f"tire_{name}",
                   drive_reaction=() if front else st["diff"], windup="front" if front else "rear",
                   windup_body=windup_body(B, name), kingpin=w.get("kingpin", ()))


VISUALS = {
    "body": ["CH_Quarter_L", "CH_Quarter_R", "CH_Roof", "CH_Pillars_L", "CH_Pillars_R", "CH_Rocker_L", "CH_Rocker_R",
             "CH_Cowl", "CH_FloorPan", "CH_Flare_rear_L", "CH_Flare_rear_R", "CH_SideSill_L", "CH_SideSill_R",
             "CH_WheelLiners_L", "CH_WheelLiners_R", "CH_TailPanel", "CH_TailLamp_Red", "CH_TailLamp_Lens",
             "CH_TailLamp_Bar", "CH_Badge_DODGE", "CH_FuelDoor", "CH_Antenna", "CH_Marker_Rear_L", "CH_Marker_Rear_R",
             "CH_Subframe_Front", "CH_Subframe_Rear", "CH_CoreSupport", "CH_DriveShaft", "CH_Differential", "CH_Glass_Frit"],
    # detachable assemblies on their own nodes (D-058)
    "radiator": ["CH_Radiator", "CH_RadiatorShroud"],
    "fuel_tank": ["CH_FuelTank"],
    "seat_FR": ["CH_Int_Seat_FR"], "seat_FL": ["CH_Int_Seat_FL"], "seat_rear": ["CH_Int_Seat_Rear"],
    "engine": ["CH_Engine", "CH_Engine_Pulleys", "CH_Transmission"],
    "hood": ["CH_Hood", "CH_Hood_Scoop", "CH_Hood_Scoop_Mesh", "CH_Hood_Extractor_L", "CH_Hood_Extractor_R",
             "CH_Hood_Extractor_Vent_L", "CH_Hood_Extractor_Vent_R"],
    "trunk": ["CH_DeckLid", "CH_Spoiler", "CH_Badge_SRT_Rear"],
    "door_FL": ["CH_Door_L", "CH_Door_Handle_L", "CH_Int_DoorCard_L"],
    "door_FR": ["CH_Door_R", "CH_Door_Handle_R", "CH_Int_DoorCard_R"],
    "fender_L": ["CH_Fender_L", "CH_Flare_front_L", "CH_Badge_Hellcat_L", "CH_Marker_Front_L"],
    "fender_R": ["CH_Fender_R", "CH_Flare_front_R", "CH_Badge_Hellcat_R", "CH_Marker_Front_R"],
    "bumper_F": ["CH_Bumper_F", "CH_Grille_Upper", "CH_Grille_Lower", "CH_Grille_Duct_L", "CH_Grille_Duct_R",
                 "CH_Splitter", "CH_Badge_SRT_Front"],
    "bumper_R": ["CH_Bumper_R", "CH_Valance", "CH_PlateRecess", "CH_Plate_Rear", "CH_Exhaust_Tips_L", "CH_Exhaust_Tips_R"],
    "headlight_L": ["CH_Headlamp_Housing_L", "CH_Headlamp_Reflector_L", "CH_Headlamp_Halo_L", "CH_Headlamp_Lens_L"],
    "headlight_R": ["CH_Headlamp_Housing_R", "CH_Headlamp_Reflector_R", "CH_Headlamp_Halo_R", "CH_Headlamp_Lens_R"],
    "mirror_L": ["CH_Mirror_Housing_L", "CH_Mirror_Glass_L", "CH_Mirror_Stalk_L"],
    "mirror_R": ["CH_Mirror_Housing_R", "CH_Mirror_Glass_R", "CH_Mirror_Stalk_R"],
    # each pane with its pre-fractured shards (hcar.glass_shards; Unity swaps them in when the pane's glass beams break)
    "glass_windshield": ["CH_Glass_Windshield", "CH_Glass_Windshield_Shards"],
    "glass_rear": ["CH_Glass_Rear", "CH_Glass_Rear_Shards"],
    "glass_side_FL": ["CH_Glass_Door_L", "CH_Glass_Door_L_Shards"], "glass_side_FR": ["CH_Glass_Door_R", "CH_Glass_Door_R_Shards"],
    "glass_quarter_L": ["CH_Glass_Quarter_L", "CH_Glass_Quarter_L_Shards"],
    "glass_quarter_R": ["CH_Glass_Quarter_R", "CH_Glass_Quarter_R_Shards"],
    "exhaust": ["CH_Exhaust_L", "CH_Exhaust_R"],
    # a visual listed by several parts binds to the nearest nodes of all of them (suspension parts
    # stretch between the body and the wheel; one knuckle object holds the front and rear knuckle)
    "wheel_FL": ["CH_Wheel_FL_Rim", "CH_Wheel_FL_Tire", "CH_Wheel_FL_Disc", "CH_Wheel_FL_Caliper", "CH_Knuckles_L",
                 "CH_Susp_Front_Arms_L", "CH_Susp_Front_Damper_L", "CH_Susp_Front_Spring_L"],
    "wheel_FR": ["CH_Wheel_FR_Rim", "CH_Wheel_FR_Tire", "CH_Wheel_FR_Disc", "CH_Wheel_FR_Caliper", "CH_Knuckles_R",
                 "CH_Susp_Front_Arms_R", "CH_Susp_Front_Damper_R", "CH_Susp_Front_Spring_R"],
    "wheel_RL": ["CH_Wheel_RL_Rim", "CH_Wheel_RL_Tire", "CH_Wheel_RL_Disc", "CH_Wheel_RL_Caliper", "CH_Knuckles_L",
                 "CH_Susp_Rear_Links_L", "CH_Susp_Rear_Damper_L", "CH_Susp_Rear_Spring_L", "CH_HalfShaft_L"],
    "wheel_RR": ["CH_Wheel_RR_Rim", "CH_Wheel_RR_Tire", "CH_Wheel_RR_Disc", "CH_Wheel_RR_Caliper", "CH_Knuckles_R",
                 "CH_Susp_Rear_Links_R", "CH_Susp_Rear_Damper_R", "CH_Susp_Rear_Spring_R", "CH_HalfShaft_R"],
    "suspension_body_side": ["CH_Susp_Front_Arms_L", "CH_Susp_Front_Arms_R", "CH_Susp_Front_Damper_L",
                             "CH_Susp_Front_Damper_R", "CH_Susp_Front_Spring_L", "CH_Susp_Front_Spring_R",
                             "CH_Susp_Rear_Links_L", "CH_Susp_Rear_Links_R", "CH_Susp_Rear_Damper_L",
                             "CH_Susp_Rear_Damper_R", "CH_Susp_Rear_Spring_L", "CH_Susp_Rear_Spring_R",
                             "CH_HalfShaft_L", "CH_HalfShaft_R"],
}


BRACES = os.path.join(os.path.dirname(__file__), "hskel_braces.json")

# Crush zones (D-057, Blender y forward): ahead of the front control-arm pivots and behind the rear subframe. No
# rigidifier may reach into them (a long beam from the core support to the trunk floor is a strut past the crush zone:
# the 50 km/h frontal stopped in 0.32 m at 56 g with them), and the designed braces inside them get their own material.
CRUSH_FRONT_Y = 1.6
CRUSH_REAR_Y = -2.0


def in_crush_zone(y):
    return y > CRUSH_FRONT_Y or y < CRUSH_REAR_Y


def add_braces(B):
    """Bracing designed by tools/skeleton/brace_design.py (compliance sensitivity, D-030): the shear webs of the
    inner fenders, wheel houses, quarter inner panels and parcel shelf, and cross members, as node-name pairs. Braces
    in a crush zone are "brace_crush" (D-057), tuned with the rails."""
    import json
    if not os.path.exists(BRACES):
        return 0
    n = 0
    for a, b in json.load(open(BRACES, encoding="utf-8")):
        if a in B.tags and b in B.tags:
            ia, ib = B.tags[a], B.tags[b]
            mid = 0.5 * (B.P(ia)[1] + B.P(ib)[1])
            B.beam(ia, ib, "brace_crush" if in_crush_zone(mid) else "brace")
            n += 1
    return n


RIGIDIFIERS = os.path.join(os.path.dirname(__file__), "hskel_rigidifiers.json")


def add_rigidifiers(B):
    """Rigidifiers designed by tools/skeleton/rigidifier_design.py (D-040): long invisible beams through the cabin and
    between the cabin and its ends that stand in for the closed-section shell stiffness of the real body, which the
    stability-limited node-beam cage cannot carry (torsion 1.1 -> ~6 kN m/deg, bending 0.18 -> ~1.8 kN/mm). They yield
    and break at moderate loads so the body still crumples in a crash; none reaches into a crush zone (D-057)."""
    import json
    if not os.path.exists(RIGIDIFIERS):
        return 0
    n = 0
    for a, b in json.load(open(RIGIDIFIERS, encoding="utf-8")):
        if a in B.tags and b in B.tags:
            ia, ib = B.tags[a], B.tags[b]
            if in_crush_zone(B.P(ia)[1]) or in_crush_zone(B.P(ib)[1]):
                continue
            B.beam(ia, ib, "rigidifier", allow_duplicate=True)
            n += 1
    return n


def build():
    B = Build()
    V = visual_grids()
    st = build_cage(B, V)
    st = build_front(B, st)
    st = build_rear(B, st)
    panels = build_panels(B, V, st)
    build_glass(B, V, st, panels)
    build_powertrain(B, st)
    build_rear_subframe(B, st)
    build_front_suspension(B, st)
    build_rear_suspension(B, st)
    build_aux(B, st, panels)
    register_wheels(B, st)
    add_braces(B)
    add_rigidifiers(B)
    # underbody collision: floor quads between sills and tunnel (outward = down)
    fl = st["floor"]
    for k in range(len(T.CABIN_Y) - 1):
        for s in ("R", "L"):
            quad = [st["sill"][s][k][0], st["sill"][s][k + 1][0], fl[s][k + 1], fl[s][k]]
            a, b, c, d = quad
            for tri in ((a, b, c), (a, c, d)):
                pa, pb, pc = (B.P(t) for t in tri)
                if np.cross(pb - pa, pc - pa)[2] > 0:
                    tri = (tri[0], tri[2], tri[1])
                B.sk.tri(*tri, group="body")
    # floor pan bending (D-032): hinges over the strips sill (inner bottom) - floor - tunnel, both sides
    ftris = []
    for k in range(len(T.CABIN_Y) - 1):
        for s in ("R", "L"):
            row0 = [st["sill"][s][k][1], fl[s][k], st["tunnel"][k]]
            row1 = [st["sill"][s][k + 1][1], fl[s][k + 1], st["tunnel"][k + 1]]
            for q in range(2):
                a, b, c, d = row0[q], row1[q], row1[q + 1], row0[q + 1]
                ftris += [{"a": a, "b": b, "c": c}, {"a": a, "b": c, "c": d}]
    B.hinge_tris(ftris, "floor_pan")
    add_damp_groups(B)
    mass = distribute_mass(B)
    # parts -> visuals (the body-side ends of the suspension parts bind to body nodes)
    for part, vis in VISUALS.items():
        for v in vis:
            B.sk.link_visual("body" if part == "suspension_body_side" else part, v)
    # cameras: cockpit eye on the driver's cabin nodes, chase target on the cell
    from .interior_tables import EYE
    cam_nodes = [st["sill"]["L"][3][2], st["rail"]["L"][3][1], st["rail"]["L"][7][1], st["tunnel"][4]]
    B.sk.camera("cockpit", cam_nodes, tuple(np.array(EYE) - B.P(cam_nodes[0])))
    B.sk.camera("chase_target", [st["sill"]["L"][4][2], st["sill"]["R"][4][2], st["sill"]["L"][6][2]], (0.0, 0.0, 1.0))
    B.sk.camera("bumper", [st["bbF"][1][0][0], st["bbF"][1][2][0], st["bbF"][1][2][1]], (0.0, 0.0, 0.25))
    return B, st, mass


WHEEL_RINGS = ("rimI", "rimO", "trI", "trC", "trO")  # node rings of a wheel, the names end in the section index

DAMP_GROUPS = [   # (group, node-name prefixes, material, break group that ends the damping, reference, reference ends)
    # attached parts are also damped towards the body's (side glass: the door's) rigid motion until their latch / hinges /
    # clips / hangers break (D-038)
    ("roof", ("roof_",), "skin", "", "body", ()), ("hood", ("hood_o_", "hood_i_"), "skin", "", "body", ("hood", "hood_latch")),
    ("trunk", ("trunk_o_", "trunk_i_"), "skin", "", "body", ("trunk", "trunk_latch")),
    ("door_FL", ("door_FL_o_", "door_FL_i_"), "skin", "", "body", ("door_FL", "door_FL_latch")),
    ("door_FR", ("door_FR_o_", "door_FR_i_"), "skin", "", "body", ("door_FR", "door_FR_latch")),
    ("fender_L", ("fender_L_",), "skin", "", "body", ()), ("fender_R", ("fender_R_",), "skin", "", "body", ()),
    ("quarter_L", ("quarter_L_",), "skin", "", "body", ()), ("quarter_R", ("quarter_R_",), "skin", "", "body", ()),
    ("fascia", ("fascia_",), "plastic", "", "body", ("bumper_F",)), ("rbumper", ("rbumper_",), "plastic", "", "body", ("bumper_R",)),
    ("glass_windshield", ("glass_windshield_",), "glass", "glass_windshield", "body", ()),
    ("glass_rear", ("glass_rear_",), "glass", "glass_rear", "body", ()),
    ("glass_side_FL", ("glass_side_FL_",), "glass", "glass_side_FL", "door_FL", ()),
    ("glass_side_FR", ("glass_side_FR_",), "glass", "glass_side_FR", "door_FR", ()),
    ("glass_quarter_L", ("glass_quarter_L_",), "glass", "glass_quarter_L", "body", ()),
    ("glass_quarter_R", ("glass_quarter_R_",), "glass", "glass_quarter_R", "body", ()),
    ("exhaust", ("exh",), "exhaust", "", "body", ("exhaust",)),
    # wheels (D-033, P3): rim rings + tread, damped towards the wheel's own rigid motion (translation and spin are not
    # damped): tire carcass hysteresis. Without it a front-tire tread mode rang for seconds after a drop (zeta ~0.005).
    # The exact ring prefixes: "FR_tr" also matched the knuckle's tie-rod end FR_tre, a node that does not spin
    # (D-046: it offset the ring-beam spin tension and cost the front wheels a once-per-revolution hop at speed)
    *((f"wheel_{w}", tuple(f"{w}_{ring}" for ring in WHEEL_RINGS), "tire", "", "", ()) for w in ("FL", "FR", "RL", "RR")),
]


def add_damp_groups(B):
    """Deformation damping groups (D-033): one per panel / pane, damped towards its own rigid motion, and the body
    structure (cell, frame, interior, powertrain, body-side suspension mounts) as one group, so its low flexible
    modes get mass-proportional damping (beam damping is stiffness-proportional: together Rayleigh damping) while the
    rigid body, the suspension and the wheels are not damped. Detachable parts leave the body group when their
    break group fires."""
    names = [n["name"] for n in B.sk.nodes]
    used = set()
    for g, prefixes, mat, bg, ref, ref_bg in DAMP_GROUPS:
        ids = [i for i, nm in enumerate(names) if nm.startswith(prefixes)]
        if len(ids) >= 4:
            B.sk.damp_group(g, ids, mat, bg, reference=ref, ref_bg=ref_bg)
            used.update(ids)
    detach = {"engine": "engine_mount", "mirror_L": "mirror_L", "mirror_R": "mirror_R", "headlight_L": "headlight_L",
              "headlight_R": "headlight_R", "radiator": "radiator", "fuel_tank": "fuel_tank", "seat_FR": "seat_FR",
              "seat_FL": "seat_FL"}
    body, node_bg = [], {}
    for i, n in enumerate(B.sk.nodes):
        if i in used or n["part"] not in ("body", "seat_rear") + tuple(detach):
            continue
        if "_tip_" in n["name"]:                       # anti-roll bar levers move with the wheels
            continue
        body.append(i)
        if n["part"] in detach:
            node_bg[i] = detach[n["part"]]
    B.sk.damp_group("body", body, "structure", "", node_bg)


def category(mat, btype):
    if btype == "HYDRO":
        return "hydro"
    for prefix, cat in (("brace_crush", "crush"), ("tire", "tire"), ("rim", "rim"), ("glass", "glass"), ("plastic", "plastic"), ("clip", "plastic"),
                        ("panel", "panel"), ("weld", "panel"), ("stop", "panel"), ("crush", "crush"), ("rail_f", "crush"),
                        ("bumper", "crush"), ("rail_r", "crush"), ("spring", "suspension"), ("damper", "suspension"),
                        ("bumpstop", "suspension"), ("arm", "suspension"), ("link", "suspension"), ("arb", "suspension"),
                        ("tierod", "suspension"), ("rack", "suspension"), ("kmember", "suspension"), ("knuckle", "rim"), ("mount", "mount"),
                        ("hinge", "mount"), ("latch", "mount"), ("bolt", "mount"), ("seat_mount", "mount"),
                        ("exhaust_hanger", "mount"), ("tank_strap", "mount"), ("subframe_mount", "mount")):
        if mat.startswith(prefix):
            return cat
    return "rigid"


def main(viz=True, save=False):
    import json
    import time
    t0 = time.time()
    B, st, mass = build()
    sk = B.sk
    size = sk.write(OUT_SIM, OUT_UNITY)
    stats = sk.stats()
    res = {"stats": stats, "mass": mass, "bytes": size, "seconds": round(time.time() - t0, 1)}
    if viz:
        from . import blend_util as bu
        from . import debugviz
        root = bu.collection("Car_Physics")
        res["viz"] = debugviz.build(sk, "PH_Hellcat", category, parent=root, tube_radius=0.004, node_radius=0.010)
        if save:
            res["blend"] = bu.save_version("P2 skeleton")
    with open(os.path.join(PROJECT_ROOT, "sim", "vehicle", "hellcat", "skeleton_stats.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    return res
