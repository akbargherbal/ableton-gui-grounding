"""
dump_ableton_states.py

Automates the manual loop of: switch Ableton to a given view, alt-tab back
to the terminal, run the dump script, repeat. Loops over one or more named
states in a single run and writes a labeled JSON dump for each, via the
same walk()/default_json_path() used by dump_ableton_pywinauto.py -- same
output format, same dumps/ folder, so nothing downstream needs to change.

Currently supported states
---------------------------
    session        Session View
    arrangement    Arrangement View
    sounds, instruments, drums, audio_effects, midi_effects, plugins
                   Browser panel categories (see note below -- less
                   verified than session/arrangement)

Browser panel categories: how selection works, and what's verified
----------------------------------------------------------------------
CONFIRMED via grep_dump.py against a real dump: these DataItem tree
nodes carry an EMPTY automation_id ("Sounds" and "Instruments" both
checked directly). Unlike the Session View mixer controls, there's no
stable structural ID to click by here, so this falls back to matching on
(control_type, name) instead -- see find_control_by_name().

The real dump also showed the category label THREE levels deep with the
same name at each level (e.g. Library > Sounds > Sounds > Sounds, going
DataItem > DataItem > Text). find_control_by_name() matches depth-first
and returns on the first hit, so it lands on the OUTERMOST node --
almost certainly the real clickable list item, with the inner two being
its own label sub-elements. That's inferred, not proven: clicking the
outer DataItem hasn't actually been confirmed to change the selected
category yet.

All six categories (sounds, instruments, drums, audio_effects,
midi_effects, plugins) have been run via `--states all` and each
resulting dump shows a distinctly-named, distinctly-counted list marker
(e.g. "Sounds List, 1001 Items", "Instruments List, 23 Items", "Drums
List, 1001 Items", "Audio Effects List, 47 Items", "MIDI Effects List,
15 Items", "Plug-Ins List, 0 Items") -- confirming each category was
actually selected, not just re-labeled. See scritps/dumps/ for the dumps
this was verified against.

How Session/Arrangement switching works
------------------------------------------
Session View and Arrangement View share one window and toggle with Tab
(Live's default shortcut) -- no dedicated UIA button has been found for
it. Blindly pressing Tab would require already knowing the current view
to avoid toggling the wrong way -- the exact kind of unverified-state
assumption that caused the stuck-soloed-track bug in
automate_ableton_task.py. Instead we detect the current view first:
Session View's tree exposes SessionView.* automation_ids only while it's
actually rendered on screen (same UI-virtualization behavior documented
in dump_ableton_pywinauto.py) -- Arrangement View doesn't. So "are we in
Session View" reduces to "does a fresh index contain any SessionView.*
id", a check we get for free from behavior already characterized.
**CONFIRMED WORKING** -- user ran this against the real app; log showed
the Tab press landing and the resulting dumps had genuinely different
content (Session dump has a "Session" group with Track Headers/Slots/
Scenes; Arrangement dump has an "Arrangement" group with Timeline/
Loop Brace).

Requirements
------------
- dump_ableton_pywinauto.py and automate_ableton_task.py in the same
  folder (imports find_ableton_window/ensure_window_ready/walk/
  print_tree/default_json_path from the former, build_automation_id_index
  from the latter -- no logic duplicated here).

Usage
-----
    python dump_ableton_states.py --states session arrangement
    python dump_ableton_states.py --states session --label-suffix before-edit
    python dump_ableton_states.py --states sounds instruments
    python dump_ableton_states.py --states all   # every known state, one command
    python dump_ableton_states.py --states all --label-suffix before-edit
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict

try:
    from pywinauto.controls.uiawrapper import UIAWrapper
except ImportError:
    print("Missing dependency. Install with:\n    pip install pywinauto\n", file=sys.stderr)
    sys.exit(1)

from dump_ableton_pywinauto import (
    find_ableton_window,
    ensure_window_ready,
    walk,
    print_tree,
    default_json_path,
)
from automate_ableton_task import build_automation_id_index

SESSION_PREFIX = "SessionView."

# Browser Sidebar category labels -- matched by (control_type, name) since
# these DataItem nodes carry no automation_id (confirmed via grep_dump.py).
# All six exact name strings below are grep-verified against a real dump
# -- see module docstring.
BROWSER_CATEGORY_NAMES: dict[str, str] = {
    "sounds": "Sounds",
    "instruments": "Instruments",
    "drums": "Drums",
    "audio_effects": "Audio Effects",
    "midi_effects": "MIDI Effects",
    "plugins": "Plug-Ins",
}

# Full preset for `--states all`. Fixed, explicit order (not just dict
# insertion order left implicit) so re-runs are reproducible and the
# order is visible at a glance here rather than only in BROWSER_CATEGORY_NAMES.
# Session/Arrangement first since those are CONFIRMED; browser categories
# after -- all six independently grep-verified (see module docstring).
ALL_STATES: list[str] = ["session", "arrangement"] + list(BROWSER_CATEGORY_NAMES)


def find_control_by_name(control: UIAWrapper, control_type: str, name: str,
                          max_depth: int = 20) -> UIAWrapper | None:
    """DFS for the first control matching (control_type, name) exactly --
    same recursive-.children() approach as automate_ableton_task.py's
    find_control(), just matching on name instead of automation_id since
    these Browser nodes don't have one. Checks the node itself before
    recursing, so given nested identically-named nodes (e.g. Library >
    Sounds > Sounds > Sounds), this returns the OUTERMOST match.
    """
    found: list[UIAWrapper] = []

    def _walk(ctrl: UIAWrapper, depth: int) -> None:
        if found:
            return
        try:
            ctype = ctrl.element_info.control_type
            cname = (ctrl.window_text() or "").strip()
        except Exception:
            ctype, cname = None, None
        if ctype == control_type and cname == name:
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

    _walk(control, 0)
    return found[0] if found else None


def goto_browser_category(window: UIAWrapper, category: str) -> None:
    """Click a Browser Sidebar category by name. CONFIRMED against the
    real app for all six categories (see module docstring). Still no
    before/after check like goto_view() has, because there's no known
    cheap signal for "which category is currently selected" the way
    SessionView.* ids give us for view detection -- confirmation comes
    only after the fact, from the resulting dump's printed tree showing a
    line like 'Tree: "<Category> List, N Items"' with the expected name
    and a distinct item count.
    """
    if category not in BROWSER_CATEGORY_NAMES:
        raise ValueError(f"Unknown browser category: {category!r}")
    target_name = BROWSER_CATEGORY_NAMES[category]

    ensure_window_ready(window)
    control = find_control_by_name(window, "DataItem", target_name)
    if control is None:
        raise LookupError(
            f"No DataItem named {target_name!r} found in a fresh tree walk. "
            "The Browser panel may not be open/docked, or Ableton's "
            "wording for this category differs from what's hardcoded here."
        )
    print(f"  Clicking Browser category {target_name!r} (unverified -- "
          "check the resulting dump/screen by eye)...", file=sys.stderr)
    control.click_input()
    time.sleep(0.3)


def is_session_view(window: UIAWrapper) -> bool:
    """True iff a fresh index currently contains any SessionView.* id --
    see module docstring for why this needs no dedicated marker control.
    """
    index = build_automation_id_index(window)
    return any(aid.startswith(SESSION_PREFIX) for aid in index)


def goto_view(window: UIAWrapper, target: str, max_attempts: int = 2) -> None:
    """Switch to Session or Arrangement View, verifying before AND after
    -- never press Tab without first confirming which way it needs to go,
    and never trust the press worked without re-checking afterward.
    """
    assert target in ("session", "arrangement")
    target_is_session = target == "session"

    for attempt in range(1, max_attempts + 1):
        ensure_window_ready(window)
        current_is_session = is_session_view(window)
        if current_is_session == target_is_session:
            print(f"  Already in {target.title()} View.", file=sys.stderr)
            return
        print(
            f"  Currently in {'Session' if current_is_session else 'Arrangement'} "
            f"View; pressing Tab to reach {target.title()} View "
            f"(attempt {attempt}/{max_attempts})...",
            file=sys.stderr,
        )
        window.type_keys("{TAB}")
        time.sleep(0.4)

    ensure_window_ready(window)
    if is_session_view(window) != target_is_session:
        raise RuntimeError(
            f"Could not reach {target} view after {max_attempts} Tab press(es). "
            "Either the view genuinely didn't change (focus stolen? Tab "
            "rebound?), or the SessionView.* detection heuristic doesn't hold "
            "for your Live version/layout -- verify by eye against the window "
            "before trusting this again."
        )
    print(f"  Now in {target.title()} View.", file=sys.stderr)


def dump_state(window: UIAWrapper, label: str, max_depth: int,
                out_dir: str, no_print: bool) -> str:
    """Walk the current tree and write it out, same shape as
    dump_ableton_pywinauto.py's own output.
    """
    path = default_json_path(label, out_dir)
    tree = walk(window, max_depth=max_depth)
    if not no_print:
        print_tree(tree)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(tree), f, indent=2, ensure_ascii=False)
    print(f"  Wrote {path}", file=sys.stderr)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--states", nargs="+", required=True,
        choices=["all", "session", "arrangement"] + list(BROWSER_CATEGORY_NAMES),
        help="Which states to dump, in order. Pass 'all' by itself as a "
        "preset for every known state (session, arrangement, every "
        "browser category), instead of listing them out. All states, "
        "including every browser category, are confirmed working -- see "
        "module docstring.",
    )
    parser.add_argument("--max-depth", type=int, default=10)
    parser.add_argument("--out-dir", type=str, default="dumps")
    parser.add_argument(
        "--label-suffix", type=str, default=None,
        help="Appended to each state's label, e.g. 'before-edit' -> "
        "'session-before-edit'.",
    )
    parser.add_argument("--no-print", action="store_true")
    args = parser.parse_args()

    if "all" in args.states:
        if len(args.states) > 1:
            print(
                "'all' was given alongside other --states values; ignoring "
                "the rest and running the full preset instead.",
                file=sys.stderr,
            )
        states = ALL_STATES
        print(f"--states all -> expanding to: {', '.join(states)}\n", file=sys.stderr)
    else:
        states = args.states

    window = find_ableton_window()
    if window is None:
        print("Could not find the Ableton Live window. Is it running?", file=sys.stderr)
        sys.exit(1)

    for state in states:
        print(f"\n=== {state} ===", file=sys.stderr)
        if state in ("session", "arrangement"):
            goto_view(window, state)
        else:
            goto_browser_category(window, state)
        label = state if not args.label_suffix else f"{state}-{args.label_suffix}"
        dump_state(window, label, args.max_depth, args.out_dir, args.no_print)


if __name__ == "__main__":
    main()
