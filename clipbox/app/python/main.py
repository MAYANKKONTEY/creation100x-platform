"""ClipBox - Linux side of the Arduino UNO Q (runs in Arduino App Lab).

The MCU sketch sends button presses with Bridge.notify("button", code).
This file timestamps each press, hands it to ClipBox (clipbox_core.py) and sends
LED/buzzer feedback back with Bridge.call("feedback", code).

Settings: edit clipbox_settings.json next to this file, or set CLIPBOX_* environment
variables (see README.md).
"""

import atexit
import queue
import signal
import sys
import time
from pathlib import Path

from arduino.app_utils import App, Bridge

from clipbox_core import SETTINGS_FILENAME, ClipBox, Settings

HERE = Path(__file__).resolve().parent

settings = Settings.load(HERE / SETTINGS_FILENAME)
data_dir = Path(settings.data_dir) if settings.data_dir else HERE.parent / "sessions"

# Presses are queued and handled in the App loop. Bridge callbacks must return fast and
# must not make Bridge calls themselves (that can deadlock), so they only record the time.
events = queue.Queue()


def on_button(code):
    events.put((int(code), time.monotonic()))


def send_feedback(code):
    try:
        Bridge.call("feedback", int(code))
    except Exception as exc:  # the MCU may still be booting; never crash the app over a light
        print(f"[clipbox] feedback {code} not delivered: {exc}", flush=True)


def log(message):
    print(message, flush=True)


box = ClipBox(settings, data_dir, feedback=send_feedback, log=log)


def shutdown(*_args):
    box.shutdown()


def on_sigterm(signum, frame):
    shutdown()
    sys.exit(0)


atexit.register(shutdown)
signal.signal(signal.SIGTERM, on_sigterm)

Bridge.provide("button", on_button)
box.startup()


def loop():
    try:
        code, at = events.get(timeout=0.05)
    except queue.Empty:
        box.tick()
        return
    box.handle(code, at)


App.run(user_loop=loop)
