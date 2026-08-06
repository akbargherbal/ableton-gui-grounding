"""
keyboard_shortcuts.py

Backing lookup for click_by_id()'s Level-2 (keyboard) escalation tier in
automate_ableton_task.py. Exists so call sites stop depending on the
agent's memory for shortcuts and do a real lookup instead -- see
keyboard_shortcuts.md for the source, per-row status, and open questions.

Deliberately data-only and dependency-free: a dict of records, not a
markdown parser. If keyboard_shortcuts.md changes, update SHORTCUTS below
to match -- the two are meant to stay in lockstep, not derived from each
other.

Every entry has a `blocked` flag. `blocked=True` means: don't wire this
into a click_by_id(..., keyboard_shortcut=...) call site yet, even though
a key sequence is known, because it depends on something this project
can't currently verify (which track is selected). load_shortcut() raises
rather than silently handing back a blocked shortcut, so a call site can't
accidentally wire one in without deliberately overriding the guard.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShortcutEntry:
    auto_id_pattern: str  # automation_id, with {N} where a track index goes
    windows: str | None
    mac: str | None
    source: str
    blocked: bool
    note: str


# Keyed by a stable label, not automation_id directly -- Activator has two
# different shortcut paths (positional F1-F8 vs selection-based "0"), so
# automation_id alone isn't a unique key here.
SHORTCUTS: dict[str, ShortcutEntry] = {
    "transport_play_stop": ShortcutEntry(
        auto_id_pattern="Transport.Play / Transport.Stop",
        windows="{VK_SPACE}",
        mac="{VK_SPACE}",
        source="Ableton manual v12, section 41.20 Transport (fetched 2026-08-04)",
        blocked=False,
        note=(
            "Single key toggles both directions. NOT live-tested: confirm "
            "get_toggle_state(Transport.Play) reads correctly right after "
            "a Space press. NOTE: currently dead code at the task_solo_one() "
            "call site because verify=None short-circuits before L2 — a "
            "verify callback must be added at the call site to activate this."
        ),
    ),
    "solo_selected_track": ShortcutEntry(
        auto_id_pattern="SessionView.Track[N].Mixer.Solo",
        windows="S",
        mac="S",
        source="Ableton manual v12, section 41.19 Commands for Tracks",
        blocked=True,
        note=(
            "Acts on the currently SELECTED track, not Track[N] specifically. "
            "No automation_id in this project's scheme exposes selected-track "
            "state. Do not unblock until that gap is resolved."
        ),
    ),
    "arm_selected_track": ShortcutEntry(
        auto_id_pattern="SessionView.Track[N].Mixer.Arm",
        windows="C",
        mac="C",
        source="Ableton manual v12, section 41.19 Commands for Tracks",
        blocked=True,
        note="Same selected-track dependency as solo_selected_track.",
    ),
    "activator_by_position": ShortcutEntry(
        auto_id_pattern="SessionView.Track[N].Mixer.Activator (N=0..7 only)",
        windows="{F1}",  # F1..F8 -- caller must pick the right one; see note
        mac="{F1}",
        source="Ableton manual v12, section 41.20 Transport",
        blocked=False,
        note=(
            "Positional, NOT selection-based -- best candidate to test first. "
            "UNVERIFIED: (a) whether position counts audio+MIDI tracks only "
            "or return tracks too, (b) whether 0-indexed Track[0] maps to F1 "
            "or there's an off-by-one, (c) undefined for track index >= 8 "
            "(only 8 keys exist). This entry's 'windows'/'mac' values are a "
            "placeholder for Track[0]==F1; a real call site needs to select "
            "F1..F8 by index, not hardcode F1."
        ),
    ),
    "deactivate_selected_track": ShortcutEntry(
        auto_id_pattern="SessionView.Track[N].Mixer.Activator",
        windows="0",
        mac="0",
        source="Ableton manual v12, section 41.19 Commands for Tracks",
        blocked=True,
        note="Selection-based alternative to activator_by_position; same gap.",
    ),
    "monitoring_buttons": ShortcutEntry(
        auto_id_pattern="SessionView.Track[N].Mixer.Monitoring.Buttons[0..2]",
        windows=None,
        mac=None,
        source="Ableton manual v12 -- not found in the shortcut chapter",
        blocked=True,
        note=(
            "No shortcut found anywhere in the manual's keyboard-shortcuts "
            "chapter. Not confirmed absent, just absent from this chapter -- "
            "no L2 path currently exists for this control."
        ),
    ),
    "launch_selected_slot": ShortcutEntry(
        auto_id_pattern="SessionView.Track[N].Slot[M]",
        windows="{ENTER}",
        mac="{ENTER}",
        source="Ableton manual v12, section 41.15 Session View",
        blocked=True,
        note=(
            "Out of scope -- clip launching not started yet. Same "
            "selected-slot dependency shape as solo/arm; logged so it isn't "
            "rediscovered from scratch later."
        ),
    ),
}


def activator_shortcut_for_index(track_index: int) -> str:
    """Return the pywinauto key sequence for Track[track_index]'s Activator,
    per the 'activator_by_position' entry above -- single source of truth
    for the F-key/track-index mapping so it isn't re-hardcoded at call
    sites (same reasoning as consolidating find_ableton_window() to one
    file elsewhere in this project).

    UNVERIFIED: assumes 0-indexed track_index N maps
    to 1-indexed F-key (N+1) -- Track[0] -> F1, Track[7] -> F8 -- with no
    off-by-one. Only defined for 0..7 since 8 keys exist; raises
    ValueError outside that range rather than guessing what happens beyond
    it.
    """
    if not (0 <= track_index <= 7):
        raise ValueError(
            f"track_index={track_index} out of range for F1..F8 (only 0..7 "
            "defined -- 8 keys exist; behavior for higher indices is an "
            "open question, not something to guess at)."
        )
    return f"{{F{track_index + 1}}}"


class ShortcutBlocked(RuntimeError):
    """Raised by load_shortcut() when the requested entry is known but
    deliberately not cleared for use -- distinct from KeyError (unknown
    label) so a caller can't confuse 'doesn't exist' with 'exists but
    guarded'."""


def load_shortcut(label: str, platform: str = "windows", allow_blocked: bool = False) -> str:
    """Look up a pywinauto key sequence for a named control.

    label: a key from SHORTCUTS above (not a raw automation_id, since some
        controls have more than one shortcut path).
    platform: "windows" or "mac" -- selects which key sequence to return.
    allow_blocked: must be explicitly True to receive a shortcut whose
        `blocked` flag is set. Default False makes the guard hard to
        bypass by accident.

    Raises KeyError if the label isn't in the index, ShortcutBlocked if it
    is but guarded, and ValueError if no shortcut exists for the requested
    platform (e.g. monitoring_buttons, both platforms None).
    """
    entry = SHORTCUTS[label]  # KeyError is fine here -- unknown label is a real bug
    if entry.blocked and not allow_blocked:
        raise ShortcutBlocked(
            f"{label!r}: known shortcut exists but is BLOCKED -- {entry.note}"
        )
    value = entry.windows if platform == "windows" else entry.mac
    if value is None:
        raise ValueError(f"{label!r}: no shortcut known for platform={platform!r}")
    return value


if __name__ == "__main__":
    # Quick manual sanity check -- no pywinauto/Ableton needed, pure data.
    for name, e in SHORTCUTS.items():
        status = "BLOCKED" if e.blocked else "available"
        print(f"{name:28s} [{status:9s}] win={e.windows!r:12s} mac={e.mac!r}")
