// ClipBox - MCU side of the Arduino UNO Q (STM32U585)
//
// Reads the REC, CLIP and UNDO buttons and plays LED/buzzer patterns.
// All decisions (sessions, markers, files) are made by python/main.py on the Linux side:
// this sketch only reports presses and shows the feedback it is told to show.
// Everything is non-blocking (millis()), so a press is never missed while a light blinks.

#include <Arduino_RouterBridge.h>

// ---- Pins (see docs/wiring.md) ---------------------------------------------
const int PIN_BTN_REC = 2;
const int PIN_BTN_CLIP = 3;
const int PIN_BTN_UNDO = 4;
const int PIN_BUZZER = 8;
const int PIN_LED_RED = 9;
const int PIN_LED_GREEN = 10;

// ---- Protocol: must match clipbox_core.py (tests/test_protocol.py checks it) --
// Button codes sent to Linux with Bridge.notify("button", code)
const int BTN_REC = 1;
const int BTN_CLIP = 2;
const int BTN_UNDO = 3;
const int BTN_REC_HOLD = 4;

// Feedback codes Linux sends with Bridge.call("feedback", code)
const int FB_READY = 1;
const int FB_REC_AUDIO = 2;
const int FB_REC_MARKERS = 3;
const int FB_STOP = 4;
const int FB_CLIP = 5;
const int FB_CLIP_BEEP = 6;
const int FB_UNDO = 7;
const int FB_UNDO_BEEP = 8;
const int FB_ERROR = 9;
const int FB_HINT = 10;

// ---- Timing ------------------------------------------------------------------
const unsigned long DEBOUNCE_MS = 30;
const unsigned long HOLD_MS = 1500;  // hold REC this long to stop a session
const unsigned long BLINK_MS = 500;  // red LED blink in marker-only mode

// ---- Patterns: alternating ON,OFF,ON,... durations in ms ------------------------
const uint16_t BEEP_SYNC[] = {200, 150, 200};  // session start: first beep = sync point
const uint16_t BEEP_STOP[] = {150, 100, 150, 100, 150};
const uint16_t BEEP_ONE[] = {120};
const uint16_t BEEP_UNDO[] = {60, 80, 60};
const uint16_t BEEP_ERROR[] = {500};

const uint16_t GREEN_READY[] = {100, 100, 100, 100, 100};
const uint16_t GREEN_CLIP[] = {400};
const uint16_t GREEN_UNDO[] = {80, 100, 80};
const uint16_t RED_FLICKER[] = {60, 60, 60, 60, 60, 60, 60};

#define LEN(a) (sizeof(a) / sizeof((a)[0]))

struct Pattern {
  int pin;
  const uint16_t* steps;
  uint8_t count;
  uint8_t index;
  unsigned long changedAt;
  bool active;
};

struct PressButton {
  int pin;
  int code;
  int holdCode;  // 0 = no hold event
  int stable;    // debounced level (HIGH = released, INPUT_PULLUP)
  int lastRead;
  unsigned long changedAt;
  unsigned long pressedAt;
  bool holdSent;
};

enum RedMode { RED_OFF, RED_SOLID, RED_BLINK };

Pattern buzzer = {PIN_BUZZER, nullptr, 0, 0, 0, false};
Pattern green = {PIN_LED_GREEN, nullptr, 0, 0, 0, false};
Pattern redFlash = {PIN_LED_RED, nullptr, 0, 0, 0, false};
RedMode redMode = RED_OFF;

PressButton buttons[] = {
  {PIN_BTN_REC, BTN_REC, BTN_REC_HOLD, HIGH, HIGH, 0, 0, false},
  {PIN_BTN_CLIP, BTN_CLIP, 0, HIGH, HIGH, 0, 0, false},
  {PIN_BTN_UNDO, BTN_UNDO, 0, HIGH, HIGH, 0, 0, false},
};

void play(Pattern& p, const uint16_t* steps, uint8_t count) {
  p.steps = steps;
  p.count = count;
  p.index = 0;
  p.changedAt = millis();
  p.active = true;
  digitalWrite(p.pin, HIGH);
}

void updatePattern(Pattern& p, unsigned long now) {
  if (!p.active) return;
  if (now - p.changedAt < p.steps[p.index]) return;
  p.index++;
  p.changedAt = now;
  if (p.index >= p.count) {
    p.active = false;
    digitalWrite(p.pin, LOW);
    return;
  }
  digitalWrite(p.pin, (p.index % 2 == 0) ? HIGH : LOW);
}

void updateRed(unsigned long now) {
  if (redFlash.active) {
    updatePattern(redFlash, now);
    return;
  }
  int level = LOW;
  if (redMode == RED_SOLID) level = HIGH;
  if (redMode == RED_BLINK) level = ((now / BLINK_MS) % 2 == 0) ? HIGH : LOW;
  digitalWrite(PIN_LED_RED, level);
}

void updateButton(PressButton& b, unsigned long now) {
  int reading = digitalRead(b.pin);
  if (reading != b.lastRead) {
    b.lastRead = reading;
    b.changedAt = now;
  }
  if (reading != b.stable && now - b.changedAt >= DEBOUNCE_MS) {
    b.stable = reading;
    if (b.stable == LOW) {
      b.pressedAt = now;
      b.holdSent = false;
      Bridge.notify("button", b.code);
    }
  }
  if (b.holdCode && b.stable == LOW && !b.holdSent && now - b.pressedAt >= HOLD_MS) {
    b.holdSent = true;
    Bridge.notify("button", b.holdCode);
  }
}

// Called by Linux. provide_safe runs it from the main loop, so digitalWrite is safe here.
void onFeedback(int code) {
  switch (code) {
    case FB_READY:
      play(green, GREEN_READY, LEN(GREEN_READY));
      break;
    case FB_REC_AUDIO:
      redMode = RED_SOLID;
      play(buzzer, BEEP_SYNC, LEN(BEEP_SYNC));
      break;
    case FB_REC_MARKERS:
      redMode = RED_BLINK;
      play(buzzer, BEEP_SYNC, LEN(BEEP_SYNC));
      break;
    case FB_STOP:
      redMode = RED_OFF;
      play(buzzer, BEEP_STOP, LEN(BEEP_STOP));
      break;
    case FB_CLIP:
      play(green, GREEN_CLIP, LEN(GREEN_CLIP));
      break;
    case FB_CLIP_BEEP:
      play(green, GREEN_CLIP, LEN(GREEN_CLIP));
      play(buzzer, BEEP_ONE, LEN(BEEP_ONE));
      break;
    case FB_UNDO:
      play(green, GREEN_UNDO, LEN(GREEN_UNDO));
      break;
    case FB_UNDO_BEEP:
      play(green, GREEN_UNDO, LEN(GREEN_UNDO));
      play(buzzer, BEEP_UNDO, LEN(BEEP_UNDO));
      break;
    case FB_ERROR:
      play(redFlash, RED_FLICKER, LEN(RED_FLICKER));
      play(buzzer, BEEP_ERROR, LEN(BEEP_ERROR));
      break;
    case FB_HINT:
      play(redFlash, RED_FLICKER, LEN(RED_FLICKER));
      break;
  }
}

void setup() {
  for (PressButton& b : buttons) pinMode(b.pin, INPUT_PULLUP);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);
  digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_LED_GREEN, LOW);

  Bridge.begin();
  Bridge.provide_safe("feedback", onFeedback);
}

void loop() {
  unsigned long now = millis();
  for (PressButton& b : buttons) updateButton(b, now);
  updatePattern(buzzer, now);
  updatePattern(green, now);
  updateRed(now);
}
