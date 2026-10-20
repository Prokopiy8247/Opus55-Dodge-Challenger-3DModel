"""Interior layout check (G-Interior): fit the camera of an interior reference photo to 2D-3D
correspondences of cockpit landmarks (OpenCV solvePnP with a focal-length search) and report the
reprojection error per landmark. Large residuals show where the modelled layout differs.

Usage: tools/.venv/Scripts/python.exe tools/ref/interior_pnp.py cabin2
Writes docs/p1b/photo_cams/<photo>.json (focal, camera in the car frame, residuals).
2D points were read from gridded crops (tools/ref/gridcrop.py) of reference/Салон 2.jpg.
"""
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
from hcar import interior_tables as it  # noqa: E402


def landmarks():
    """3D cockpit landmarks in the car frame, from the same tables the interior is built from."""
    C = np.array(it.WHEEL_CENTRE)
    a = math.radians(it.COLUMN_DEG)
    A = np.array([0.0, -math.cos(a), math.sin(a)])
    U = np.array([0.0, math.sin(a), math.cos(a)])
    pts = {"wheel_badge": C + A * 0.0487 + U * 0.004}
    c = np.array(it.CLUSTER_CENTRE)
    pts["tach_centre"] = c + [-it.POD_DX, 0, 0]
    pts["speedo_centre"] = c + [it.POD_DX, 0, 0]
    s = math.radians(it.STACK_TILT_DEG)
    n = np.array([0.0, -math.cos(s), math.sin(s)])
    up = np.array([0.0, math.sin(s), math.cos(s)])
    sc = np.array(it.STACK_CENTRE) + n * 0.0222
    hw, hh = it.SCREEN_W / 2, it.SCREEN_H / 2
    pts["screen_tl"] = sc - [hw, 0, 0] + up * hh
    pts["screen_tr"] = sc + [hw, 0, 0] + up * hh
    pts["screen_bl"] = sc - [hw, 0, 0] - up * hh
    pts["screen_br"] = sc + [hw, 0, 0] - up * hh
    vc = np.array(it.STACK_CENTRE) + n * 0.015
    pts["vent_left"] = vc - [0.163, 0, 0]
    pts["vent_right"] = vc + [0.163, 0, 0]
    t = math.radians(it.START_BUTTON_TILT_DEG)
    pts["start_button"] = np.array(it.START_BUTTON) + 0.0065 * np.array([0.0, -math.cos(t), math.sin(t)])
    # console: switch bank knobs (top faces) and the top of the selector grip
    ys, zs = zip(*it.CONSOLE_TOP)
    ztop = lambda y: float(np.interp(y, ys, zs))  # noqa: E731
    us = np.array([0.0, 0.545 - 0.34, 0.738 - 0.592])
    us /= np.linalg.norm(us)
    ns = np.array([0.0, -us[2], us[1]])
    cb = np.array([0.0, it.SWITCH_BANK_Y, ztop(it.SWITCH_BANK_Y)]) + ns * 0.012
    pts["knob_left"] = cb + ns * 0.024 + [-0.071, 0, 0]
    pts["knob_right"] = cb + ns * 0.024 + [0.071, 0, 0]
    sx, sy, _ = it.SHIFTER
    pts["shifter_top"] = np.array([sx, sy - 0.080, ztop(sy) + 0.004 + 0.092 + 0.022])
    return pts


PHOTOS = {
    "cabin2": {"file": "Салон 2.jpg", "size": (1920, 1280), "uv": {
        "wheel_badge": (596, 403), "tach_centre": (704, 226), "speedo_centre": (994, 259),
        "screen_tl": (1307, 244), "screen_tr": (1611, 267), "screen_bl": (1267, 455), "screen_br": (1580, 490),
        "vent_left": (1193, 331), "vent_right": (1705, 377), "start_button": (1130, 575),
        "knob_left": (1227, 730), "knob_right": (1470, 791), "shifter_top": (1352, 809)}},
}


def solve(key, f_range=(800, 2200), exclude=("start_button", "knob_left", "knob_right", "shifter_top")):
    """Fit with the landmarks not in `exclude`; residuals are reported for all of them. The focal
    range covers 15-41 mm (full-frame equivalent) lenses: the interior photos are wide-angle shots
    taken inside the car."""
    ph = PHOTOS[key]
    W, H = ph["size"]
    P3 = landmarks()
    fit = [n for n in ph["uv"] if n in P3 and n not in exclude]
    names = [n for n in ph["uv"] if n in P3]
    Xf = np.array([P3[n] for n in fit], np.float64)
    xf = np.array([ph["uv"][n] for n in fit], np.float64)
    X = np.array([P3[n] for n in names], np.float64)
    x = np.array([ph["uv"][n] for n in names], np.float64)
    best = None
    for f in np.linspace(f_range[0], f_range[1], 141):
        K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]], np.float64)
        ok, rvec, tvec = cv2.solvePnP(Xf, xf, K, None, flags=cv2.SOLVEPNP_SQPNP)
        if not ok:
            continue
        ok, rvec, tvec = cv2.solvePnP(Xf, xf, K, None, rvec, tvec, useExtrinsicGuess=True, flags=cv2.SOLVEPNP_ITERATIVE)
        pf, _ = cv2.projectPoints(Xf, rvec, tvec, K, None)
        rms_fit = float(np.sqrt(np.mean(np.sum((pf[:, 0] - xf) ** 2, axis=1))))
        proj, _ = cv2.projectPoints(X, rvec, tvec, K, None)
        err = np.linalg.norm(proj[:, 0] - x, axis=1)
        if best is None or rms_fit < best[0]:
            best = (rms_fit, f, rvec, tvec, err, proj[:, 0])
        K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]], np.float64)
        ok, rvec, tvec = cv2.solvePnP(X, x, K, None, flags=cv2.SOLVEPNP_SQPNP)
        if not ok:
            continue
        ok, rvec, tvec = cv2.solvePnP(X, x, K, None, rvec, tvec, useExtrinsicGuess=True, flags=cv2.SOLVEPNP_ITERATIVE)
        proj, _ = cv2.projectPoints(X, rvec, tvec, K, None)
        err = np.linalg.norm(proj[:, 0] - x, axis=1)
        rms = float(np.sqrt(np.mean(err ** 2)))
        if best is None or rms < best[0]:
            best = (rms, f, rvec, tvec, err, proj[:, 0])
    rms, f, rvec, tvec, err, proj = best
    R, _ = cv2.Rodrigues(rvec)
    cam = (-R.T @ tvec).ravel()
    # where each photo landmark lies on the plane through its model point facing the camera (layout
    # correction hint: the photo position at the model point's depth)
    K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]], np.float64)
    hint = {}
    for n, P, q in zip(names, X, x):
        ray = R.T @ np.linalg.solve(K, np.array([q[0], q[1], 1.0]))
        nrm = (cam - P) / np.linalg.norm(cam - P)
        t = np.dot(P - cam, nrm) / np.dot(ray, nrm)
        hint[n] = [round(float(v), 3) for v in cam + t * ray]
    Rb = R.T @ np.diag([1.0, -1.0, -1.0])          # Blender camera axes -> world
    Mw = np.eye(4)
    Mw[:3, :3] = Rb
    Mw[:3, 3] = cam
    out = {"fit_landmarks": fit, "rms_fit_px": round(rms, 2), "photo_point_at_model_depth": hint,
           "size": [W, H], "matrix_world": Mw.tolist()}
    out.update({"photo": key, "file": ph["file"], "focal_px": round(float(f), 1),
           "lens_mm_36": round(float(f) * 36.0 / W, 1), "camera_car_frame": [round(float(v), 4) for v in cam],
           "rms_px": round(rms, 2), "rms_pct_width": round(100 * rms / W, 2),
           "per_point_px": {n: round(float(e), 1) for n, e in zip(names, err)},
           "per_point_residual": {n: [round(float(p[0] - q[0]), 1), round(float(p[1] - q[1]), 1)]
                                  for n, p, q in zip(names, proj, x)}})
    d = ROOT / "docs" / "p1b" / "photo_cams"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{key}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def overlay(key, render_png, out_jpg, alpha=0.55):
    """Photo with the transparent-background render of the fitted camera on top, plus landmark crosses
    (green: photo, red: model projection)."""
    from PIL import Image, ImageDraw
    ph = PHOTOS[key]
    photo = Image.open(ROOT / "reference" / ph["file"]).convert("RGBA")
    ren = Image.open(render_png).convert("RGBA").resize(photo.size)
    a = np.asarray(ren).astype(float)
    a[..., 3] *= alpha
    comp = Image.alpha_composite(photo, Image.fromarray(a.astype(np.uint8)))
    d = ImageDraw.Draw(comp)
    res = json.loads((ROOT / "docs" / "p1b" / "photo_cams" / f"{key}.json").read_text(encoding="utf-8"))
    for n, (u, v) in ph["uv"].items():
        d.line([(u - 12, v), (u + 12, v)], fill=(0, 255, 0, 255), width=3)
        d.line([(u, v - 12), (u, v + 12)], fill=(0, 255, 0, 255), width=3)
        r = res["per_point_residual"].get(n)
        if r:
            pu, pv = u + r[0], v + r[1]
            d.ellipse([pu - 7, pv - 7, pu + 7, pv + 7], outline=(255, 40, 40, 255), width=3)
    comp.convert("RGB").save(out_jpg, quality=90)
    return out_jpg


if __name__ == "__main__":
    if len(sys.argv) > 3 and sys.argv[1] == "--overlay":
        print(overlay(sys.argv[2], sys.argv[3], sys.argv[4]))
    else:
        print(json.dumps(solve(sys.argv[1] if len(sys.argv) > 1 else "cabin2"), indent=1))
