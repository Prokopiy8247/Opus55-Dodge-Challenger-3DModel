"""Interior inspection and evidence shots: a look-at camera (driver's eye, passenger, rear seat) and
cut-away views with the roof / doors hidden for the render only."""
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector

from . import interior_tables as it

CUTAWAY_ROOF = ("CH_Roof", "CH_Pillars_L", "CH_Pillars_R", "CH_Glass_Windshield", "CH_Glass_Rear", "CH_Glass_Door_L",
                "CH_Glass_Door_R", "CH_Glass_Quarter_L", "CH_Glass_Quarter_R", "CH_Int_Headliner", "CH_Int_SunVisors",
                "CH_Antenna", "CH_Glass_Frit", "CH_Int_Mirror")
CUTAWAY_LEFT = ("CH_Door_L", "CH_Glass_Door_L", "CH_Int_DoorCard_L", "CH_Mirror_Housing_L", "CH_Mirror_Glass_L",
                "CH_Mirror_Stalk_L", "CH_Door_Handle_L")


def look_cam(eye, target, fov_h_deg=85.0, name="HC_LookCam"):
    from .blend_util import collection
    data = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, data)
        collection("HC_Stage").objects.link(cam)
    d = Vector(target) - Vector(eye)
    rot = d.to_track_quat("-Z", "Y").to_matrix().to_4x4()
    cam.matrix_world = Matrix.Translation(Vector(eye)) @ rot
    data.type = "PERSP"
    data.sensor_fit = "HORIZONTAL"
    data.angle = math.radians(fov_h_deg)
    data.clip_start, data.clip_end = 0.01, 500.0
    bpy.context.scene.camera = cam
    return cam


def shot(path, eye, target, fov=85.0, res=(1600, 900), samples=48, hide=()):
    from .render import eevee
    hidden = []
    for n in hide:
        o = bpy.data.objects.get(n)
        if o is not None and not o.hide_render:
            o.hide_render = True
            hidden.append(o)
    try:
        look_cam(eye, target, fov)
        eevee(samples, res)
        sc = bpy.context.scene
        os.makedirs(os.path.dirname(path), exist_ok=True)
        sc.render.filepath = path
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.color_mode = "RGB"
        bpy.ops.render.render(write_still=True)
    finally:
        for o in hidden:
            o.hide_render = False
    return path


def driver_view(path, fov=None, pitch_deg=-7.0, res=(1600, 900), samples=48):
    eye = np.array(it.EYE)
    p = math.radians(pitch_deg)
    target = eye + np.array([0.0, math.cos(p), math.sin(p)])
    return shot(path, eye, target, fov or it.FOV_H_DEG, res, samples)


VIEWS = {
    # name: (eye, target, fov, hide)
    "driver": (it.EYE, (it.EYE[0], it.EYE[1] + 1.0, it.EYE[2] - 0.12), it.FOV_H_DEG, ()),
    "passenger": ((0.36, -0.30, 1.13), (-0.25, 0.70, 0.86), 80.0, ()),
    "dash_closeup": ((-0.10, -0.05, 1.05), (-0.30, 0.60, 0.88), 70.0, ()),
    "rear_seat": ((0.0, 0.25, 1.15), (0.0, -1.20, 0.75), 85.0, ()),
    "top_cutaway": ((0.0, -0.30, 3.6), (0.0, -0.30, 0.4), 50.0, CUTAWAY_ROOF),
    "side_cutaway": ((-3.2, -0.20, 1.05), (0.0, -0.20, 0.75), 55.0, CUTAWAY_LEFT),
    "front_seats_from_rear": ((0.0, -1.30, 1.25), (0.0, 0.40, 0.75), 85.0, ()),
}


def gauge_tests(folder, prefix, res=(1280, 720), samples=48):
    """Cluster close-ups at the brief's test values (0 / 3000 / 6000 rpm with 0 / 100 / 200 mph) and the
    driver view with the wheel at -90 / 0 / +90 deg."""
    from .interior import pose_cockpit
    c = np.array(it.CLUSTER_CENTRE)
    eye = np.array(it.EYE)
    cam = c + (eye - c) / np.linalg.norm(eye - c) * 0.42
    out = {}
    try:
        for rpm, mph in ((0, 0), (3000, 100), (6000, 200)):
            pose_cockpit(rpm=rpm, mph=mph)
            out[f"gauges_{rpm}rpm_{mph}mph"] = shot(os.path.join(folder, f"{prefix}_gauges_{rpm}rpm_{mph}mph.png"), cam, c,
                                                     46.0, res, samples, hide=("CH_Int_SteeringWheel",))
        for deg in (-90, 0, 90):
            pose_cockpit(rpm=800, steer_deg=deg)
            p = math.radians(-9.0)
            out[f"steer_{deg}"] = shot(os.path.join(folder, f"{prefix}_steer_{deg:+d}.png"), eye,
                                       eye + np.array([0.0, math.cos(p), math.sin(p)]), it.FOV_H_DEG, res, samples)
    finally:
        pose_cockpit()
    return out


def cockpit_sequence(folder, frame0, frame1, n=96, res=(1280, 720), samples=32):
    """Driver-view frames: the tach sweeps to the red line and back, the speedo climbs, the wheel turns
    90 deg each way (frames frame0..frame1-1 of n; call in batches, ffmpeg joins them)."""
    from .interior import pose_cockpit
    eye = np.array(it.EYE)
    p = math.radians(-9.0)
    target = eye + np.array([0.0, math.cos(p), math.sin(p)])
    done = []
    try:
        for k in range(frame0, min(frame1, n)):
            t = k / (n - 1)
            rpm = 750 + 5900 * math.sin(math.pi * min(1.0, t * 1.6)) ** 2
            mph = 140 * t
            steer = 90 * math.sin(2 * math.pi * t)
            pose_cockpit(rpm=rpm, mph=mph, steer_deg=steer, throttle=float(rpm > 3000), brake=0.0)
            shot(os.path.join(folder, f"seq_{k:04d}.png"), eye, target, it.FOV_H_DEG, res, samples)
            done.append(k)
    finally:
        pose_cockpit()
    return {"frames": done}


def views(folder, prefix, names=None, res=(1600, 900), samples=48):
    out = {}
    for name, (eye, target, fov, hide) in VIEWS.items():
        if names and name not in names:
            continue
        out[name] = shot(os.path.join(folder, f"{prefix}_{name}.png"), eye, target, fov, res, samples, hide)
    return out
