"""Stand-in for the UNO Q's arduino.app_utils (App + Bridge).

Bridge records every call Linux makes to the MCU, and lets a test play the MCU's part
with Bridge.mcu_notify(). App.run hands the user loop to a test-provided scenario.
"""


class _Bridge:
    def __init__(self):
        self.reset()

    def reset(self):
        self.provided = {}
        self.calls = []

    def provide(self, name, fn):
        self.provided[name] = fn

    def call(self, name, *args):
        self.calls.append((name, *args))
        return None

    def notify(self, name, *args):
        self.calls.append((name, *args))

    # --- test helper: what the MCU sketch would do -----------------------
    def mcu_notify(self, name, *args):
        self.provided[name](*args)


class _App:
    def __init__(self):
        self.scenario = None

    def run(self, user_loop=None):
        if self.scenario is None:
            raise RuntimeError("Set App.scenario before running main.py in tests")
        self.scenario(user_loop)


Bridge = _Bridge()
App = _App()
