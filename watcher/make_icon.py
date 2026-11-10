"""Draw the G WhiteBoard app icon in pure code (Pillow) — same design as
assets/logo.svg — and write it as Windows .ico and macOS .icns.

Run once after changing the design:  .venv/Scripts/python.exe watcher/make_icon.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

WATCHER_DIR = Path(__file__).resolve().parent
OUT_DIR = WATCHER_DIR / "assets"

NAVY_TOP = (22, 50, 79)
NAVY_BOT = (14, 26, 43)
BLUE = (63, 169, 245)
GREEN = (76, 195, 138)
ORANGE = (240, 162, 2)
CREAM = (255, 248, 230)
GRAY1 = (183, 196, 210)
GRAY2 = (211, 220, 229)
DOTGREEN = (63, 185, 80)

S = 4  # supersample factor for smooth edges


def _vgrad(size: int) -> Image.Image:
    """Navy diagonal gradient tile with rounded corners."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    top, bot = NAVY_TOP, NAVY_BOT
    grad = Image.new("RGBA", (size, size))
    px = grad.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size)
            px[x, y] = (
                int(top[0] + (bot[0] - top[0]) * t),
                int(top[1] + (bot[1] - top[1]) * t),
                int(top[2] + (bot[2] - top[2]) * t),
                255,
            )
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=size // 4, fill=255
    )
    img.paste(grad, (0, 0), mask)
    return img


def draw_icon(size: int) -> Image.Image:
    big = size * S
    img = _vgrad(big)
    d = ImageDraw.Draw(img)
    u = big / 512  # design-space unit

    def rr(box, radius, **kw):
        d.rounded_rectangle([c * u for c in box], radius=radius * u, **kw)

    # the whiteboard + clip
    rr((96, 112, 416, 352), 28, fill=(255, 255, 255, 255))
    rr((216, 96, 296, 130), 12, fill=NAVY_BOT + (255,))

    # capture card
    rr((132, 164, 264, 250), 14, fill=CREAM + (255,), outline=ORANGE + (255,), width=int(6 * u))
    rr((148, 182, 220, 191), 4.5 * u, fill=(201, 185, 138, 255))
    rr((148, 200, 248, 209), 4.5 * u, fill=(226, 212, 168, 255))

    # green pen mark (quadratic beziers, sampled)
    def q(p0, p1, p2, steps=48):
        pts = []
        for i in range(steps + 1):
            t = i / steps
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
            y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
            pts.append((x * u, y * u))
        return pts

    curve = q((286, 250), (320, 198), (348, 242)) + q((348, 242), (370, 276), (406, 224))
    d.line(curve, fill=GREEN + (255,), width=int(16 * u), joint="curve")
    r = 8 * u
    for p in (curve[0], curve[-1]):
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=GREEN + (255,))

    # timestamp dashes
    rr((132, 278, 196, 288), 5 * u, fill=GRAY1 + (255,))
    rr((206, 278, 250, 288), 5 * u, fill=GRAY2 + (255,))

    # capture-arrived dot
    d.ellipse(
        [(424 - 30) * u, (120 - 30) * u, (424 + 30) * u, (120 + 30) * u],
        fill=DOTGREEN + (255,),
        outline=(14, 26, 43, 140),
        width=int(10 * u),
    )

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    master = draw_icon(256)
    master.save(OUT_DIR / "gwhiteboard.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    draw_icon(512).save(OUT_DIR / "gwhiteboard.icns")  # macOS dock/tab icon
    master.save(OUT_DIR / "gwhiteboard-512.png")
    print("Icon written:", OUT_DIR)


if __name__ == "__main__":
    main()
