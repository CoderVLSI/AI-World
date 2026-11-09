"""The Gita-on-a-TFT pipeline: authentic text, readable layout, a flash image that round-trips, and a C++ player that draws the same pixels."""
import hashlib
import json
import random
import re
import shutil
import struct
import subprocess
from pathlib import Path

import numpy as np
import pytest

from gita_tft import build, flashimage as fi, prepare_text, render, scene, text

ROOT = Path(__file__).resolve().parent.parent
FIRMWARE = ROOT / "gita_tft" / "firmware"
DATA = ROOT / "gita_tft" / "data" / "gita_sanskrit.json"
DATA_SHA256 = "e3799e38c2b25d588aa7e2ad56f05d7eb1a2856f6172050dfd5ce127b3398ed2"
HAVE_GPP = shutil.which("g++") is not None


@pytest.fixture(scope="module")
def chapter1():
    return build.build([1])


@pytest.fixture(scope="module")
def whole():
    return build.build(list(range(1, 19)))


# ------------------------------------------------------------------------------------------------ the text
def test_the_sanskrit_data_is_the_validated_extract_and_is_unchanged():
    assert hashlib.sha256(DATA.read_bytes()).hexdigest() == DATA_SHA256, "the text changed: re-run prepare_text and re-check it"
    chapters = text.chapters()
    assert [len(c) for c in chapters] == prepare_text.VERSES_PER_CHAPTER and sum(len(c) for c in chapters) == 701
    assert prepare_text.validate(chapters) == []
    for ci, c in enumerate(chapters, 1):
        for vi, v in enumerate(c, 1):
            assert (v["chapter"], v["verse"]) == (ci, vi) and v["lines"] and all(line.strip() for line in v["lines"])
            assert not v["speaker"] or v["speaker"].endswith("वाच")


def test_the_reference_marker_parser_accepts_the_source_forms_and_refuses_a_verse_without_one():
    v = prepare_text.parse_verse("श्रीभगवानुवाच\n\nअसंशयं महाबाहो मनो दुर्निग्रहं चलम्।\n\nअभ्यासेन तु कौन्तेय वैराग्येण च गृह्यते।।6.35।।\n ")
    assert (v["chapter"], v["verse"], v["speaker"]) == (6, 35, "श्रीभगवानुवाच") and len(v["lines"]) == 2
    assert prepare_text.parse_verse("एकम्।।18.78।\n")["verse"] == 78            # the source closes 18.78 with a single danda
    assert prepare_text.parse_verse("अर्जुन उवाच\n\nप्रथमा पङ्क्तिः\n\nद्वितीया।।2.4।।")["speaker"] == "अर्जुन उवाच"
    joined = prepare_text.parse_verse("श्री भगवानुवाच\n\nप्रथमा पङ्क्तिः।\n\nद्वितीया।।2.5।।")
    assert joined["speaker"] == "श्री भगवानुवाच", "the joined form of the speaker line is a speaker too"
    half = prepare_text.parse_verse("गुरूनहत्वा हि महानुभावान्\n\nश्रेयो भोक्तुं भैक्ष्यमपीह लोके।।2.5।।")
    assert half["speaker"] == "" and len(half["lines"]) == 2, "a half-verse without a danda is not a speaker"
    with pytest.raises(ValueError):
        prepare_text.parse_verse("बिना संख्या")


def test_transliteration_is_generated_by_code_and_the_screens_have_what_they_should():
    v = text.chapters()[0][0]
    sk, la = text.verse_screens(v)["sanskrit"], text.verse_screens(v)["iast"]
    assert sk[0] == "१.१  धृतराष्ट्र उवाच" and la[0] == "1.1  ·  dhṛtarāṣṭra uvāca"
    assert la[1][0] == "dharmakṣetre kurukṣetre samavetā yuyutsavaḥ|" and la[1][1].endswith("||")
    assert sk[1][-1].endswith("॥") and sk[1][0].endswith("।")


def test_the_reading_pace_is_a_fixed_rule_and_the_whole_gita_is_under_three_hours(whole):
    assert text.reading_frames(["क"]) == 40 and text.reading_frames(["क" * 1000]) == 180
    assert 150 <= whole[1]["minutes"] <= 190, whole[1]["minutes"]


# ------------------------------------------------------------------------------------------------ layout
def test_every_verse_fits_the_screen_in_both_scripts_at_a_readable_size():
    smallest = {"sanskrit": 16, "iast": 11}
    tiny = 0
    for c in text.chapters():
        for v in c:
            for kind, (top, lines) in text.verse_screens(v).items():
                rows, size, top_size = render.layout(kind, top, lines)
                assert size >= smallest[kind]
                tiny += size == smallest[kind]
                assert len(rows) * int(size * render.LINE_GAP) <= render.SCREEN_H - 10 - int(top_size * render.LINE_GAP) - 6
                assert all(render.measure(r, kind, size) <= render.W - 2 * render.MARGIN + 2 for r in rows), (v["chapter"], v["verse"], kind)
    assert tiny < 70, "almost every screen should use a comfortable size"


def test_a_rendered_screen_is_a_320_wide_mask_with_a_halo_and_text_and_a_top_line_split():
    mask, split = render.render_screen("sanskrit", *text.verse_screens(text.chapters()[0][0])["sanskrit"])
    assert all(len(row) == 320 for row in mask) and 100 < len(mask) <= 240 and 0 < split < 40
    values = {q for row in mask for q in row}
    assert values == {0, 1, 2, 3}
    assert mask[0] != [0] * 320 and mask[-1] != [0] * 320, "trimmed to the content"


# ------------------------------------------------------------------------------------------------ the flash image
def test_packbits_round_trips_random_and_run_heavy_data_and_rejects_corruption():
    rng = random.Random(7)
    for _ in range(60):
        data = bytes(rng.choice([0, 0, 0, 1, 255, rng.randrange(256)]) for _ in range(rng.randrange(0, 700)))
        assert fi.unpackbits(fi.packbits(data), len(data)) == data
    assert len(fi.packbits(bytes(20000))) < 400
    with pytest.raises(ValueError):
        fi.unpackbits(fi.packbits(b"abcdef")[:-2], 6)


def test_the_image_round_trips_and_chapter_one_is_small_and_deterministic(chapter1):
    blob, report = chapter1
    assert build.build([1])[0] == blob, "the same input must give the same bytes"
    img = fi.parse_image(blob)
    assert report["verses"] == 47 and len(img["screens"]) == 94 and [v["screens"] for v in img["verses"]] == [2] * 47
    s = img["screens"][0]
    expected, split = render.render_screen("sanskrit", *text.verse_screens(text.chapters()[0][0])["sanskrit"])
    assert fi.screen_mask(blob, s) == expected and s["split"] == split and s["y0"] == (240 - len(expected)) // 2
    assert len(blob) < 600_000
    with pytest.raises(ValueError):
        fi.parse_image(blob[:-1])


def test_the_whole_gita_fits_the_8_mb_partition_and_sanskrit_only_is_smaller(whole):
    blob, report = whole
    assert report["verses"] == 701 and report["screens"] == 1402
    partition = {}
    for line in (FIRMWARE / "partitions_8MB.csv").read_text().splitlines():
        if line and not line.startswith("#"):
            name, _, _, offset, size = [x.strip() for x in line.split(",")]
            partition[name] = (int(offset, 16), int(size, 16))
    assert len(blob) <= partition["gita"][1] and partition["gita"][0] + partition["gita"][1] <= 8 * 1024 * 1024
    assert partition["gita"][0] == 0x150000 and "0x150000" in (ROOT / "gita_tft" / "README.md").read_text(encoding="utf-8")
    assert partition["app0"][0] + partition["app0"][1] <= partition["gita"][0]
    sanskrit_only = build.build([1, 2], translit=False)[0]
    assert len(sanskrit_only) < len(build.build([1, 2])[0]) * 0.75


# ------------------------------------------------------------------------------------------------ the art
def test_each_chapter_has_its_own_deterministic_art_and_it_moves():
    params = [scene.art_params(c) for c in range(1, 19)]
    assert params == [scene.art_params(c) for c in range(1, 19)]
    assert len({json.dumps(p, sort_keys=True) for p in params}) == 18
    ch = params[4]
    a0, a1 = scene.art(ch, 0), scene.art(ch, 1)
    assert (a0 != 0).sum() > 1000 and not np.array_equal(a0, a1), "something is drawn and it changes frame to frame"
    assert np.array_equal(scene.art(ch, 5), scene.art(ch, 5))


def test_text_fades_in_and_out_and_is_fully_visible_in_the_middle(chapter1):
    blob, _ = chapter1
    img = fi.parse_image(blob)
    ch, s = img["chapters"][0], img["screens"][0]
    mask = fi.screen_mask(blob, s)
    first = scene.compose(ch, mask, s["y0"], s["split"], 10, 0, s["frames"])
    middle = scene.compose(ch, mask, s["y0"], s["split"], 10, s["frames"] // 2, s["frames"])
    last = scene.compose(ch, mask, s["y0"], s["split"], 10, s["frames"] - 1, s["frames"])
    plain = scene.compose(ch, None, 0, 0, 10, 0, s["frames"])
    assert np.array_equal(first, plain) and np.array_equal(last, plain), "invisible on the first and last frame"
    assert (middle != plain).sum() > 5000


# ------------------------------------------------------------------------------------------------ the C++ player
def test_the_cpp_header_has_the_python_sine_table_and_struct_sizes():
    header = (FIRMWARE / "gita_player" / "gita_core.h").read_text(encoding="utf-8")
    table = [int(x) for x in re.search(r"SIN_TABLE\[256\] = \{(.*?)\};", header, re.S).group(1).replace("\n", " ").replace(",", " ").split()]
    assert table == scene.SIN
    sizes = {name: int(n) for name, n in re.findall(r"static_assert\(sizeof\((\w+)\) == (\d+)", header)}
    assert sizes == {"Header": fi.HEADER.size, "ChapterRec": fi.CHAPTER.size, "VerseRec": fi.VERSE.size, "ScreenRec": fi.SCREEN.size}


@pytest.mark.skipif(not HAVE_GPP, reason="no g++")
def test_the_cpp_player_draws_exactly_the_pixels_the_python_reference_draws(tmp_path, chapter1):
    blob, _ = chapter1
    exe, image = tmp_path / "host_render", tmp_path / "g.bin"
    subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(FIRMWARE), "-o", str(exe), str(FIRMWARE / "host_render.cpp")], check=True)
    image.write_bytes(blob)
    img = fi.parse_image(blob)
    cases = [(0, 0, 0, 240), (1, 77, 9, 16), (3, 500, 20, 24), (10, 4000, 3, 13), (47, 4100, 40, 240), (90, 9, 2, 7), (93, 6500, 5, 32)]
    for si, t, k, strip in cases:
        s = img["screens"][si]
        k = min(k, s["frames"] - 1)
        ref = scene.compose(img["chapters"][0], fi.screen_mask(blob, s), s["y0"], s["split"], t, k, s["frames"])
        out = subprocess.run([str(exe), str(image), "0", str(si), str(t), str(k), str(strip)], capture_output=True, check=True).stdout
        assert np.array_equal(ref, np.frombuffer(out, dtype=np.uint16).reshape(240, 320)), (si, t, k, strip)


@pytest.mark.skipif(not HAVE_GPP, reason="no g++")
def test_the_cpp_player_refuses_a_corrupt_image(tmp_path, chapter1):
    blob, _ = chapter1
    exe = tmp_path / "host_render"
    subprocess.run(["g++", "-std=c++17", "-O2", "-I", str(FIRMWARE), "-o", str(exe), str(FIRMWARE / "host_render.cpp")], check=True)
    bad = tmp_path / "bad.bin"
    bad.write_bytes(blob[:-5])
    assert subprocess.run([str(exe), str(bad), "0", "0", "0", "0", "16"], capture_output=True).returncode == 5
    flipped = bytearray(blob)
    flipped[fi.HEADER.size + fi.CHAPTER.size + 100] ^= 0xFF
    bad.write_bytes(bytes(flipped))
    assert subprocess.run([str(exe), str(bad), "0", "0", "0", "0", "16"], capture_output=True).returncode in (0, 5, 6)   # never crashes


@pytest.mark.skipif(not HAVE_GPP, reason="no g++")
def test_the_esp32_sketch_passes_a_syntax_check_against_stand_in_headers():
    done = subprocess.run(["g++", "-std=c++17", "-fsyntax-only", "-Wall", "-Wextra", "-I", str(FIRMWARE / "shims"), "-I", str(FIRMWARE / "gita_player"),
                           "-include", "Arduino.h", "-x", "c++", str(FIRMWARE / "gita_player" / "gita_player.ino")], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-1500:]
