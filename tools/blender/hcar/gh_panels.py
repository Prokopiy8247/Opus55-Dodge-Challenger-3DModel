"""Panels of the greenhouse loft and of the caps (pure numpy).

Greenhouse loft parameters: s = y - GH_Y[0], t with knots B 0, A 0.42, I 0.58, C 1.0.
    side glass   t in [0, A] where the DLO exists (split into door glass and quarter glass)
    pillars/rails/sails (body colour)   t in [A, I] between the glass corners
    roof (matte black)   t in [I, C] between the rear-glass top and the windshield top
    windshield / rear glass   height fields over plan Coons patches, z taken from the loft
Caps: hood (matte black) and deck lid (white) panels with gaps.
"""
import numpy as np

from . import body_tables as bt
from .panels import CapSurface, Panel, StripSurface, coons

KA, KI = bt.GH_KNOTS[1], bt.GH_KNOTS[2]


def _iso_t(s0, s1, t, n=80):
    return np.stack([np.linspace(s0, s1, n), np.full(n, t)], axis=1)


def _iso_s(s, t0, t1, n=40):
    return np.stack([np.full(n, s), np.linspace(t0, t1, n)], axis=1)


def greenhouse_panels(m, edge=0.025, gap=0.004):
    gh = m["gh"]
    O = gh.O
    surf = StripSurface(gh, ds=0.004, nt=1001)
    sy = O.s_side_y
    out = {}
    # side window: DLO from its rear tip to its front tip, door / quarter split at the door's rear cut
    s_r, s_f = sy(-0.962), sy(0.596)          # front tip stops 6 mm short of the door top corner
    s_split = sy(-0.640)
    glass_off = lambda a, b: np.full(np.broadcast(a, b).shape, -0.004)  # noqa: E731  glass sits 4 mm inboard
    # the lower glass edge runs into the belt slot: no rolled edge there (it would cross the door's)
    gfl = dict(bottom=False, right=True, top=True, left=True)
    out["CH_Glass_Door"] = Panel("CH_Glass_Door", surf, _iso_t(s_split, s_f, 0.0), _iso_s(s_f, 0.0, KA),
                                 _iso_t(s_split, s_f, KA), _iso_s(s_split, 0.0, KA), edge=edge, gap=gap,
                                 flange=(0.002, 0.005), offset=glass_off, flange_sides=gfl)
    out["CH_Glass_Quarter"] = Panel("CH_Glass_Quarter", surf, _iso_t(s_r, s_split, 0.0), _iso_s(s_split, 0.0, KA),
                                    _iso_t(s_r, s_split, KA), _iso_s(s_r, 0.0, KA), edge=edge, gap=gap,
                                    flange=(0.002, 0.005), offset=glass_off, flange_sides=gfl)
    # pillars, rails and sails: band [A, I] between the rear-glass and windshield base corners
    s0, s1 = sy(-1.622), sy(0.846)
    out["CH_Pillars"] = Panel("CH_Pillars", surf, _iso_t(s0, s1, KA), _iso_s(s1, KA, KI), _iso_t(s0, s1, KI),
                              _iso_s(s0, KA, KI), edge=edge, gap=0.0, inset=dict(bottom=False, top=False,
                                                                                    left=False, right=False))
    # roof between the rear-glass top and the windshield top (matte black wrap): a 2 mm hairline
    # towards the pillars, so the inward thickness of the two panels (which meet at the convex roof
    # edge) never crosses
    s0, s1 = sy(-1.240), sy(0.287)
    out["CH_Roof"] = Panel("CH_Roof", surf, _iso_t(s0, s1, KI), _iso_s(s1, KI, 1.0), _iso_t(s0, s1, 1.0),
                           _iso_s(s0, KI, 1.0), edge=edge, gap=0.004,
                           inset=dict(bottom=True, top=False, left=False, right=False),
                           flange_sides=dict(bottom=False, top=False, left=False, right=False))
    return out


def cap_panels(m, edge=0.025, gap=0.005):
    """Hood and deck lid as panels on their height fields (a = x, b = y)."""
    out = {}
    hood = m["hood"]
    o = hood.outline
    surf = CapSurface(hood)
    rear = o["rear"][:, :2]                                   # centre -> rear corner
    side = o["side"][:, :2]                                   # rear corner -> front corner
    front = o["front"][:, :2][::-1]                           # centre -> front corner
    left = np.stack([np.zeros(60), np.linspace(rear[0, 1], front[0, 1], 60)], axis=1)
    out["CH_Hood"] = Panel("CH_Hood", surf, rear, side, front, left, edge=edge, gap=gap,
                           inset=dict(left=False), flange=(0.003, 0.012))
    deck = m["deck"]
    P = deck.outline["side"][:, :2]                           # rear centre -> rear corner -> side -> front
    i_c = int(np.argmin(np.abs(P[:, 1] - (-2.36)) + (P[:, 0] < 0.6)))
    bottom = P[:i_c + 1]
    top = deck.outline["front"][:, :2]                        # rear-window base, centre -> corner
    right = P[i_c:]
    right = np.vstack([right[right[:, 1] < top[-1, 1] - 0.03], top[-1]])   # end at the glass base corner
    left = np.stack([np.zeros(60), np.linspace(bottom[0, 1], top[0, 1], 60)], axis=1)
    out["CH_DeckLid"] = Panel("CH_DeckLid", CapSurface(deck), bottom, right, top, left, edge=edge, gap=gap,
                              inset=dict(left=False), flange=(0.003, 0.012))
    return out


# ------------------------------------------------------------------------------------------------
def loft_z(gh, x, y):
    """Height of the greenhouse loft above (x, y) on its I -> C part (windshield / rear-glass area)."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    z = np.empty_like(x)
    for k in range(x.size):
        s = gh.O.s_side_y(float(y.flat[k]))
        sec = gh.section(s)
        t, p = sec["t"], sec["p"]
        m = t >= KI - 1e-9
        xs = p[m, 0] + gh.O.x0   # h -> x
        zs = p[m, 1]
        o = np.argsort(xs)
        z.flat[k] = np.interp(float(x.flat[k]), xs[o], zs[o])
    return z


def glass_patch(m, which, nu=34, nv=30, inset=0.006):
    """Windshield or rear glass: plan Coons patch of the opening (centreline, base, side edge, top)
    with z from the loft, inset by `inset` along -z (approx. along the normal for these slopes)."""
    gh = m["gh"]
    O = gh.O
    from .shape import FeatureCurve
    I = FeatureCurve(bt.GH_CURVES["I"]).p
    B = FeatureCurve(bt.GH_CURVES["B"]).p
    # the glass edges tuck 15-20 mm under the roof (y_top) and the pillars, so no gap shows
    if which == "front":
        y_top, y_corner = 0.270, 0.846
        base = B[B[:, 1] >= y_corner - 1e-6]                     # base corner -> centre
        base = base[np.argsort(-base[:, 0])][::-1]              # centre -> corner
        side = I[(I[:, 1] >= y_top - 0.02) & (I[:, 1] <= y_corner + 1e-6)]
        side = side[np.argsort(-side[:, 1])]                    # base corner -> top
        x_top = float(np.interp(y_top, side[::-1, 1], side[::-1, 0]))
        top = np.stack([np.linspace(0, x_top, 40), np.full(40, y_top)], axis=1)
        bottom = base[:, :2]
        left = np.stack([np.zeros(40), np.linspace(bottom[0, 1], y_top, 40)], axis=1)
        right = side[:, :2]
        right = right[right[:, 1] >= y_top]
        right = np.vstack([right, [x_top, y_top]])
    else:
        y_top, y_corner = -1.225, -1.622
        base = B[B[:, 1] <= y_corner + 1e-6]
        base = base[np.argsort(base[:, 0])]                     # centre -> corner
        side = I[(I[:, 1] <= y_top + 0.02) & (I[:, 1] >= y_corner - 1e-6)]
        side = side[np.argsort(side[:, 1])]                     # base corner -> top
        x_top = float(np.interp(y_top, side[:, 1], side[:, 0]))
        top = np.stack([np.linspace(0, x_top, 40), np.full(40, y_top)], axis=1)
        bottom = base[:, :2]
        left = np.stack([np.zeros(40), np.linspace(bottom[0, 1], y_top, 40)], axis=1)
        right = side[:, :2]
        right = right[right[:, 1] <= y_top]
        right = np.vstack([right, [x_top, y_top]])
    from .panels import polyline_arclen

    def rs(c, n):
        c = np.asarray(c, float)
        s = polyline_arclen(c)
        q = np.linspace(0, s[-1], n)
        return np.stack([np.interp(q, s, c[:, 0]), np.interp(q, s, c[:, 1])], axis=1)
    # small margin inside the opening (the glass edge sits under the frame)
    G = coons(rs(bottom, nu), rs(top, nu), rs(left, nv), rs(right, nv))
    z = loft_z(gh, G[..., 0], G[..., 1]) - inset
    # at the lower outer corner the A/C-pillar base folds down over the glass edge: let the glass
    # dip up to 16 mm there so it stays below the pillar's thickness
    u = np.linspace(0, 1, nu)[:, None]
    v = np.linspace(0, 1, nv)[None, :]
    w = np.clip((u - 0.8) / 0.2, 0, 1) * np.clip(1 - v / 0.3, 0, 1)
    z = z - 0.016 * w * w * (3 - 2 * w)
    P = np.concatenate([G, z[..., None]], axis=-1)
    return P
