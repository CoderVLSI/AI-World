// Minimal stand-ins so the sketch can be compile-checked on a computer (no hardware, no Arduino core). Not used on the device.
#pragma once
#include <stdint.h>
#include <stddef.h>
#define INPUT_PULLUP 2
#define LOW 0
struct SerialStub { void begin(long) {} };
static SerialStub Serial;
inline void pinMode(int, int) {}
inline int digitalRead(int) { return 1; }
inline void delay(uint32_t) {}
inline uint32_t millis() { return 0; }
void setup();
void loop();
