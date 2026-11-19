// Minimal Arduino API so sketch.ino compiles and runs on a normal computer (tests only).
#pragma once
#include <cstdint>
#include <cstdio>

#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1
#define INPUT_PULLUP 2

unsigned long millis();
void pinMode(int pin, int mode);
void digitalWrite(int pin, int level);
int digitalRead(int pin);
