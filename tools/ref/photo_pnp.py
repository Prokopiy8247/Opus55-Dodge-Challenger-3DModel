"""Camera of a reference photo from 2D-3D correspondences (OpenCV solvePnP with a focal-length
search), for the G-Model perspective overlays.

Usage: tools/.venv/Scripts/python.exe tools/ref/photo_pnp.py 4
Writes docs/p1/photo_cams/photo<k>.json (focal, Blender camera matrix, reprojection error).
3D points come from the model (hcar shape tables / strip surface); 2D points were read from
gridded crops of the photo (tools/ref/gridcrop.py).
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))


def model_points():
    from hcar import body
    from hcar.panels import StripSurface
    from hcar.sidemap import face_param
    m = body.model()
    st = m["strip"]
    surf = StripSurface(st)

    def front(x, z):
        s, t = face_param(st, abs(x), z, "front", t_lo=0.0, t_hi=1.0)
        P = surf.P(np.array([s]), np.array([t]))[0]
        N = surf.N(np.array([s]), np.array([t]))[0]
        return np.array([np.sign(x) * abs(P[0]), P[1], P[2]]), N

    pts = {}
    for name, x in (("lamp_R_out", 0.7495), ("lamp_R_in", 0.5796), ("lamp_L_in", -0.5796), ("lamp_L_out", -0.7495)):
        P, N = front(x, 0.714)
        fwd = np.array([N[0] * np.sign(x), N[1], 0.0])
        fwd /= np.linalg.norm(fwd)
        pts[name] = P - fwd * 0.035 + np.array([0, 0, 0])
        pts[name][0] = np.sign(x) * abs(pts[name][0]) if abs(pts[name][0]) > 0 else pts[name][0]
    P, _ = front(-0.44, 0.70)
    pts["srt_badge"] = np.array([-0.44, P[1] - 0.062, 0.70])
    pts["wheel_FR_hub"] = np.array([0.8335 + 0.075, 1.4755, 0.352])
    pts["wheel_FR_contact"] = np.array([0.8335, 1.4755, 0.0])
    pts["mirror_R_tip"] = np.array([1.084, 0.375, 1.052])
    pts["apillar_R_top"] = np.array([0.66, 0.29, 1.36])
    pts["apillar_L_top"] = np.array([-0.66, 0.29, 1.36])
    return pts


PHOTOS = {
    4: {"size": (1920, 1280), "uv": {
        "lamp_R_out": (821, 652), "lamp_R_in": (957, 652), "lamp_L_in": (1690, 642), "lamp_L_out": (1775, 643),
        "srt_badge": (1594, 654), "wheel_FR_hub": (462, 890), "wheel_FR_contact": (472, 1102),
        "mirror_R_tip": (213, 440), "apillar_R_top": (445, 285), "apillar_L_top": (1095, 322)}},
}


def solve(k):
    ph = PHOTOS[k]
    W, H = ph["size"]
    P3 = model_points()
    names = [n for n in ph["uv"] if n in P3]
    X = np.array([P3[n] for n in names], np.float64)
    x = np.array([ph["uv"][n] for n in names], np.float64)
    best = None
    for f in np.linspace(800, 6000, 261):
        K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]], np.float64)
        ok, rvec, tvec = cv2.solvePnP(X, x, K, None, flags=cv2.SOLVEPNP_SQPNP)
        if not ok:
            continue
        ok, rvec, tvec = cv2.solvePnP(X, x, K, None, rvec, tvec, useExtrinsicGuess=True, flags=cv2.SOLVEPNP_ITERATIVE)
        proj, _ = cv2.projectPoints(X, rvec, tvec, K, None)
        err = np.linalg.norm(proj[:, 0] - x, axis=1)
        rms = float(np.sqrt(np.mean(err ** 2)))
        if best is None or rms < best[0]:
            best = (rms, f, rvec, tvec, err)
    rms, f, rvec, tvec, err = best
    R, _ = cv2.Rodrigues(rvec)
    C = (-R.T @ tvec).ravel()
    Rb = R.T @ np.diag([1.0, -1.0, -1.0])          # Blender camera axes -> world
    M = np.eye(4)
    M[:3, :3] = Rb
    M[:3, 3] = C
    out = {"photo": k, "size": [W, H], "focal_px": float(f), "lens_mm_36": float(f * 36.0 / W),
           "rms_px": rms, "per_point_px": {n: round(float(e), 1) for n, e in zip(names, err)},
           "camera_location": C.tolist(), "matrix_world": M.tolist(),
           "distance_to_origin": float(np.linalg.norm(C))}
    od = ROOT / "docs" / "p1" / "photo_cams"
    od.mkdir(parents=True, exist_ok=True)
    (od / f"photo{k}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    solve(int(sys.argv[1]))
