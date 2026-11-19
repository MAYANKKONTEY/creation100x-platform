"""Runs app/python/main.py exactly as App Lab would, against a fake board.

The fake Bridge plays the MCU (button presses in, feedback out), and a fake `arecord`
script records a real WAV file, so this covers main.py, the recorder and the files on disk.
"""

import atexit
import json
import queue  # noqa: F401  imported before time.monotonic is faked, so it binds the real clock
import runpy
import signal
import subprocess  # noqa: F401  same reason
import sys
import threading  # noqa: F401  same reason
import time

import pytest

from clipbox_core import Button, Feedback, wav_duration

REAL_SLEEP = time.sleep


def wait_for(condition, timeout=10.0):
    end = time.perf_counter() + timeout
    while time.perf_counter() < end:
        if condition():
            return
        REAL_SLEEP(0.02)
    raise AssertionError("timed out waiting for condition")


@pytest.fixture
def board(monkeypatch, root, clock):
    monkeypatch.syspath_prepend(str(root / "tests" / "fake_board"))
    for name in [m for m in sys.modules if m == "arduino" or m.startswith("arduino.")]:
        monkeypatch.delitem(sys.modules, name)
    from arduino.app_utils import App, Bridge

    Bridge.reset()
    monkeypatch.setattr(time, "monotonic", clock)
    monkeypatch.setattr(time, "sleep", clock.sleep)
    monkeypatch.setattr(signal, "signal", lambda *a: None)
    monkeypatch.setattr(atexit, "register", lambda *a: None)
    return App, Bridge


def run_main(root):
    runpy.run_path(str(root / "app" / "python" / "main.py"), run_name="__main__")


def feedback_codes(bridge):
    return [c[1] for c in bridge.calls if c[0] == "feedback"]


def test_full_session_with_audio(board, root, clock, tmp_path, monkeypatch):
    App, Bridge = board
    data_dir = tmp_path / "sessions"
    monkeypatch.setenv("CLIPBOX_DATA_DIR", str(data_dir))
    monkeypatch.setenv("CLIPBOX_AUDIO_DEVICE", "plughw:fake")
    monkeypatch.setenv("CLIPBOX_ARECORD_BIN", f"{sys.executable} {root / 'tests' / 'fake_arecord.py'}")
    monkeypatch.setenv("CLIPBOX_SAMPLE_RATE", "8000")

    def press(code, loop):
        Bridge.mcu_notify("button", code)
        loop()

    def scenario(loop):
        assert "button" in Bridge.provided
        press(Button.REC, loop)
        session = next(data_dir.iterdir())
        wait_for(lambda: (session / "audio.wav").exists())
        clock.advance(65)
        press(Button.CLIP, loop)  # t = 65
        clock.advance(30)
        press(Button.CLIP, loop)  # t = 95
        clock.advance(2)
        press(Button.UNDO, loop)  # removes t = 95
        clock.advance(100)
        press(Button.CLIP, loop)  # t = 197
        REAL_SLEEP(0.3)  # let the fake recorder write some audio
        loop()  # idle tick: recorder still alive
        press(Button.REC, loop)  # tap: hint only
        press(Button.REC_HOLD, loop)  # hold: stop

    App.scenario = scenario
    run_main(root)

    assert feedback_codes(Bridge) == [
        Feedback.READY,
        Feedback.REC_AUDIO,
        Feedback.CLIP,
        Feedback.CLIP,
        Feedback.UNDO,
        Feedback.CLIP,
        Feedback.HINT,
        Feedback.STOP,
    ]
    session = next(data_dir.iterdir())
    data = json.loads((session / "markers.json").read_text())
    assert data["mode"] == "audio"
    assert data["audio_device"] == "plughw:fake"
    assert [m["t"] for m in data["markers"]] == [65.0, 197.0]
    assert [m["t"] for m in data["undone"]] == [95.0]
    assert data["ended_at"] is not None and data["interrupted"] is False
    assert data["audio_offset"] == pytest.approx(0.6)
    for name in ("markers.csv", "audacity_labels.txt", "chapters.txt", "audio.wav"):
        assert (session / name).exists(), name
    assert wav_duration(session / "audio.wav") > 0


def test_marker_only_when_no_mic(board, root, clock, tmp_path, monkeypatch):
    App, Bridge = board
    data_dir = tmp_path / "sessions"
    monkeypatch.setenv("CLIPBOX_DATA_DIR", str(data_dir))
    monkeypatch.setenv("CLIPBOX_AUDIO_DEVICE", "none")

    def scenario(loop):
        for code, wait in [(Button.REC, 0), (Button.CLIP, 42), (Button.REC_HOLD, 10)]:
            clock.advance(wait)
            Bridge.mcu_notify("button", code)
            loop()

    App.scenario = scenario
    run_main(root)
    data = json.loads(next(data_dir.iterdir()).joinpath("markers.json").read_text())
    assert data["mode"] == "marker-only"
    assert [m["t"] for m in data["markers"]] == [42.0]
    assert feedback_codes(Bridge)[1] == Feedback.REC_MARKERS
