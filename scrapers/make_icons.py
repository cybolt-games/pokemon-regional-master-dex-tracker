#!/usr/bin/env python3
"""Generate the app icon set.

The icon is the app in one glyph: a PC box holding slots, most of them filled
gold the way a caught Pokemon shows in the UI, the last few still empty rings.
Nothing is traced from the games -- it is drawn from the stylesheet's own
palette, so the home-screen icon and the site look like the same product.

Why this is drawn in code rather than exported from an SVG: the shapes are
plain geometry, and an icon has to survive being shrunk to 16px. Drawing at
4x and downsampling gives clean edges at every size, with no dependency on a
system SVG rasterizer (this machine has none). It also lets the art simplify
as it gets smaller -- a 4x4 grid of slots turns to mush as a favicon, so small
sizes drop to 3x3 and 2x2 while staying recognisably the same mark.

Usage: python3 scrapers/make_icons.py
Writes site/icons/*.png and site/favicon.ico.
"""

import os
import subprocess

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "site", "icons")

# Straight from site/css/app.css, so the icon cannot drift from the app.
BG = "#12141c"          # --bg
PANEL = "#1b1f2b"       # between --bg-raised and --bg-cell
PANEL_EDGE = "#2f3545"  # --line, slightly lifted
CAUGHT = "#e0a437"      # --caught
EMPTY = "#39415a"       # --line, brightened enough to read on PANEL

SS = 4  # supersampling factor

# How many slots are filled, per grid size. Spelled out rather than computed:
# the point is that the grid reads as partly finished, and the pleasing ratio
# is different at each size. 4x4 leaves the bottom row plus one slot empty.
FILLED = {2: 3, 3: 6, 4: 11}


def draw_icon(size, grid=4, inset=0.13, radius=0.22, bleed=False, panel=True, hollow=True):
    """Draw one icon.

    inset  fraction of the canvas left clear around the box panel
    radius corner radius of the background, as a fraction of the canvas
    bleed  True for a background that fills the whole square (iOS and
           Android mask the corners themselves; a transparent corner would
           otherwise be filled with white or black by the platform)
    hollow False fills the empty slots dimly instead of ringing them. A ring
           needs about two pixels of stroke to read; at 16px it has less than
           one and smears into a blob.
    panel  False drops the box outline. At 16px its border is a third of the
           thickness of the slots themselves and the mark turns to mush, so
           the smallest favicon keeps only the slots.
    """
    n = size * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if bleed:
        d.rectangle([0, 0, n - 1, n - 1], fill=BG)
    else:
        d.rounded_rectangle([0, 0, n - 1, n - 1], radius=radius * n, fill=BG)

    # The slot grid, sized from the space left inside the inset.
    box = n * (1 - 2 * inset)
    pitch = box / grid
    dot = pitch * 0.76
    origin = n * inset + (pitch - dot) / 2

    # Panel behind the slots, so the mark reads as a box with things in it
    # rather than as loose dots.
    if panel:
        pad = dot * 0.34
        x0 = origin - pad
        x1 = origin + (grid - 1) * pitch + dot + pad
        edge = max(1, int(round((x1 - x0) * 0.028)))
        d.rounded_rectangle([x0, x0, x1, x1], radius=(x1 - x0) * 0.2,
                            fill=PANEL, outline=PANEL_EDGE, width=edge)

    filled = FILLED[grid]
    stroke = max(1, int(round(dot * 0.14)))
    for i in range(grid * grid):
        row, col = divmod(i, grid)
        cx = origin + col * pitch
        cy = origin + row * pitch
        slot = [cx, cy, cx + dot, cy + dot]
        if i < filled:
            d.ellipse(slot, fill=CAUGHT)
        elif hollow:
            # An empty slot is a ring, not a flat disc: at a glance the icon
            # shows progress, which is the whole point of the app.
            d.ellipse([slot[0] + stroke / 2, slot[1] + stroke / 2,
                       slot[2] - stroke / 2, slot[3] - stroke / 2],
                      outline=EMPTY, width=stroke)
        else:
            d.ellipse(slot, fill=EMPTY)

    return img.resize((size, size), Image.LANCZOS)


def write_svg(path, size=512, grid=4, inset=0.13, radius=0.22):
    """Emit the same mark as SVG.

    Generated from the constants above rather than hand-drawn, so the vector
    favicon and the PNGs can never drift apart. Browsers that take an SVG icon
    get one that stays sharp at any size the OS asks for.
    """
    n = float(size)
    box = n * (1 - 2 * inset)
    pitch = box / grid
    dot = pitch * 0.76
    origin = n * inset + (pitch - dot) / 2
    pad = dot * 0.34
    x0 = origin - pad
    side = (origin + (grid - 1) * pitch + dot + pad) - x0
    edge = side * 0.028
    stroke = dot * 0.14

    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %g %g" '
           'role="img" aria-label="Regional Dex Buddy">' % (n, n),
           '<rect width="%g" height="%g" rx="%g" fill="%s"/>'
           % (n, n, radius * n, BG),
           # Stroked inward, to match the way Pillow draws an outline.
           '<rect x="%g" y="%g" width="%g" height="%g" rx="%g" fill="%s" '
           'stroke="%s" stroke-width="%g"/>'
           % (x0 + edge / 2, x0 + edge / 2, side - edge, side - edge,
              side * 0.2, PANEL, PANEL_EDGE, edge)]

    filled = FILLED[grid]
    for i in range(grid * grid):
        row, col = divmod(i, grid)
        cx = origin + col * pitch + dot / 2
        cy = origin + row * pitch + dot / 2
        if i < filled:
            out.append('<circle cx="%g" cy="%g" r="%g" fill="%s"/>'
                       % (cx, cy, dot / 2, CAUGHT))
        else:
            out.append('<circle cx="%g" cy="%g" r="%g" fill="none" '
                       'stroke="%s" stroke-width="%g"/>'
                       % (cx, cy, (dot - stroke) / 2, EMPTY, stroke))
    out.append('</svg>')

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print("  %-26s %5d bytes" % (os.path.basename(path), os.path.getsize(path)))


def grid_for(size):
    """Simplify the art as the canvas shrinks."""
    if size <= 20:
        return 2
    if size <= 64:
        return 3
    return 4


def save(img, name):
    path = os.path.join(OUT, name)
    img.save(path, "PNG", optimize=True)
    print("  %-26s %5d bytes" % (name, os.path.getsize(path)))


def main():
    os.makedirs(OUT, exist_ok=True)
    print("icons -> site/icons/")

    # Favicons. Small radius: at this size a big one eats the art.
    for size in (16, 32, 48):
        small = size <= 20
        save(draw_icon(size, grid=grid_for(size), inset=0.10 if small else 0.07,
                       radius=0.16, panel=not small, hollow=not small),
             "favicon-%d.png" % size)

    # PWA icons, purpose "any" -- rounded, transparent outside the corners.
    for size in (192, 512):
        save(draw_icon(size, grid=4, inset=0.13, radius=0.22),
             "icon-%d.png" % size)

    # Maskable. Android may crop to a circle, so everything important has to
    # sit inside the centre 80% -- a square inscribed in that circle is only
    # 57% of the width, hence the much larger inset.
    for size in (192, 512):
        save(draw_icon(size, grid=4, inset=0.215, bleed=True),
             "maskable-%d.png" % size)

    # iOS home screen. Opaque, square, no transparency: iOS rounds it itself.
    for size in (180, 167, 152, 120):
        save(draw_icon(size, grid=4, inset=0.13, bleed=True).convert("RGB"),
             "apple-touch-icon-%d.png" % size)

    write_svg(os.path.join(OUT, "icon.svg"))

    # Multi-resolution .ico, built from the three distinct favicon drawings so
    # each size keeps its own art instead of being downsampled from one image.
    ico = os.path.join(ROOT, "site", "favicon.ico")
    subprocess.run(["convert"] + [os.path.join(OUT, "favicon-%d.png" % s)
                                  for s in (16, 32, 48)] + [ico], check=True)
    print("  %-26s %5d bytes" % ("../favicon.ico", os.path.getsize(ico)))


if __name__ == "__main__":
    main()
