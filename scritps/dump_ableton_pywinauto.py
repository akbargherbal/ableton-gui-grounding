"""
dump_ableton_pywinauto.py

Same purpose as dump_ableton_uia.py, ported to pywinauto's `uia` backend
instead of the raw `uiautomation` library. Read-only inspection tool --
does not click, type, or otherwise control Live.

Requirements
------------
- Windows 10/11
- Ableton Live 12+ running, with at least one project open
- Python 3.9+
- pip install pywinauto

Usage
-----
    python dump_ableton_pywinauto.py                  # dump full tree to console + JSON
    python dump_ableton_pywinauto.py --max-depth 6     # limit recursion depth
    python dump_ableton_pywinauto.py --json out.json   # custom output path
    python dump_ableton_pywinauto.py --diagnose        # list all top-level windows pywinauto can see
    python dump_ableton_pywinauto.py --no-maximize     # dump at current window size (see note below)

Output
------
Prints an indented tree to stdout (control_type, name, automation_id) and
writes the same structure as JSON.

Window readiness (important)
-----------------------------
Ableton's Session View is UI-virtualized: controls that aren't actually
rendered on screen (window minimized, too small, unfocused) don't exist
as UIA elements at all yet, even though their automation_id is
well-defined once they ARE visible. A dump taken against a backgrounded
or restored-size window can silently return far fewer elements with no
error -- confirmed in practice (~60 vs ~201 automation_ids on the same
project, depending only on window state). By default this script
restores/focuses/maximizes the window before every dump
(`ensure_window_ready()`) so you get the full tree; pass --no-maximize
only if you deliberately want to capture the window at its current size
and are aware the result may be incomplete.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


def default_json_path(label: Optional[str], out_dir: str) -> str:
    """Build a timestamped, optionally-labeled output filename so repeat
    runs never silently overwrite a previous dump.

    e.g. dumps/ableton_uia_20260803_153000.json
         dumps/ableton_uia_20260803_153512_sounds-pane.json
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if label:
        safe_label = "".join(
            c if (c.isalnum() or c in "-_") else "-" for c in label
        ).strip("-")
        fname = f"ableton_uia_{stamp}_{safe_label}.json"
    else:
        fname = f"ableton_uia_{stamp}.json"
    return str(Path(out_dir) / fname)

try:
    from pywinauto import Desktop
    from pywinauto.controls.uiawrapper import UIAWrapper
except ImportError:
    print(
        "Missing dependency. Install with:\n"
        "    pip install pywinauto\n",
        file=sys.stderr,
    )
    sys.exit(1)


# Ableton Live's window title format is:
#   "{ProjectName}{*if unsaved} - Ableton Live {Version} {Edition}"
# e.g. "Untitled* - Ableton Live 12 Suite" or "MySet.als - Ableton Live 12 Suite"
# Project name comes first, so match on substring, not prefix.
WINDOW_TITLE_SUBSTRING = "Ableton Live"


@dataclass
class UIANode:
    control_type: str
    name: str
    automation_id: str
    class_name: str
    bounding_rect: Optional[tuple] = None
    is_enabled: bool = True
    is_visible: bool = True
    children: list["UIANode"] = field(default_factory=list)


def is_elevated() -> Optional[bool]:
    """Check whether this script is running with Administrator privileges.

    Windows UIPI silently blocks UI Automation from reading windows owned
    by a process at a *different* privilege level. If this script and
    Ableton don't match on elevation, enumeration will succeed but return
    almost nothing -- the same symptom as with the uiautomation version.
    """
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return None


def diagnose_root_children() -> None:
    """Dump raw info on every top-level window pywinauto/uia can currently
    see, regardless of name/type filtering. Use this when the normal
    search finds suspiciously few (or zero) windows.
    """
    elevated = is_elevated()
    if elevated is True:
        print(
            "This script IS running elevated (as Administrator).\n"
            "If Ableton Live is NOT running elevated, UIPI will block "
            "this script from seeing its window. Try closing this "
            "terminal and rerunning from a normal (non-admin) terminal.\n",
            file=sys.stderr,
        )
    elif elevated is False:
        print(
            "This script is NOT running elevated. If Ableton Live IS "
            "running elevated (as Administrator), that mismatch would "
            "explain seeing nothing / very little below.\n",
            file=sys.stderr,
        )
    else:
        print("Could not determine elevation status.\n", file=sys.stderr)

    try:
        windows = Desktop(backend="uia").windows()
    except Exception as e:
        print(f"Desktop(backend='uia').windows() raised: {e}", file=sys.stderr)
        return

    print(f"Desktop(backend='uia').windows() returned {len(windows)} elements:\n",
          file=sys.stderr)

    for i, w in enumerate(windows):
        name = "?"
        ctype = "?"
        class_name = "?"
        pid = "?"
        handle = "?"
        try:
            name = w.window_text() or "(empty)"
        except Exception as e:
            name = f"(error: {e})"
        try:
            ctype = w.element_info.control_type
        except Exception as e:
            ctype = f"(error: {e})"
        try:
            class_name = w.element_info.class_name or "(empty)"
        except Exception as e:
            class_name = f"(error: {e})"
        try:
            pid = w.process_id()
        except Exception as e:
            pid = f"(error: {e})"
        try:
            handle = w.handle
        except Exception as e:
            handle = f"(error: {e})"

        print(
            f"[{i}] Name={name!r} ControlType={ctype} "
            f"ClassName={class_name!r} ProcessId={pid} Handle={handle}",
            file=sys.stderr,
        )


def find_ableton_window(
    timeout: float = 5.0, title_contains: str = WINDOW_TITLE_SUBSTRING
) -> Optional[UIAWrapper]:
    """Locate the main Ableton Live window by a substring match on title."""
    end_time = time.time() + timeout
    seen_titles = set()
    while time.time() < end_time:
        try:
            windows = Desktop(backend="uia").windows()
        except Exception:
            windows = []
        for w in windows:
            try:
                name = w.window_text() or ""
            except Exception:
                continue
            if name:
                seen_titles.add(name)
            if title_contains.lower() in name.lower():
                return w
        time.sleep(0.25)

    if seen_titles:
        print(
            "\nNo window matched. Top-level window titles that WERE "
            "visible:",
            file=sys.stderr,
        )
        for title in sorted(seen_titles):
            print(f"  - {title}", file=sys.stderr)
        print(
            f"\nNone contained '{title_contains}'. If Ableton's title "
            "format has changed, rerun with --title-contains to match "
            "whatever you see above.",
            file=sys.stderr,
        )
    else:
        print(
            "\nNo top-level windows were visible at all. Run with "
            "--diagnose for more detail (elevation mismatch is the "
            "usual cause).",
            file=sys.stderr,
        )
    return None


def ensure_window_ready(window: UIAWrapper, maximize: bool = True) -> None:
    """Best-effort: make sure Live's window is restored/foregrounded (and,
    by default, maximized) before we read its UIA tree.

    This matters even for a read-only dump: Ableton's Session View is
    UI-virtualized -- controls that aren't actually rendered on screen
    (window minimized, too small, not focused) simply don't exist as UIA
    elements yet, even though their automation_id is well-defined once
    they ARE visible. Confirmed in practice while developing
    automate_ableton_task.py: the same window went from ~60 indexed
    automation_ids to ~201 depending only on whether it was maximized/
    focused, with no error or warning either way -- a dump taken against
    a backgrounded window looks completely valid, just silently
    incomplete. This is the single canonical copy of this function;
    automate_ableton_task.py imports it from here rather than keeping
    its own copy, so the two scripts can't drift apart on this.

    Pass maximize=False if you deliberately want to inspect the window
    at its current (non-maximized) size/position -- e.g. to capture what
    a dialog looks like docked in a specific layout -- but be aware the
    resulting dump may then be missing off-screen/virtualized controls,
    same as any other non-maximized capture.
    """
    try:
        if window.is_minimized():
            print("Window is minimized; restoring...", file=sys.stderr)
            window.restore()
    except Exception:
        pass
    try:
        window.set_focus()
    except Exception:
        pass
    if maximize:
        try:
            window.maximize()
        except Exception:
            pass
    time.sleep(0.3)  # give the redraw a moment before we walk the tree


def rect_to_tuple(rect) -> Optional[tuple]:
    try:
        return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        return None


def walk(control: UIAWrapper, max_depth: int, depth: int = 0) -> UIANode:
    """Recursively walk the tree starting at `control`."""
    try:
        control_type = control.element_info.control_type or ""
    except Exception:
        control_type = "(error)"
    try:
        name = (control.window_text() or "").strip()
    except Exception:
        name = ""
    try:
        automation_id = control.element_info.automation_id or ""
    except Exception:
        automation_id = ""
    try:
        class_name = control.element_info.class_name or ""
    except Exception:
        class_name = ""
    try:
        bounding_rect = rect_to_tuple(control.rectangle())
    except Exception:
        bounding_rect = None
    try:
        is_enabled = bool(control.is_enabled())
    except Exception:
        is_enabled = True
    try:
        is_visible = bool(control.is_visible())
    except Exception:
        is_visible = True

    node = UIANode(
        control_type=control_type,
        name=name,
        automation_id=automation_id,
        class_name=class_name,
        bounding_rect=bounding_rect,
        is_enabled=is_enabled,
        is_visible=is_visible,
    )

    if depth >= max_depth:
        return node

    try:
        children = control.children()
    except Exception:
        children = []

    for child in children:
        node.children.append(walk(child, max_depth, depth + 1))

    return node


def print_tree(node: UIANode, depth: int = 0) -> None:
    indent = "  " * depth
    label = node.name if node.name else "(unnamed)"
    flags = []
    if not node.is_enabled:
        flags.append("disabled")
    if not node.is_visible:
        flags.append("hidden")
    flag_str = f" [{', '.join(flags)}]" if flags else ""
    print(f"{indent}- {node.control_type}: \"{label}\"{flag_str}")
    for child in node.children:
        print_tree(child, depth + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="How many levels deep to recurse (default: 10). "
        "Ableton's tree can be deep inside device chains; raise this "
        "if a device's internals are getting cut off.",
    )
    parser.add_argument(
        "--json",
        type=str,
        default=None,
        help="Path to write the JSON dump. If omitted, an auto-timestamped "
        "filename is generated under --out-dir (default: dumps/), so "
        "repeat runs never overwrite each other. Pass this explicitly "
        "only if you want a fixed filename.",
    )
    parser.add_argument(
        "--label",
        type=str,
        default=None,
        help="Short tag describing what state Ableton was in for this "
        "dump, e.g. 'sounds-pane', 'file-menu-open', 'device-loaded'. "
        "Folded into the auto-generated filename. Ignored if --json is "
        "given explicitly.",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="dumps",
        help="Directory for auto-generated dump filenames (default: dumps/). "
        "Ignored if --json is given explicitly.",
    )
    parser.add_argument(
        "--no-print",
        action="store_true",
        help="Skip printing the tree to stdout, only write JSON.",
    )
    parser.add_argument(
        "--title-contains",
        type=str,
        default=WINDOW_TITLE_SUBSTRING,
        help=f"Substring to match in the window title "
        f"(default: '{WINDOW_TITLE_SUBSTRING}'). Override this if "
        "Ableton's title format differs on your system/version.",
    )
    parser.add_argument(
        "--no-maximize",
        action="store_true",
        help="Skip restoring/focusing/maximizing the window before the "
        "dump. Off by default because Session View is UI-virtualized -- "
        "a non-maximized window can expose far fewer automation_ids with "
        "no warning that the dump is incomplete. Only use this if you "
        "specifically want to capture the window at its current size.",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Instead of searching for Ableton, dump raw info on every "
        "top-level window pywinauto can see (name, control type, class, "
        "process id) plus this script's elevation status. Use this "
        "when normal search finds suspiciously few / zero windows.",
    )
    args = parser.parse_args()

    if args.json is None:
        args.json = default_json_path(args.label, args.out_dir)

    if args.diagnose:
        diagnose_root_children()
        return

    print("Looking for the Ableton Live window...", file=sys.stderr)
    window = find_ableton_window(title_contains=args.title_contains)
    if window is None:
        print(
            f"\nCould not find a window containing '{args.title_contains}'. "
            "Is Ableton Live running with a project open?",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Found window: \"{window.window_text()}\" -- walking tree "
          f"(max depth {args.max_depth})...", file=sys.stderr)

    ensure_window_ready(window, maximize=not args.no_maximize)

    tree = walk(window, max_depth=args.max_depth)

    if not args.no_print:
        print_tree(tree)

    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(asdict(tree), f, indent=2, ensure_ascii=False)

    print(f"\nJSON tree written to: {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
