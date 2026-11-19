# Roadmap

Pick v0.2 features from what the first five outside users ask for, not from this list.

## v0.1 (now)

- REC / CLIP / UNDO with LED and buzzer feedback, hold-to-stop
- Audio recording with a USB mic, or marker-only mode
- Crash-safe markers, recovery of interrupted sessions
- Exports: JSON, CSV, Audacity labels, YouTube chapters
- Clipper: audio clips, camera clips, 9:16 crop, audiograms, Whisper captions

## First: confirm on real hardware

- [ ] Bridge calls work both ways on a UNO Q (button events in, feedback out)
- [ ] `arecord` can reach a USB mic from inside App Lab
- [ ] Sessions folder lands in `/home/arduino/ArduinoApps/clipbox/sessions`
- [ ] Measure the delay between the sync beep and `audio_offset`

## Ideas for v0.2

- **Automatic sync:** find the two start beeps in the camera audio so `--offset` is no longer needed
- **Marker count on the UNO Q's built-in LED matrix**
- **Long-press CLIP** for a longer clip (for example 60 s back)
- **Labels:** a 4th button, or tags added later in a small web page served by the board
- **Download page:** get sessions from the board in a browser instead of SSH
- **Hinglish captions:** compare Whisper models and settings on real episodes, document the best one
- **Highlight ranking:** use the transcript to suggest titles and hooks for each clip
- **Multi-cam:** cut the same markers from several camera files
