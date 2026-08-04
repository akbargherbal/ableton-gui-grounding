"""
grep_dump.py

Search a JSON tree dump (produced by dump_ableton_pywinauto.py or
dump_ableton_states.py) for nodes whose name, automation_id, or
class_name contains a substring. Prints each match's breadcrumb path,
control_type, automation_id, and bounding_rect -- everything needed to
wire a new automation_id into automate_ableton_task.py or
dump_ableton_states.py without re-deriving it from scratch.

Typical use: capture a dump while a specific UI state is visible by hand
(e.g. Browser panel open, "Sounds" category selected), then grep it for
"sound" to find that category tab's automation_id.

Pure stdlib, no pywinauto dependency -- works on any machine with the
JSON file, not just the Windows box Ableton runs on.

Usage
-----
    python grep_dump.py dumps/ableton_uia_..._browser-sounds.json sound
    python grep_dump.py dumps/foo.json instrument --max-results 20
"""

from __future__ import annotations

import argparse
import json


def walk_matches(node: dict, path: list[str], query: str,
                  matches: list[tuple[str, dict]]) -> None:
    name = node.get("name", "") or ""
    aid = node.get("automation_id", "") or ""
    cls = node.get("class_name", "") or ""
    label = name or f"({node.get('control_type', '?')})"
    breadcrumb = path + [label]

    haystack = f"{name} {aid} {cls}".lower()
    if query.lower() in haystack:
        matches.append((" > ".join(breadcrumb), node))

    for child in node.get("children", []):
        walk_matches(child, breadcrumb, query, matches)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("json_path", type=str)
    parser.add_argument(
        "query", type=str,
        help="Substring to search for (case-insensitive) in name/automation_id/class_name",
    )
    parser.add_argument("--max-results", type=int, default=30)
    args = parser.parse_args()

    with open(args.json_path, "r", encoding="utf-8") as f:
        tree = json.load(f)

    matches: list[tuple[str, dict]] = []
    walk_matches(tree, [], args.query, matches)

    if not matches:
        print(f"No matches for {args.query!r} in {args.json_path}")
        return

    print(f"{len(matches)} match(es) for {args.query!r} (showing up to {args.max_results}):\n")
    for breadcrumb, node in matches[: args.max_results]:
        print(f"- {node.get('control_type')}: {node.get('name')!r}")
        print(f"    automation_id: {node.get('automation_id')!r}")
        print(f"    class_name:    {node.get('class_name')!r}")
        print(f"    bounding_rect: {node.get('bounding_rect')}")
        print(f"    path: {breadcrumb}\n")

    if len(matches) > args.max_results:
        print(f"...and {len(matches) - args.max_results} more (raise --max-results to see them).")


if __name__ == "__main__":
    main()
