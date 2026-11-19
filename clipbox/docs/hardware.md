# Hardware

Prices are rough (India, late 2026). Check before you buy. Robu.in, Amazon.in and local electronics markets stock all of it.

| Part | Qty | Approx. Rs | Why |
|---|---|---|---|
| Arduino UNO Q (2 GB or 4 GB) | 1 | — | Linux side records and saves; MCU side reads buttons |
| USB-C hub with PD power input | 1 | 800–1,500 | The board has one USB-C port; the hub adds USB-A ports and power |
| 5 V / 3 A USB-C PD power supply | 1 | 400–800 | Weak chargers cause random resets |
| Push buttons (30 mm arcade or tactile) | 3 | 30–300 | REC, CLIP, UNDO |
| LEDs, red + green, with 220 Ω resistors | 2 | 15 | On-air light, clip confirmation |
| Active buzzer, 3.3–5 V | 1 | 20–40 | Sync beeps and confirmations |
| NPN transistor (2N2222 / BC547) + 1 kΩ resistor | 1 | 10 | Drives the buzzer safely (see [wiring](wiring.md)) |
| USB microphone, class-compliant | 1 | varies | Optional: lets the box record audio itself |
| Jumper wires + breadboard | 1 set | 100–200 | Prototyping |
| Project box or 3D-printed case | 1 | 100–500 | Later, for a finished look |

**USB mic:** "class-compliant" (plug-and-play, no driver) mics show up on Linux as `USB-Audio` and work with `arecord`. Check with `arecord -l` on the board after plugging it in.

**Software on the board:** Arduino App Lab (pre-installed). **On your laptop:** Python 3.9+, ffmpeg, and optionally `faster-whisper` for captions.
