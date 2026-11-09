// CAITANYA Gita TFT player (ESP32 + a 320x240 SPI TFT, using the TFT_eSPI library).
// Plays the flash image built by `python -m gita_tft.build`: Sanskrit verses and their transliteration over a mandala drawn live every frame.
// Read-only: the image sits in its own flash partition ("gita") and is read in place; nothing is written at run time.
// NOT yet run on hardware. The drawing core (gita_core.h) is tested to match the Python reference pixel for pixel on a computer.
#include <Arduino.h>
#include <TFT_eSPI.h>
#include "esp_partition.h"
#include "gita_core.h"

static const int STRIP_ROWS = 24;            // the frame is drawn and sent 24 rows at a time (two 15 KB buffers, no full-frame buffer)
static const int FPS = 10;
static const int BUTTON_PIN = 0;             // BOOT button on most boards: short press = next chapter (optional)

static TFT_eSPI tft;
static gita::Image image;
static uint8_t mask[gita::MASK_MAX_BYTES];
static uint16_t strip_out[STRIP_ROWS * gita::W];
static uint16_t strip_scratch[STRIP_ROWS * gita::W];

static int chapter_index = 0, verse_in_chapter = 0, screen_in_verse = 0, frame_k = 0;
static int32_t art_t = 0;
static bool need_screen = true;
static uint32_t next_frame_ms = 0;

static const gita::ScreenRec* current_screen() {
  const gita::ChapterRec& ch = image.chapter(chapter_index);
  const gita::VerseRec& v = image.verse(ch.first_verse + verse_in_chapter);
  return &image.screen(v.first_screen + screen_in_verse);
}

static void advance() {
  const gita::ChapterRec& ch = image.chapter(chapter_index);
  const gita::VerseRec& v = image.verse(ch.first_verse + verse_in_chapter);
  frame_k = 0;
  need_screen = true;
  if (++screen_in_verse < v.screens) return;
  screen_in_verse = 0;
  if (++verse_in_chapter < ch.verses) return;
  verse_in_chapter = 0;
  art_t = 0;
  chapter_index = (chapter_index + 1) % image.head->chapters;
}

static void next_chapter() {
  verse_in_chapter = screen_in_verse = frame_k = 0;
  art_t = 0;
  need_screen = true;
  chapter_index = (chapter_index + 1) % image.head->chapters;
}

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  tft.init();
  tft.setRotation(1);                        // landscape 320x240; change if your display is mounted differently
  tft.setSwapBytes(true);                    // our pixels are native RGB565; TFT_eSPI wants them byte-swapped
  tft.fillScreen(TFT_BLACK);
  const esp_partition_t* part = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, (esp_partition_subtype_t)0x40, "gita");
  const void* mapped = nullptr;
  spi_flash_mmap_handle_t handle;
  if (!part || esp_partition_mmap(part, 0, part->size, ESP_PARTITION_MMAP_DATA, &mapped, &handle) != ESP_OK) {
    tft.setTextColor(TFT_RED); tft.drawString("no 'gita' partition", 8, 8, 2);
    while (true) delay(1000);
  }
  const uint32_t total = reinterpret_cast<const gita::Header*>(mapped)->total;
  if (total > part->size || !image.open(reinterpret_cast<const uint8_t*>(mapped), total)) {
    tft.setTextColor(TFT_RED); tft.drawString("bad Gita image in flash", 8, 8, 2);
    while (true) delay(1000);
  }
  next_frame_ms = millis();
}

void loop() {
  if (digitalRead(BUTTON_PIN) == LOW) { next_chapter(); delay(300); }
  if (need_screen) {
    const gita::ScreenRec* s = current_screen();
    if (!gita::unpackbits(image.screen_data(*s), s->csize, mask, (uint32_t)s->height * gita::MASK_ROW_BYTES)) { advance(); return; }
    need_screen = false;
  }
  const gita::ScreenRec* s = current_screen();
  const gita::ChapterRec& ch = image.chapter(chapter_index);
  for (int row0 = 0; row0 < gita::H; row0 += STRIP_ROWS) {
    const int rows = row0 + STRIP_ROWS <= gita::H ? STRIP_ROWS : gita::H - row0;
    gita::render_strip(strip_out, strip_scratch, row0, rows, ch, mask, s->y0, s->height, s->split, art_t, frame_k, s->frames);
    tft.pushImage(0, row0, gita::W, rows, strip_out);
  }
  art_t++;
  if (++frame_k >= s->frames) advance();
  const uint32_t now = millis();
  next_frame_ms += 1000 / FPS;
  if ((int32_t)(next_frame_ms - now) > 0) delay(next_frame_ms - now); else next_frame_ms = now;
}
