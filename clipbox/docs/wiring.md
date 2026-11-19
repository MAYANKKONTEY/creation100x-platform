# Wiring

The UNO Q's header pins use **3.3 V logic**. Buttons only ever connect a pin to GND, so they are safe on any digital pin.

| Part | UNO Q pin | Connection |
|---|---|---|
| REC button | D2 | One leg to D2, other leg to GND (internal pull-up, no resistor needed) |
| CLIP button | D3 | One leg to D3, other leg to GND |
| UNDO button | D4 | One leg to D4, other leg to GND |
| Buzzer (active) | D8 | Through a transistor, see below |
| Red LED | D9 | D9 → 220 Ω → LED long leg (+). Short leg (−) → GND |
| Green LED | D10 | D10 → 220 Ω → LED long leg (+). Short leg (−) → GND |

To use other pins, change the `PIN_...` lines at the top of `app/sketch/sketch.ino`.

## Buzzer

Many 3.3–5 V active buzzers draw 20–30 mA, more than a microcontroller pin should supply. Drive it through a small NPN transistor (2N2222, BC547 or similar):

```
D8 ──[1 kΩ]── base
              collector ── buzzer (−)      buzzer (+) ── 5V
              emitter   ── GND
```

If your buzzer's datasheet says it draws 10 mA or less at 3.3 V, you can connect it directly: D8 → buzzer (+), buzzer (−) → GND.

## Tips

- Put the box out of the microphone's reach, or use soft tactile buttons. Clicky arcade buttons are loud on a recording.
- Space the buttons so REC is not right next to CLIP. You'll press CLIP without looking.
- Use a 5 V / 3 A USB-C PD supply on the hub. Weak chargers cause random resets.

## Quick test (Week 1 "done")

1. Run the app in App Lab. The green LED blinks 3 times and the console prints `[clipbox] Sessions folder: ...`.
2. Tap **REC**: 2 beeps, red LED on (solid with a mic, blinking without).
3. Press **CLIP**: green flash, and the console prints `[clipbox] CLIP #1 at 00:00:04.210 ...`.
4. Press **UNDO**: 2 quick green blinks, console prints `UNDO removed CLIP #1`.
5. **Hold REC** for 1.5 s: 3 beeps, red LED off, console prints the session folder.

If the LEDs or buzzer never react but the console shows the presses, the `feedback` call from Linux isn't reaching the sketch. Check the App Lab console for `feedback ... not delivered` lines.
