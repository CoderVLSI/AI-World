#pragma once
#include <stdint.h>
#define TFT_BLACK 0x0000
#define TFT_RED 0xF800
struct TFT_eSPI {
  void init() {}
  void setRotation(uint8_t) {}
  void setSwapBytes(bool) {}
  void fillScreen(uint32_t) {}
  void setTextColor(uint32_t) {}
  int16_t drawString(const char*, int32_t, int32_t, uint8_t) { return 0; }
  void pushImage(int32_t, int32_t, int32_t, int32_t, uint16_t*) {}
};
