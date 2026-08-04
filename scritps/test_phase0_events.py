"""
test_phase0_events.py

Pure control-flow tests for Phase 0's structured-event instrumentation
(emit_event, and its wiring into set_checkbox_by_id(), click_by_id(), and
the new run_task() task_start/task_done wrapper).
"""

from __future__ import annotations

import json
import os
import sys
import types
from io import StringIO
from pathlib import Path
from types import SimpleNamespace


def _install_fake_pywinauto() -> None:
    """If real pywinauto is available and importable, do nothing.
    Otherwise (e.g. in Linux sandbox without win32api), register a dummy package
    structure in sys.modules so imports of UIAWrapper succeed.
    """
    try:
        from pywinauto.controls.uiawrapper import UIAWrapper  # noqa: F401

        return  # Real pywinauto works on this system! No fake needed.
    except Exception:
        pass  # Fall back to fake module below for non-Windows environments

    fake_pywinauto = types.ModuleType("pywinauto")
    fake_pywinauto.__path__ = []  # Required so Python treats it as a package

    fake_controls = types.ModuleType("pywinauto.controls")
    fake_controls.__path__ = []

    fake_uiawrapper = types.ModuleType("pywinauto.controls.uiawrapper")

    class UIAWrapper:
        pass

    fake_uiawrapper.UIAWrapper = UIAWrapper
    fake_controls.uiawrapper = fake_uiawrapper
    fake_pywinauto.controls = fake_controls

    sys.modules["pywinauto"] = fake_pywinauto
    sys.modules["pywinauto.controls"] = fake_controls
    sys.modules["pywinauto.controls.uiawrapper"] = fake_uiawrapper


_install_fake_pywinauto()

# Cross-platform directory resolution (Windows + Linux)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import automate_ableton_task as sut  # noqa: E402

# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


class FakeControl:
    def __init__(self, automation_id: str, toggle_state: bool = False, on_click=None):
        self.element_info = SimpleNamespace(automation_id=automation_id)
        self._toggle_state = toggle_state
        self.click_count = 0
        self.type_keys_calls: list[str] = []
        self._on_click = on_click

    def children(self):
        return []

    def click_input(self):
        self.click_count += 1
        if self._on_click is not None:
            self._on_click(self)

    def get_toggle_state(self):
        return self._toggle_state

    def type_keys(self, keys: str):
        self.type_keys_calls.append(keys)


class Capture:
    def __enter__(self):
        self._real_stdout = sys.stdout
        sys.stdout = self._buf = StringIO()
        return self

    def __exit__(self, *exc):
        sys.stdout = self._real_stdout

    def events(self) -> list[dict]:
        out = []
        for line in self._buf.getvalue().splitlines():
            if line.startswith("EVENT: "):
                out.append(json.loads(line[len("EVENT: ") :]))
        return out


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


def test_emit_event_shape():
    with Capture() as cap:
        sut.emit_event("task_start", task="arm_track", tracks=[1])
    events = cap.events()
    assert len(events) == 1
    ev = events[0]
    assert ev["v"] == 1
    assert ev["type"] == "task_start"
    assert ev["task"] == "arm_track"
    assert ev["tracks"] == [1]


def test_emit_event_stringifies_unserializable_fields():
    with Capture() as cap:
        sut.emit_event(
            "task_done",
            task="x",
            tracks=[],
            result="failed",
            error=RuntimeError("boom"),
        )
    ev = cap.events()[0]
    assert ev["error"] == "boom"


def test_set_checkbox_skip_when_already_desired():
    control = FakeControl("SessionView.Track[0].Mixer.Arm", toggle_state=True)
    window = control
    with Capture() as cap:
        sut.set_checkbox_by_id(
            window,
            control.element_info.automation_id,
            desired=True,
            dry_run=False,
            label="Track[0].Arm",
        )
    events = cap.events()
    assert events == [
        {
            "v": 1,
            "type": "action_result",
            "label": "Track[0].Arm",
            "level": "L1",
            "result": "skip",
        }
    ]
    assert control.click_count == 0


def test_set_checkbox_dry_run_does_not_click():
    control = FakeControl("SessionView.Track[0].Mixer.Arm", toggle_state=False)
    with Capture() as cap:
        sut.set_checkbox_by_id(
            control,
            control.element_info.automation_id,
            desired=True,
            dry_run=True,
            label="Track[0].Arm",
        )
    events = cap.events()
    assert events[-1]["type"] == "action_result"
    assert events[-1]["result"] == "dry_run"
    assert control.click_count == 0


def test_set_checkbox_success_first_attempt():
    def flip(c):
        c._toggle_state = True

    control = FakeControl(
        "SessionView.Track[0].Mixer.Arm", toggle_state=False, on_click=flip
    )
    with Capture() as cap:
        sut.set_checkbox_by_id(
            control,
            control.element_info.automation_id,
            desired=True,
            dry_run=False,
            label="Track[0].Arm",
        )
    events = cap.events()
    types_seen = [e["type"] for e in events]
    assert types_seen == ["action_start", "action_result"]
    assert events[-1]["result"] == "success"
    assert events[-1]["attempt"] == 1
    assert control.click_count == 1


def test_set_checkbox_warn_then_fail_raises():
    control = FakeControl("SessionView.Track[0].Mixer.Solo", toggle_state=False)
    with Capture() as cap:
        try:
            sut.set_checkbox_by_id(
                control,
                control.element_info.automation_id,
                desired=True,
                dry_run=False,
                label="Track[0].Solo",
                max_attempts=2,
            )
            raised = False
        except RuntimeError:
            raised = True
    assert raised
    events = cap.events()
    results = [(e["type"], e.get("result")) for e in events]
    assert results == [
        ("action_start", None),
        ("action_result", "warn"),
        ("action_result", "warn"),
        ("action_result", "failed"),
    ]
    assert control.click_count == 2


def test_click_by_id_dry_run():
    control = FakeControl("Transport.Play")
    with Capture() as cap:
        sut.click_by_id(
            control,
            control.element_info.automation_id,
            dry_run=True,
            label="Transport.Play",
        )
    events = cap.events()
    assert events[-1] == {
        "v": 1,
        "type": "action_result",
        "label": "Transport.Play",
        "level": "L1",
        "result": "dry_run",
    }
    assert control.click_count == 0


def test_click_by_id_verify_none_trusts_l1():
    control = FakeControl("SessionView.Track[N].Mixer.Stop")
    with Capture() as cap:
        sut.click_by_id(
            control,
            control.element_info.automation_id,
            dry_run=False,
            label="Stop",
            verify=None,
        )
    events = cap.events()
    types_seen = [e["type"] for e in events]
    assert types_seen == ["action_start", "action_result"]
    assert events[-1]["result"] == "success"
    assert events[-1]["verified"] is False
    assert control.click_count == 1


def test_click_by_id_l1_success_with_verify():
    calls = {"n": 0}

    def verify():
        calls["n"] += 1
        return True

    control = FakeControl("SessionView.Track[1].Mixer.Monitoring.Buttons[0]")
    with Capture() as cap:
        sut.click_by_id(
            control,
            control.element_info.automation_id,
            dry_run=False,
            label="Track[1].Monitoring=In",
            verify=verify,
        )
    events = cap.events()
    assert [e["type"] for e in events] == ["action_start", "action_result"]
    assert events[-1] == {
        "v": 1,
        "type": "action_result",
        "label": "Track[1].Monitoring=In",
        "level": "L1",
        "result": "success",
        "attempt": 1,
    }
    assert control.click_count == 1


def test_click_by_id_full_ladder_no_shortcut_raises():
    control = FakeControl("Some.Control")
    with Capture() as cap:
        try:
            sut.click_by_id(
                control,
                control.element_info.automation_id,
                dry_run=False,
                label="Some.Control",
                verify=lambda: False,
                keyboard_shortcut=None,
                max_attempts=2,
            )
            raised = False
        except sut.EscalationExhausted:
            raised = True
    assert raised
    events = cap.events()
    seq = [
        (
            e["type"],
            e.get("level"),
            e.get("from_level"),
            e.get("to_level"),
            e.get("result"),
        )
        for e in events
    ]
    assert seq == [
        ("action_start", "L1", None, None, None),
        ("action_result", "L1", None, None, "warn"),
        ("action_result", "L1", None, None, "warn"),
        ("escalate", None, "L1", "L2", None),
        ("escalate", None, "L2", "L3", None),
        ("action_result", "L3", None, None, "failed"),
    ]
    assert control.click_count == 2


def test_click_by_id_escalates_to_l2_and_succeeds():
    control = FakeControl("Some.Control")
    with Capture() as cap:
        sut.click_by_id(
            control,
            control.element_info.automation_id,
            dry_run=False,
            label="Some.Control",
            verify=lambda: len(control.type_keys_calls) > 0,
            keyboard_shortcut="{F3}",
            max_attempts=1,
        )
    events = cap.events()
    types_seen = [e["type"] for e in events]
    assert types_seen == [
        "action_start",
        "action_result",
        "escalate",
        "action_start",
        "action_result",
    ]
    assert events[1] == {
        "v": 1,
        "type": "action_result",
        "label": "Some.Control",
        "level": "L1",
        "result": "warn",
        "attempt": 1,
    }
    assert events[2] == {
        "v": 1,
        "type": "escalate",
        "label": "Some.Control",
        "from_level": "L1",
        "to_level": "L2",
    }
    assert events[4]["level"] == "L2"
    assert events[4]["result"] == "success"
    assert control.type_keys_calls == ["{F3}"]


def test_click_by_id_l2_fails_escalates_to_l3_raises():
    control = FakeControl("Some.Control")
    with Capture() as cap:
        try:
            sut.click_by_id(
                control,
                control.element_info.automation_id,
                dry_run=False,
                label="Some.Control",
                verify=lambda: False,
                keyboard_shortcut="{F3}",
                max_attempts=1,
            )
            raised = False
        except sut.EscalationExhausted:
            raised = True
    assert raised
    events = cap.events()
    seq = [
        (
            e["type"],
            e.get("level"),
            e.get("from_level"),
            e.get("to_level"),
            e.get("result"),
        )
        for e in events
    ]
    assert seq == [
        ("action_start", "L1", None, None, None),
        ("action_result", "L1", None, None, "warn"),
        ("escalate", None, "L1", "L2", None),
        ("action_start", "L2", None, None, None),
        ("action_result", "L2", None, None, "warn"),
        ("escalate", None, "L2", "L3", None),
        ("action_result", "L3", None, None, "failed"),
    ]


def test_run_task_success_emits_start_and_done():
    with Capture() as cap:
        sut.run_task("arm_track", [1], lambda: None)
    events = cap.events()
    assert events == [
        {"v": 1, "type": "task_start", "task": "arm_track", "tracks": [1]},
        {
            "v": 1,
            "type": "task_done",
            "task": "arm_track",
            "tracks": [1],
            "result": "success",
        },
    ]


def test_run_task_failure_emits_done_failed_and_reraises():
    def boom():
        raise RuntimeError("simulated failure")

    with Capture() as cap:
        try:
            sut.run_task("solo_tour", [0, 1], boom)
            raised = False
        except RuntimeError:
            raised = True
    assert raised
    events = cap.events()
    assert events[0]["type"] == "task_start"
    assert events[1] == {
        "v": 1,
        "type": "task_done",
        "task": "solo_tour",
        "tracks": [0, 1],
        "result": "failed",
        "error": "simulated failure",
    }


if __name__ == "__main__":
    import traceback

    tests = [
        (name, fn)
        for name, fn in list(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    passed, failed = 0, 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
            passed += 1
        except Exception:
            print(f"FAIL  {name}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
