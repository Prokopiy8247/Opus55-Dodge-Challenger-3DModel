"""Procedural interior textures (PIL + numpy), drawn after the interior reference photos.

    tach_dial.png, speedo_dial.png   instrument dials (angles from hcar.interior_tables.GAUGES)
    cluster_display.png              centre TFT, static frame for Blender renders (Unity draws it live)
    screen_perf_pages.png            8.4 in touchscreen, "Performance Pages"-style layout
    carbon_twill.png                 2x2 twill carbon-style trim (tileable)
    leather_perforated.png           black perforated leather insert (tileable)
    leather_grain.png                black leather grain (tileable)
    seat_emboss.png                  "SRT HELLCAT" back-rest emboss (RGBA)
    wheel_badge.png                  "SRT" steering-wheel badge (RGBA)
    needle.png                       red needle (RGBA)

Usage: tools/.venv/Scripts/python.exe tools/textures/make_interior_textures.py
Output: assets/textures/interior/
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
from hcar.interior_tables import GAUGES  # noqa: E402  (pure python module)

OUT = ROOT / "assets" / "textures" / "interior"
FONTS = Path("C:/Windows/Fonts")


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def polar(c, r, a_deg):
    """Point at radius r, angle a clockwise from 12 o'clock."""
    a = math.radians(a_deg)
    return c[0] + r * math.sin(a), c[1] - r * math.cos(a)


def radial(size, stops):
    """RGB radial gradient: stops = [(r_frac, (r, g, b)), ...] from the centre outwards."""
    n = size
    y, x = np.mgrid[0:n, 0:n]
    d = np.hypot(x - n / 2 + 0.5, y - n / 2 + 0.5) / (n / 2)
    rs = np.array([s[0] for s in stops])
    out = np.zeros((n, n, 3))
    for k in range(3):
        out[..., k] = np.interp(d, rs, [s[1][k] for s in stops])
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def text_c(draw, xy, s, f, fill):
    l, t, r, b = draw.textbbox((0, 0), s, font=f)
    draw.text((xy[0] - (r - l) / 2 - l, xy[1] - (b - t) / 2 - t), s, font=f, fill=fill)


def dial(kind):
    N = 1024
    c = (N / 2, N / 2)
    g = GAUGES[kind]
    red = (220, 30, 36)
    # dark face, red glow towards the rim (the dials are lit red), dark hub area
    img = radial(N, [(0.0, (34, 34, 36)), (0.36, (30, 30, 32)), (0.40, (22, 8, 9)), (0.62, (70, 10, 12)),
                     (0.86, (120, 16, 18)), (0.92, (60, 8, 9)), (0.95, (18, 18, 20)), (1.0, (12, 12, 13))])
    d = ImageDraw.Draw(img)
    # outer red ring
    d.ellipse([c[0] - 470, c[1] - 470, c[0] + 470, c[1] + 470], outline=red, width=6)
    d.ellipse([c[0] - 452, c[1] - 452, c[0] + 452, c[1] + 452], outline=(90, 12, 14), width=2)

    def ang(v):
        return g["a_min"] + (v - g["min"]) / (g["max"] - g["min"]) * (g["a_max"] - g["a_min"])

    if kind == "tach":
        # red-line band
        a0, a1 = ang(g["redline"]), ang(g["max"])
        d.arc([c[0] - 440, c[1] - 440, c[0] + 440, c[1] + 440], a0 - 90, a1 - 90, fill=red, width=34)
        for v in range(0, 7001, 100):
            major, half = v % 1000 == 0, v % 500 == 0
            L, w = (64, 9) if major else ((40, 6) if half else (20, 3))
            col = (255, 255, 255) if v < g["redline"] else (255, 230, 230)
            p0, p1 = polar(c, 448, ang(v)), polar(c, 448 - L, ang(v))
            d.line([p0, p1], fill=col, width=w)
        fb, fs = font("arialbd.ttf", 104), font("arial.ttf", 30)
        for k in range(8):
            text_c(d, polar(c, 318, ang(k * 1000)), str(k), fb, (255, 255, 255))
        for k in range(7):
            text_c(d, polar(c, 360, ang(k * 1000 + 500)), str(k * 1000 + 500), fs, (235, 235, 235))
        text_c(d, (c[0], c[1] + 268), "RPM", font("arialbd.ttf", 46), (240, 240, 240))
        text_c(d, (c[0], c[1] + 314), "x1000", font("arial.ttf", 34), (220, 220, 220))
    else:
        for v in range(0, 201, 2):
            major, mid = v % 20 == 0, v % 10 == 0
            if not (major or mid or v % 2 == 0):
                continue
            L, w = (60, 8) if major else ((38, 5) if mid else (16, 2))
            p0, p1 = polar(c, 448, ang(v)), polar(c, 448 - L, ang(v))
            d.line([p0, p1], fill=(255, 255, 255), width=w)
        fb, fs = font("arialbd.ttf", 66), font("arial.ttf", 30)
        for v in range(0, 201, 20):
            text_c(d, polar(c, 330, ang(v)), str(v), fb, (255, 255, 255))
        for v in range(10, 200, 20):
            text_c(d, polar(c, 372, ang(v)), str(v), fs, (230, 230, 230))
        text_c(d, (c[0], c[1] + 250), "SRT", font("ariblk.ttf" if (FONTS / "ariblk.ttf").exists() else "arialbd.ttf", 56), red)
        text_c(d, (c[0], c[1] + 306), "MPH", font("arialbd.ttf", 44), (240, 240, 240))
    # hub: perforated grey disc (the photos show a grey mesh centre)
    hub = 190
    y, x = np.mgrid[0:N, 0:N]
    rr = np.hypot(x - c[0], y - c[1])
    a = np.asarray(img).astype(float)
    m = rr < hub
    base = 58 + 12 * (1 - rr / hub)
    dots = ((x % 14 - 7) ** 2 + (y % 14 - 7) ** 2) < 14
    for k in range(3):
        a[..., k][m] = np.where(dots[m], base[m] * 0.45, base[m])
    ring = (rr >= hub) & (rr < hub + 10)
    a[ring] = (150, 150, 155)
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    return img


def cluster_display(gear="P", speed="0"):
    """Centre TFT between the pods (0.086 x 0.092 m): range, speed in km/h, PRNDM column on the right,
    temperature and fuel bars on the left (the layout of reference/Панель.jpg)."""
    W, H = 704, 768
    img = Image.new("RGB", (W, H), (8, 10, 18))
    a = np.asarray(img).astype(float)
    y, x = np.mgrid[0:H, 0:W]
    a += (16 * np.exp(-((x - W / 2) ** 2 / (2 * 200 ** 2) + (y - H * 0.55) ** 2 / (2 * 200 ** 2))))[..., None] * [0.6, 0.8, 1.4]
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([170, 40, 534, 112], 16, outline=(70, 80, 110), width=3)
    text_c(d, (352, 76), "RANGE --- km", font("segoeui.ttf", 36), (210, 215, 230))
    text_c(d, (352, 360), speed, font("segoeuib.ttf", 220), (245, 245, 250))
    text_c(d, (352, 505), "km/h", font("segoeui.ttf", 50), (200, 205, 220))
    for k, s in enumerate("PRNDM"):
        col = (255, 255, 255) if s == gear else (120, 125, 140)
        text_c(d, (640, 190 + k * 78), s, font("segoeuib.ttf", 58), col)
    for x0, label, lit in ((36, "C", 5), (108, "F", 7)):
        for k in range(10):
            col = (230, 120, 40) if k < lit else (60, 64, 78)
            d.rectangle([x0, 560 - k * 36, x0 + 44, 560 - k * 36 + 24], fill=col)
        text_c(d, (x0 + 22, 615), label, font("segoeuib.ttf", 36), (200, 205, 220))
    text_c(d, (352, 690), "ODO 22763 km", font("segoeui.ttf", 36), (180, 185, 200))
    return img


def perf_pages():
    W, H = 1024, 640
    img = Image.new("RGB", (W, H), (12, 12, 16))
    d = ImageDraw.Draw(img)
    orange = (232, 92, 24)
    d.rectangle([0, 0, W, 64], fill=(28, 28, 34))
    d.text((24, 12), "SRT", font=font("arialbd.ttf", 38), fill=orange)
    d.text((112, 14), "Performance Pages", font=font("segoeui.ttf", 36), fill=(235, 235, 240))
    d.text((W - 130, 14), "11:42", font=font("segoeui.ttf", 36), fill=(235, 235, 240))
    items = ["Timers", "Gauges", "Engine", "G-Force", "Launch", "Drive Modes"]
    for k, s in enumerate(items):
        y0 = 84 + k * 82
        d.rectangle([0, y0, 250, y0 + 72], fill=(36, 36, 44) if k else (70, 34, 18))
        d.text((24, y0 + 16), s, font=font("segoeui.ttf", 34), fill=(230, 230, 235))
    tiles = [("Power", "hp"), ("Torque", "lb-ft"), ("Boost", "psi"), ("Oil", "psi"), ("Coolant", "F"), ("Trans", "F")]
    for k, (s, u) in enumerate(tiles):
        cx, cy = 360 + (k % 3) * 230, 200 + (k // 3) * 250
        d.ellipse([cx - 82, cy - 82, cx + 82, cy + 82], outline=(200, 200, 210), width=6)
        d.arc([cx - 82, cy - 82, cx + 82, cy + 82], 150, 300, fill=orange, width=10)
        text_c(d, (cx, cy - 8), "0", font("segoeuib.ttf", 54), (245, 245, 250))
        text_c(d, (cx, cy + 40), u, font("segoeui.ttf", 26), (190, 190, 200))
        text_c(d, (cx, cy + 112), s, font("segoeui.ttf", 32), (225, 225, 230))
    d.rectangle([0, H - 56, W, H], fill=(28, 28, 34))
    for k, s in enumerate(["Media", "Climate", "Apps", "Controls", "Phone", "Nav"]):
        text_c(d, (90 + k * 168, H - 28), s, font("segoeui.ttf", 28), (215, 215, 220))
    return img


def carbon_twill(n=512, tow=32):
    """2x2 twill: tows alternate over/under in a staircase; each tow is shaded along its fibre direction."""
    y, x = np.mgrid[0:n, 0:n]
    i, j = x // tow, y // tow
    horiz = ((i + j) // 2) % 2 == 0          # 2x2 twill staircase
    u = np.where(horiz, (y % tow) / tow, (x % tow) / tow)          # across the tow
    v = np.where(horiz, (x % tow) / tow, (y % tow) / tow)          # along the tow
    across = np.sin(np.pi * u) ** 0.6
    sheen = np.where(horiz, 0.75, 1.15) * (0.55 + 0.45 * across)
    fib = 0.05 * np.sin(2 * np.pi * (u * 9 + 0.3 * v))
    val = 18 + 34 * sheen + 10 * fib * 10
    rgb = np.stack([val, val, val * 1.04], axis=-1)
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))


def leather(n=512, perforated=False, seed=3):
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 1, (n // 8, n // 8))
    img = Image.fromarray(((noise - noise.min()) / np.ptp(noise) * 255).astype(np.uint8)).resize((n, n), Image.BICUBIC)
    base = 14 + 6 * (np.asarray(img).astype(float) / 255.0)
    fine = rng.normal(0, 1.2, (n, n))
    val = base + fine
    if perforated:
        y, x = np.mgrid[0:n, 0:n]
        p = 16
        yy = y % p
        xx = (x + (y // p % 2) * p // 2) % p
        hole = (xx - p / 2) ** 2 + (yy - p / 2) ** 2 < 6
        val = np.where(hole, 3.0, val)
    rgb = np.stack([val, val, val * 1.02], axis=-1)
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))


def emboss_text(lines, size=(1024, 512), fill=(30, 30, 31, 255)):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = size[1] * 0.38
    for s, fsize in lines:
        f = font("arialbi.ttf", fsize)
        text_c(d, (size[0] / 2 + 3, y + 3), s, f, (70, 70, 72, 255))    # lit lower edge
        text_c(d, (size[0] / 2, y), s, f, fill)
        y += fsize * 1.05
    return img


def wheel_badge():
    W, H = 512, 256
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font("arialbi.ttf", 150)
    text_c(d, (W / 2 + 4, H / 2 + 4), "SRT", f, (90, 90, 95, 255))
    text_c(d, (W / 2, H / 2), "SRT", f, (20, 20, 22, 255))
    return img


def needle():
    W, H = 64, 512
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(W / 2 - 10, H - 20), (W / 2 + 10, H - 20), (W / 2 + 3, 10), (W / 2 - 3, 10)], fill=(255, 60, 50, 255))
    return img.filter(ImageFilter.GaussianBlur(0.6))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    dial("tach").save(OUT / "tach_dial.png")
    dial("speedo").save(OUT / "speedo_dial.png")
    cluster_display().save(OUT / "cluster_display.png")
    perf_pages().save(OUT / "screen_perf_pages.png")
    carbon_twill().save(OUT / "carbon_twill.png")
    leather(perforated=True).save(OUT / "leather_perforated.png")
    leather(perforated=False, seed=5).save(OUT / "leather_grain.png")
    emboss_text([("SRT", 230), ("HELLCAT", 96)]).save(OUT / "seat_emboss.png")
    wheel_badge().save(OUT / "wheel_badge.png")
    needle().save(OUT / "needle.png")
    print("\n".join(sorted(p.name for p in OUT.glob("*.png"))))


if __name__ == "__main__":
    main()
