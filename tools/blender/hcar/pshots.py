"""Physics-skeleton shots: the node-beam debug collection alone, and composited over the painted car
(skeleton pass on a transparent background, alpha-blended over the beauty pass)."""
import os

import bpy

from . import render as R

VIEWS = {
    "front34": dict(target=(0.0, 0.10, 0.55), distance=7.0, elevation_deg=16.0, azimuth_deg=128.0, lens=50.0),
    "rear34": dict(target=(0.0, -0.20, 0.55), distance=7.0, elevation_deg=16.0, azimuth_deg=-52.0, lens=50.0),
    "side": dict(target=(0.0, -0.05, 0.60), distance=8.2, elevation_deg=2.0, azimuth_deg=0.0, lens=55.0),
    "top": dict(target=(0.0, -0.05, 0.40), distance=9.0, elevation_deg=89.0, azimuth_deg=0.0, lens=50.0),
    "under": dict(target=(0.0, 0.0, 0.30), distance=7.5, elevation_deg=-28.0, azimuth_deg=140.0, lens=50.0),
}
CAR_COLS = ("Car_Visual", "Car_Interior")


def _set_visible(cols, visible):
    """Include / exclude the named layer collections together with their whole subtree."""
    lc = bpy.context.view_layer.layer_collection
    stack = list(lc.children)
    while stack:
        c = stack.pop()
        if c.name in cols:
            sub = [c]
            while sub:
                s = sub.pop()
                s.exclude = not visible
                sub.extend(s.children)
            continue
        stack.extend(c.children)


def shots_blender(folder, prefix, names=None, samples=32, res=(1920, 1080), hide_cats=()):
    """Renders <prefix>_<view>_car.png (beauty, physics hidden) and <prefix>_<view>_skel.png
    (skeleton only, transparent) for each view; compositing runs in the venv. hide_cats: beam
    categories (PH_Beams_<cat>; "nodes" for PH_Nodes) left out of the skeleton pass, e.g. the skin for
    a structure-only view."""
    os.makedirs(folder, exist_ok=True)
    out = {}
    floor = bpy.data.objects.get("HC_Floor")
    hidden = [o for o in (bpy.data.objects.get("PH_Nodes" if c == "nodes" else f"PH_Beams_{c}") for c in hide_cats)
              if o is not None]
    for o in hidden:
        o.hide_render = True
    try:
        for name, cam in VIEWS.items():
            if names and name not in names:
                continue
            # beauty pass (views from below the floor plane render the car without it)
            _set_visible(("Car_Physics",), False)
            _set_visible(CAR_COLS, True)
            if floor is not None:
                floor.hide_render = cam["elevation_deg"] < 0
            R.eevee(samples, res)
            p_car = os.path.join(folder, f"{prefix}_{name}_car.png")
            R.still(p_car, **cam)
            # skeleton pass: Standard view transform keeps the category colours saturated (AgX pulls
            # bright saturated colours toward white)
            _set_visible(("Car_Physics",), True)
            _set_visible(CAR_COLS, False)
            if floor is not None:
                floor.hide_render = True
            R.eevee(samples, res, film_transparent=True)
            vs = bpy.context.scene.view_settings
            vs.view_transform, vs.look = "Standard", "None"
            bpy.context.scene.render.image_settings.color_mode = "RGBA"
            p_sk = os.path.join(folder, f"{prefix}_{name}_skel.png")
            R.still(p_sk, **cam)
            bpy.context.scene.render.film_transparent = False
            bpy.context.scene.render.image_settings.color_mode = "RGB"
            if floor is not None:
                floor.hide_render = False
            out[name] = (p_car, p_sk)
    finally:
        _set_visible(CAR_COLS, True)
        _set_visible(("Car_Physics",), False)
        vs = bpy.context.scene.view_settings
        vs.view_transform, vs.look = "AgX", "AgX - Medium High Contrast"
        if floor is not None:
            floor.hide_render = False
        for o in hidden:
            o.hide_render = False
    return out
