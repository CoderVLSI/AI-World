// Host test harness: renders one frame with the SAME core the TFT player uses, so tests can compare it with the Python reference.
//   host_render image.bin chapter_index screen_index t k strip_rows > frame.raw      (240*320 little-endian uint16 RGB565)
#include <cstdio>
#include <cstdlib>
#include <vector>
#include "gita_player/gita_core.h"

int main(int argc, char** argv) {
  if (argc < 7) { fprintf(stderr, "usage: host_render image.bin chapter screen t k strip_rows\n"); return 2; }
  FILE* f = fopen(argv[1], "rb");
  if (!f) return 3;
  fseek(f, 0, SEEK_END); long size = ftell(f); fseek(f, 0, SEEK_SET);
  std::vector<uint8_t> blob(size);
  if (fread(blob.data(), 1, size, f) != (size_t)size) return 4;
  fclose(f);
  gita::Image img;
  if (!img.open(blob.data(), (uint32_t)size)) { fprintf(stderr, "bad image\n"); return 5; }
  const int chapter = atoi(argv[2]), screen_index = atoi(argv[3]), t = atoi(argv[4]), k = atoi(argv[5]), strip = atoi(argv[6]);
  const gita::ChapterRec& ch = img.chapter(chapter);
  const gita::ScreenRec& s = img.screen(screen_index);
  std::vector<uint8_t> mask(gita::MASK_MAX_BYTES);
  if (!gita::unpackbits(img.screen_data(s), s.csize, mask.data(), (uint32_t)s.height * gita::MASK_ROW_BYTES)) { fprintf(stderr, "bad screen\n"); return 6; }
  std::vector<uint16_t> out(strip * gita::W), scratch(strip * gita::W);
  for (int row0 = 0; row0 < gita::H; row0 += strip) {
    int rows = row0 + strip <= gita::H ? strip : gita::H - row0;
    gita::render_strip(out.data(), scratch.data(), row0, rows, ch, mask.data(), s.y0, s.height, s.split, t, k, s.frames);
    fwrite(out.data(), sizeof(uint16_t), rows * gita::W, stdout);
  }
  return 0;
}
