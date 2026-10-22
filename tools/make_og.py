#!/usr/bin/env python3
"""Generate the Open Graph card (site/og.png, 1200x630) from the site palette.
Pure local generation (PIL + macOS system fonts); re-run after design changes."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "site", "og.png")
BG, PANEL, LINE = "#05070a", "#0a0e14", "#1c2432"
FG, DIM, GREEN = "#edf1f7", "#95a1b4", "#3fd68f"

def font(candidates, size):
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default(size)

SERIF = ["/System/Library/Fonts/Supplemental/Georgia.ttf",
         "/System/Library/Fonts/Georgia.ttf"]
SANS_B = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
          "/System/Library/Fonts/Helvetica.ttc"]
SANS = ["/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc"]
MONO = ["/System/Library/Fonts/Menlo.ttc"]

img = Image.new("RGB", (1200, 630), BG)
d = ImageDraw.Draw(img)
# soft green glow, top-left
glow = Image.new("L", (1200, 630), 0)
gd = ImageDraw.Draw(glow)
gd.ellipse([-350, -320, 560, 360], fill=26)
img.paste(Image.new("RGB", (1200, 630), "#16a364"), (0, 0), glow)
# framed panel
d.rounded_rectangle([56, 56, 1144, 574], radius=26, outline=LINE, width=2,
                    fill=PANEL)
# omega mark
d.text((104, 96), "Ω", font=font(SERIF, 112), fill=GREEN)
# title + subtitle
d.text((104, 252), "Agent Omega", font=font(SANS_B, 76), fill=FG)
d.text((104, 352), "Autonomous AI repair system for open-source projects",
       font=font(SANS, 33), fill=DIM)
# rule + receipts line
d.line([104, 436, 1096, 436], fill=LINE, width=2)
d.text((104, 464),
       "11 PRs merged upstream   ·   16 fail-closed gates   ·   recorded proof",
       font=font(MONO, 28), fill=GREEN)
d.text((104, 516), "omegademo.com", font=font(MONO, 24), fill=DIM)
img.save(OUT, "PNG", optimize=True)
print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes)")
