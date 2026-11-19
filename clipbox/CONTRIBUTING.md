# Contributing

Thanks for helping. The most useful contribution right now is **running ClipBox on a real UNO Q** and reporting what happened.

## Hardware reports

Open an issue with:

- Board (UNO Q 2 GB / 4 GB) and App Lab version
- What worked and what didn't, from the quick test in [docs/wiring.md](docs/wiring.md)
- The App Lab console output
- Your USB mic model and the output of `arecord -l`

## Code changes

1. Fork, create a branch, make your change.
2. Run the tests: `pip install -r requirements-dev.txt`, then `pytest`. The full run needs ffmpeg and a C++ compiler.
3. If you change a button or feedback code, change it in **both** `app/sketch/sketch.ino` and `app/python/clipbox_core.py`. `tests/test_protocol.py` fails if they differ.
4. Keep the board side light. Anything slow (transcription, video) belongs in `tools/`.
5. Open a pull request that says what you changed and how you tested it.

Every contributor is credited in the README.

## Layout notes

- `clipbox_core.py` has no Bridge or board imports, so it runs anywhere. Put logic there and keep `main.py` as thin wiring.
- `tools/clipper.py` is standalone (standard library + ffmpeg) so people can copy just that file.
- CI runs from `.github/workflows/clipbox-tests.yml`. If ClipBox moves to its own repository, move that file into the new repo's `.github/workflows/` and remove the `working-directory` and `paths` lines.
