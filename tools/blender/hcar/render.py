"""Look-dev renders (EEVEE): HDRI world, showroom floor, scene camera, still images to files."""
import math
import os

import bpy
from mathutils import Euler, Matrix, Vector

from . import PROJECT_ROOT

HDRI = {
    "studio": "assets/hdri/studio_small_09_2k.hdr",
    "sky": "assets/hdri/kloofendal_48d_partly_cloudy_puresky_2k.hdr",
    "warehouse": "assets/hdri/empty_warehouse_01_2k.hdr",
}


def world_hdri(key="studio", strength=1.0, rotation_deg=0.0):
    path = os.path.join(PROJECT_ROOT, HDRI.get(key, key))
    world = bpy.data.worlds.get("HC_World") or bpy.data.worlds.new("HC_World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(rotation_deg))
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    img = bpy.data.images.get(os.path.basename(path)) or bpy.data.images.load(path, check_existing=True)
    env.image = img
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return {"world": world.name, "hdri": path}


def floor(size=40.0, color=(0.55, 0.55, 0.56), roughness=0.25):
    """Large glossy tiled floor (showroom look), at z = 0."""
    from .blend_util import collection, material
    from .meshkit import to_blender
    import numpy as np
    col = collection("HC_Stage")
    V = np.array([(-size, -size, 0), (size, -size, 0), (size, size, 0), (-size, size, 0)], float)
    F = np.array([[0, 1, 2, 3]])
    o = to_blender("HC_Floor", V, F, col=col, smooth=False)
    mat = material("HC_Floor_Tiles", color, roughness=roughness)
    nt = mat.node_tree
    if not any(n.type == "TEX_BRICK" for n in nt.nodes):
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        tc = nt.nodes.new("ShaderNodeTexCoord")
        br = nt.nodes.new("ShaderNodeTexBrick")
        br.inputs["Scale"].default_value = 0.85
        br.inputs["Mortar Size"].default_value = 0.004
        br.inputs["Bias"].default_value = 0.0
        br.offset = 0.0
        br.inputs["Color1"].default_value = (*color, 1)
        br.inputs["Color2"].default_value = (color[0] * 0.95, color[1] * 0.95, color[2] * 0.95, 1)
        br.inputs["Mortar"].default_value = (0.35, 0.35, 0.36, 1)
        nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
        nt.links.new(br.outputs["Color"], bsdf.inputs["Base Color"])
    o.data.materials.append(mat)
    return o.name


def camera(target=(0, 0, 0.6), distance=7.0, elevation_deg=10.0, azimuth_deg=125.0, lens=50.0, ortho=False,
           sensor=36.0, name="HC_Camera"):
    from .blend_util import collection
    col = collection("HC_Stage")
    data = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, data)
        col.objects.link(cam)
    el, az = math.radians(elevation_deg), math.radians(azimuth_deg)
    rot = Euler((math.pi / 2 - el, 0.0, math.pi / 2 + az), "XYZ")
    back = distance + (30.0 if ortho else 0.0)
    cam.matrix_world = Matrix.Translation(Vector(target) + rot.to_matrix() @ Vector((0, 0, back))) @ rot.to_matrix().to_4x4()
    data.sensor_fit = "HORIZONTAL"
    data.sensor_width = sensor
    data.lens = lens
    data.clip_start, data.clip_end = 0.05, 500.0
    data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        data.ortho_scale = 2 * distance
    bpy.context.scene.camera = cam
    return cam


def eevee(samples=64, res=(1920, 1080), film_transparent=False):
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            continue
    ee = sc.eevee
    for attr, val in (("taa_render_samples", samples), ("use_raytracing", True), ("use_shadows", True)):
        if hasattr(ee, attr):
            try:
                setattr(ee, attr, val)
            except Exception:
                pass
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = film_transparent
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    return sc.render.engine


def still(path, **cam):
    """Render the scene camera to a PNG (creates the camera from keyword arguments if given)."""
    if cam:
        camera(**cam)
    sc = bpy.context.scene
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc.render.filepath = path
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    return {"png": path}


def photo_match(cam_json, path, samples=32, hide=()):
    """Render the car from a solved photo camera (tools/ref/photo_pnp.py, tools/ref/interior_pnp.py)
    with a transparent background at the photo's resolution (for the overlay). hide: objects left out
    of this render (e.g. seats between an interior camera and the dash)."""
    import json
    with open(cam_json, encoding="utf-8") as f:
        cj = json.load(f)
    hidden = []
    for n in hide:
        o = bpy.data.objects.get(n)
        if o is not None and not o.hide_render:
            o.hide_render = True
            hidden.append(o)
    W, H = cj["size"]
    data = bpy.data.cameras.get("HC_PhotoCam") or bpy.data.cameras.new("HC_PhotoCam")
    cam = bpy.data.objects.get("HC_PhotoCam")
    if cam is None:
        from .blend_util import collection
        cam = bpy.data.objects.new("HC_PhotoCam", data)
        collection("HC_Stage").objects.link(cam)
    cam.matrix_world = Matrix(cj["matrix_world"])
    data.sensor_fit = "HORIZONTAL"
    data.sensor_width = 36.0
    data.lens = cj["lens_mm_36"]
    data.clip_start = 0.05
    sc = bpy.context.scene
    sc.camera = cam
    eevee(samples, (W, H), film_transparent=True)
    floor_obj = bpy.data.objects.get("HC_Floor")
    hid = None
    if floor_obj is not None:
        hid = floor_obj.hide_render
        floor_obj.hide_render = True
    try:
        sc.render.filepath = path
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.color_mode = "RGBA"
        bpy.ops.render.render(write_still=True)
    finally:
        if floor_obj is not None:
            floor_obj.hide_render = hid
        sc.render.film_transparent = False
        for o in hidden:
            o.hide_render = False
    return {"png": path}


def render_only(collections=("Car_Visual", "Car_Interior", "Car_Visual_WIP", "HC_Stage")):
    """Render visibility = viewport visibility for the given collections; everything else is
    excluded from the view layer (old slice objects, startup collection)."""
    lc = bpy.context.view_layer.layer_collection
    for child in lc.children:
        child.exclude = child.name not in collections
    hidden = 0
    for o in bpy.context.view_layer.objects:
        o.hide_render = o.hide_get()
        hidden += o.hide_render
    return {"hidden_in_render": hidden}


def setup(hdri="studio", strength=1.0, rotation_deg=0.0, samples=64, res=(1920, 1080)):
    out = {"world": world_hdri(hdri, strength, rotation_deg), "floor": floor(), "engine": eevee(samples, res)}
    out.update(render_only())
    return out


ORTHO_VIEWS = {
    # screen axes: (world axis, sign) for image x (right) and image y (up)
    "side": dict(target=(0.0, -0.07, 0.75), distance=2.8, elevation_deg=0.0, azimuth_deg=0.0, res=(2400, 1200),
                 axes=((1, 1), (2, 1))),
    "front": dict(target=(0.0, 0.0, 0.75), distance=1.25, elevation_deg=0.0, azimuth_deg=90.0, res=(1600, 1600),
                  axes=((0, -1), (2, 1))),
    "rear": dict(target=(0.0, 0.0, 0.75), distance=1.25, elevation_deg=0.0, azimuth_deg=-90.0, res=(1600, 1600),
                 axes=((0, 1), (2, 1))),
    "top": dict(target=(0.0, -0.07, 0.0), distance=2.8, elevation_deg=90.0, azimuth_deg=0.0, res=(2400, 1200),
                axes=((1, 1), (0, -1))),
}


def _hide_floor(hide=True):
    f = bpy.data.objects.get("HC_Floor")
    if f is not None:
        f.hide_render = hide


def ortho_views(folder, prefix, samples=32, names=None):
    """Orthographic renders with a transparent background plus the camera framing (JSON), for the
    silhouette overlays (tools/ref/ortho_overlay.py)."""
    import json
    os.makedirs(folder, exist_ok=True)
    meta = {}
    _hide_floor(True)
    try:
        for name, v in ORTHO_VIEWS.items():
            if names and name not in names:
                continue
            camera(target=v["target"], distance=v["distance"], elevation_deg=v["elevation_deg"],
                   azimuth_deg=v["azimuth_deg"], ortho=True, name="HC_OrthoCam")
            eevee(samples, v["res"], film_transparent=True)
            sc = bpy.context.scene
            sc.render.image_settings.color_mode = "RGBA"
            path = os.path.join(folder, f"{prefix}_{name}.png")
            still(path)
            meta[name] = dict(png=path, target=v["target"], width_m=2 * v["distance"], res=v["res"], axes=v["axes"])
    finally:
        _hide_floor(False)
        bpy.context.scene.render.film_transparent = False
    with open(os.path.join(folder, f"{prefix}_views.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    return meta


BEAUTY_VIEWS = {
    "front34_left": dict(target=(0.0, 0.25, 0.62), distance=7.2, elevation_deg=9.0, azimuth_deg=128.0, lens=55.0),
    "front34_right": dict(target=(0.0, 0.25, 0.62), distance=7.2, elevation_deg=9.0, azimuth_deg=52.0, lens=55.0),
    "rear34_left": dict(target=(0.0, -0.25, 0.62), distance=7.2, elevation_deg=10.0, azimuth_deg=-128.0, lens=55.0),
    "rear34_right": dict(target=(0.0, -0.25, 0.62), distance=7.2, elevation_deg=10.0, azimuth_deg=-52.0, lens=55.0),
    "side_low": dict(target=(0.0, -0.05, 0.55), distance=8.0, elevation_deg=4.0, azimuth_deg=-2.0, lens=60.0),
    "top_down": dict(target=(0.0, 0.0, 0.5), distance=9.0, elevation_deg=62.0, azimuth_deg=40.0, lens=45.0),
}


def beauty(folder, prefix, names=None, samples=96, res=(1920, 1080)):
    out = {}
    eevee(samples, res)
    for name, cam in BEAUTY_VIEWS.items():
        if names and name not in names:
            continue
        out[name] = still(os.path.join(folder, f"{prefix}_{name}.png"), **cam)["png"]
    return out


def turntable(folder, frame0, frame1, n_frames=120, samples=48, res=(1280, 720), distance=7.6, elevation_deg=8.0,
              target=(0.0, 0.0, 0.6), lens=50.0):
    """Frames frame0..frame1-1 of an orbit (call in batches, ffmpeg joins them)."""
    os.makedirs(folder, exist_ok=True)
    eevee(samples, res)
    done = []
    for k in range(frame0, min(frame1, n_frames)):
        az = 125.0 + 360.0 * k / n_frames
        still(os.path.join(folder, f"tt_{k:04d}.png"), target=target, distance=distance, elevation_deg=elevation_deg,
              azimuth_deg=az, lens=lens)
        done.append(k)
    return {"frames": done}
