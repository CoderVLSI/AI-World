"""The flash image: everything the TFT player needs, in one binary that is written to a flash partition and read in place.

Layout (all little-endian, packed):  Header | chapter records | verse records | screen records | data.
Each verse has one or two *screens* (Sanskrit, and its transliteration). A screen is a 2-bit alpha mask of its text, PackBits-compressed,
plus where it sits on the display, where its accent-coloured top line ends, and how many frames it stays up. The art is NOT stored:
the player generates it live from a few numbers per chapter (see scene.py), which is why a 700-verse "video" fits in a few megabytes.
"""
import struct

MAGIC = b"GITA"
VERSION = 1
HEADER = struct.Struct("<4sHHHHIIIII")          # magic, version, chapters, verses, screens, chapter_off, verse_off, screen_off, data_off, total
CHAPTER = struct.Struct("<BBHHH6HBBBB8B8B8B8B8b8b8BHH")      # id, verses, first_verse, bg_top, bg_bottom, palette[6], symmetry, layers, dot, pad,
#                                                              points[8], radius[8], petals[8], amp[8], speed[8], wobble[8], phase[8], accent, main
VERSE = struct.Struct("<BBHB")                  # chapter, verse, first_screen, screens
SCREEN = struct.Struct("<IHHHHHBB")             # data offset, compressed bytes, height, y0, split, frames, kind, pad
WIDTH_BYTES = 80                                # 320 pixels at 4 per byte


def packbits(data):
    """PackBits: control 0..127 = copy n+1 literal bytes; 129..255 = repeat the next byte 257-n times."""
    out, i, n = bytearray(), 0, len(data)
    while i < n:
        run = 1
        while i + run < n and run < 128 and data[i + run] == data[i]:
            run += 1
        if run >= 3:
            out += bytes([257 - run, data[i]])
            i += run
            continue
        j = i
        while j < n and j - i < 128 and not (j + 2 < n and data[j] == data[j + 1] == data[j + 2]):
            j += 1
        j = max(j, i + 1)
        out += bytes([j - i - 1]) + bytes(data[i:j])
        i = j
    return bytes(out)


def unpackbits(data, size):
    out, i = bytearray(), 0
    while i < len(data) and len(out) < size:
        c = data[i]
        i += 1
        if c < 128:
            out += data[i:i + c + 1]
            i += c + 1
        elif c > 128:
            out += bytes([data[i]]) * (257 - c)
            i += 1
    if len(out) != size:
        raise ValueError("packbits data does not decode to the expected size")
    return bytes(out)


def pack_mask(mask_rows):
    """Rows of 320 values 0..3 to bytes, four pixels per byte, first pixel in the high bits."""
    out = bytearray()
    for row in mask_rows:
        for x in range(0, 320, 4):
            out.append((row[x] << 6) | (row[x + 1] << 4) | (row[x + 2] << 2) | row[x + 3])
    return bytes(out)


def unpack_mask(data, height):
    rows = []
    for y in range(height):
        row = []
        for b in data[y * WIDTH_BYTES:(y + 1) * WIDTH_BYTES]:
            row += [(b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3]
        rows.append(row)
    return rows


def build_image(chapters_meta, art, verses, screens):
    """chapters_meta: list of (chapter_id, verse_count, first_verse_index); art: list of dicts from scene.art_params (same order);
    verses: list of (chapter, verse, first_screen, screen_count); screens: list of dicts with mask_rows, split, frames, kind."""
    blobs, recs, offset = bytearray(), [], 0
    for s in screens:
        raw = pack_mask(s["mask_rows"])
        comp = packbits(raw)
        if len(comp) > 0xFFFF:
            raise ValueError("a screen does not fit 64 KB compressed")
        h = len(s["mask_rows"])
        y0 = (240 - h) // 2
        recs.append(SCREEN.pack(offset, len(comp), h, y0, s["split"], s["frames"], s["kind"], 0))
        blobs += comp
        offset += len(comp)
    ch_off = HEADER.size
    v_off = ch_off + CHAPTER.size * len(chapters_meta)
    s_off = v_off + VERSE.size * len(verses)
    d_off = s_off + SCREEN.size * len(screens)
    head = HEADER.pack(MAGIC, VERSION, len(chapters_meta), len(verses), len(screens), ch_off, v_off, s_off, d_off, d_off + len(blobs))
    ch_bytes = b"".join(
        CHAPTER.pack(cid, nv, first, a["bg_top"], a["bg_bottom"], *a["palette"], a["symmetry"], a["layers"], a["dot"], 0,
                     *a["points"], *a["radius"], *a["petals"], *a["amp"], *a["speed"], *a["wobble"], *a["phase"], a["accent"], a["main"])
        for (cid, nv, first), a in zip(chapters_meta, art))
    v_bytes = b"".join(VERSE.pack(*v) for v in verses)
    return head + ch_bytes + v_bytes + b"".join(recs) + bytes(blobs)


def parse_image(blob):
    """Read an image back (used by the Python reference renderer and by the tests; the C++ player reads the same bytes)."""
    magic, ver, nch, nv, ns, ch_off, v_off, s_off, d_off, total = HEADER.unpack_from(blob, 0)
    if magic != MAGIC or ver != VERSION or total != len(blob):
        raise ValueError("not a Gita flash image")
    chapters = []
    for i in range(nch):
        f = CHAPTER.unpack_from(blob, ch_off + i * CHAPTER.size)
        chapters.append({"id": f[0], "verses": f[1], "first_verse": f[2], "bg_top": f[3], "bg_bottom": f[4], "palette": list(f[5:11]),
                         "symmetry": f[11], "layers": f[12], "dot": f[13],
                         "points": list(f[15:23]), "radius": list(f[23:31]), "petals": list(f[31:39]), "amp": list(f[39:47]),
                         "speed": list(f[47:55]), "wobble": list(f[55:63]), "phase": list(f[63:71]), "accent": f[71], "main": f[72]})
    verses = [dict(zip(("chapter", "verse", "first_screen", "screens"), VERSE.unpack_from(blob, v_off + i * VERSE.size))) for i in range(nv)]
    screens = []
    for i in range(ns):
        off, csize, h, y0, split, frames, kind, _ = SCREEN.unpack_from(blob, s_off + i * SCREEN.size)
        screens.append({"offset": d_off + off, "csize": csize, "height": h, "y0": y0, "split": split, "frames": frames, "kind": kind})
    return {"chapters": chapters, "verses": verses, "screens": screens, "data_offset": d_off}


def screen_mask(blob, screen):
    raw = unpackbits(blob[screen["offset"]:screen["offset"] + screen["csize"]], screen["height"] * WIDTH_BYTES)
    return unpack_mask(raw, screen["height"])
