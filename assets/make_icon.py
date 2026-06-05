"""
assets/make_icon.py -- Generate assets/mic.ico from scratch using Pillow.

Creates a mic-on-dark-pill icon at 256 x 256 and resamples to
16, 32, 48, and 256 so Windows shows a sharp icon at every size.

Run once:  python assets/make_icon.py
"""

from PIL import Image, ImageDraw
import os, math

OUT = os.path.join(os.path.dirname(__file__), "mic.ico")


def draw_mic(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    s   = size
    cx  = s / 2
    cy  = s / 2

    # ── Dark pill background ───────────────────────────────────────────────
    r = s * 0.22                                  # corner radius
    d.rounded_rectangle([0, 0, s - 1, s - 1],
                        radius=int(r), fill="#1C1C1E")

    # ── Red mic capsule (oval) ─────────────────────────────────────────────
    mw = s * 0.155     # half-width  of capsule
    mh = s * 0.255     # half-height of capsule
    my = cy - s * 0.08 # centre of capsule, slightly above screen centre

    d.ellipse([cx - mw, my - mh, cx + mw, my + mh], fill="#FF3B30")

    # ── White stand arc (U-shape below capsule) ────────────────────────────
    aw  = s * 0.30          # half-width  of arc bounding box
    ath = my + mh * 0.35    # top  of arc bbox (overlaps capsule bottom)
    abh = cy + s * 0.22     # bottom of arc bbox
    lw  = max(1, int(s / 18))   # line width

    d.arc([cx - aw, ath, cx + aw, abh],
          start=0, end=180,
          fill="white", width=lw)

    # ── Pole ──────────────────────────────────────────────────────────────
    pole_top = abh
    pole_bot = cy + s * 0.34
    d.line([cx, pole_top, cx, pole_bot], fill="white", width=lw)

    # ── Base ──────────────────────────────────────────────────────────────
    bw = s * 0.20
    d.line([cx - bw, pole_bot, cx + bw, pole_bot], fill="white", width=lw)

    return img


def main():
    # Draw at full resolution; Pillow downsamples to each requested size.
    # Pass sizes= on the single source image — this is the correct Pillow API
    # for multi-resolution ICO (append_images is for animated formats, not ICO).
    base = draw_mic(256)
    base.save(OUT, format="ICO",
              sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()
