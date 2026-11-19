"""ClipBox core logic: sessions, markers, exports, audio recorder and the button state machine.

Nothing in this file talks to the Arduino Bridge directly, so it can be tested on any computer.
main.py wires it to the board.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import signal
import struct
import subprocess
import time
from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

# ---------------------------------------------------------------------------
# Protocol shared with sketch/sketch.ino. tests/test_protocol.py checks that the
# numbers below match the constants in the sketch.
# ---------------------------------------------------------------------------


class Button:
    """Codes the MCU sends with Bridge.notify("button", code)."""

    REC = 1
    CLIP = 2
    UNDO = 3
    REC_HOLD = 4  # REC held down for HOLD_MS (sketch) -> stop the session


class Feedback:
    """Codes Linux sends to the MCU with Bridge.call("feedback", code)."""

    READY = 1  # app started: 3 quick green blinks
    REC_AUDIO = 2  # 2 sync beeps, red LED solid
    REC_MARKERS = 3  # 2 sync beeps, red LED blinking (marker-only mode)
    STOP = 4  # 3 beeps, red LED off
    CLIP = 5  # green flash, silent
    CLIP_BEEP = 6  # green flash + 1 beep
    UNDO = 7  # 2 quick green blinks, silent
    UNDO_BEEP = 8  # 2 quick green blinks + 2 short beeps
    ERROR = 9  # red flicker + long beep
    HINT = 10  # red flicker, silent ("hold REC to stop", "nothing to undo")


BUTTON_NAMES = {Button.REC: "REC", Button.CLIP: "CLIP", Button.UNDO: "UNDO", Button.REC_HOLD: "REC (hold)"}

SCHEMA_VERSION = 1
SETTINGS_FILENAME = "clipbox_settings.json"
MARKERS_FILENAME = "markers.json"
AUDIO_FILENAME = "audio.wav"

# A REC_HOLD that arrives this soon after a session started belongs to the press that
# started it, so it must not stop the session.
HOLD_IGNORE_AFTER_START = 3.0


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    """All tunable options. Load order: defaults < clipbox_settings.json < CLIPBOX_* env vars."""

    data_dir: str = ""  # empty -> <app folder>/sessions
    audio_device: str = "auto"  # "auto" (first USB mic), "none", or an ALSA name like "plughw:1,0"
    sample_rate: int = 48000
    channels: int = 1
    pre_roll: float = 20.0  # seconds kept before a CLIP press
    post_roll: float = 10.0  # seconds kept after a CLIP press
    beep_during_session: bool = False  # beep on CLIP/UNDO while recording (the mic will hear it)
    stop_requires_hold: bool = True  # hold REC to stop, so a stray tap can't end an episode
    recorder_warmup: float = 0.6  # wait for the mic before the sync beeps
    rec_guard: float = 1.5  # ignore a new REC press this soon after a stop
    arecord_bin: str = "arecord"

    @classmethod
    def load(cls, settings_file: Optional[Path] = None, env: Optional[dict] = None) -> "Settings":
        env = os.environ if env is None else env
        values: dict = {}
        if settings_file is not None and Path(settings_file).is_file():
            raw = json.loads(Path(settings_file).read_text(encoding="utf-8"))
            values.update({k: v for k, v in raw.items() if not k.startswith("_")})
        for f in fields(cls):
            key = "CLIPBOX_" + f.name.upper()
            if key in env:
                values[f.name] = env[key]
        known = {f.name: f for f in fields(cls)}
        unknown = set(values) - set(known)
        if unknown:
            raise ValueError(f"Unknown ClipBox setting(s): {', '.join(sorted(unknown))}")
        kwargs = {}
        for name, value in values.items():
            default = getattr(cls, name)
            if isinstance(default, bool):
                kwargs[name] = _parse_bool(value)
            elif isinstance(default, int):
                kwargs[name] = int(value)
            elif isinstance(default, float):
                kwargs[name] = float(value)
            else:
                kwargs[name] = str(value)
        s = cls(**kwargs)
        if s.pre_roll < 0 or s.post_roll < 0:
            raise ValueError("pre_roll and post_roll must be >= 0")
        if s.pre_roll + s.post_roll <= 0:
            raise ValueError("pre_roll + post_roll must be > 0")
        return s


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def format_hms(seconds: float, millis: bool = True) -> str:
    """123.456 -> '00:02:03.456' (or '00:02:03' without millis)."""
    seconds = max(0.0, float(seconds))
    total_ms = int(round(seconds * 1000))
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    if millis:
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_youtube(seconds: float) -> str:
    """YouTube chapter time: 0:00, 4:05, 1:02:03."""
    total = int(max(0.0, seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def atomic_write_text(path: Path, text: str) -> None:
    """Write a file so that a power cut leaves either the old or the new version, never half."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    try:
        fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass  # directory fsync is not supported everywhere (e.g. Windows)


def now_iso(now: Optional[datetime] = None) -> str:
    return (now or datetime.now().astimezone()).isoformat(timespec="seconds")


_CARD_RE = re.compile(r"^\s*(\d+)\s+\[(\S+)\s*\]:\s+(\S+)\s+-\s+(.*)$")


def resolve_audio_device(setting: str, cards_path: str = "/proc/asound/cards") -> Optional[str]:
    """Turn the audio_device setting into an ALSA device name, or None for marker-only mode.

    "auto" picks the first USB audio card (a class-compliant USB mic shows up as USB-Audio).
    """
    setting = (setting or "").strip()
    if setting.lower() in ("", "none", "off", "false", "0"):
        return None
    if setting.lower() != "auto":
        return setting
    try:
        text = Path(cards_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        m = _CARD_RE.match(line)
        if m and m.group(3) == "USB-Audio":
            return f"plughw:CARD={m.group(2)},DEV=0"
    return None


def repair_wav_header(path: Path) -> bool:
    """Fix RIFF/data sizes of a WAV whose writer was killed (power cut). Returns True if changed."""
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size < 12:
        return False
    with open(path, "r+b") as f:
        head = f.read(12)
        if head[0:4] != b"RIFF" or head[8:12] != b"WAVE":
            return False
        pos = 12
        changed = False
        while pos + 8 <= size:
            f.seek(pos)
            chunk = f.read(8)
            cid, csize = chunk[0:4], struct.unpack("<I", chunk[4:8])[0]
            if cid == b"data":
                real = size - (pos + 8)
                if csize != real:
                    f.seek(pos + 4)
                    f.write(struct.pack("<I", real))
                    changed = True
                break
            pos += 8 + csize + (csize & 1)
        else:
            return False
        riff = size - 8
        f.seek(4)
        if struct.unpack("<I", f.read(4))[0] != riff:
            f.seek(4)
            f.write(struct.pack("<I", riff))
            changed = True
    return changed


def wav_duration(path: Path) -> Optional[float]:
    """Duration in seconds of a 16-bit PCM WAV, read from its header and file size."""
    try:
        with open(path, "rb") as f:
            data = f.read(64)
        if data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
            return None
        pos = 12
        rate = channels = bits = None
        size = Path(path).stat().st_size
        with open(path, "rb") as f:
            while pos + 8 <= size:
                f.seek(pos)
                cid = f.read(4)
                csize = struct.unpack("<I", f.read(4))[0]
                if cid == b"fmt ":
                    fmt = f.read(16)
                    _, channels, rate, _, _, bits = struct.unpack("<HHIIHH", fmt)
                elif cid == b"data":
                    if not (rate and channels and bits):
                        return None
                    data_bytes = size - (pos + 8)
                    return data_bytes / (rate * channels * (bits // 8))
                pos += 8 + csize + (csize & 1)
    except (OSError, struct.error):
        return None
    return None


# ---------------------------------------------------------------------------
# Session: markers, saving and exports
# ---------------------------------------------------------------------------


@dataclass
class Marker:
    id: int
    t: float  # seconds after the first sync beep
    pre: float
    post: float
    created_at: str
    label: str = ""

    @property
    def start(self) -> float:
        return max(0.0, self.t - self.pre)

    @property
    def end(self) -> float:
        return self.t + self.post

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "t": round(self.t, 3),
            "pre": self.pre,
            "post": self.post,
            "created_at": self.created_at,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Marker":
        return cls(
            id=int(d["id"]),
            t=float(d["t"]),
            pre=float(d.get("pre", 20.0)),
            post=float(d.get("post", 10.0)),
            created_at=str(d.get("created_at", "")),
            label=str(d.get("label", "")),
        )


@dataclass
class Session:
    folder: Path
    session_id: str
    started_at: str
    mode: str = "marker-only"  # "audio" or "marker-only"
    audio_file: Optional[str] = None
    audio_device: Optional[str] = None
    audio_offset: Optional[float] = None  # seconds into audio.wav where t=0 (first sync beep) is
    audio_lost_at: Optional[float] = None  # t when the recorder died mid-session, if it did
    pre_roll: float = 20.0
    post_roll: float = 10.0
    ended_at: Optional[str] = None
    duration: Optional[float] = None
    interrupted: bool = False
    markers: List[Marker] = field(default_factory=list)
    undone: List[Marker] = field(default_factory=list)

    # -- persistence -------------------------------------------------------

    @property
    def markers_path(self) -> Path:
        return self.folder / MARKERS_FILENAME

    def to_dict(self) -> dict:
        return {
            "version": SCHEMA_VERSION,
            "app": "clipbox",
            "session_id": self.session_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration": None if self.duration is None else round(self.duration, 3),
            "interrupted": self.interrupted,
            "mode": self.mode,
            "audio_file": self.audio_file,
            "audio_device": self.audio_device,
            "audio_offset": None if self.audio_offset is None else round(self.audio_offset, 3),
            "audio_lost_at": None if self.audio_lost_at is None else round(self.audio_lost_at, 3),
            "pre_roll": self.pre_roll,
            "post_roll": self.post_roll,
            "time_base": "t = seconds after the first REC start beep",
            "markers": [m.to_dict() for m in self.markers],
            "undone": [m.to_dict() for m in self.undone],
        }

    @classmethod
    def from_dict(cls, folder: Path, d: dict) -> "Session":
        return cls(
            folder=Path(folder),
            session_id=d["session_id"],
            started_at=d["started_at"],
            mode=d.get("mode", "marker-only"),
            audio_file=d.get("audio_file"),
            audio_device=d.get("audio_device"),
            audio_offset=d.get("audio_offset"),
            audio_lost_at=d.get("audio_lost_at"),
            pre_roll=float(d.get("pre_roll", 20.0)),
            post_roll=float(d.get("post_roll", 10.0)),
            ended_at=d.get("ended_at"),
            duration=d.get("duration"),
            interrupted=bool(d.get("interrupted", False)),
            markers=[Marker.from_dict(m) for m in d.get("markers", [])],
            undone=[Marker.from_dict(m) for m in d.get("undone", [])],
        )

    @classmethod
    def load(cls, folder: Path) -> "Session":
        folder = Path(folder)
        return cls.from_dict(folder, json.loads((folder / MARKERS_FILENAME).read_text(encoding="utf-8")))

    def save(self) -> None:
        """Write markers.json first (source of truth), then the derived exports."""
        self.folder.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.markers_path, json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n")
        atomic_write_text(self.folder / "markers.csv", self.export_csv())
        atomic_write_text(self.folder / "audacity_labels.txt", self.export_audacity())
        atomic_write_text(self.folder / "chapters.txt", self.export_chapters())

    # -- editing -------------------------------------------------------------

    def add_marker(self, t: float, created_at: str) -> Marker:
        next_id = max([m.id for m in self.markers + self.undone], default=0) + 1
        marker = Marker(id=next_id, t=max(0.0, t), pre=self.pre_roll, post=self.post_roll, created_at=created_at)
        self.markers.append(marker)
        self.save()
        return marker

    def undo_last(self) -> Optional[Marker]:
        if not self.markers:
            return None
        marker = self.markers.pop()
        self.undone.append(marker)
        self.save()
        return marker

    # -- exports -----------------------------------------------------------

    def audio_time(self, t: float) -> Optional[float]:
        if self.audio_offset is None:
            return None
        return max(0.0, t + self.audio_offset)

    def export_csv(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(
            ["clip", "pressed_at", "clip_start", "clip_end", "t_seconds", "start_seconds", "end_seconds",
             "audio_start_seconds", "label"]
        )
        for m in self.markers:
            a = self.audio_time(m.start)
            w.writerow(
                [m.id, format_hms(m.t), format_hms(m.start), format_hms(m.end), f"{m.t:.3f}", f"{m.start:.3f}",
                 f"{m.end:.3f}", "" if a is None else f"{a:.3f}", m.label]
            )
        return buf.getvalue()

    def export_audacity(self) -> str:
        """Audacity label track: start<TAB>end<TAB>label, in seconds of audio.wav.

        Without audio (marker-only), times are seconds after the first start beep.
        """
        lines = []
        for m in self.markers:
            start = self.audio_time(m.start) if self.audio_offset is not None else m.start
            end = self.audio_time(m.end) if self.audio_offset is not None else m.end
            lines.append(f"{start:.6f}\t{end:.6f}\t{m.label or f'Clip {m.id}'}")
        return "\n".join(lines) + ("\n" if lines else "")

    def export_chapters(self) -> str:
        """Starter YouTube chapters: 0:00 first, each chapter at least 10 s after the previous one."""
        lines = ["0:00 Intro"]
        last = 0.0
        for m in self.markers:
            if m.start - last < 10.0:
                continue
            lines.append(f"{format_youtube(m.start)} {m.label or f'Clip {m.id}'}")
            last = m.start
        header = "# Starter chapters from ClipBox markers. Rename them, and shift the times if you trim the start.\n"
        return header + "\n".join(lines) + "\n"


def new_session_id(base: Path, now: datetime) -> str:
    sid = now.strftime("%Y-%m-%d_%H-%M-%S")
    candidate, n = sid, 2
    while (Path(base) / candidate).exists():
        candidate = f"{sid}_{n}"
        n += 1
    return candidate


def recover_unfinished_sessions(data_dir: Path, now: Optional[datetime] = None, log: Callable[[str], None] = print) -> List[str]:
    """Close sessions that never got a clean stop (power cut, crash). Markers are already on disk."""
    recovered = []
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        return recovered
    for mfile in sorted(data_dir.glob(f"*/{MARKERS_FILENAME}")):
        try:
            session = Session.load(mfile.parent)
        except (OSError, ValueError, KeyError) as exc:
            log(f"[clipbox] Could not read {mfile}: {exc}")
            continue
        if session.ended_at is not None:
            continue
        session.interrupted = True
        mtime = datetime.fromtimestamp(mfile.stat().st_mtime).astimezone()
        session.ended_at = now_iso(now or mtime)
        audio = session.folder / AUDIO_FILENAME
        if session.audio_file and audio.exists():
            repair_wav_header(audio)
            length = wav_duration(audio)
            if length is not None and session.audio_offset is not None:
                session.duration = max(0.0, length - session.audio_offset)
        if session.duration is None and session.markers:
            session.duration = max(m.t for m in session.markers)
        session.save()
        recovered.append(session.session_id)
        log(f"[clipbox] Recovered interrupted session {session.session_id} ({len(session.markers)} markers)")
    return recovered


# ---------------------------------------------------------------------------
# Audio recorder (arecord on the board's Linux side)
# ---------------------------------------------------------------------------


class RecorderError(RuntimeError):
    pass


class ArecordRecorder:
    """Records a WAV file with ALSA's arecord until stop() is called."""

    def __init__(self, path: Path, device: str, sample_rate: int = 48000, channels: int = 1,
                 binary: str = "arecord", popen: Callable = subprocess.Popen):
        self.path = Path(path)
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.binary = binary
        self._popen = popen
        self._proc = None
        self._log_path = self.path.with_name("recorder.log")
        self.started_at: Optional[float] = None  # time.monotonic() just before the process was spawned

    def command(self) -> List[str]:
        return [
            *self.binary.split(),
            "-q",
            "-D", self.device,
            "-f", "S16_LE",
            "-r", str(self.sample_rate),
            "-c", str(self.channels),
            "-t", "wav",
            str(self.path),
        ]

    def start(self) -> float:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        log = open(self._log_path, "ab")
        self.started_at = time.monotonic()
        try:
            self._proc = self._popen(self.command(), stdout=log, stderr=log, stdin=subprocess.DEVNULL)
        except OSError as exc:
            raise RecorderError(f"could not run {self.binary!r}: {exc}") from exc
        finally:
            log.close()
        return self.started_at

    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def error_text(self) -> str:
        try:
            return self._log_path.read_text(encoding="utf-8", errors="replace").strip()[-400:]
        except OSError:
            return ""

    def stop(self, timeout: float = 5.0) -> None:
        if self._proc is None:
            return
        if self._proc.poll() is None:
            # SIGINT lets arecord finish the WAV header cleanly.
            self._proc.send_signal(signal.SIGINT)
            try:
                self._proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait()
        self._proc = None
        if self.path.exists():
            repair_wav_header(self.path)


# ---------------------------------------------------------------------------
# The button state machine
# ---------------------------------------------------------------------------


class ClipBox:
    """Turns button presses into sessions and markers, and tells the MCU what to show.

    feedback(code) is called with a Feedback code. Every marker is written to disk
    before the feedback is sent, so a confirmed CLIP is always saved.
    """

    def __init__(
        self,
        settings: Settings,
        data_dir: Path,
        feedback: Callable[[int], None],
        log: Callable[[str], None] = print,
        clock: Optional[Callable[[], float]] = None,
        sleep: Optional[Callable[[float], None]] = None,
        wall_clock: Optional[Callable[[], datetime]] = None,
        recorder_factory: Optional[Callable[..., ArecordRecorder]] = None,
        cards_path: str = "/proc/asound/cards",
    ):
        self.settings = settings
        self.data_dir = Path(data_dir)
        self.feedback = feedback
        self.log = log
        self.clock = clock or (lambda: time.monotonic())
        self.sleep = sleep or (lambda s: time.sleep(s))
        self.wall_clock = wall_clock or (lambda: datetime.now().astimezone())
        self.recorder_factory = recorder_factory or ArecordRecorder
        self.cards_path = cards_path
        self.session: Optional[Session] = None
        self.recorder: Optional[ArecordRecorder] = None
        self.t0: Optional[float] = None
        self._last_rec_change = -1e9

    @property
    def recording(self) -> bool:
        return self.session is not None

    # -- lifecycle ---------------------------------------------------------

    def startup(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        recover_unfinished_sessions(self.data_dir, log=self.log)
        device = resolve_audio_device(self.settings.audio_device, self.cards_path)
        self.log(f"[clipbox] Sessions folder: {self.data_dir.resolve()}")
        self.log(f"[clipbox] Audio device: {device or 'none (marker-only mode)'}")
        self.log(f"[clipbox] Clip window: {self.settings.pre_roll:g}s before, {self.settings.post_roll:g}s after")
        self.feedback(Feedback.READY)

    def shutdown(self) -> None:
        if self.session is not None:
            self.log("[clipbox] App stopping: closing the open session")
            self._stop_session(beep=False)

    # -- events ------------------------------------------------------------

    def handle(self, button: int, at: Optional[float] = None) -> None:
        at = self.clock() if at is None else at
        name = BUTTON_NAMES.get(button, f"unknown({button})")
        if button == Button.REC:
            if self.session is None:
                if at - self._last_rec_change < self.settings.rec_guard:
                    self.log("[clipbox] REC ignored (pressed right after a stop)")
                    return
                self._start_session()
            elif self.settings.stop_requires_hold:
                self.log("[clipbox] Hold REC to stop the session")
                self.feedback(Feedback.HINT)
            else:
                self._stop_session()
        elif button == Button.REC_HOLD:
            if self.session is None or not self.settings.stop_requires_hold:
                return
            if at - self._last_rec_change < HOLD_IGNORE_AFTER_START:
                return  # this hold belongs to the press that started the session
            self._stop_session()
        elif button == Button.CLIP:
            self._clip(at)
        elif button == Button.UNDO:
            self._undo()
        else:
            self.log(f"[clipbox] Ignoring {name}")

    def tick(self) -> None:
        """Called regularly from the main loop. Notices a recorder that died mid-session."""
        if self.session is None or self.recorder is None or self.session.mode != "audio":
            return
        if not self.recorder.alive():
            t = self._since_start(self.clock())
            self.log(f"[clipbox] Audio recording stopped unexpectedly at {format_hms(t)}; "
                     f"switching to marker-only. {self.recorder.error_text()}")
            self.session.mode = "marker-only"
            self.session.audio_lost_at = t
            self.session.save()
            self.recorder.stop()
            self.recorder = None
            self.feedback(Feedback.ERROR)
            self.sleep(0.8)
            self.feedback(Feedback.REC_MARKERS)

    def _since_start(self, at: float) -> float:
        if self.t0 is None:
            return 0.0
        return max(0.0, at - self.t0)

    # -- actions -----------------------------------------------------------

    def _start_session(self) -> None:
        wall = self.wall_clock()
        sid = new_session_id(self.data_dir, wall)
        folder = self.data_dir / sid
        folder.mkdir(parents=True)
        session = Session(folder=folder, session_id=sid, started_at=now_iso(wall),
                          pre_roll=self.settings.pre_roll, post_roll=self.settings.post_roll)

        device = resolve_audio_device(self.settings.audio_device, self.cards_path)
        recorder = None
        rec_started = None
        if device:
            recorder = self.recorder_factory(folder / AUDIO_FILENAME, device, self.settings.sample_rate,
                                             self.settings.channels, self.settings.arecord_bin)
            try:
                rec_started = self.clock()
                recorder.start()
                self.sleep(self.settings.recorder_warmup)  # let the mic open so it hears the sync beeps
                if not recorder.alive():
                    raise RecorderError(recorder.error_text() or "recorder exited right away")
            except RecorderError as exc:
                self.log(f"[clipbox] Could not record from {device}: {exc}. Using marker-only mode.")
                recorder.stop()
                recorder = None
                rec_started = None
                self.feedback(Feedback.ERROR)
                self.sleep(0.8)  # let the error beep finish before the sync beeps

        if recorder is not None:
            session.mode = "audio"
            session.audio_file = AUDIO_FILENAME
            session.audio_device = device
            self.feedback(Feedback.REC_AUDIO)
        else:
            self.feedback(Feedback.REC_MARKERS)
        # t = 0 is the moment the first sync beep sounds.
        self.t0 = self.clock()
        if rec_started is not None:
            session.audio_offset = max(0.0, self.t0 - rec_started)
        self._last_rec_change = self.t0
        self.session = session
        self.recorder = recorder
        session.save()
        self.log(f"[clipbox] REC started: session {sid} ({session.mode})")

    def _stop_session(self, beep: bool = True) -> None:
        session = self.session
        assert session is not None
        stop_at = self.clock()
        if beep:
            self.feedback(Feedback.STOP)
            if self.recorder is not None:
                self.sleep(0.8)  # keep the stop beeps in the recording
        if self.recorder is not None:
            self.recorder.stop()
            self.recorder = None
        session.duration = self._since_start(stop_at)
        session.ended_at = now_iso(self.wall_clock())
        session.save()
        self.log(f"[clipbox] REC stopped: {len(session.markers)} markers, {format_hms(session.duration, False)} "
                 f"-> {session.folder}")
        self.session = None
        self.t0 = None
        self._last_rec_change = self.clock()

    def _clip(self, at: float) -> None:
        if self.session is None:
            self.log("[clipbox] CLIP ignored: press REC first")
            self.feedback(Feedback.ERROR)
            return
        t = self._since_start(at)
        marker = self.session.add_marker(t, now_iso(self.wall_clock()))
        self.feedback(Feedback.CLIP_BEEP if self.settings.beep_during_session else Feedback.CLIP)
        self.log(f"[clipbox] CLIP #{marker.id} at {format_hms(t)} "
                 f"(clip {format_hms(marker.start, False)}-{format_hms(marker.end, False)})")

    def _undo(self) -> None:
        if self.session is None:
            self.log("[clipbox] UNDO ignored: no session running")
            self.feedback(Feedback.ERROR)
            return
        marker = self.session.undo_last()
        if marker is None:
            self.log("[clipbox] UNDO: nothing to undo")
            self.feedback(Feedback.ERROR if self.settings.beep_during_session else Feedback.HINT)
            return
        self.feedback(Feedback.UNDO_BEEP if self.settings.beep_during_session else Feedback.UNDO)
        self.log(f"[clipbox] UNDO removed CLIP #{marker.id} at {format_hms(marker.t)}")
