"""Compiles sketch.ino for this computer with a fake Arduino API and checks its behaviour:
debouncing, the REC hold event, and the exact LED/buzzer timings.

This checks the sketch's logic, not the real Bridge library: run it on the board too.
"""

import re
import shutil
import subprocess

import pytest

from clipbox_core import Button, Feedback

CXX = shutil.which("g++") or shutil.which("clang++")
pytestmark = pytest.mark.skipif(CXX is None, reason="needs a C++ compiler")

REC, CLIP, UNDO, BUZZER, RED, GREEN = 2, 3, 4, 8, 9, 10


@pytest.fixture(scope="module")
def harness(tmp_path_factory, root):
    h = root / "tests" / "sketch_harness"
    exe = tmp_path_factory.mktemp("sketch") / "harness"
    subprocess.run(
        [CXX, "-std=c++11", "-Wall", "-Werror", "-I", str(h), "-include", str(h / "mock_arduino.h"),
         "-x", "c++", str(root / "app" / "sketch" / "sketch.ino"), "-x", "c++", str(h / "harness.cpp"),
         "-o", str(exe)],
        check=True,
    )

    def run(script: str):
        out = subprocess.run([str(exe)], input=script, capture_output=True, text=True, check=True).stdout
        notifies = [(int(c), int(t)) for c, t in re.findall(r"notify button (\d+) @(\d+)", out)]
        pins = [(int(p), int(l), int(t)) for p, l, t in re.findall(r"pin (\d+) (\d) @(\d+)", out)]
        return notifies, pins

    return run


def edges(pins, pin):
    return [(level, t) for p, level, t in pins if p == pin]


def test_clean_press_sends_one_event_after_debounce(harness):
    notifies, _ = harness(f"run 100 set {CLIP} 0 run 200 set {CLIP} 1 run 100")
    assert notifies == [(Button.CLIP, 130)]


def test_bouncy_press_is_one_event(harness):
    bounce = " ".join(f"set {UNDO} {i % 2} run 3" for i in range(8))
    notifies, _ = harness(f"run 50 {bounce} set {UNDO} 0 run 100 set {UNDO} 1 run 100")
    assert [c for c, _ in notifies] == [Button.UNDO]


def test_rec_hold_sends_hold_event_once(harness):
    notifies, _ = harness(f"set {REC} 0 run 4000 set {REC} 1 run 100")
    assert notifies == [(Button.REC, 30), (Button.REC_HOLD, 1530)]


def test_short_rec_tap_has_no_hold_event(harness):
    notifies, _ = harness(f"set {REC} 0 run 300 set {REC} 1 run 2000")
    assert [c for c, _ in notifies] == [Button.REC]


def test_sync_beeps_and_solid_red(harness):
    _, pins = harness(f"run 10 fb {Feedback.REC_AUDIO} run 1500")
    # first beep starts the instant the command arrives: that is t = 0 for markers
    assert edges(pins, BUZZER) == [(1, 10), (0, 210), (1, 360), (0, 560)]
    assert edges(pins, RED) == [(1, 10)]


def test_marker_only_blinks_red_and_stop_turns_it_off(harness):
    _, pins = harness(f"fb {Feedback.REC_MARKERS} run 2000 fb {Feedback.STOP} run 1000")
    red = edges(pins, RED)
    assert len(red) >= 4 and red[-1][0] == 0
    beeps = [t for level, t in edges(pins, BUZZER) if level == 1]
    assert len(beeps) == 2 + 3  # 2 start beeps, 3 stop beeps


def test_quiet_clip_flashes_green_without_buzzer(harness):
    _, pins = harness(f"fb {Feedback.CLIP} run 1000")
    assert edges(pins, GREEN) == [(1, 0), (0, 400)]
    assert edges(pins, BUZZER) == []


def test_error_flickers_red_then_restores_mode(harness):
    _, pins = harness(f"fb {Feedback.REC_AUDIO} run 1000 fb {Feedback.ERROR} run 1000")
    red = edges(pins, RED)
    assert red[-1] == (1, red[-1][1])  # back to solid red after the flicker
    assert any(level == 1 for level, _ in edges(pins, BUZZER) if _ >= 1000)
