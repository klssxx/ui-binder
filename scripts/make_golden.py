"""Generate the golden reference screenshot deterministically.

The synthetic UI is designed to be recoverable by the heuristic vision
pipeline: solid navbar/sidebar bands, a card panel, a chart polyline,
a bordered input, two solid buttons and text lines. No OCR needed.

Usage: python scripts/make_golden.py [--out samples/golden-reference/reference.png]
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 800
BG = "#101216"
NAVBAR = "#202633"
SIDEBAR = "#1a2130"
CARD = "#1a1f2a"
INPUT_BORDER = "#3a4254"
BUTTON_PRIMARY = "#4f8cff"
BUTTON_SECONDARY = "#3556c9"
TEXT = "#e8eaf0"
TEXT_DIM = "#9aa3b2"
CHART = "#4f8cff"
DIVIDER = "#2a2f3a"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow without scalable default font
        return ImageFont.load_default()


def build() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # navbar band + divider
    d.rectangle([0, 0, W, 64], fill=NAVBAR)
    d.rectangle([0, 64, W, 66], fill=DIVIDER)
    d.text((24, 18), "UI BINDER", font=font(22), fill=TEXT)

    # sidebar
    d.rectangle([0, 66, 220, H], fill=SIDEBAR)
    for i, label in enumerate(["Dashboard", "Projects", "Bindings", "Verify", "Export"]):
        d.text((24, 110 + i * 42), label, font=font(15), fill=TEXT_DIM)
    d.rectangle([24, 96, 196, 98], fill=DIVIDER)

    # main card panel
    d.rectangle([280, 120, 920, 560], fill=CARD)

    # heading + body text (42px renders ~31px tall → crosses the heading threshold)
    d.text((300, 136), "Idea Generator", font=font(42), fill=TEXT)
    d.text((300, 184), "Describe a product idea and generate a structured brief.", font=font(14), fill=TEXT_DIM)
    d.text((300, 206), "Results include scoring and exportable report sections.", font=font(14), fill=TEXT_DIM)

    # bordered input
    d.rectangle([300, 236, 720, 274], outline=INPUT_BORDER, width=2)

    # buttons
    d.rectangle([300, 300, 440, 340], fill=BUTTON_PRIMARY)
    d.rectangle([460, 300, 580, 340], fill=BUTTON_SECONDARY)

    # chart polyline inside the card
    points = [(320, 520), (380, 470), (440, 495), (500, 420), (560, 445),
              (620, 390), (680, 410), (740, 360), (800, 385), (860, 330)]
    d.line(points, fill=CHART, width=3)

    # status footer text
    d.text((280, 600), "Status: ready", font=font(14), fill=TEXT_DIM)
    return img


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else \
        Path(__file__).resolve().parent.parent / "samples" / "golden-reference" / "reference.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img = build()
    img.save(out, format="PNG")
    print(f"golden reference written: {out} ({img.width}x{img.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
