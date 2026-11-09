// CAITANYA / Gita TFT player core: reads the flash image and draws one frame. Header-only, no Arduino or ESP32 dependencies,
// so the same code runs on the microcontroller and (for the pixel-for-pixel test) on a computer.
// It must stay in step with gita_tft/scene.py and gita_tft/flashimage.py (tests/test_gita_tft.py compares them).
#pragma once
#include <stdint.h>
#include <string.h>

namespace gita {

static const int W = 320, H = 240, CX = 160, CY = 120;
static const int FADE_STEPS = 6;
static const uint16_t DARKEN_QUARTER = 0x39E7;     // a pixel in a letter's halo is darkened to 1/4

// 256-step sine table, value = round(256 * sin(2*pi*i/256)); cos(a) = SIN[(a + 64) & 255]
static const int16_t SIN_TABLE[256] = {
    0, 6, 13, 19, 25, 31, 38, 44, 50, 56, 62, 68, 74, 80, 86, 92,
    98, 104, 109, 115, 121, 126, 132, 137, 142, 147, 152, 157, 162, 167, 172, 177,
    181, 185, 190, 194, 198, 202, 206, 209, 213, 216, 220, 223, 226, 229, 231, 234,
    237, 239, 241, 243, 245, 247, 248, 250, 251, 252, 253, 254, 255, 255, 256, 256,
    256, 256, 256, 255, 255, 254, 253, 252, 251, 250, 248, 247, 245, 243, 241, 239,
    237, 234, 231, 229, 226, 223, 220, 216, 213, 209, 206, 202, 198, 194, 190, 185,
    181, 177, 172, 167, 162, 157, 152, 147, 142, 137, 132, 126, 121, 115, 109, 104,
    98, 92, 86, 80, 74, 68, 62, 56, 50, 44, 38, 31, 25, 19, 13, 6,
    0, -6, -13, -19, -25, -31, -38, -44, -50, -56, -62, -68, -74, -80, -86, -92,
    -98, -104, -109, -115, -121, -126, -132, -137, -142, -147, -152, -157, -162, -167, -172, -177,
    -181, -185, -190, -194, -198, -202, -206, -209, -213, -216, -220, -223, -226, -229, -231, -234,
    -237, -239, -241, -243, -245, -247, -248, -250, -251, -252, -253, -254, -255, -255, -256, -256,
    -256, -256, -256, -255, -255, -254, -253, -252, -251, -250, -248, -247, -245, -243, -241, -239,
    -237, -234, -231, -229, -226, -223, -220, -216, -213, -209, -206, -202, -198, -194, -190, -185,
    -181, -177, -172, -167, -162, -157, -152, -147, -142, -137, -132, -126, -121, -115, -109, -104,
    -98, -92, -86, -80, -74, -68, -62, -56, -50, -44, -38, -31, -25, -19, -13, -6,
};

#pragma pack(push, 1)
struct Header { char magic[4]; uint16_t version, chapters, verses, screens; uint32_t chapter_off, verse_off, screen_off, data_off, total; };
struct ChapterRec {
  uint8_t id, verses; uint16_t first_verse, bg_top, bg_bottom; uint16_t palette[6];
  uint8_t symmetry, layers, dot, pad; uint8_t points[8], radius[8], petals[8], amp[8]; int8_t speed[8], wobble[8]; uint8_t phase[8];
  uint16_t accent, main_color;
};
struct VerseRec { uint8_t chapter, verse; uint16_t first_screen; uint8_t screens; };
struct ScreenRec { uint32_t offset; uint16_t csize, height, y0, split, frames; uint8_t kind, pad; };
#pragma pack(pop)
static_assert(sizeof(Header) == 32, "Header size");
static_assert(sizeof(ChapterRec) == 84, "ChapterRec size");
static_assert(sizeof(VerseRec) == 5, "VerseRec size");
static_assert(sizeof(ScreenRec) == 16, "ScreenRec size");

static const int MASK_ROW_BYTES = 80;      // 320 pixels, 4 per byte, first pixel in the high bits
static const int MASK_MAX_BYTES = MASK_ROW_BYTES * H;

struct Image {
  const uint8_t* base = nullptr;
  const Header* head = nullptr;
  bool open(const uint8_t* blob, uint32_t size) {
    base = blob; head = reinterpret_cast<const Header*>(blob);
    return size >= sizeof(Header) && memcmp(head->magic, "GITA", 4) == 0 && head->version == 1 && head->total == size;
  }
  const ChapterRec& chapter(int i) const { return *reinterpret_cast<const ChapterRec*>(base + head->chapter_off + i * sizeof(ChapterRec)); }
  const VerseRec& verse(int i) const { return *reinterpret_cast<const VerseRec*>(base + head->verse_off + i * sizeof(VerseRec)); }
  const ScreenRec& screen(int i) const { return *reinterpret_cast<const ScreenRec*>(base + head->screen_off + i * sizeof(ScreenRec)); }
  const uint8_t* screen_data(const ScreenRec& s) const { return base + head->data_off + s.offset; }
};

// PackBits: control 0..127 = copy n+1 literal bytes; 129..255 = repeat the next byte 257-n times. Returns bytes written (0 on error).
inline uint32_t unpackbits(const uint8_t* src, uint32_t csize, uint8_t* dst, uint32_t raw) {
  uint32_t i = 0, o = 0;
  while (i < csize && o < raw) {
    uint8_t c = src[i++];
    if (c < 128) {
      uint32_t n = c + 1;
      if (i + n > csize || o + n > raw) return 0;
      memcpy(dst + o, src + i, n); i += n; o += n;
    } else if (c > 128) {
      uint32_t n = 257 - c;
      if (i >= csize || o + n > raw) return 0;
      memset(dst + o, src[i++], n); o += n;
    }
  }
  return o == raw ? o : 0;
}

// Mix RGB565 a toward b by weight/denom, per channel (integer arithmetic; matches scene.mix565).
inline uint16_t mix565(uint16_t a, uint16_t b, int weight, int denom) {
  uint16_t out = 0;
  const int shifts[3] = {11, 5, 0}, masks[3] = {31, 63, 31};
  for (int c = 0; c < 3; c++) {
    const int ca = (a >> shifts[c]) & masks[c], cb = (b >> shifts[c]) & masks[c];
    out |= (uint16_t)(((ca * (denom - weight) + cb * weight) / denom) << shifts[c]);
  }
  return out;
}

inline int fade_level(int k, int frames) {
  int f = k < frames - 1 - k ? k : frames - 1 - k;
  if (f > FADE_STEPS) f = FADE_STEPS;
  return f < 0 ? 0 : f;
}

inline uint16_t gradient(const ChapterRec& ch, int y) {
  uint16_t out = 0;
  const int shifts[3] = {11, 5, 0}, masks[3] = {31, 63, 31};
  for (int c = 0; c < 3; c++) {
    int a = (ch.bg_top >> shifts[c]) & masks[c], b = (ch.bg_bottom >> shifts[c]) & masks[c];
    out |= (uint16_t)(((a * (H - 1 - y) + b * y) / (H - 1)) << shifts[c]);
  }
  return out;
}

// Draw rows [row0, row0 + rows) of frame (t, k) into out (rows * W pixels, RGB565, native byte order).
// `scratch` is another rows * W uint16_t buffer for the art. `mask` is the decoded text mask (or nullptr), drawn at text_y0 for text_h rows.
inline void render_strip(uint16_t* out, uint16_t* scratch, int row0, int rows, const ChapterRec& ch,
                         const uint8_t* mask, int text_y0, int text_h, int split, int32_t t, int k, int frames) {
  memset(scratch, 0, sizeof(uint16_t) * rows * W);
  const int sym = ch.symmetry;
  for (int l = 0; l < ch.layers; l++) {
    const int n = ch.points[l];
    for (int i = 0; i < n; i++) {
      const int a = ((i * 256) / n + t * ch.speed[l]) & 255;
      const int r = ch.radius[l] + (((int32_t)SIN_TABLE[(a * ch.petals[l] + ch.phase[l] + t * ch.wobble[l]) & 255] * ch.amp[l]) >> 8);
      for (int kk = 0; kk < sym; kk++) {
        const int ang = (a + (kk * 256) / sym) & 255;
        const int x = CX + (((int32_t)SIN_TABLE[(ang + 64) & 255] * r) >> 8);
        const int y = CY + (((int32_t)SIN_TABLE[ang] * r) >> 8);
        const uint16_t col = ch.palette[(l + i / 8 + kk) % 6];
        const int count = ch.dot == 1 ? 1 : 4;
        for (int d = 0; d < count; d++) {
          const int xs = x + (d & 1), ys = y + (d >> 1);
          if (xs >= 0 && xs < W && ys >= row0 && ys < row0 + rows) scratch[(ys - row0) * W + xs] |= col;
        }
      }
    }
  }
  const int fade = fade_level(k, frames);
  for (int yy = 0; yy < rows; yy++) {
    const int y = row0 + yy;
    const uint16_t bg = gradient(ch, y);
    uint16_t* line = out + yy * W;
    const uint16_t* art = scratch + yy * W;
    for (int x = 0; x < W; x++) line[x] = art[x] ? art[x] : bg;
    if (mask && y >= text_y0 && y < text_y0 + text_h) {
      const int ty = y - text_y0;
      const uint16_t color = ty < split ? ch.accent : ch.main_color;
      const uint8_t* mrow = mask + ty * MASK_ROW_BYTES;
      for (int x = 0; x < W; x++) {
        uint16_t p = line[x];
        const int q = (mrow[x >> 2] >> (6 - 2 * (x & 3))) & 3;
        if (q >= 1) {
          const uint16_t dark = (uint16_t)((p >> 2) & DARKEN_QUARTER);          // halo: toward 1/4 brightness as the screen fades in
          p = mix565(p, dark, fade, FADE_STEPS);
          if (q >= 2) p = mix565(p, color, (q == 3 ? 3 : 2) * fade, 3 * FADE_STEPS);
        }
        line[x] = p;
      }
    }
  }
}

}  // namespace gita
