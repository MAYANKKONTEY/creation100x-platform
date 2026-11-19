"""Fake `arecord` for tests: writes a growing silent WAV until it gets SIGINT/SIGTERM.

Like the real arecord it writes the header with unknown sizes first and fixes them on exit.
"""
import signal
import struct
import sys
import time

args = sys.argv[1:]
path = args[-1]
rate = int(args[args.index("-r") + 1]) if "-r" in args else 8000
channels = int(args[args.index("-c") + 1]) if "-c" in args else 1
device = args[args.index("-D") + 1] if "-D" in args else "default"

if device == "fail":
    print(f"arecord: main:831: audio open error: No such file or directory ({device})", file=sys.stderr)
    sys.exit(1)

stop = False


def on_signal(signum, frame):
    global stop
    stop = True


signal.signal(signal.SIGINT, on_signal)
signal.signal(signal.SIGTERM, on_signal)

block_align = channels * 2
with open(path, "wb") as f:
    f.write(b"RIFF" + struct.pack("<I", 0x7FFFFFFF) + b"WAVE")
    f.write(b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, rate, rate * block_align, block_align, 16))
    f.write(b"data" + struct.pack("<I", 0x7FFFFFFF))
    f.flush()
    chunk = b"\x00" * (rate // 10) * block_align
    while not stop:
        f.write(chunk)
        f.flush()
        time.sleep(0.1)
        if device == "die":
            sys.exit(2)
    size = f.tell()
    f.seek(4)
    f.write(struct.pack("<I", size - 8))
    f.seek(40)
    f.write(struct.pack("<I", size - 44))
