# ClipBox

**One button for your podcast's best moments.** Press CLIP the moment something great is said. After the show, one command turns every press into a ready-to-edit clip.

ClipBox is a desk box built on the [Arduino UNO Q](https://docs.arduino.cc/hardware/uno-q/). The microcontroller reads the buttons and drives the lights in real time. The Linux side records audio and saves your markers. Captions and vertical crops run on your laptop, because transcribing long audio is too slow on the board's CPU.

> **Status: v0.1, not yet tested on real hardware.** The Python logic, the clipper and the sketch's button and light timing are covered by 48 automated tests, including a simulated recording session and a host-compiled build of the sketch. The Bridge calls follow Arduino's documented App Lab API, but nobody has run them on a board yet. If you build one, please [report what happened](CONTRIBUTING.md).

## How it works

| Button | Press | Feedback |
|---|---|---|
| **REC** | Tap to start a session | 2 beeps (camera sync point). Red LED **solid** = recording audio, **blinking** = marker-only |
| **REC** | **Hold 1.5 s** to stop (a tap does nothing, so a stray press can't end your episode) | 3 beeps, red LED off |
| **CLIP** | Mark a highlight: 20 s before the press to 10 s after | Green flash (silent by default, so the beep doesn't end up in your clip) |
| **UNDO** | Remove the last marker | 2 quick green blinks |

Every marker is written to disk (with `fsync`) before the light confirms it, so a power cut never loses a highlight. If the board loses power mid-session, the next start closes the session and repairs the WAV header.

## Quick start

1. **Wire it.** 3 buttons, 2 LEDs and a buzzer: [docs/wiring.md](docs/wiring.md). Parts list: [docs/hardware.md](docs/hardware.md).
2. **Create the app.** In Arduino App Lab, create a new app called `clipbox`. Copy in `app/sketch/sketch.ino`, `app/python/main.py`, `app/python/clipbox_core.py` and `app/python/clipbox_settings.json`. Keep the `sketch.yaml` App Lab generated. Run it: the green LED blinks 3 times when the app is ready.
3. **Plug in a USB mic** (optional) through the hub. With `"audio_device": "auto"` the box uses the first USB mic it finds. The App Lab console prints which device it picked. Without a mic, ClipBox runs in marker-only mode and you record on your phone or camera.
4. **Record.** Tap REC, talk, press CLIP at good moments, hold REC to stop. Each session is saved in its own folder.
5. **Make clips** on your laptop:

```bash
tools/pull_sessions.sh arduino@<board-name>.local
```

```bash
python tools/clipper.py sessions/2026-11-20_19-30-05
```

## What each session saves

```
sessions/2026-11-20_19-30-05/
  markers.json          source of truth: every marker, plus undone ones
  markers.csv           for Sheets/Excel
  audacity_labels.txt   File > Import > Labels in Audacity
  chapters.txt          starter YouTube chapters
  audio.wav             only when a mic is connected
  recorder.log          arecord's messages, for troubleshooting
```

All marker times are **seconds after the first REC start beep**. `audio_offset` in `markers.json` says where that beep falls in `audio.wav`, so clips from the box's own recording line up automatically.

## Making clips

The clipper needs Python 3.9+ and [ffmpeg](https://ffmpeg.org/download.html). Captions also need `pip install faster-whisper`.

```bash
# Audio clips (.m4a) from the box's own recording
python tools/clipper.py SESSION

# Clips from your camera. --offset = seconds into the video where the first start beep begins
python tools/clipper.py SESSION --video cam.mp4 --offset 12.4

# Vertical 9:16 for Reels/Shorts, with burned-in captions
python tools/clipper.py SESSION --video cam.mp4 --offset 12.4 --vertical --captions --language hi

# No camera: a vertical waveform video with captions, from audio.wav
python tools/clipper.py SESSION --audiogram --captions
```

Useful flags: `--pre/--post` change the window, `--only 2,5` renders some clips, `--crop-x 0.3` moves the vertical crop left, `--no-merge` keeps overlapping clips separate (by default, presses whose windows overlap become one clip), `--dry-run` prints the plan. Each captioned clip also gets an `.srt` next to it for your editor.

**Finding `--offset`:** open the camera file in any editor or Audacity and look for the two short beeps at the start. Use the time where the first one begins. The box beeps when it starts, so the camera mic must be close enough to hear it.

**Hindi and Hinglish captions:** `--language hi` usually writes Devanagari, while `--language en` tends to write Hinglish in Roman script with more mistakes. Try both on your own episodes. For Devanagari, pass a font that has it, for example `--font "Noto Sans Devanagari"`. Larger models (`--model medium`) are slower but more accurate.

## Settings

Edit `app/python/clipbox_settings.json`, or set `CLIPBOX_<NAME>` environment variables (they win over the file).

| Setting | Default | What it does |
|---|---|---|
| `audio_device` | `auto` | `auto` = first USB mic, `none` = marker-only, or an ALSA name like `plughw:1,0` (from `arecord -l`) |
| `pre_roll` / `post_roll` | `20` / `10` | Seconds kept before and after each CLIP |
| `beep_during_session` | `false` | Beep on CLIP and UNDO too. Off by default because the mic records the beep |
| `stop_requires_hold` | `true` | `false` = a single REC tap stops the session |
| `sample_rate` / `channels` | `48000` / `1` | Recording format |
| `data_dir` | empty | Where sessions go. Empty = `sessions/` inside the app folder |

## Troubleshooting

- **Nothing happens when I press a button.** Check that the App Lab console shows `[clipbox] Sessions folder: ...`. If it does, check the wiring: each button goes between its pin and GND.
- **Red LED blinks when I expected solid (no audio).** The console says why: no USB mic found, or `arecord` failed (see `recorder.log` in the session folder). Run `arecord -l` on the board to see your mic. If App Lab can't reach the mic, use marker-only mode with your phone or camera.
- **`pull_sessions.sh` finds no folder.** Your app folder may have a different name. The console prints the real sessions path at startup; pass it with `CLIPBOX_REMOTE_DIR=/path/to/sessions`.
- **Clips are cut at the wrong place.** Check `--offset` against the first start beep, not the second.

## Development

```bash
pip install -r requirements-dev.txt
```

```bash
pytest
```

The tests need ffmpeg and a C++ compiler (`g++` or `clang++`) for the full run, and skip those parts if either is missing. The tests run a fake board (`tests/fake_board/`) with a fake `arecord`, and compile `sketch.ino` for your computer against a fake Arduino API (`tests/sketch_harness/`). See [CONTRIBUTING.md](CONTRIBUTING.md) and the [roadmap](docs/roadmap.md).

```
app/                      copy into an Arduino App Lab app
  python/main.py          Linux side: Bridge wiring, event queue
  python/clipbox_core.py  sessions, markers, exports, recorder, state machine
  sketch/sketch.ino       MCU side: buttons, LEDs, buzzer
tools/clipper.py          laptop: markers to clips, 9:16 crop, captions
tools/pull_sessions.sh    laptop: copy sessions from the board
tests/                    pytest suite, fake board, sketch harness
docs/                     hardware list, wiring, roadmap
```

## License

MIT. Build it, fork it, sell boxes with it. See [LICENSE](LICENSE).
