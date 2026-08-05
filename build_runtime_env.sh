#!/usr/bin/env bash
# build_runtime_env.sh — assemble the minimal, agent-facing runtime folder
# from this dev repo, so OpenCode never has filesystem access to the audit
# trail (context.md, docs/, tests, stale dumps, README).
#
# WHITELIST, not blacklist: only files listed in FILES[] below ever leave
# this repo. A new dev file added later is invisible to the agent unless
# someone deliberately adds it to the list — fails safe by default.
#
# Usage:
#   ./build_runtime_env.sh [target_dir]
#   target_dir defaults to a sibling folder: ../ableton-runtime
#
# Point OpenCode's working directory at <target_dir>, not this dev repo.
# Re-run this script any time AGENTS.md or the whitelisted scripts change;
# it's a straight overwrite of the code files, but never touches LABS/ or
# scritps/dumps/ once they exist, so prior session artifacts aren't lost.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-$SCRIPT_DIR/../ableton-runtime}"

# --- The whitelist -----------------------------------------------------
# Everything the agent needs to actually execute AGENTS.md's routing
# rules, and nothing else. Dependency chain verified by grepping actual
# imports, not assumed from file names:
#   automate_ableton_task.py imports dump_ableton_pywinauto (window/tree
#     helpers) and keyboard_shortcuts (L2 escalation) — both hard deps.
#   dump_ableton_states.py imports both of the above too, if included.
#   orchestrate.sh calls automate_ableton_task.py and take_shot.sh by
#     relative path — both must sit exactly where it expects them.
FILES=(
  "AGENTS.md"
  "orchestrate.sh"
  "take_shot.sh"
  "scritps/automate_ableton_task.py"
  "scritps/dump_ableton_pywinauto.py"    # hard dep of automate_ableton_task.py
  "scritps/keyboard_shortcuts.py"        # hard dep of automate_ableton_task.py
  "scritps/keyboard_shortcuts.md"        # human-readable shortcut reference
  "scritps/dump_ableton_states.py"       # optional: view/browser-category switching
)
# Deliberately NOT included: LICENSE, README.md, context.md, docs/**
# (including item_8_plan.md, v2_observations.md, the risk framework doc,
# the MCP setup doc, archived/**), scritps/grep_dump.py, scritps/dumps/*,
# scritps/test_*.py, and docs/routing_test_protocol.md specifically —
# that last one is the answer key for live agent tests; shipping it into
# the runtime folder would let the agent read its own eval.
# -------------------------------------------------------------------------

mkdir -p "$TARGET"
echo "[build] target: $TARGET"

for f in "${FILES[@]}"; do
  src="$SCRIPT_DIR/$f"
  if [ ! -f "$src" ]; then
    echo "[build] FATAL: whitelisted file missing from dev repo: $f" >&2
    exit 1
  fi
  mkdir -p "$TARGET/$(dirname "$f")"
  cp -f "$src" "$TARGET/$f"
  echo "  copied: $f"
done

# Runtime-only output directories — created empty if missing, never wiped
# if they already exist.
mkdir -p "$TARGET/LABS"
mkdir -p "$TARGET/scritps/dumps"

echo "[build] done. ${#FILES[@]} files synced."
echo "[build] LABS/ and scritps/dumps/ preserved if pre-existing, created empty otherwise."
echo "[build] Point OpenCode's working directory at: $TARGET"
