// Drives sketch.ino with a script on stdin and prints what the MCU does.
//   set <pin> <0|1>   drive an input pin (buttons are active LOW)
//   run <ms>          run loop() once per simulated millisecond
//   fb <code>         Linux calls Bridge.call("feedback", code)
// Output lines: "notify button <code> @<ms>" and "pin <pin> <level> @<ms>" (outputs, on change).
#include <cstdio>
#include <cstring>
#include "mock_arduino.h"
#include "Arduino_RouterBridge.h"

FakeBridge Bridge;
static unsigned long now_ms = 0;
static int input_level[64];
static int output_level[64];
static bool is_output[64];

unsigned long millis() { return now_ms; }
void pinMode(int pin, int mode) { is_output[pin] = (mode == OUTPUT); }
int digitalRead(int pin) { return input_level[pin]; }
void digitalWrite(int pin, int level) {
  if (output_level[pin] != level) {
    output_level[pin] = level;
    std::printf("pin %d %d @%lu\n", pin, level, now_ms);
  }
}

void setup();
void loop();

int main() {
  for (int i = 0; i < 64; i++) { input_level[i] = HIGH; output_level[i] = LOW; }
  setup();
  char cmd[16];
  long a, b;
  while (std::scanf("%15s", cmd) == 1) {
    if (!std::strcmp(cmd, "set") && std::scanf("%ld %ld", &a, &b) == 2) {
      input_level[a] = (int)b;
    } else if (!std::strcmp(cmd, "run") && std::scanf("%ld", &a) == 1) {
      for (long i = 0; i < a; i++) { loop(); now_ms++; }
    } else if (!std::strcmp(cmd, "fb") && std::scanf("%ld", &a) == 1) {
      if (Bridge.feedback) Bridge.feedback((int)a);
    }
  }
  return 0;
}
