import json
import shutil
import subprocess

import pytest

import clipper
from clipper import Clip, Word, build_command, clip_name, group_words, plan_clips, to_srt

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg + ffprobe")


def M(id, t, pre=20.0, post=10.0):
    return {"id": id, "t": t, "pre": pre, "post": post}


# --- planning -------------------------------------------------------------------


def test_plan_applies_offset_and_clamps_start():
    clips = plan_clips([M(1, 5.0), M(2, 100.0)], offset=12.0)
    assert [(c.start, c.end) for c in clips] == [(0.0, 27.0), (92.0, 122.0)]


def test_plan_merges_overlaps_unless_disabled():
    markers = [M(1, 100.0), M(2, 110.0), M(3, 300.0)]
    merged = plan_clips(markers, offset=0)
    assert [(c.start, c.end, c.marker_ids) for c in merged] == [(80.0, 120.0, [1, 2]), (280.0, 310.0, [3])]
    assert len(plan_clips(markers, offset=0, merge=False)) == 3


def test_plan_overrides_and_media_end():
    clips = plan_clips([M(1, 50.0), M(2, 95.0), M(3, 500.0)], offset=0, pre=5, post=5, media_duration=98.0)
    assert [(c.start, c.end) for c in clips] == [(45.0, 55.0), (90.0, 98.0)]  # marker 3 is past the end


def test_clip_name():
    assert clip_name(Clip(3, [3], 125.0, 155.0), "mp4") == "clip_03_02m05s.mp4"
    assert clip_name(Clip(12, [1], 3725.0, 3755.0), "m4a") == "clip_12_1h02m05s.m4a"


# --- captions -------------------------------------------------------------------


def test_group_words_and_srt():
    words = [Word(0.0, 0.3, " Yeh"), Word(0.3, 0.6, " AI"), Word(0.6, 0.9, " ka"), Word(0.9, 1.2, " future"),
             Word(1.2, 1.5, " hai"), Word(1.5, 1.8, " bhai"), Word(4.0, 4.4, " Next")]
    cues = group_words(words, max_words=5)
    assert [c.text for c in cues] == ["Yeh AI ka future hai", "bhai", "Next"]
    srt = to_srt(cues)
    assert srt.startswith("1\n00:00:00,000 --> 00:00:01,500\nYeh AI ka future hai\n")
    assert "3\n00:00:04,000 --> 00:00:04,400\nNext" in srt


def test_commands():
    clip = Clip(1, [1], 10.0, 40.0)
    v = build_command(clipper.Path("in.mp4"), clip, clipper.Path("out.mp4"), "video", vertical=True,
                      srt_name="captions.srt")
    vf = v[v.index("-vf") + 1]
    assert vf.startswith("crop=") and "scale=1080:1920" in vf and "subtitles=filename='captions.srt'" in vf
    assert v[v.index("-ss") + 1] == "10.000" and v[v.index("-t") + 1] == "30.000"
    a = build_command(clipper.Path("a.wav"), clip, clipper.Path("o.m4a"), "audio")
    assert "-vn" in a and "-vf" not in a


def test_video_requires_offset(tmp_path):
    with pytest.raises(SystemExit):
        clipper.parse_args([str(tmp_path), "--video", "cam.mp4"])


# --- end to end with real ffmpeg -------------------------------------------------


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def probe_stream(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json",
         str(path)], capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    return float(data["format"]["duration"]), video


def write_session(folder, audio=False, markers=((1, 20.0), (2, 45.0))):
    folder.mkdir(parents=True, exist_ok=True)
    data = {
        "session_id": folder.name,
        "mode": "audio" if audio else "marker-only",
        "audio_file": "audio.wav" if audio else None,
        "audio_offset": 0.5 if audio else None,
        "markers": [{"id": i, "t": t, "pre": 5.0, "post": 3.0} for i, t in markers],
    }
    (folder / "markers.json").write_text(json.dumps(data))
    if audio:
        ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=60", "-ar", "48000", "-ac", "1",
               str(folder / "audio.wav"))
    return folder


@needs_ffmpeg
def test_video_clips_horizontal_and_vertical(tmp_path):
    video = tmp_path / "cam.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=60", "-f", "lavfi", "-i",
           "sine=frequency=440:duration=60", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
           "-shortest", str(video))
    session = write_session(tmp_path / "s1")

    out = clipper.run([str(session), "--video", str(video), "--offset", "2.0"])
    assert [p.name for p in out] == ["clip_01_00m17s.mp4", "clip_02_00m42s.mp4"]
    duration, stream = probe_stream(out[0])
    assert duration == pytest.approx(8.0, abs=0.15)
    assert (stream["width"], stream["height"]) == (640, 360)
    assert (session / "clips" / "clips.csv").exists()

    out = clipper.run([str(session), "--video", str(video), "--offset", "2.0", "--vertical", "--only", "2",
                       "--out", str(tmp_path / "vert")])
    assert len(out) == 1
    _, stream = probe_stream(out[0])
    assert (stream["width"], stream["height"]) == (1080, 1920)


@needs_ffmpeg
def test_audio_session_clips(tmp_path):
    session = write_session(tmp_path / "s2", audio=True)
    out = clipper.run([str(session)])
    assert [p.suffix for p in out] == [".m4a", ".m4a"]
    duration, stream = probe_stream(out[0])
    assert stream is None
    assert duration == pytest.approx(8.0, abs=0.15)


@needs_ffmpeg
def test_audiogram_with_captions(tmp_path):
    session = write_session(tmp_path / "s3", audio=True, markers=((1, 20.0),))

    class FakeTranscriber:
        def __init__(self, model, language):
            assert language == "hi"

        def __call__(self, wav):
            assert wav.exists()
            return [Word(0.5, 1.0, " Namaste"), Word(1.0, 1.6, " doston")]

    out = clipper.run([str(session), "--audiogram", "--captions", "--language", "hi"],
                      transcriber_factory=FakeTranscriber)
    duration, stream = probe_stream(out[0])
    assert (stream["width"], stream["height"]) == (1080, 1920)
    assert duration == pytest.approx(8.0, abs=0.2)
    assert "Namaste doston" in out[0].with_suffix(".srt").read_text()


def test_dry_run_writes_nothing(tmp_path, capsys):
    session = tmp_path / "s4"
    session.mkdir()
    (session / "markers.json").write_text(json.dumps({"audio_file": None, "markers": [{"id": 1, "t": 30.0}]}))
    assert clipper.run([str(session), "--video", "cam.mp4", "--offset", "1", "--dry-run"]) == []
    assert not (session / "clips").exists()
    assert "ffmpeg" in capsys.readouterr().out


def test_marker_only_session_needs_video(tmp_path):
    session = tmp_path / "s5"
    session.mkdir()
    (session / "markers.json").write_text(json.dumps({"audio_file": None, "markers": [{"id": 1, "t": 30.0}]}))
    with pytest.raises(SystemExit, match="marker-only"):
        clipper.run([str(session)])
