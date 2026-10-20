"""Viewport and render shots of the work, saved as PNG files (for checks and the YouTube video)."""
import math
import os

import bpy
from mathutils import Euler, Matrix, Vector

from . import PROJECT_ROOT


def _view3d():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                region = next(r for r in area.regions if r.type == "WINDOW")
                return window, area, region, area.spaces.active
    raise RuntimeError("no 3D viewport")


_LAST_VIEW = {}


def set_view(target=(0.0, 0.0, 0.6), distance=8.0, elevation_deg=25.0, azimuth_deg=-40.0, shading="SOLID",
             ortho=False, lens=50.0, color_type="OBJECT", overlays=True):
    """Orbit view: azimuth 0 = eye on the +X side (car's right), 90 = eye in front (+Y).
    Updates the user's viewport and remembers the view for viewport_png (which renders it through
    its own camera, so the result does not depend on viewport redraws)."""
    _, _, _, space = _view3d()
    r3d = space.region_3d
    r3d.view_location = Vector(target)
    r3d.view_distance = distance
    el = math.radians(elevation_deg)
    az = math.radians(azimuth_deg)
    # The view looks along its local -Z; eye direction from the target = (cos el cos az, cos el sin az, sin el).
    rot = Euler((math.pi / 2 - el, 0.0, math.pi / 2 + az), "XYZ")
    r3d.view_rotation = rot.to_quaternion()
    r3d.view_perspective = "ORTHO" if ortho else "PERSP"
    space.lens = lens
    space.shading.type = shading
    if shading == "SOLID":
        space.shading.color_type = color_type
    space.overlay.show_overlays = overlays
    _LAST_VIEW.update(target=tuple(target), distance=distance, rot=rot, ortho=ortho, lens=lens)
    return {"view": [target, distance, elevation_deg, azimuth_deg, shading]}


def _shot_camera():
    """Hidden camera that reproduces the last set_view (perspective lens or ortho framing)."""
    cam_data = bpy.data.cameras.get("HC_ShotCam") or bpy.data.cameras.new("HC_ShotCam")
    cam = bpy.data.objects.get("HC_ShotCam")
    if cam is None:
        cam = bpy.data.objects.new("HC_ShotCam", cam_data)
    v = _LAST_VIEW
    rot = v["rot"].to_matrix().to_4x4()
    # orthographic: the framing is set by ortho_scale, so stand far back (outside the car)
    back = v["distance"] + (30.0 if v["ortho"] else 0.0)
    loc = Vector(v["target"]) + v["rot"].to_matrix() @ Vector((0.0, 0.0, back))
    cam.matrix_world = Matrix.Translation(loc) @ rot
    cam_data.sensor_fit = "AUTO"
    cam_data.sensor_width = 72.0  # Blender viewport convention: lens is relative to a 72 mm sensor
    cam_data.lens = v["lens"]
    cam_data.clip_start = 0.01
    cam_data.clip_end = 500.0
    if v["ortho"]:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = 2.0 * v["distance"]
    else:
        cam_data.type = "PERSP"
    return cam


def hide_startup_objects():
    """The original file is Blender's startup scene; its Cube is not part of the car."""
    removed = []
    cube = bpy.data.objects.get("Cube")
    if cube is not None and cube.type == "MESH" and len(cube.data.vertices) == 8:
        bpy.data.objects.remove(cube, do_unlink=True)
        removed.append("Cube")
    return removed


def viewport_png(path, max_size=1400):
    """Offscreen draw of the 3D viewport (works when the window is not in the foreground)."""
    import gpu
    import numpy as np
    window, area, region, space = _view3d()
    r3d = space.region_3d
    w, h = region.width, region.height
    s = min(1.0, max_size / max(w, h))
    w2, h2 = max(1, int(w * s)), max(1, int(h * s))
    if _LAST_VIEW:
        cam = _shot_camera()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        view_m = cam.matrix_world.inverted()
        proj_m = cam.calc_matrix_camera(depsgraph, x=w2, y=h2)
    else:
        view_m, proj_m = r3d.view_matrix, r3d.window_matrix
    off = gpu.types.GPUOffScreen(w2, h2)
    try:
        with bpy.context.temp_override(window=window, area=area, region=region):
            off.draw_view3d(bpy.context.scene, bpy.context.view_layer, space, region,
                            view_m, proj_m, do_color_management=True)
        buf = off.texture_color.read()
    finally:
        off.free()
    buf.dimensions = w2 * h2 * 4
    px = np.asarray(buf, dtype=np.float32) / 255.0
    img = bpy.data.images.new("hc_viewshot", w2, h2, alpha=True)
    img.pixels.foreach_set(px.ravel())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return {"png": path, "size": [w2, h2]}


def shot(path, **view):
    set_view(**view)
    return viewport_png(path)


def isolate(collections=("Car_Visual_WIP",)):
    """Show only the given top-level collections (viewport visibility), hide the rest."""
    lc = bpy.context.view_layer.layer_collection
    shown = []
    for child in lc.children:
        vis = child.name in collections
        child.hide_viewport = not vis
        if vis:
            shown.append(child.name)
    for obj in bpy.context.scene.collection.objects:
        obj.hide_set(True)
    return {"shown": shown}


def shots(folder, prefix, views, max_size=1400):
    """Several named views in one call: views = {name: dict(set_view kwargs)}."""
    out = {}
    for name, v in views.items():
        set_view(**v)
        out[name] = viewport_png(os.path.join(folder, f"{prefix}_{name}.png"), max_size)["png"]
    return out


STD_VIEWS = {
    "fl34": dict(target=(0.0, 0.2, 0.6), distance=7.0, elevation_deg=12, azimuth_deg=125, shading="MATERIAL", overlays=False),
    "fr34": dict(target=(0.0, 0.2, 0.6), distance=7.0, elevation_deg=12, azimuth_deg=55, shading="MATERIAL", overlays=False),
    "rl34": dict(target=(0.0, -0.2, 0.6), distance=7.0, elevation_deg=12, azimuth_deg=-125, shading="MATERIAL", overlays=False),
    "rr34": dict(target=(0.0, -0.2, 0.6), distance=7.0, elevation_deg=12, azimuth_deg=-55, shading="MATERIAL", overlays=False),
    # orthographic views: the image width is 2 * distance metres
    "side": dict(target=(0.0, -0.07, 0.75), distance=2.8, elevation_deg=0, azimuth_deg=0, shading="MATERIAL", overlays=False, ortho=True),
    "front": dict(target=(0.0, 0.0, 0.75), distance=1.25, elevation_deg=0, azimuth_deg=90, shading="MATERIAL", overlays=False, ortho=True),
    "rear": dict(target=(0.0, 0.0, 0.75), distance=1.25, elevation_deg=0, azimuth_deg=-90, shading="MATERIAL", overlays=False, ortho=True),
    "top": dict(target=(0.0, -0.07, 0.75), distance=2.8, elevation_deg=90, azimuth_deg=0, shading="MATERIAL", overlays=False, ortho=True),
}


def std_shots(prefix, names=None, folder=None, max_size=1400):
    folder = folder or os.path.join(PROJECT_ROOT, "_cache", "shots")
    views = {k: v for k, v in STD_VIEWS.items() if names is None or k in names}
    return shots(folder, prefix, views, max_size)
