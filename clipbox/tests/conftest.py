import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "python"))
sys.path.insert(0, str(ROOT / "tools"))


class FakeClock:
    """Controllable stand-in for time.monotonic / time.sleep."""

    def __init__(self, start: float = 1000.0):
        self.now = start
        self.slept = []

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture(scope="session")
def root():
    return ROOT
