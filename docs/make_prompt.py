#!/usr/bin/env python
"""
make_prompt.py -- extract one routing_test_protocol.md prompt as plain text.

Single source of truth is docs/routing_test_protocol.md itself -- there is no
separate prompts.json to keep in sync. Every probe's fenced ```text``` block
is parsed directly from the protocol doc each time this runs, so the prompt
list always matches whatever's currently in the protocol.

Usage:
    python make_prompt.py [output_path]

    output_path omitted   -> writes ./<PROBE_ID>.txt in the current directory
    output_path is a dir  -> writes <output_path>/<PROBE_ID>.txt
    output_path is a file -> writes exactly to that path

Example (run from inside docs/, OpenCode workflow):
    python make_prompt.py ../../ableton-ai-training/
    # then in OpenCode: Read my prompt is @P0.1.txt
"""
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROTOCOL_PATH = os.path.join(SCRIPT_DIR, "routing_test_protocol.md")

HEADING_RE = re.compile(r"^###\s+(P\d+\.\d+)\b.*$", re.MULTILINE)
CODE_BLOCK_RE = re.compile(r"```text\s*\n(.*?)```", re.DOTALL)


def parse_probes(protocol_path):
    """Return an ordered list of (probe_id, prompt_text) from the protocol doc."""
    with open(protocol_path, "r", encoding="utf-8") as f:
        content = f.read()

    headings = list(HEADING_RE.finditer(content))
    probes = []

    for i, m in enumerate(headings):
        probe_id = m.group(1)
        section_start = m.end()
        section_end = headings[i + 1].start() if i + 1 < len(headings) else len(content)
        section = content[section_start:section_end]

        code_block = CODE_BLOCK_RE.search(section)
        if not code_block:
            continue

        probes.append((probe_id, code_block.group(1).strip()))

    return probes


def resolve_output_path(raw_arg, probe_id):
    """Turn the user's CLI argument into a concrete output file path."""
    default_filename = f"{probe_id}.txt"

    if not raw_arg:
        return default_filename

    if os.path.isdir(raw_arg) or raw_arg.endswith(("/", "\\")):
        os.makedirs(raw_arg, exist_ok=True)
        return os.path.join(raw_arg, default_filename)

    parent = os.path.dirname(raw_arg)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    return raw_arg


def main():
    if not os.path.exists(PROTOCOL_PATH):
        print(f"Error: {PROTOCOL_PATH} not found.")
        sys.exit(1)

    probes = parse_probes(PROTOCOL_PATH)
    if not probes:
        print("No probes with a ```text``` prompt block found in routing_test_protocol.md.")
        sys.exit(1)

    print(f"Found {len(probes)} prompts in routing_test_protocol.md:\n")
    for i, (probe_id, prompt_text) in enumerate(probes, start=1):
        preview = prompt_text if len(prompt_text) <= 70 else prompt_text[:67] + "..."
        preview = preview.replace("\n", " ")
        print(f"  {i:>2}. {probe_id:<6} {preview}")

    raw_arg = sys.argv[1] if len(sys.argv) > 1 else ""

    try:
        selection = int(input(f"\nPick a number (1 to {len(probes)}): "))
    except ValueError:
        print("Invalid selection.")
        sys.exit(1)

    if not (1 <= selection <= len(probes)):
        print("Selection out of range.")
        sys.exit(1)

    probe_id, prompt_text = probes[selection - 1]
    output_path = resolve_output_path(raw_arg, probe_id)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(prompt_text)

    print(f"\nSaved {probe_id} -> {output_path}")
    print(f"In OpenCode: Read my prompt is @{os.path.basename(output_path)}")


if __name__ == "__main__":
    main()
