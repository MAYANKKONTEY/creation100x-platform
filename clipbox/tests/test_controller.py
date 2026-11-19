import json
from datetime import datetime, timedelta, timezone

import pytest

from clipbox_core import Button, ClipBox, Feedback, RecorderError, Settings


class FakeRecorder:
    instances = []

    def __init__(self, path, device, rate, channels, binary):
        self.path, self.device = path, device
        self._alive = False
        self.stopped = False
        FakeRecorder.instances.append(self)

    def start(self):
        if self.device == "fail":
            raise RecorderError("audio open error")
        self._alive = True
        self.path.write_bytes(b"")
        return 0.0

    def alive(self):
        return self._alive

    def error_text(self):
        return "audio open error"

    def stop(self):
        self._alive = False
        self.stopped = True


@pytest.fixture(autouse=True)
def _reset_recorders():
    FakeRecorder.instances.clear()


def make_box(tmp_path, clock, **settings):
    feedback = []
    wall = [datetime(2026, 11, 20, 19, 30, 0, tzinfo=timezone.utc)]

    def wall_clock():
        wall[0] += timedelta(seconds=1)
        return wall[0]

    box = ClipBox(
        Settings(**{"audio_device": "none", **settings}),
        tmp_path / "sessions",
        feedback=feedback.append,
        log=lambda m: None,
        clock=clock,
        sleep=clock.sleep,
        wall_clock=wall_clock,
        recorder_factory=FakeRecorder,
    )
    box.startup()
    feedback.clear()
    return box, feedback


def markers_json(box_or_folder):
    folder = box_or_folder
    return json.loads((folder / "markers.json").read_text())


def only_session(tmp_path):
    folders = [p for p in (tmp_path / "sessions").iterdir() if p.is_dir()]
    assert len(folders) == 1
    return folders[0]


def test_marker_only_session(tmp_path, clock):
    box, fb = make_box(tmp_path, clock)
    box.handle(Button.REC)
    assert fb == [Feedback.REC_MARKERS]
    clock.advance(65)
    box.handle(Button.CLIP)
    clock.advance(30)
    box.handle(Button.CLIP)
    box.handle(Button.UNDO)
    clock.advance(10)
    box.handle(Button.REC)  # a tap does not stop
    assert box.recording
    box.handle(Button.REC_HOLD)
    assert not box.recording
    assert fb == [Feedback.REC_MARKERS, Feedback.CLIP, Feedback.CLIP, Feedback.UNDO, Feedback.HINT, Feedback.STOP]
    data = markers_json(only_session(tmp_path))
    assert data["mode"] == "marker-only"
    assert data["audio_offset"] is None
    assert [m["t"] for m in data["markers"]] == [65.0]
    assert data["duration"] == pytest.approx(105.0)
    assert data["ended_at"] is not None


def test_press_time_comes_from_the_event_not_processing(tmp_path, clock):
    box, _ = make_box(tmp_path, clock)
    box.handle(Button.REC)
    pressed = clock.now + 12.0
    clock.advance(12.5)  # event handled half a second late
    box.handle(Button.CLIP, at=pressed)
    assert markers_json(only_session(tmp_path))["markers"][0]["t"] == 12.0


def test_audio_session_offset_and_recorder_stop(tmp_path, clock):
    box, fb = make_box(tmp_path, clock, audio_device="plughw:1,0", recorder_warmup=0.6)
    box.handle(Button.REC)
    rec = FakeRecorder.instances[0]
    assert rec.device == "plughw:1,0"
    assert fb == [Feedback.REC_AUDIO]
    data = markers_json(only_session(tmp_path))
    assert data["mode"] == "audio"
    assert data["audio_offset"] == pytest.approx(0.6)  # beeps start after the mic warm-up
    clock.advance(30)
    box.handle(Button.CLIP)
    clock.advance(10)
    box.handle(Button.REC_HOLD)
    assert rec.stopped
    assert fb[-1] == Feedback.STOP


def test_recorder_failure_falls_back_to_marker_only(tmp_path, clock):
    box, fb = make_box(tmp_path, clock, audio_device="fail")
    box.handle(Button.REC)
    assert fb == [Feedback.ERROR, Feedback.REC_MARKERS]
    data = markers_json(only_session(tmp_path))
    assert data["mode"] == "marker-only"
    assert data["audio_file"] is None


def test_recorder_dying_mid_session_switches_mode(tmp_path, clock):
    box, fb = make_box(tmp_path, clock, audio_device="plughw:1,0")
    box.handle(Button.REC)
    clock.advance(40)
    FakeRecorder.instances[0]._alive = False  # mic unplugged
    box.tick()
    assert fb[-2:] == [Feedback.ERROR, Feedback.REC_MARKERS]
    data = markers_json(only_session(tmp_path))
    assert data["mode"] == "marker-only"
    assert data["audio_lost_at"] == pytest.approx(40.0)
    box.handle(Button.CLIP)  # markers still work
    assert len(markers_json(only_session(tmp_path))["markers"]) == 1


def test_hold_that_started_the_session_does_not_stop_it(tmp_path, clock):
    box, _ = make_box(tmp_path, clock)
    box.handle(Button.REC)
    clock.advance(1.5)
    box.handle(Button.REC_HOLD)  # same press, still held
    assert box.recording


def test_tap_to_stop_when_hold_disabled_and_guard(tmp_path, clock):
    box, fb = make_box(tmp_path, clock, stop_requires_hold=False)
    box.handle(Button.REC)
    clock.advance(20)
    box.handle(Button.REC)
    assert not box.recording
    clock.advance(0.5)
    box.handle(Button.REC)  # accidental double tap right after stop: ignored
    assert not box.recording
    clock.advance(2)
    box.handle(Button.REC)
    assert box.recording


def test_buttons_without_session_and_empty_undo(tmp_path, clock):
    box, fb = make_box(tmp_path, clock)
    box.handle(Button.CLIP)
    box.handle(Button.UNDO)
    assert fb == [Feedback.ERROR, Feedback.ERROR]
    box.handle(Button.REC)
    box.handle(Button.UNDO)
    assert fb[-1] == Feedback.HINT  # silent while recording


def test_beep_during_session_option(tmp_path, clock):
    box, fb = make_box(tmp_path, clock, beep_during_session=True)
    box.handle(Button.REC)
    box.handle(Button.CLIP)
    box.handle(Button.UNDO)
    box.handle(Button.UNDO)
    assert fb == [Feedback.REC_MARKERS, Feedback.CLIP_BEEP, Feedback.UNDO_BEEP, Feedback.ERROR]


def test_shutdown_closes_open_session(tmp_path, clock):
    box, fb = make_box(tmp_path, clock, audio_device="plughw:1,0")
    box.handle(Button.REC)
    clock.advance(5)
    box.handle(Button.CLIP)
    box.shutdown()
    assert FakeRecorder.instances[0].stopped
    data = markers_json(only_session(tmp_path))
    assert data["ended_at"] is not None and not data["interrupted"]
    assert Feedback.STOP not in fb  # no beeps on shutdown


def test_two_sessions_get_separate_folders(tmp_path, clock):
    box, _ = make_box(tmp_path, clock)
    for _ in range(2):
        box.handle(Button.REC)
        clock.advance(5)
        box.handle(Button.REC_HOLD)
        clock.advance(5)
    assert len(list((tmp_path / "sessions").iterdir())) == 2
