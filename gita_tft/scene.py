"""The procedural art and the frame composer: the Python reference of what the TFT player draws.

Everything is integer arithmetic on a 256-step sine table, so the C++ player (firmware/gita_core.h) can reproduce a frame pixel for pixel.
Per chapter, a few numbers (made here, deterministically, from the chapter number) describe a rotating mandala of petal curves; the player
draws it live every frame. Dots are combined with bitwise OR, so the order they are drawn in never changes the picture.
"""
import math

import numpy as np

W, H = 320, 240
CX, CY = 160, 120
SIN = [round(256 * math.sin(2 * math.pi * i / 256)) for i in range(256)]      # also written into the C++ header
SIN_NP = np.array(SIN, dtype=np.int64)
FADE_STEPS = 6
DARKEN_QUARTER = 0x39E7           # a pixel in a letter's halo is darkened to 1/4: (p>>2) & mask, per channel
ACCENT = (0xE6, 0xC2, 0x5A)       # the top line (reference and speaker)
MAIN = (0xF4, 0xF4, 0xEE)         # the verse


def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def hsv565(h, s, v):
    h %= 360
    region, rem = h // 60, (h % 60) * 255 // 60
    p = v * (255 - s) // 255
    q = v * (255 - s * rem // 255) // 255
    t = v * (255 - s * (255 - rem) // 255) // 255
    r, g, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][region]
    return rgb565(r, g, b)


class Rng:
    """xorshift32: the same few lines exist in no other place, so the numbers are fixed here and stored in the image."""
    def __init__(self, seed):
        self.s = (seed * 2654435761 + 1) & 0xFFFFFFFF or 1

    def next(self):
        s = self.s
        s ^= (s << 13) & 0xFFFFFFFF
        s ^= s >> 17
        s ^= (s << 5) & 0xFFFFFFFF
        self.s = s
        return s


def art_params(chapter):
    """The numbers that describe chapter `chapter`'s mandala and colours (deterministic; stored in the flash image)."""
    rng = Rng(chapter)
    r = lambda n: rng.next() % n
    hue = (chapter * 20 + r(20)) % 360
    pal = [hsv565(hue + off, 150 + r(80), 200 + r(56)) for off in (0, 25, 50, 170, 200, 330)]
    layers = 5 + r(3)
    out = {"bg_top": hsv565(hue + 10, 200, 16), "bg_bottom": hsv565(hue + 200, 160, 48), "palette": pal,
           "symmetry": (5, 6, 7, 8, 9, 12)[r(6)], "layers": layers, "dot": 2,
           "accent": rgb565(*ACCENT), "main": rgb565(*MAIN)}
    keys = ("points", "radius", "petals", "amp", "speed", "wobble", "phase")
    for k in keys:
        out[k] = [0] * 8
    for l in range(layers):
        out["points"][l] = 64 + r(49)
        out["radius"][l] = 22 + l * 13 + r(6)
        out["petals"][l] = 3 + r(7)
        out["amp"][l] = 6 + r(10 + 3 * l)
        out["speed"][l] = (1 + r(3)) * (-1 if l % 2 else 1)
        out["wobble"][l] = r(7) - 3
        out["phase"][l] = r(256)
    return out


def background(top, bottom):
    """The vertical gradient, one RGB565 value per row, as an (H,) array."""
    y = np.arange(H, dtype=np.int64)
    chans = []
    for shift, mask in ((11, 31), (5, 63), (0, 31)):
        a, b = (top >> shift) & mask, (bottom >> shift) & mask
        chans.append((a * (H - 1 - y) + b * y) // (H - 1))
    return ((chans[0] << 11) | (chans[1] << 5) | chans[2]).astype(np.uint16)


def art(ch, t):
    """The mandala for frame `t` as a (H, W) uint16 array, 0 where nothing is drawn."""
    canvas = np.zeros((H, W), dtype=np.uint16)
    sym, size, pal = ch["symmetry"], ch["dot"], ch["palette"]
    for l in range(ch["layers"]):
        n = ch["points"][l]
        i = np.arange(n, dtype=np.int64)
        a = ((i * 256) // n + t * ch["speed"][l]) & 255
        r = ch["radius"][l] + ((SIN_NP[(a * ch["petals"][l] + ch["phase"][l] + t * ch["wobble"][l]) & 255] * ch["amp"][l]) >> 8)
        for k in range(sym):
            ang = (a + (k * 256) // sym) & 255
            x = CX + ((SIN_NP[(ang + 64) & 255] * r) >> 8)
            y = CY + ((SIN_NP[ang] * r) >> 8)
            col = np.array(pal, dtype=np.uint16)[(l + i // 8 + k) % 6]
            for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1))[:1 if size == 1 else 4]:
                xs, ys = x + dx, y + dy
                ok = (xs >= 0) & (xs < W) & (ys >= 0) & (ys < H)
                np.bitwise_or.at(canvas, (ys[ok], xs[ok]), col[ok])
    return canvas


def fade_level(k, frames):
    return max(0, min(FADE_STEPS, k, frames - 1 - k))


def mix565(a, b, weight, denom):
    """Mix RGB565 arrays a toward b by weight/denom, per channel, integer arithmetic (arrays or scalars)."""
    out = 0
    for shift, mask in ((11, 31), (5, 63), (0, 31)):
        ca, cb = (a >> shift) & mask, (b >> shift) & mask
        out = out | (((ca * (denom - weight) + cb * weight) // denom) << shift)
    return out


def blend(base, color, weight, denom):
    """Mix RGB565 `base` toward `color` by weight/denom, per channel, integer arithmetic."""
    out = 0
    for shift, mask in ((11, 31), (5, 63), (0, 31)):
        a, b = (base >> shift) & mask, (color >> shift) & mask
        out = out | (((a * (denom - weight) + b * weight) // denom) << shift)
    return out


def compose(ch, mask_rows, y0, split, t, k, frames):
    """One finished frame: the live art, a darkened caption band, and the verse text fading in and out. Returns (H, W) uint16."""
    bg = background(ch["bg_top"], ch["bg_bottom"])
    a = art(ch, t)
    pix = np.where(a != 0, a, bg[:, None]).astype(np.uint16)
    if mask_rows is not None:
        h = len(mask_rows)
        region = pix[y0:y0 + h].astype(np.int64)
        m = np.array(mask_rows, dtype=np.int64)
        f = fade_level(k, frames)
        dark = (region >> 2) & DARKEN_QUARTER
        base = np.where(m >= 1, mix565(region, dark, f, FADE_STEPS), region)
        color = np.zeros(region.shape, dtype=np.int64)
        color[:split] = ch["accent"]
        color[split:] = ch["main"]
        weight = np.where(m == 3, 3, np.where(m == 2, 2, 0)) * f
        out = np.where(m >= 2, mix565(base, color, weight, 3 * FADE_STEPS), base)
        pix[y0:y0 + h] = out.astype(np.uint16)
    return pix


def to_rgb888(frame565):
    r5, g6, b5 = (frame565 >> 11) & 31, (frame565 >> 5) & 63, frame565 & 31
    rgb = np.stack([(r5 << 3) | (r5 >> 2), (g6 << 2) | (g6 >> 4), (b5 << 3) | (b5 >> 2)], axis=-1)
    return rgb.astype(np.uint8)
