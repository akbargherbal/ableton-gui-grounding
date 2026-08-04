#!/usr/bin/env bash
# orchestrate.sh — Phase 1 coordination layer (see phased_plan.md, context.md)
#
# Runs ONE automate_ableton_task.py task against real Ableton, then takes ONE
# screenshot of the result via take_shot.sh, auto-numbering and auto-
# labeling the screenshot from the task's own structured EVENT: output
# (Phase 0). Single-action tasks only — see SINGLE_ACTION_TASKS below.
# `solo_tour` is explicitly excluded (Phase 2 territory: it's multi-step
# internally, so one orchestrate.sh call would only get a before/after
# screenshot pair, not per-click).
#
# Usage:
#   ./orchestrate.sh <lab_dir> <task> [task-args...]
#
# <lab_dir> is passed straight through to take_shot.sh, unmodified — same
# meaning as there (a path relative to the project root, e.g.
# LABS/MOD_02_2026-08-03_1430/creating-drum-loop). This script never
# reinterprets or converts it (no /mnt/c/... <-> C:\... logic lives here);
# that discipline belongs to take_shot.sh alone.
#
# Examples:
#   ./orchestrate.sh LABS/MOD_02_2026-08-03_1430/creating-drum-loop arm_track --tracks 1
#   ./orchestrate.sh LABS/MOD_02_2026-08-03_1430/creating-drum-loop set_tempo --bpm 128
#   ./orchestrate.sh LABS/MOD_02_2026-08-03_1430/creating-drum-loop read_solo_states --tracks 0 1 2
#
# Every call:
#   1. Runs `python.exe scritps/automate_ableton_task.py --task <task> --live
#      [task-args...]`, capturing its stdout (automate's own print() lines
#      AND its EVENT: lines are interleaved exactly as emitted — this
#      script does not separate them, see Phase 0 note in automate's own
#      module docstring on why that ordering is deliberate).
#   2. Checks automate's exit code. On failure: does NOT retry against the
#      live Ableton session (never safe — see phased_plan.md Phase 1) but
#      DOES still take a screenshot, tagged "_FAILED", so the failure
#      itself is part of the documentation trail. Then this script exits
#      with automate's own exit code, so a caller (or a human) can tell
#      success from failure without parsing output.
#   3. Derives the screenshot's <short_description> from the LAST EVENT:
#      line's "label" field (falls back to "task", falls back to the
#      --task name itself if no EVENT: line was emitted at all — e.g. a
#      crash before the first one).
#   4. Calls ./take_shot.sh <lab_dir> <seq> <desc>, where <seq> is
#      maintained automatically per lab_dir (see SEQ_FILE below) so
#      repeated orchestrate.sh calls for the same lab don't need manual
#      numbering.
#
# Every line this script itself prints (not automate's, not take_shot's)
# is tagged "[orchestrator]" and its two sub-calls are wrapped in visible
# "--- ... ---" separators, so a raw terminal transcript stays scannable
# across all three layers even though this script doesn't touch the other
# two scripts' own output.
#
# Test seams (used by scritps/test_orchestrate.py to verify control flow —
# arg parsing, seq counter, path passthrough, error branching — without
# Windows/Ableton). Defaults are the real, unmodified paths; only a test
# harness should ever override these:
#   ORCH_PYTHON_CMD      default: python.exe
#   ORCH_AUTOMATE_SCRIPT default: <this script's dir>/scritps/automate_ableton_task.py
#   ORCH_TAKE_SHOT       default: <this script's dir>/take_shot.sh

set -uo pipefail
# Deliberately NOT `set -e`: this script inspects automate's and
# take_shot's exit codes itself (to decide "still take the failure
# screenshot" and "which code to exit with") rather than aborting on the
# first non-zero status.

SINGLE_ACTION_TASKS=(arm_track set_tempo probe_toggle probe_solo_transport
                      probe_keyboard_activator read_solo_states)
# Hardcoded here deliberately (Phase 1 scope). Phase 3's --list-tasks
# introspection is what's supposed to close the drift risk of this list
# silently going stale vs automate_ableton_task.py's own --task choices —
# not built yet, see phased_plan.md Phase 3.

usage() {
  echo "Usage: $0 <lab_dir> <task> [task-args...]" >&2
  echo "  <task> must be one of: ${SINGLE_ACTION_TASKS[*]}" >&2
  echo "  (solo_tour is explicitly excluded — see phased_plan.md Phase 2)" >&2
  exit 1
}

if [ "$#" -lt 2 ]; then
  usage
fi

LAB_DIR="$1"
TASK="$2"
shift 2
TASK_ARGS=("$@")

log() { echo "[orchestrator] $*"; }

task_is_allowed=0
for t in "${SINGLE_ACTION_TASKS[@]}"; do
  if [ "$t" = "$TASK" ]; then
    task_is_allowed=1
    break
  fi
done
if [ "$task_is_allowed" -ne 1 ]; then
  if [ "$TASK" = "solo_tour" ]; then
    echo "[orchestrator] ERROR: solo_tour is explicitly excluded from orchestrate.sh (Phase 1)." >&2
    echo "[orchestrator]        It's multi-step internally; this script only gets a before/after" >&2
    echo "[orchestrator]        screenshot pair, not per-click. See phased_plan.md Phase 2." >&2
  else
    echo "[orchestrator] ERROR: unknown or unsupported task '$TASK'." >&2
  fi
  usage
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Mirrors take_shot.sh's own PROJECT_ROOT resolution exactly (including the
# same ABLETON_PROJECT_ROOT override) so that if a caller ever does
# override it, this script's seq-counter file and take_shot.sh's actual
# screenshot both land under the same root — never two different ideas of
# "where the lab dir is."
PROJECT_ROOT="${ABLETON_PROJECT_ROOT:-$SCRIPT_DIR}"
LAB_ABS_DIR="$PROJECT_ROOT/$LAB_DIR"

PYTHON_CMD="${ORCH_PYTHON_CMD:-python.exe}"
AUTOMATE_SCRIPT="${ORCH_AUTOMATE_SCRIPT:-$SCRIPT_DIR/scritps/automate_ableton_task.py}"
TAKE_SHOT="${ORCH_TAKE_SHOT:-$SCRIPT_DIR/take_shot.sh}"

mkdir -p "$LAB_ABS_DIR"
SEQ_FILE="$LAB_ABS_DIR/.orchestrate_seq"
LAST_SEQ=0
if [ -f "$SEQ_FILE" ]; then
  LAST_SEQ="$(cat "$SEQ_FILE")"
  case "$LAST_SEQ" in (*[!0-9]*|'') LAST_SEQ=0 ;; esac
fi
SEQ=$((LAST_SEQ + 1))
printf '%s' "$SEQ" > "$SEQ_FILE"
SEQ_PADDED="$(printf "%02d" "$SEQ")"

EVENTS_TMP="$(mktemp)"
cleanup() { rm -f "$EVENTS_TMP"; }
trap cleanup EXIT

log "task=$TASK args=${TASK_ARGS[*]:-<none>} lab_dir=$LAB_DIR seq=$SEQ_PADDED"
log "running automate task (--live, no dry-run — this is a real action)"
echo "--- automate_ableton_task.py output ---"
"$PYTHON_CMD" "$AUTOMATE_SCRIPT" --task "$TASK" --live "${TASK_ARGS[@]:-}" 2>&1 | tee "$EVENTS_TMP"
AUTOMATE_EXIT="${PIPESTATUS[0]}"
echo "--- end automate_ableton_task.py output ---"

if [ "$AUTOMATE_EXIT" -eq 0 ]; then
  log "task succeeded (exit 0)"
else
  log "task FAILED (exit $AUTOMATE_EXIT) — not retrying against live Ableton; still capturing a failure screenshot"
fi

# --- derive <short_description> from the last EVENT: line ---
extract_field() {
  # $1 = raw JSON body (no "EVENT: " prefix), $2 = field name
  local json="$1" field="$2"
  if command -v python3 >/dev/null 2>&1; then
    python3 -c '
import json, sys
try:
    d = json.loads(sys.argv[1])
    v = d.get(sys.argv[2], "")
    print(v if isinstance(v, str) else "")
except Exception:
    print("")
' "$json" "$field"
  else
    # Minimal fallback if python3 isn't on PATH: string-literal fields only
    # (label/task are always strings in the Phase 0 schema, so this is
    # sufficient — no need for a full JSON parser here).
    echo "$json" | sed -n "s/.*\"$field\":[[:space:]]*\"\([^\"]*\)\".*/\1/p"
  fi
}

slugify() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/_/g; s/^_+|_+$//g'
}

LAST_EVENT_LINE="$(grep '^EVENT: ' "$EVENTS_TMP" | tail -n 1 || true)"
RAW_DESC=""
if [ -n "$LAST_EVENT_LINE" ]; then
  JSON_BODY="${LAST_EVENT_LINE#EVENT: }"
  RAW_DESC="$(extract_field "$JSON_BODY" "label")"
  if [ -z "$RAW_DESC" ]; then
    RAW_DESC="$(extract_field "$JSON_BODY" "task")"
  fi
fi
if [ -z "$RAW_DESC" ]; then
  RAW_DESC="$TASK"  # no EVENT: line at all (e.g. crash before the first one)
fi

DESC="$(slugify "$RAW_DESC")"
if [ "$AUTOMATE_EXIT" -ne 0 ]; then
  DESC="${DESC}_FAILED"
fi

# --- screenshot (always, success or failure) ---
log "capturing screenshot: seq=$SEQ_PADDED desc=$DESC"
echo "--- take_shot.sh output ---"
"$TAKE_SHOT" "$LAB_DIR" "$SEQ_PADDED" "$DESC"
SHOT_EXIT=$?
echo "--- end take_shot.sh output ---"

if [ "$SHOT_EXIT" -ne 0 ]; then
  log "screenshot capture FAILED too (exit $SHOT_EXIT)"
fi

log "done. automate_exit=$AUTOMATE_EXIT shot_exit=$SHOT_EXIT"

# The automate task's own failure is the primary signal — surface that
# exit code first if both went wrong, since that's the real-world cause.
if [ "$AUTOMATE_EXIT" -ne 0 ]; then
  exit "$AUTOMATE_EXIT"
fi
exit "$SHOT_EXIT"