"""
automate_ableton_task.py

Builds on dump_ableton_pywinauto.py: instead of just reading the UIA tree,
this script *acts* on it, using the stable `automation_id` scheme Ableton
exposes under the Session View (discovered by inspecting a prior dump):

    SessionView.Track[N].Mixer.Arm                    CheckBox
    SessionView.Track[N].Mixer.Activator               CheckBox (mute)
    SessionView.Track[N].Mixer.Solo                     CheckBox
    SessionView.Track[N].Mixer.Monitoring.Buttons[0..2] RadioButton (In/Auto/Off)
    SessionView.Track[N].Mixer.Stop                     Button (clip stop)
    SessionView.Track[N].Slot[M]                        Group (clip slot)
    SessionView.ReturnTrack[N].Mixer.*                   same shape, return tracks
    Transport.Tempo                                     Slider
    Transport.Play / Transport.Stop

Using automation_id instead of visible `name` matters because names repeat
on every track ("In", "Auto", "Off", "Solo/Cue" all exist 4+ times) and are
locale-dependent, while these IDs are structural, per-track, and index-based.

Two hard-won lessons baked into this version (found by actually running it):

1. Ableton's Session View is UI-virtualized. A non-maximized/backgrounded
   window can expose ~60 automation_ids instead of ~201, missing controls
   entirely -- not a lookup bug, the element wasn't rendered yet. We
   maximize + focus the window before every run (see ensure_window_ready).

2. Cached control references go stale across state-changing actions.
   Holding a UIAWrapper captured before clicking Play, sleeping, then
   clicking Stop, and reusing that *same* reference afterward silently
   returned the wrong toggle state in testing -- one track was left
   soloed after a "restore" step that should have turned it off. The fix
   is to never hold a control across a gap; every click/read below
   re-resolves the control from a fresh, targeted tree walk immediately
   before touching it (see resolve()).

That trades some speed for correctness. For this scale of tree (~200
elements) a fresh walk is well under a second -- worth it for a script
that touches a live project.

Requirements
------------
- Windows 10/11, Ableton Live 12+ running with a project open
- pip install pywinauto
- dump_ableton_pywinauto.py in the same folder (we import find_ableton_window
  from it rather than re-implementing window discovery)

Usage
-----
    # Safe: prints the plan, clicks nothing
    python automate_ableton_task.py --task solo_tour --tracks 0 1 2 3

    # Actually perform it
    python automate_ableton_task.py --task solo_tour --tracks 0 1 2 3 --live

    # Arm track 1 for recording and set its monitor to "In"
    python automate_ableton_task.py --task arm_track --tracks 1 --live

    # Discover what track indices exist right now
    python automate_ableton_task.py --list-tracks

    # Diagnostics (always live-click regardless of --live -- see their
    # own docstrings for why)
    python automate_ableton_task.py --task probe_toggle --tracks 1
    python automate_ableton_task.py --task probe_solo_transport --tracks 1

    # Test click_by_id()'s L2 keyboard path directly (F1..F8
    # positional shortcut against Track[N].Activator, N=0..7 only)
    python automate_ableton_task.py --task probe_keyboard_activator --tracks 0
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Callable

try:
    from pywinauto.controls.uiawrapper import UIAWrapper  # type: ignore[assignment]
except ImportError:
    UIAWrapper = None  # let --list-tasks work without pywinauto; main() guards actions

# Reuse window discovery AND window-readiness handling from the read-only
# dump script instead of duplicating them -- keep one source of truth for
# "how do we find Live" and "how do we make sure its tree is fully visible
# before we touch it" (the latter used to be a local copy here; consolidated
# so the two scripts can't quietly drift apart on this).
# Lazy import: --list-tasks works without pywinauto / Ableton.
_find_ableton_window = None
_ensure_window_ready = None


def _lazy_import_dump() -> None:
    global _find_ableton_window, _ensure_window_ready
    if _find_ableton_window is not None:
        return
    from dump_ableton_pywinauto import find_ableton_window, ensure_window_ready
    _find_ableton_window = find_ableton_window
    _ensure_window_ready = ensure_window_ready


def find_ableton_window():
    _lazy_import_dump()
    return _find_ableton_window()


def ensure_window_ready(window):
    _lazy_import_dump()
    _ensure_window_ready(window)

# Canonical F1..F8 lookup for the Activator positional-shortcut test
# below. Kept in its own module (keyboard_shortcuts.py) rather than
# hardcoded here -- see that file for the full index, sourcing, and which
# other shortcuts are still BLOCKED on the "no selected-track read" gap.
from keyboard_shortcuts import activator_shortcut_for_index, load_shortcut


# --------------------------------------------------------------------------
# Structured events
# --------------------------------------------------------------------------
#
# Goal: replace stdout-parsing-by-wording (an orchestrator grepping for
# "[click]"/"[warn]"/etc. and hoping the wording never changes) with a
# stable, greppable, versioned signal. This is ADDITIVE: every existing
# print() line stays exactly where it was, for a human reading raw
# terminal output. emit_event() lines are a second, parallel channel on
# the same stdout stream (so ordering relative to the print() lines is
# preserved for free), each prefixed "EVENT: " for a trivial `grep`.
#
# The "v" field is a schema version. A consumer (orchestrate.sh) should
# read the fields it recognizes for the "v" it knows about and ignore the
# rest -- that's what lets this vocabulary grow later (e.g. a new event
# type, or a new field on action_result) without breaking an
# already-written orchestrator.

EVENT_SCHEMA_VERSION = 1

TASK_REGISTRY: dict[str, dict] = {
    "arm_track": {
        "required_args": ["tracks"], "optional_args": [], "atomic": True,
        "description": "Arm a track for recording",
    },
    "solo_one": {
        "required_args": ["tracks", "seconds"], "optional_args": [], "atomic": True,
        "description": "Solo one track, play, stop, unsolo",
    },
    "solo_tour": {
        "required_args": ["tracks", "seconds"], "optional_args": [], "atomic": False,
        "description": "Tour through tracks one by one (solo, play, stop, unsolo per track)",
    },
    "set_tempo": {
        "required_args": ["bpm"], "optional_args": [], "atomic": True,
        "description": "Set the session tempo",
    },
    "probe_toggle": {
        "required_args": ["tracks"], "optional_args": [], "atomic": True,
        "description": "Diagnostic: probe toggle state reading",
    },
    "probe_solo_transport": {
        "required_args": ["tracks", "seconds"], "optional_args": [], "atomic": True,
        "description": "Diagnostic: probe solo + transport interaction",
    },
    "probe_keyboard_activator": {
        "required_args": ["tracks"], "optional_args": [], "atomic": True,
        "description": "Diagnostic: probe keyboard shortcut path",
    },
    "read_solo_states": {
        "required_args": ["tracks"], "optional_args": [], "atomic": True,
        "description": "Read and report solo states of tracks",
    },
}


def emit_event(event_type: str, **fields) -> None:
    """Print one single-line, greppable, versioned JSON event.

    `default=str` on json.dumps is a deliberate safety net: some fields
    passed in here (e.g. a caught exception) aren't natively JSON-
    serializable, and this is a logging call, not a wire protocol -- it's
    better to stringify something unexpected than to raise out of a
    logging call and mask the real error underneath it.
    """
    payload = {"v": EVENT_SCHEMA_VERSION, "type": event_type, **fields}
    print(f"EVENT: {json.dumps(payload, default=str)}")


# --------------------------------------------------------------------------
# Control resolution
# --------------------------------------------------------------------------
#
# NOTE: pywinauto's element_info.descendants(auto_id=...) doesn't exist --
# UIAElementInfo.descendants() only builds conditions on process, class_name,
# title, control_type, content_only. And even descendants(control_type=...)
# -- a single FindAll-style query -- returned nothing against Ableton's
# deeply-nested, custom-drawn UIA tree in testing, the same way
# dump_ableton_pywinauto.py needed a manual recursive control.children()
# walk (not a single query) to see everything. So we walk manually here too.
#
# Deliberately NOT caching resolved controls across calls: see the module
# docstring for why a stale reference produced a wrong result in testing.

def find_control(window: UIAWrapper, auto_id: str, max_depth: int = 20) -> UIAWrapper | None:
    """DFS the live tree for one control by automation_id, stopping at the
    first match. Returns None if not found (caller decides how to react).
    """
    found: list[UIAWrapper] = []

    def _walk(ctrl: UIAWrapper, depth: int) -> None:
        if found:
            return
        try:
            aid = ctrl.element_info.automation_id
        except Exception:
            aid = None
        if aid == auto_id:
            found.append(ctrl)
            return
        if depth >= max_depth:
            return
        try:
            children = ctrl.children()
        except Exception:
            children = []
        for child in children:
            _walk(child, depth + 1)
            if found:
                return

    _walk(window, 0)
    return found[0] if found else None


def resolve(window: UIAWrapper, auto_id: str, retry_with_refocus: bool = True) -> UIAWrapper:
    """Resolve one control by automation_id, right now, freshly.

    If it's missing, try once more after ensure_window_ready() -- covers
    the case where focus/visibility shifted between the start of a task
    and this particular click (e.g. clicking Play could plausibly steal
    focus). Raises a clear error if it's still missing after that.
    """
    control = find_control(window, auto_id)
    if control is None and retry_with_refocus:
        ensure_window_ready(window)
        control = find_control(window, auto_id)
    if control is None:
        raise LookupError(
            f"No element with automation_id={auto_id!r} found in a fresh tree walk. "
            "The control may be off-screen/virtualized, or the UI just redrew mid-task. "
            "Run --list-tracks to check what's currently visible/indexed."
        )
    return control


def build_automation_id_index(control: UIAWrapper, max_depth: int = 20) -> dict[str, list[UIAWrapper]]:
    """Full one-shot index, used only for --list-tracks (bulk discovery,
    not held onto for later clicking) and for the up-front sanity check
    before a task starts.
    """
    index: dict[str, list[UIAWrapper]] = {}

    def _walk(ctrl: UIAWrapper, depth: int) -> None:
        try:
            aid = ctrl.element_info.automation_id
        except Exception:
            aid = None
        if aid:
            index.setdefault(aid, []).append(ctrl)
        if depth >= max_depth:
            return
        try:
            children = ctrl.children()
        except Exception:
            children = []
        for child in children:
            _walk(child, depth + 1)

    _walk(control, 0)
    return index


def verify_present(index: dict[str, list[UIAWrapper]], required_ids: list[str]) -> None:
    """Fail fast, before clicking anything, if expected controls aren't
    visible right now. This is a friendly up-front check only -- actual
    clicks still re-resolve fresh via resolve(), since state can shift
    between this check and the moment we act.
    """
    missing = [i for i in required_ids if i not in index]
    if missing:
        raise LookupError(
            "The following controls were not found in the tree:\n  "
            + "\n  ".join(missing)
            + "\n\nThis usually means Ableton's window wasn't fully visible/maximized "
              "(Session View appears to be UI-virtualized -- off-screen controls aren't "
              "exposed to accessibility APIs until rendered). Maximize the window and "
              "try again, or run --list-tracks to confirm what's currently indexed."
        )


def track_mixer_id(track_index: int, field: str, return_track: bool = False) -> str:
    prefix = "ReturnTrack" if return_track else "Track"
    return f"SessionView.{prefix}[{track_index}].Mixer.{field}"


# --------------------------------------------------------------------------
# Control actions
# --------------------------------------------------------------------------

def get_toggle_state(control: UIAWrapper) -> bool:
    """Read a CheckBox's current on/off state.

    pywinauto's uia backend exposes TogglePattern via get_toggle_state()
    for real checkboxes; fall back to legacy is_selected() if that's
    absent, since Ableton's radio-style Monitoring buttons behave a bit
    differently.
    """
    try:
        return bool(control.get_toggle_state())
    except Exception:
        try:
            return bool(control.is_selected())
        except Exception:
            aid = getattr(control.element_info, "automation_id", "?")
            raise RuntimeError(
                f"Could not read state of {aid!r}; add a case for this control "
                "type before automating it."
            )


def set_checkbox_by_id(window: UIAWrapper, auto_id: str, desired: bool,
                        dry_run: bool, label: str, max_attempts: int = 2) -> None:
    """Resolve fresh, read current state, click only if it doesn't already
    match `desired` -- then, critically, RE-READ after clicking to confirm
    it actually changed. Testing showed a click can be logged as sent while
    the real toggle state doesn't end up where we expected (either the read
    or the click itself is unreliable against this custom-drawn control) --
    trusting the click without checking is what left a track soloed after
    a "restore" step. If verification fails, retry once, then raise loudly
    instead of silently continuing with wrong bookkeeping.
    """
    control = resolve(window, auto_id)
    current = get_toggle_state(control)
    if current == desired:
        print(f"  [skip] {label} already {'on' if desired else 'off'}")
        emit_event("action_result", label=label, level="L1", result="skip")
        return

    print(f"  {'[dry-run] would click' if dry_run else '[click]'} {label} "
          f"({'on' if current else 'off'} -> {'on' if desired else 'off'})")
    if dry_run:
        emit_event("action_result", label=label, level="L1", result="dry_run")
        return

    emit_event("action_start", label=label, level="L1")
    for attempt in range(1, max_attempts + 1):
        control.click_input()
        time.sleep(0.15)  # let the UI actually redraw before we re-read
        verify_control = resolve(window, auto_id)  # fresh again, not the same handle
        actual = get_toggle_state(verify_control)
        if actual == desired:
            emit_event("action_result", label=label, level="L1", result="success", attempt=attempt)
            return
        print(f"  [warn] {label}: clicked but state reads "
              f"{'on' if actual else 'off'}, expected {'on' if desired else 'off'} "
              f"(attempt {attempt}/{max_attempts})")
        emit_event("action_result", label=label, level="L1", result="warn", attempt=attempt)
        control = verify_control  # try the freshly-resolved one next attempt

    emit_event("action_result", label=label, level="L1", result="failed", attempts=max_attempts)
    raise RuntimeError(
        f"{label}: state did not change to {'on' if desired else 'off'} after "
        f"{max_attempts} click attempt(s). Either the click isn't landing on the "
        "real control (coordinates stale/offset) or get_toggle_state() isn't "
        "reporting this control's true state. Run --task probe_toggle to isolate which."
    )


class EscalationExhausted(RuntimeError):
    """Raised when click_by_id()'s full ladder fails to verify the action.
    Distinct from a plain RuntimeError so a caller could one day catch this
    specifically and treat it as 'needs a human', not 'code bug'."""


def click_by_id(window: UIAWrapper, auto_id: str, dry_run: bool, label: str,
                 verify: Callable[[], bool] | None = None,
                 keyboard_shortcut: str | None = None,
                 max_attempts: int = 2) -> None:
    """Click a control via an escalation ladder: Mouse -> Keyboard shortcut
    -> explicit human instructions.

    NO MCP/LOM TIER HERE, on purpose. This project has no MCP/Remote
    Script/MIDI bridge at all; padding in a 4th level for a direct
    MCP/LOM call that could never fire here would be dead code, not a
    real design. This ladder is scoped to what this file actually has:
    3 levels.

    verify: zero-arg callable returning bool, called after each attempt to
    confirm the action actually landed -- NOT "was a click sent." Clicking
    a control and trusting it worked without reading its state back is
    exactly what leaves a track stuck soloed after a supposed restore.
    Pass None ONLY for a control with no known structural signal of
    success. That is a documented gap at the call site, not a silent one
    -- e.g. SessionView.Track[N].Mixer.Stop (clip stop) has no
    automation_id exposing "is this slot playing," so there is currently
    nothing to verify against.

    keyboard_shortcut: optional pywinauto key sequence (e.g. "{VK_SPACE}").
    Only pass one that's been independently confirmed unambiguous for
    THIS control (checked against the manual or keyboard_shortcuts.py's
    sourced entries) -- evidence-based, never a memory-based guess.
    Currently passed by task_solo_one() at Transport.Play / Transport.Stop,
    but is dead code at those call sites because verify=None short-circuits
    before the L2 tier is reached (see the verify is None early-return at
    line 433). To activate L2 for these controls, add a real verify
    callback and remove the verify=None guard. Additional call sites should
    use the same pattern once their matching shortcuts are unblocked in
    keyboard_shortcuts.py.
    """
    if verify is None:
        print(f"  [warn] {label}: no verification available for this control -- "
              "click-and-trust (a documented gap, not a silent one). Add a "
              "verify callable once this control exposes a readable outcome.")

    # --- Level 1: mouse ---
    control = resolve(window, auto_id)
    print(f"  {'[dry-run] would click' if dry_run else '[click L1/mouse]'} {label}")
    if dry_run:
        emit_event("action_result", label=label, level="L1", result="dry_run")
        return
    emit_event("action_start", label=label, level="L1")
    for attempt in range(1, max_attempts + 1):
        control.click_input()
        time.sleep(0.15)  # let the UI redraw before re-checking, same as set_checkbox_by_id
        if verify is None:
            # Nothing to check against; trust by necessity, not by default --
            # still a real, distinct outcome worth an event of its own so an
            # orchestrator can tell "verified success" from "unverifiable".
            emit_event("action_result", label=label, level="L1", result="success", verified=False)
            return
        if verify():
            emit_event("action_result", label=label, level="L1", result="success", attempt=attempt)
            return
        print(f"  [warn] {label}: L1 mouse click did not verify "
              f"(attempt {attempt}/{max_attempts})")
        emit_event("action_result", label=label, level="L1", result="warn", attempt=attempt)
        control = resolve(window, auto_id)  # fresh handle for the retry, never reused

    # --- Level 2: keyboard shortcut ---
    if keyboard_shortcut is None:
        print(f"  [escalate] {label}: L1 (mouse) exhausted. No confirmed keyboard "
              "shortcut supplied for this control -- not the same as 'none exists'; "
              "check ableton-live-12-manual-en.pdf or the (not-yet-built) "
              "keyboard-shortcut index before assuming there isn't one.")
        emit_event("escalate", label=label, from_level="L1", to_level="L2",
                    reason="no_keyboard_shortcut_supplied")
        emit_event("escalate", label=label, from_level="L2", to_level="L3",
                    reason="L2_unavailable")
    else:
        emit_event("escalate", label=label, from_level="L1", to_level="L2")
        print(f"  [click L2/keyboard] {label}: sending {keyboard_shortcut!r}")
        emit_event("action_start", label=label, level="L2")
        # type_keys() (BaseWrapper) is the correct call for UIAWrapper --
        # verified against pywinauto 0.6.9 source directly, not assumed.
        # send_keystrokes() is a real pywinauto method too, but it lives on
        # HwndWrapper (the older win32 backend) and doesn't exist on
        # UIAWrapper, which is what this project uses throughout.
        window.type_keys(keyboard_shortcut)
        time.sleep(0.15)
        # Note: reaching this branch means verify is guaranteed non-None --
        # the "verify is None" case above always returns at L1 on the first
        # attempt and never falls through to L2 at all.
        if verify():
            emit_event("action_result", label=label, level="L2", result="success")
            return
        print(f"  [warn] {label}: L2 keyboard shortcut did not verify either")
        emit_event("action_result", label=label, level="L2", result="warn")
        emit_event("escalate", label=label, from_level="L2", to_level="L3")

    # --- Level 3: explicit human instructions (last resort) ---
    # Per the escalation-ladder design: named menu paths/states only, never
    # relative/visual description, and must end with an explicit request
    # for confirmation. This function can't hold a live conversation --
    # it prints to the terminal, which the user pastes back -- so it
    # raises with the instruction text ready to relay verbatim, rather
    # than a generic failure message.
    emit_event("action_result", label=label, level="L3", result="failed")
    raise EscalationExhausted(
        f"{label}: automated levels exhausted (mouse"
        + (", keyboard" if keyboard_shortcut else "")
        + ") without verifying the action landed.\n"
        f"  MANUAL STEP: please click the '{label}' control directly in "
        "Ableton Live, then confirm here whether it changed, or tell me "
        "if you hit a problem."
    )


def task_probe_toggle(window: UIAWrapper, track_index: int) -> None:
    """Diagnostic: click a track's Solo checkbox 4 times, 1s apart, printing
    the read-back state after each click plus its screen bounding_rect.

    NOTE: this task always live-clicks, regardless of --live / dry-run.
    A probe that doesn't click can't tell you anything -- there'd be no
    "after" to compare. main() skips the "*** DRY RUN ***" banner for
    this task specifically so that isn't misreported (see main()).

    Use this to tell apart the two possible causes of the solo_tour bug:
      * if the printed state toggles cleanly on/off/on/off each click,
        get_toggle_state() and click_input() actually agree with each
        other -- the bug is elsewhere (e.g. a race with Play/Stop).
      * if the state DOESN'T toggle cleanly (e.g. stays "on" for two
        clicks in a row, or the rect stays identical across the run while
        Ableton visibly shows different colors), that points at
        get_toggle_state() misreading this custom RadioButton-style
        control, or click_input() missing its target.
    Watch the actual Ableton window while this runs and compare what you
    see on screen to what gets printed.
    """
    auto_id = track_mixer_id(track_index, "Solo")
    print(f"Probing {auto_id} -- watch the Ableton window while this runs.\n")
    for i in range(4):
        control = resolve(window, auto_id)
        rect = control.rectangle()
        before = get_toggle_state(control)
        control.click_input()
        time.sleep(1.0)
        control2 = resolve(window, auto_id)
        after = get_toggle_state(control2)
        print(f"click {i+1}: before={'on' if before else 'off'} -> "
              f"after={'on' if after else 'off'}  rect={rect}")


def task_probe_solo_transport(window: UIAWrapper, track_index: int, seconds: float) -> None:
    """Diagnostic: reproduce solo_tour's exact sequence for ONE track --
    solo on -> Play -> sleep -> Stop -> solo off -- but read+print state
    after every single action instead of only verifying at the end.

    probe_toggle showed the toggle read/click agree with each other and
    with the screen in isolation (clean off/on/off/on, identical rect
    every time). That rules out "click doesn't land" and "get_toggle_state
    misreads this control" as standalone causes. This probe exists to
    catch a timing interaction with Play/Stop specifically -- e.g. Play
    stealing focus, or Ableton's tree re-virtualizing during playback --
    that wouldn't show up when Solo is clicked in isolation with nothing
    else happening in between.

    Like probe_toggle, this always live-clicks regardless of --live.
    Watch the actual Solo button on screen throughout and compare against
    what's printed -- specifically the two states are most interesting:
    "after Stop, before unsolo click" and "after unsolo click".
    """
    solo_id = track_mixer_id(track_index, "Solo")

    def read(label: str) -> bool:
        control = resolve(window, solo_id)
        state = get_toggle_state(control)
        rect = control.rectangle()
        print(f"  [{label}] solo={'on' if state else 'off'}  rect={rect}")
        return state

    print(f"Probing full solo_tour sequence on Track[{track_index}] -- "
          f"watch the Ableton window throughout.\n")

    original = read("0. before anything")

    control = resolve(window, solo_id)
    control.click_input()
    time.sleep(0.15)
    read("1. after solo-on click")

    play = resolve(window, "Transport.Play")
    play.click_input()
    print(f"  [2. clicked Transport.Play] sleeping {seconds}s...")
    time.sleep(seconds)
    read("3. after sleep, before Stop click")

    stop = resolve(window, "Transport.Stop")
    stop.click_input()
    time.sleep(0.15)
    read("4. after Stop click, before unsolo click")

    control = resolve(window, solo_id)
    control.click_input()
    time.sleep(0.15)
    final = read("5. after unsolo click")

    if final != original:
        print(f"\n  [MISMATCH] started {'on' if original else 'off'}, "
              f"ended {'on' if final else 'off'} -- track was NOT restored. "
              "Compare step 3/4/5 above against what the screen showed at "
              "each moment to see where the click and the real state part ways.")
    else:
        print(f"\n  [OK] state restored to {'on' if original else 'off'} "
              "as expected.")


def task_read_solo_states(window: UIAWrapper, track_indices: list[int]) -> None:
    """Pure read, no clicks at all -- print current Solo state for each
    given track. Use this BEFORE solo_tour if you have any doubt about
    whether a track was left soloed by a previous run; solo_tour treats
    whatever it finds at the start as the state to restore back to, so a
    bad baseline here silently becomes permanent (see the mismatch found
    via probe_solo_transport in this session).
    """
    for i in track_indices:
        auto_id = track_mixer_id(i, "Solo")
        control = resolve(window, auto_id)
        state = get_toggle_state(control)
        flag = "  <-- currently ON" if state else ""
        print(f"  Track[{i}].Solo = {'on' if state else 'off'}{flag}")


def task_probe_keyboard_activator(window: UIAWrapper, track_index: int) -> None:
    """Diagnostic: send the F1..F8 positional keyboard shortcut
    DIRECTLY to Track[track_index]'s Activator (mute), bypassing
    click_by_id()'s mouse-first ladder entirely, and read state before/after.

    WHY THIS CAN'T JUST BE A click_by_id() CALL: click_by_id() always tries
    L1 (mouse) first and only escalates to L2 (keyboard) if L1's verify()
    fails. The mouse click on Activator already works reliably (same
    confirmed control shape as Monitoring), so a normal
    click_by_id() call would resolve at L1 every single time -- the
    keyboard path would never actually fire, proving nothing. This probe
    isolates L2 on purpose, the same way probe_toggle isolates the
    read-vs-click question for Solo.

    Tests two currently-unverified things at once (see keyboard_shortcuts.py,
    'activator_by_position' entry, and keyboard_shortcuts.md):
      1. Does F1..F8, sent via window.type_keys(), actually toggle Track
         Activator at all -- or is the manual's positional-shortcut
         description not translating cleanly into a real UIA-level keypress?
      2. Does 0-indexed Track[track_index] line up with 1-indexed F-key with
         no off-by-one (track_index=0 -> F1)?

    Only accepts track_index 0..7 (see activator_shortcut_for_index() in
    keyboard_shortcuts.py) -- 8 keys exist, behavior beyond that is an open
    question, not something this probe guesses at.

    NOTE: like the other probe_* tasks, this always live-sends the
    keystroke regardless of --live -- a probe that doesn't act can't tell
    you anything. main() skips the "*** DRY RUN ***" banner for this task
    for the same reason it does for the others.
    """
    key = activator_shortcut_for_index(track_index)  # raises ValueError if out of range
    auto_id = track_mixer_id(track_index, "Activator")

    print(f"Probing keyboard L2 path: Track[{track_index}].Activator via {key!r}")
    print("Watch the Ableton window while this runs.\n")

    control = resolve(window, auto_id)
    before = get_toggle_state(control)
    print(f"  before: {'on' if before else 'off'}")

    print(f"  sending {key!r} to the window (window.type_keys is the "
          "confirmed-correct call for UIAWrapper)...")
    window.type_keys(key)
    time.sleep(0.2)  # let the UI redraw before re-reading, same as elsewhere

    control = resolve(window, auto_id)  # fresh handle, never reused across the gap
    after = get_toggle_state(control)
    print(f"  after:  {'on' if after else 'off'}")

    if after != before:
        print(f"\n[result] State changed ({'on' if before else 'off'} -> "
              f"{'on' if after else 'off'}). Now cross-check against the "
              f"real Ableton window: did Track[{track_index}]'s activator "
              "visibly toggle, and was it the RIGHT track (not a "
              "neighbor)? If both hold, that confirms the F-key/track-index "
              "mapping cleanly -- if the WRONG track toggled instead, that's "
              "the off-by-one question answered too, just not the way we'd "
              "want.")
    else:
        print(f"\n[result] State did NOT change. Before concluding the "
              f"shortcut doesn't work, run --task probe_toggle --tracks "
              f"{track_index} first to rule out get_toggle_state() "
              "misreading this control -- if THAT toggles cleanly on mouse "
              f"clicks, the fault is specifically in {key!r} not reaching "
              "Ableton (focus stolen by something else?) or the manual's "
              "positional mapping not applying here.")


# --------------------------------------------------------------------------
# Discovery: what track indices currently exist
# --------------------------------------------------------------------------

def list_tracks(index: dict[str, list[UIAWrapper]]) -> None:
    all_ids = index.keys()
    track_ids = sorted(
        a for a in all_ids
        if a.startswith("SessionView.Track[") and a.endswith(".Mixer")
    )
    return_ids = sorted(
        a for a in all_ids
        if a.startswith("SessionView.ReturnTrack[") and a.endswith(".Mixer")
    )
    print("Tracks found:")
    for t in track_ids:
        print(f"  {t}")
    print("Return tracks found:")
    for t in return_ids:
        print(f"  {t}")
    if not track_ids and not return_ids:
        print(f"\n(nothing matched -- indexed {len(all_ids)} automation_ids total; "
              "if that's 0, see the troubleshooting note in this script's docstring)")


# --------------------------------------------------------------------------
# Tasks
# --------------------------------------------------------------------------

def task_arm_track(window: UIAWrapper, track_index: int, dry_run: bool) -> None:
    """Arm a track for recording and set its monitor mode to 'In'."""
    arm_id = track_mixer_id(track_index, "Arm")
    monitor_id = track_mixer_id(track_index, "Monitoring.Buttons[0]")

    preflight = build_automation_id_index(window)
    verify_present(preflight, [arm_id, monitor_id])

    print(f"Task: arm track {track_index} + set monitor to In")
    set_checkbox_by_id(window, arm_id, desired=True, dry_run=dry_run,
                        label=f"Track[{track_index}].Arm")
    # Monitoring.Buttons[0] ("In") is a confirmed RadioButton (dumps/
    # ableton_uia_..._session.json), so get_toggle_state() is a real
    # structural check here -- not the "click and trust" default.
    # keyboard_shortcut stays None: no shortcut for this control has been
    # confirmed against the manual or a shortcut index yet (neither exists
    # yet -- see click_by_id docstring), so nothing is passed here.
    click_by_id(window, monitor_id, dry_run=dry_run,
                label=f"Track[{track_index}].Monitoring=In",
                verify=lambda: get_toggle_state(resolve(window, monitor_id)) is True)


def task_solo_one(window: UIAWrapper, track_index: int,
                    seconds: float, dry_run: bool) -> None:
    """One solo -> play -> wait -> stop -> unsolo cycle for a single track.

    This is the atomic unit solo_tour decomposes into, so the orchestrator
    can regain control between tracks and screenshot each one
    individually. solo_tour() remains a thin
    in-process loop over this function so standalone CLI use doesn't regress.

    Restores the track's original solo state in a finally block, the same
    safety-net pattern as the full solo_tour.
    """
    solo_id = track_mixer_id(track_index, "Solo")

    preflight = build_automation_id_index(window)
    verify_present(preflight, [solo_id, "Transport.Play", "Transport.Stop"])

    original = get_toggle_state(resolve(window, solo_id))
    print(f"Track[{track_index}].Solo = {'on' if original else 'off'} (saved original)")

    try:
        print(f"Track {track_index}: solo -> play {seconds}s -> stop -> unsolo")
        set_checkbox_by_id(window, solo_id, desired=True, dry_run=dry_run,
                            label=f"Track[{track_index}].Solo")
        transport_key = load_shortcut("transport_play_stop")
        click_by_id(window, "Transport.Play", dry_run=dry_run, label="Transport.Play",
                      keyboard_shortcut=transport_key)
        if not dry_run:
            time.sleep(seconds)
        click_by_id(window, "Transport.Stop", dry_run=dry_run, label="Transport.Stop",
                      keyboard_shortcut=transport_key)
        set_checkbox_by_id(window, solo_id, desired=original, dry_run=dry_run,
                            label=f"Track[{track_index}].Solo")
    finally:
        set_checkbox_by_id(window, solo_id, desired=original, dry_run=dry_run,
                            label=f"Track[{track_index}].Solo (restore)")


def task_solo_tour(window: UIAWrapper, track_indices: list[int],
                    seconds: float, dry_run: bool) -> None:
    """Solo each given track in turn -- thin loop over task_solo_one().

    task_solo_one() is the atomic unit (Phase 2 decomposition). This
    function is kept as a convenience for standalone CLI use where
    per-track granularity isn't needed, so existing workflows don't regress.
    """
    for i in track_indices:
        task_solo_one(window, i, seconds, dry_run)


def task_set_tempo(window: UIAWrapper, bpm: float, dry_run: bool) -> None:
    """Set the project tempo.

    Live's tempo slider supports direct numeric entry: double-click to
    enter edit mode, type the value, press Enter. We try the UIA
    RangeValuePattern first (exact, no simulated typing) and fall back to
    the click+type approach, since not every build exposes ValuePattern
    on this control.
    """
    preflight = build_automation_id_index(window)
    verify_present(preflight, ["Transport.Tempo"])

    tempo = resolve(window, "Transport.Tempo")
    print(f"Task: set tempo to {bpm} BPM")

    try:
        current = tempo.iface_value.CurrentValue
        print(f"  current value (RangeValuePattern): {current}")
        if dry_run:
            print(f"  [dry-run] would set_value({bpm})")
        else:
            tempo.iface_value.SetValue(str(bpm))
        return
    except Exception as e:
        print(f"  RangeValuePattern unavailable ({e}); falling back to click+type")

    if dry_run:
        print(f"  [dry-run] would double-click tempo field and type {bpm}")
        return
    tempo.double_click_input()
    tempo.type_keys(f"{bpm}{{ENTER}}", with_spaces=True)


def run_task(task_name: str, tracks: list[int], fn: Callable[[], None]) -> None:
    """Wrap a single task_* call with task_start/task_done events.

    One instrumentation point in main()'s dispatch, rather than duplicating
    start/done bookkeeping inside every task_* function -- every dispatch
    path (arm_track, solo_tour, the probes, etc.) goes through here, so
    every task_* function gets task_start/task_done coverage without
    touching each function's own body. Re-raises after emitting task_done
    on failure, so the caller's own error handling/exit code is unaffected
    -- this only adds a signal, it never changes control flow.
    """
    emit_event("task_start", task=task_name, tracks=tracks)
    try:
        fn()
    except Exception as e:
        emit_event("task_done", task=task_name, tracks=tracks, result="failed", error=str(e))
        raise
    else:
        emit_event("task_done", task=task_name, tracks=tracks, result="success")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _require_pywinauto(reason: str) -> None:
    if UIAWrapper is None:
        print(f"Missing dependency for '{reason}'. Install with:\n"
              "    pip install pywinauto", file=sys.stderr)
        sys.exit(1)


def _require_ableton_window() -> UIAWrapper:
    window = find_ableton_window()
    if window is None:
        print("Could not find the Ableton Live window. Is it running?", file=sys.stderr)
        sys.exit(1)
    ensure_window_ready(window)
    return window


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", choices=["arm_track", "solo_one", "solo_tour",
                                             "set_tempo",
                                             "probe_toggle", "probe_solo_transport",
                                             "probe_keyboard_activator",
                                             "read_solo_states"],
                         help="Which demo task to run")
    parser.add_argument("--tracks", type=int, nargs="+", default=[],
                         help="Zero-based track indices to act on")
    parser.add_argument("--seconds", type=float, default=3.0,
                         help="Playback duration per track for solo_tour (default: 3.0)")
    parser.add_argument("--bpm", type=float, default=120.0,
                         help="Target tempo for set_tempo (default: 120.0)")
    parser.add_argument("--live", action="store_true",
                         help="Actually click/type. Without this flag, only the plan is printed.")
    parser.add_argument("--list-tracks", action="store_true",
                         help="Print discovered track/return-track automation_ids and exit")
    parser.add_argument("--list-tasks", action="store_true",
                         help="Print task registry with schema version as JSON and exit")
    args = parser.parse_args()

    if args.list_tasks:
        print(json.dumps({"schema_version": EVENT_SCHEMA_VERSION, "tasks": TASK_REGISTRY}))
        return

    if args.list_tracks:
        _require_pywinauto("--list-tracks")
        window = _require_ableton_window()
        print("Indexing controls by automation_id (recursive walk, matches dump script)...",
              file=sys.stderr)
        index = build_automation_id_index(window)
        print(f"Indexed {len(index)} distinct automation_ids.\n", file=sys.stderr)
        list_tracks(index)
        return

    if not args.task:
        parser.error("--task is required unless --list-tracks or --list-tasks is given")

    _require_pywinauto(args.task)
    window = _require_ableton_window()

    dry_run = not args.live

    probe_tasks = ("probe_toggle", "probe_solo_transport", "probe_keyboard_activator")
    if args.task == "read_solo_states":
        pass  # pure read, no dry-run/live distinction applies
    elif dry_run and args.task not in probe_tasks:
        print("*** DRY RUN -- nothing will be clicked. Pass --live to actually execute. ***\n")
    elif args.task in probe_tasks:
        print(f"*** {args.task} always live-clicks regardless of --live -- "
              "a probe that doesn't click can't tell you anything. ***\n")

    if args.task == "arm_track":
        if len(args.tracks) != 1:
            parser.error("--task arm_track needs exactly one --tracks index")
        run_task("arm_track", args.tracks,
                  lambda: task_arm_track(window, args.tracks[0], dry_run))
    elif args.task == "solo_one":
        if len(args.tracks) != 1:
            parser.error("--task solo_one needs exactly one --tracks index")
        run_task("solo_one", args.tracks,
                  lambda: task_solo_one(window, args.tracks[0], args.seconds, dry_run))
    elif args.task == "solo_tour":
        if not args.tracks:
            parser.error("--task solo_tour needs at least one --tracks index")
        run_task("solo_tour", args.tracks,
                  lambda: task_solo_tour(window, args.tracks, args.seconds, dry_run))
    elif args.task == "set_tempo":
        run_task("set_tempo", [], lambda: task_set_tempo(window, args.bpm, dry_run))
    elif args.task == "probe_toggle":
        if len(args.tracks) != 1:
            parser.error("--task probe_toggle needs exactly one --tracks index")
        run_task("probe_toggle", args.tracks,
                  lambda: task_probe_toggle(window, args.tracks[0]))
    elif args.task == "probe_solo_transport":
        if len(args.tracks) != 1:
            parser.error("--task probe_solo_transport needs exactly one --tracks index")
        run_task("probe_solo_transport", args.tracks,
                  lambda: task_probe_solo_transport(window, args.tracks[0], args.seconds))
    elif args.task == "probe_keyboard_activator":
        if len(args.tracks) != 1:
            parser.error("--task probe_keyboard_activator needs exactly one --tracks index")
        run_task("probe_keyboard_activator", args.tracks,
                  lambda: task_probe_keyboard_activator(window, args.tracks[0]))
    elif args.task == "read_solo_states":
        if not args.tracks:
            parser.error("--task read_solo_states needs at least one --tracks index")
        run_task("read_solo_states", args.tracks,
                  lambda: task_read_solo_states(window, args.tracks))


if __name__ == "__main__":
    main()