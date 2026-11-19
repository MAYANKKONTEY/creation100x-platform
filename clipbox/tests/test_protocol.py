"""The sketch and the Python app must agree on button and feedback codes."""

import re

from clipbox_core import Button, Feedback


def sketch_constants(root, prefix):
    text = (root / "app" / "sketch" / "sketch.ino").read_text()
    return {name: int(value) for name, value in re.findall(rf"const int {prefix}_(\w+) = (\d+);", text)}


def class_constants(cls):
    return {k: v for k, v in vars(cls).items() if k.isupper()}


def test_button_codes_match(root):
    assert sketch_constants(root, "BTN") == class_constants(Button)


def test_feedback_codes_match(root):
    assert sketch_constants(root, "FB") == class_constants(Feedback)


def test_bridge_method_names_match(root):
    sketch = (root / "app" / "sketch" / "sketch.ino").read_text()
    main = (root / "app" / "python" / "main.py").read_text()
    assert 'Bridge.notify("button"' in sketch and 'Bridge.provide("button"' in main
    assert 'provide_safe("feedback"' in sketch and 'Bridge.call("feedback"' in main
