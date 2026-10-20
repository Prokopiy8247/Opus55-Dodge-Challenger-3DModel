"""Shapes and corner points of the panel grids (venv python; no Blender needed)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import numpy as np  # noqa: E402
from hcar import body  # noqa: E402
from hcar.body_panels import bumper_panels, side_panels  # noqa: E402
from hcar.gh_panels import cap_panels, glass_patch, greenhouse_panels  # noqa: E402
from hcar.flares import flare_panel  # noqa: E402

m = body.model()
panels = dict(side_panels(m))
panels.update(bumper_panels(m))
panels.update(greenhouse_panels(m))
panels.update(cap_panels(m))
out = {}
for k, p in panels.items():
    P = p.mesh()["P"]
    nu, nv = P.shape[:2]
    out[k] = {"shape": [nu, nv], "c00": P[0, 0].round(3).tolist(), "cN0": P[-1, 0].round(3).tolist(),
              "c0N": P[0, -1].round(3).tolist(), "cNN": P[-1, -1].round(3).tolist(),
              "mid": P[nu // 2, nv // 2].round(3).tolist()}
for which in ("front", "rear"):
    G = glass_patch(m, which)
    out[f"glass_{which}"] = {"shape": list(G.shape[:2]), "c00": G[0, 0].round(3).tolist(), "cN0": G[-1, 0].round(3).tolist(),
                             "c0N": G[0, -1].round(3).tolist(), "cNN": G[-1, -1].round(3).tolist()}
for which in ("front", "rear"):
    P = flare_panel(m["strip"], which).mesh()["P"]
    out[f"flare_{which}"] = {"shape": list(P.shape[:2]), "c00": P[0, 0].round(3).tolist(), "cNN": P[-1, -1].round(3).tolist()}
print(json.dumps(out, indent=0))
