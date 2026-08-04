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

Not yet supported: Browser panel categories (sounds, instruments, ...)
------------------------------------------------------------------------
Every automation_id used anywhere in this project so far ("SessionView.
Track[N].Mixer.Solo" etc.) was found by inspecting a real dump, never
predicted from a naming convention -- guessing browser-category IDs isn't
worth the risk of silently clicking the wrong thing. To add one:
    1. In Ableton, open the Browser panel and select the category by hand.
    2. python dump_ableton_pywinauto.py --label browser-sounds
    3. python grep_dump.py dumps/..._browser-sounds.json sound
    4. Add the automation_id you find to BROWSER_CATEGORY_IDS below.

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
id", a check we get for free from behavior already characterized, no new
discovery needed for this half of the problem.

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

# Fill in once discovered -- see module docstring for how.
BROWSER_CATEGORY_IDS: dict[str, str] = {
    # "sounds": "???",
    # "instruments": "???",
}


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
        choices=["session", "arrangement"] + list(BROWSER_CATEGORY_IDS),
        help="Which states to dump, in order.",
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

    window = find_ableton_window()
    if window is None:
        print("Could not find the Ableton Live window. Is it running?", file=sys.stderr)
        sys.exit(1)

    for state in args.states:
        print(f"\n=== {state} ===", file=sys.stderr)
        if state in ("session", "arrangement"):
            goto_view(window, state)
        else:
            raise NotImplementedError(
                f"Browser category '{state}' needs its automation_id wired "
                "into BROWSER_CATEGORY_IDS first -- see module docstring."
            )
        label = state if not args.label_suffix else f"{state}-{args.label_suffix}"
        dump_state(window, label, args.max_depth, args.out_dir, args.no_print)


if __name__ == "__main__":
    main()
