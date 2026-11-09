"""Turn a screen's text into a 2-bit mask (320 pixels wide) using real text shaping (Devanagari conjuncts need it).

Mask values: 0 nothing, 1 a dark halo around the letters (so small marks stay readable over bright art), 2 text edge (2/3 strength), 3 text.

The result is what goes into flash: the TFT's microcontroller cannot shape Devanagari, so shaping is done here, once.
"""
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

FONTS = Path(__file__).parent / "fonts"
DEV = FONTS / "noto-sans-devanagari-devanagari-400-normal.woff"
LAT = FONTS / "noto-sans-latin-400-normal.woff"
EXT = FONTS / "noto-sans-latin-ext-400-normal.woff"
W, SCREEN_H = 320, 240
MARGIN = 14                     # left/right, pixels
TOP_SIZE = {"sanskrit": 17, "iast": 12}
SIZES = {"sanskrit": range(30, 15, -1), "iast": range(21, 10, -1)}
LINE_GAP = 1.32
HALO = 1                        # pixels of dark halo around the letters (2 looks a little clearer but adds 25% to the flash size)
DEV_TOP_PAD = 0


@lru_cache(maxsize=None)
def _cmap(path):
    return set(TTFont(str(path)).getBestCmap())


@lru_cache(maxsize=None)
def _font(path, size):
    return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.RAQM)


def _runs(text, base=None):
    """Split text into runs that each use one font file. Latin text: basic Latin, or the extended set with the IAST marks. For Devanagari
    (`base` = the Devanagari font) a character the Devanagari font lacks, such as the full stop between chapter and verse, uses Latin."""
    out, cur, cur_font = [], "", None
    for ch in text:
        if base is not None and ord(ch) in _cmap(base):
            font = base
        else:
            font = LAT if ord(ch) in _cmap(LAT) else EXT
        if font != cur_font and cur:
            out.append((cur, cur_font))
            cur = ""
        cur, cur_font = cur + ch, font
    if cur:
        out.append((cur, cur_font))
    return out


def measure(text, kind, size):
    return sum(_font(font, size).getlength(run) for run, font in _runs(text, DEV if kind == "sanskrit" else None))


def draw_text(draw, x, y, text, kind, size, stroke=0):
    for run, font in _runs(text, DEV if kind == "sanskrit" else None):
        draw.text((x, y), run, font=_font(font, size), fill=255, stroke_width=stroke, stroke_fill=255)
        x += _font(font, size).getlength(run)


def wrap(line, kind, size, maxw):
    """Break one source line into rows that fit, at spaces; a single word wider than the screen is left whole."""
    rows, cur = [], ""
    for word in line.split(" "):
        trial = (cur + " " + word) if cur else word
        if cur and measure(trial, kind, size) > maxw:
            rows.append(cur)
            cur = word
        else:
            cur = trial
        while kind == "iast" and measure(cur, kind, size) > maxw and len(cur) > 2:    # one compound word wider than the screen: split it with a hyphen
            cut = len(cur) - 1
            while cut > 1 and measure(cur[:cut] + "-", kind, size) > maxw:
                cut -= 1
            rows.append(cur[:cut] + "-")
            cur = cur[cut:]
    if cur:
        rows.append(cur)
    return rows


def layout(kind, top, lines):
    """Pick the largest type size at which everything fits the screen. Returns (rows, size, top_size)."""
    maxw = W - 2 * MARGIN
    top_size = TOP_SIZE[kind]
    avail = SCREEN_H - 10 - int(top_size * LINE_GAP) - 6
    for size in SIZES[kind]:
        rows = [r for line in lines for r in wrap(line, kind, size, maxw)]
        if len(rows) * int(size * LINE_GAP) <= avail and all(measure(r, kind, size) <= maxw + 2 for r in rows):
            return rows, size, top_size
    rows = [r for line in lines for r in wrap(line, kind, SIZES[kind][-1], maxw)]
    return rows, SIZES[kind][-1], top_size


def render_screen(kind, top, lines):
    """Returns ``(mask_rows, split)``: a list of rows of 320 values 0..3, and the row where the accent colour (the top line) ends."""
    rows, size, top_size = layout(kind, top, lines)
    top_h = int(top_size * LINE_GAP)
    body_h = len(rows) * int(size * LINE_GAP)
    height = 6 + top_h + body_h + 6
    img, halo = Image.new("L", (W, height), 0), Image.new("L", (W, height), 0)
    for target, stroke in ((img, 0), (halo, HALO)):
        d = ImageDraw.Draw(target)
        draw_text(d, (W - measure(top, kind, top_size)) / 2, 4, top, kind, top_size, stroke)
        y = 6 + top_h
        for r in rows:
            draw_text(d, (W - measure(r, kind, size)) / 2, y, r, kind, size, stroke)
            y += int(size * LINE_GAP)
    px, hx = img.load(), halo.load()
    mask = [[3 if px[x, yy] >= 170 else 2 if px[x, yy] >= 64 else 1 if hx[x, yy] >= 64 else 0 for x in range(W)] for yy in range(img.height)]
    split = 6 + top_h
    keep = [i for i, row in enumerate(mask) if any(row)]
    lo, hi = keep[0], keep[-1] + 1
    return mask[lo:hi], max(0, split - lo)
