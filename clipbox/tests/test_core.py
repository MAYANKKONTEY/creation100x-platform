import json
import struct
from datetime import datetime, timezone

import pytest

from clipbox_core import (
    Session,
    Settings,
    atomic_write_text,
    format_hms,
    format_youtube,
    recover_unfinished_sessions,
    repair_wav_header,
    resolve_audio_device,
    wav_duration,
)

WALL = datetime(2026, 11, 20, 19, 30, 5, tzinfo=timezone.utc)


def make_session(tmp_path, **kw):
    folder = tmp_path / "s1"
    s = Session(folder=folder, session_id="s1", started_at=WALL.isoformat(), **kw)
    s.save()
    return s


def write_wav(path, seconds=2.0, rate=8000, channels=1, broken=False):
    frames = int(seconds * rate)
    data = b"\x00\x00" * frames * channels
    riff = 0x7FFFFFFF if broken else 36 + len(data)
    dsize = 0x7FFFFFFF if broken else len(data)
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", riff) + b"WAVE")
        f.write(b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, rate, rate * channels * 2, channels * 2, 16))
        f.write(b"data" + struct.pack("<I", dsize) + data)


# --- formatting -------------------------------------------------------------


def test_format_hms():
    assert format_hms(0) == "00:00:00.000"
    assert format_hms(123.4567) == "00:02:03.457"
    assert format_hms(3725.5, millis=False) == "01:02:05"
    assert format_hms(-3) == "00:00:00.000"


def test_format_youtube():
    assert format_youtube(0) == "0:00"
    assert format_youtube(65.9) == "1:05"
    assert format_youtube(3723) == "1:02:03"


# --- settings -----------------------------------------------------------------


def test_settings_file_then_env_override(tmp_path):
    f = tmp_path / "clipbox_settings.json"
    f.write_text(json.dumps({"_help": "ignored", "pre_roll": 30, "beep_during_session": True, "audio_device": "none"}))
    s = Settings.load(f, env={"CLIPBOX_PRE_ROLL": "45", "CLIPBOX_STOP_REQUIRES_HOLD": "false"})
    assert s.pre_roll == 45.0
    assert s.beep_during_session is True
    assert s.stop_requires_hold is False
    assert s.audio_device == "none"
    assert s.post_roll == 10.0


def test_settings_rejects_typos_and_bad_values(tmp_path):
    f = tmp_path / "clipbox_settings.json"
    f.write_text(json.dumps({"pre_rol": 30}))
    with pytest.raises(ValueError, match="pre_rol"):
        Settings.load(f, env={})
    with pytest.raises(ValueError):
        Settings.load(None, env={"CLIPBOX_PRE_ROLL": "-1"})


def test_shipped_settings_file_loads(root):
    s = Settings.load(root / "app" / "python" / "clipbox_settings.json", env={})
    assert s.audio_device == "auto"
    assert (s.pre_roll, s.post_roll) == (20.0, 10.0)


# --- audio device -------------------------------------------------------------

CARDS = """\
 0 [PCH            ]: HDA-Intel - HDA Intel PCH
                      HDA Intel PCH at 0xf7f10000 irq 31
 1 [Device         ]: USB-Audio - USB PnP Sound Device
                      C-Media Electronics Inc. USB PnP Sound Device at usb-xhci-hcd.0-1, full speed
"""


def test_resolve_audio_device(tmp_path):
    cards = tmp_path / "cards"
    cards.write_text(CARDS)
    assert resolve_audio_device("auto", str(cards)) == "plughw:CARD=Device,DEV=0"
    assert resolve_audio_device("plughw:2,0", str(cards)) == "plughw:2,0"
    assert resolve_audio_device("none", str(cards)) is None
    assert resolve_audio_device("", str(cards)) is None
    assert resolve_audio_device("auto", str(tmp_path / "missing")) is None
    cards.write_text(" 0 [PCH            ]: HDA-Intel - HDA Intel PCH\n")
    assert resolve_audio_device("auto", str(cards)) is None


# --- files ----------------------------------------------------------------------


def test_atomic_write_leaves_no_tmp(tmp_path):
    p = tmp_path / "a.json"
    atomic_write_text(p, "one")
    atomic_write_text(p, "two")
    assert p.read_text() == "two"
    assert not (tmp_path / "a.json.tmp").exists()


def test_wav_repair_and_duration(tmp_path):
    p = tmp_path / "audio.wav"
    write_wav(p, seconds=2.0, broken=True)
    assert repair_wav_header(p) is True
    assert wav_duration(p) == pytest.approx(2.0)
    assert repair_wav_header(p) is False  # already correct
    (tmp_path / "x.wav").write_bytes(b"not a wav")
    assert repair_wav_header(tmp_path / "x.wav") is False


# --- session + exports ------------------------------------------------------------


def test_markers_saved_on_every_press_and_undo(tmp_path):
    s = make_session(tmp_path, mode="audio", audio_file="audio.wav", audio_offset=0.5)
    s.add_marker(65.0, "t1")
    s.add_marker(5.0, "t2")
    on_disk = json.loads((s.folder / "markers.json").read_text())
    assert [m["t"] for m in on_disk["markers"]] == [65.0, 5.0]
    removed = s.undo_last()
    assert removed.id == 2
    s.add_marker(80.0, "t3")
    on_disk = json.loads((s.folder / "markers.json").read_text())
    assert [m["id"] for m in on_disk["markers"]] == [1, 3]  # ids never reused
    assert [m["id"] for m in on_disk["undone"]] == [2]
    assert on_disk["time_base"].startswith("t = seconds after")


def test_exports(tmp_path):
    s = make_session(tmp_path, mode="audio", audio_file="audio.wav", audio_offset=0.5)
    s.add_marker(5.0, "a")  # clip starts at 0 (clamped)
    s.add_marker(65.0, "b")  # 45..75
    s.add_marker(70.0, "c")  # 50..80 -> less than 10 s after previous chapter, skipped in chapters
    s.add_marker(200.0, "d")  # 180..210

    rows = (s.folder / "markers.csv").read_text().splitlines()
    assert rows[0].startswith("clip,pressed_at,clip_start")
    assert rows[2].split(",")[:4] == ["2", "00:01:05.000", "00:00:45.000", "00:01:15.000"]
    assert rows[2].split(",")[7] == "45.500"  # audio time includes the offset

    labels = (s.folder / "audacity_labels.txt").read_text().splitlines()
    assert labels[0] == "0.500000\t15.500000\tClip 1"
    assert labels[1] == "45.500000\t75.500000\tClip 2"

    chapters = [l for l in (s.folder / "chapters.txt").read_text().splitlines() if not l.startswith("#")]
    assert chapters == ["0:00 Intro", "0:45 Clip 2", "3:00 Clip 4"]


def test_audacity_labels_marker_only_use_beep_time(tmp_path):
    s = make_session(tmp_path)
    s.add_marker(65.0, "a")
    assert (s.folder / "audacity_labels.txt").read_text() == "45.000000\t75.000000\tClip 1\n"


def test_recover_unfinished_session(tmp_path):
    s = make_session(tmp_path, mode="audio", audio_file="audio.wav", audio_offset=0.5)
    s.add_marker(1.0, "a")
    write_wav(s.folder / "audio.wav", seconds=3.0, broken=True)
    logs = []
    assert recover_unfinished_sessions(tmp_path, now=WALL, log=logs.append) == ["s1"]
    data = json.loads((s.folder / "markers.json").read_text())
    assert data["interrupted"] is True
    assert data["ended_at"] == WALL.isoformat(timespec="seconds")
    assert data["duration"] == pytest.approx(2.5)
    assert len(data["markers"]) == 1
    assert wav_duration(s.folder / "audio.wav") == pytest.approx(3.0)
    # Already closed sessions are left alone.
    assert recover_unfinished_sessions(tmp_path, now=WALL, log=logs.append) == []
