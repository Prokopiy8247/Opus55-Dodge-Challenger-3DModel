"""P3b video assets: the front suspension of the rebuilt skeleton (K-member, tie rods, anti-roll-bar links, knuckles) with
only the running-gear beam categories shown, and the composite over the painted car."""
import os
from hcar import hskel, pshots

hskel.main(viz=True, save=False)        # debug view with the kmember category
pshots.VIEWS["front_susp"] = dict(target=(0.0, 1.50, 0.30), distance=3.0, elevation_deg=-14.0, azimuth_deg=145.0, lens=35.0)
pshots.VIEWS["front_susp_top"] = dict(target=(0.0, 1.50, 0.30), distance=3.4, elevation_deg=88.0, azimuth_deg=180.0, lens=35.0)
root = os.path.abspath(os.path.join(os.path.dirname(pshots.__file__), "..", "..", ".."))
out = pshots.shots_blender(os.path.join(root, "docs", "video_assets", "P3b"), "2026-10-13_P3b_frontsusp",
                           names=["front_susp", "front_susp_top"], samples=24,
                           hide_cats=("panel", "glass", "plastic", "rigid", "crush", "tire", "nodes"))
print(out)
