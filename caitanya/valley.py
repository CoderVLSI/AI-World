"""geography-v2: two river valleys that meet at a delta, with dry land between them and highlands upstream.

A pure function of ``(x, z, width, depth, seed)`` like geography-v1, but built once per map (cached) from seeded river lines:

* two main rivers start in the highlands at the far (high-z) edge, meander south and join into one trunk that reaches the sea;
  each has one tributary;
* rivers are water that cannot be walked on, except at *fords* (shallows placed every few dozen tiles) so a river divides the land
  without making half of it unreachable;
* beside the water: marsh (wetland), then a fertile **floodplain** that is wider downstream;
* away from water the land dries out (dryland), with forest where it is wetter and highland where it is high;
* the sea lies along the low-z edge.

It only describes the land. It says nothing about what to do there; inhabitants find out through their own observations.
The output for a given seed is frozen once released: change the algorithm only by adding a new version.
"""
import math
import random
from functools import lru_cache

NAMES = ("water", "wetland", "grassland", "forest", "dryland", "highland", "floodplain")
WATER, WETLAND, GRASS, FOREST, DRY, HIGH, FLOOD = range(7)
_INF = 10 ** 9
_RIVER_SAMPLE = 0.5          # tiles between sample points along a river line


def _smooth(a, b, v):
    t = min(1.0, max(0.0, (v - a) / (b - a)))
    return t * t * (3 - 2 * t)


class _Map:
    __slots__ = ("width", "depth", "biome", "elev", "walk")

    def tile(self, x, z):
        if not (0 <= x < self.width and 0 <= z < self.depth):
            return dict(biome="water", elevation=-.25, walkable=False)       # outside the map is open sea, never land
        i = z * self.width + x
        return dict(biome=NAMES[self.biome[i]], elevation=self.elev[i], walkable=bool(self.walk[i]))


def _line(rng, p0, p1, amplitude, waves):
    """A meandering line from p0 to p1 (both fixed), as a list of (x, z) points."""
    length = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    n = max(2, int(length / _RIVER_SAMPLE))
    phase = rng.random() * math.tau
    pts = []
    for k in range(n + 1):
        t = k / n
        bend = amplitude * math.sin(math.pi * t) * math.sin(math.tau * waves * t + phase)
        pts.append((p0[0] + (p1[0] - p0[0]) * t + bend, p0[1] + (p1[1] - p0[1]) * t))
    return pts


def _stamp(cells, width, depth, pts, half_widths):
    """Mark every tile within the (varying) half width of the line."""
    for (px, pz), hw in zip(pts, half_widths):
        r = int(math.ceil(hw))
        for x in range(int(px) - r, int(px) + r + 1):
            for z in range(int(pz) - r, int(pz) + r + 1):
                if 0 <= x < width and 0 <= z < depth and (x + .5 - px) ** 2 + (z + .5 - pz) ** 2 <= hw * hw:
                    cells.add(z * width + x)


def _chamfer(sources, width, depth, limit):
    """Approximate distance (in tiles) from the nearest source tile, capped at `limit`. 3-4 chamfer, two passes."""
    dist = [_INF] * (width * depth)
    for i in sources:
        dist[i] = 0
    for z in range(depth):
        for x in range(width):
            i = z * width + x
            d = dist[i]
            if x > 0 and dist[i - 1] + 3 < d:
                d = dist[i - 1] + 3
            if z > 0:
                j = i - width
                if dist[j] + 3 < d:
                    d = dist[j] + 3
                if x > 0 and dist[j - 1] + 4 < d:
                    d = dist[j - 1] + 4
                if x < width - 1 and dist[j + 1] + 4 < d:
                    d = dist[j + 1] + 4
            dist[i] = d
    for z in range(depth - 1, -1, -1):
        for x in range(width - 1, -1, -1):
            i = z * width + x
            d = dist[i]
            if x < width - 1 and dist[i + 1] + 3 < d:
                d = dist[i + 1] + 3
            if z < depth - 1:
                j = i + width
                if dist[j] + 3 < d:
                    d = dist[j] + 3
                if x < width - 1 and dist[j + 1] + 4 < d:
                    d = dist[j + 1] + 4
                if x > 0 and dist[j - 1] + 4 < d:
                    d = dist[j - 1] + 4
            dist[i] = d
    cap = limit * 3
    return [min(d, cap) / 3.0 for d in dist]


@lru_cache(maxsize=4)
def build(width, depth, seed):
    rng = random.Random(seed * 1_000_003 + 20_261_104)
    p1, p2, p3 = (rng.random() * math.tau for _ in range(3))
    amp = max(2.0, width * 0.045)

    def coast(x):                                   # the sea's edge: wavy, 2 to 8 tiles from the low-z edge
        return 5 + 2.5 * math.sin(x / 13 + p1) + 1.5 * math.sin(x / 31 + p2)

    xc = width * (0.50 + (rng.random() - .5) * .16)                 # where the two rivers join
    zc = depth * (0.22 + (rng.random() - .5) * .06)
    xm = xc + (rng.random() - .5) * width * .06                     # the trunk's mouth
    zm = coast(xm) + 1
    heads = [(width * (0.22 + (rng.random() - .5) * .10), depth - 3.0), (width * (0.78 + (rng.random() - .5) * .10), depth - 3.0)]
    lines = []          # (points, half widths, number of fords)
    for hx, hz in heads:
        pts = _line(rng, (hx, hz), (xc, zc), amp, 2.5)
        hw = [1.2 + 0.8 * k / (len(pts) - 1) for k in range(len(pts))]
        lines.append((pts, hw))
        side = -1 if hx < xc else 1                                                  # a tributary from the outer side, joining mid-stream
        j = int(len(pts) * (0.35 + rng.random() * .2))
        start = (pts[j][0] + side * width * (0.12 + rng.random() * .06), min(depth - 3.0, pts[j][1] + depth * (0.18 + rng.random() * .1)))
        tpts = _line(rng, start, pts[j], amp * .6, 1.5)
        lines.append((tpts, [0.9 + 0.3 * k / (len(tpts) - 1) for k in range(len(tpts))]))
    trunk = _line(rng, (xc, zc), (xm, zm), amp * .5, 1.0)
    lines.append((trunk, [2.0 + 1.2 * k / (len(trunk) - 1) for k in range(len(trunk))]))

    channel, ford = set(), set()
    for pts, hw in lines:
        _stamp(channel, width, depth, pts, hw)
        spacing = max(14, int(width * 0.17))        # a shallow crossing about every 17% of the map width along the river
        step = int(spacing / _RIVER_SAMPLE)
        k = int(rng.random() * step) + step // 2
        while k < len(pts):
            _stamp(ford, width, depth, [pts[k]], [2.4])
            k += step + int(rng.random() * step * .4)
        _stamp(ford, width, depth, [pts[len(pts) // 2]], [2.4])
    ford &= channel
    banks = _chamfer(channel, width, depth, 70)

    biome, elev, walk = bytearray(width * depth), [0.0] * (width * depth), bytearray(width * depth)
    for z in range(depth):
        north = z / depth
        sea = coast
        flood_w = 9 + 6 * (1 - north)
        marsh_w = 2.5 + 4 * (1 - _smooth(.04, .22, north))
        for x in range(width):
            i = z * width + x
            d = banks[i] + 1.3 * (math.sin(x / 6 + p3) + math.cos(z / 8 + p1))        # roughens the band edges so they are not parallel curves
            if z < sea(x) or (i in channel and i not in ford):
                biome[i], elev[i], walk[i] = WATER, -.25, 0
                continue
            hills = 1.4 + 1.3 * math.sin(x / 17 + p1) * math.cos(z / 23 + p2)
            ridge = 3.5 * _smooth(.52, .95, north) * (0.6 + 0.4 * max(0.0, math.sin(x / 19 + z / 27 + p3)))
            vf = _smooth(0, 28, d)
            e = max(.2, 0.5 + 0.8 * north + (hills - 0.5) * (0.25 + 0.75 * vf) + ridge * (0.2 + 0.8 * vf))
            walk[i] = 1
            if i in ford:
                biome[i], elev[i] = WETLAND, round(min(e, .5), 3)
                continue
            if d <= marsh_w and e < 3.5:
                b = WETLAND
            elif d <= flood_w and e < 3.0:
                b = FLOOD
                e = min(e, 0.9 + 0.3 * north)
            elif e > 4:
                b = HIGH
            else:
                noise = 0.5 + 0.25 * (math.sin(x / 23 + p2) + math.cos(z / 26 + p3))
                moist = 0.85 - 0.6 * min(max(d, 0), 70) / 70 + 0.6 * (noise - .5)
                b = FOREST if moist > .64 else DRY if moist < .34 else GRASS
            biome[i], elev[i] = b, round(e, 3)
    m = _Map()
    m.width, m.depth, m.biome, m.elev, m.walk = width, depth, biome, elev, walk
    return m


def tile(x, z, width, depth, seed):
    return build(width, depth, seed).tile(x, z)


def founding_site(width, depth, seed, radius):
    """Where the founders start: the floodplain tile nearest the usual spot (a quarter in, mid-height) whose surroundings are mostly land."""
    m = build(width, depth, seed)
    want_x, want_z = width // 4, depth // 2
    flood = [i for i in range(width * depth) if m.biome[i] == FLOOD and m.walk[i] and i // width >= 3]
    flood.sort(key=lambda i: (abs(i % width - want_x) + abs(i // width - want_z), i))
    for i in flood[:400]:
        cx, cz = i % width, i // width
        window = [(x, z) for x in range(max(0, cx - radius), min(width, cx + radius + 1)) for z in range(max(3, cz - radius), min(depth, cz + radius + 1))]
        if window and sum(m.walk[z * width + x] for x, z in window) >= 0.85 * len(window):
            return cx, cz
    return (flood[0] % width, flood[0] // width) if flood else (want_x, want_z)
