# Gita on a TFT, from flash

The Bhagavad Gita (all 18 chapters, 701 verses in this edition) as a "video" for a small TFT display driven by an ESP32, stored in the
microcontroller's own flash. Real Sanskrit text, a transliteration made by code, and art that is **generated live on the device**.

## Why it fits in flash
A rendered 2.8 hour video cannot live in a few megabytes. This stores only what cannot be computed cheaply and draws the rest live:
* **The verses** (Sanskrit, plus its Latin transliteration) as pre-shaped 2-bit text masks, PackBits-compressed. Devanagari needs complex-script
  shaping (conjuncts), which a microcontroller cannot do, so shaping happens once, here. All 701 verses, both screens: **6.9 MB**
  (Sanskrit only: 3.7 MB).
* **The art** is not stored: per chapter a few numbers (colours, symmetry, petal counts, speeds; made deterministically from the chapter
  number) describe a rotating mandala that the player draws every frame with integer maths and a 256-step sine table.

## Pipeline
```
python -m gita_tft.prepare_text --source verse.json       # once: extract and validate the Sanskrit (701 verses; counts per chapter checked)
python -m gita_tft.build --chapters 1 --out build/gita_ch1.bin --video build/gita_ch1_preview.mp4     # one chapter + a preview video
python -m gita_tft.build --chapters all --out build/gita_all.bin                                       # the whole Gita (6.9 MB)
python -m gita_tft.build --chapters all --no-translit --out build/gita_sanskrit_only.bin               # Sanskrit only (3.7 MB)
```
The preview video is rendered by the Python reference of the same drawing code the TFT runs (10 frames per second, 320x240).
Pacing is a fixed rule (about 0.1 s per character, 4 s minimum; transliteration 65% of that, 3 s minimum): the whole Gita is about **2 h 50 min** (170 minutes).
It is not a recitation timing.

## On the device
`firmware/gita_player/` is an Arduino sketch for an ESP32 with a 320x240 SPI TFT (TFT_eSPI; pick the driver for your display in TFT_eSPI's
`User_Setup`). It reads the image in place from a flash partition named `gita` and draws 24-row strips (no full-frame buffer).
1. Choose a partition table: `firmware/partitions_8MB.csv` (whole Gita with transliteration) or `partitions_16MB.csv`. A 4 MB module cannot hold
   the whole Gita; build a few chapters with `--chapters 1-3` and a matching partition.
2. Flash the sketch with that partition table, then write the image at the `gita` partition's offset (0x150000 for the 8 MB table):
   `python -m esptool --chip esp32 write_flash 0x150000 build/gita_all.bin`
3. The BOOT button (GPIO 0) skips to the next chapter.

## What is verified, and what is not
* The Sanskrit comes from the public-domain (Unlicense) `gita/gita` repository's `data/verse.json`; only the Sanskrit is used. Counts per chapter
  (47, 72, 43, 42, 29, 47, 30, 28, 34, 42, 55, 20, 35, 27, 20, 24, 28, 78) and each verse's own reference marker are checked. Nothing is written
  or invented by a model. The text was not proof-read word by word against another edition.
* The C++ drawing core (`gita_core.h`) and the Python reference produce **identical pixels** (tested at several strip heights).
* The sketch passes a syntax check against stand-in headers. **It has not been compiled with the Arduino toolchain or run on hardware**: pins,
  display driver, rotation, frame rate and the SPI speed are untested on a real board.
* Fonts: Noto Sans and Noto Sans Devanagari (SIL Open Font License, in `fonts/`).
