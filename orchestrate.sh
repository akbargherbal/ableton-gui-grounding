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

set -uo pipefail

SINGLE_ACTION_TASKS=(arm_track set_tempo probe_toggle probe_solo_transport
                      probe_keyboard_activator read_solo_states)

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

# --- derive <short_description> from EVENT: line ---
extract_field() {
  # $1 = raw JSON body (no "EVENT: " prefix), $2 = field name
  local json="$1" field="$2"
  local py_bin=""
  if command -v python3 >/dev/null 2>&1; then
    py_bin="python3"
  elif command -v python >/dev/null 2>&1; then
    py_bin="python"
  fi

  if [ -n "$py_bin" ]; then
    "$py_bin" -c '
import json, sys
try:
    d = json.loads(sys.argv[1])
    v = d.get(sys.argv[2], "")
    print(v if isinstance(v, str) else "")
except Exception:
    print("")
' "$json" "$field"
  else
    echo "$json" | sed -n "s/.*\"$field\":[[:space:]]*\"\([^\"]*\)\".*/\1/p"
  fi
}

slugify() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/_/g; s/^_+|_+$//g'
}

# Prefer the last event line containing a "label" field; fall back to the last event line overall
LAST_EVENT_LINE="$(grep '^EVENT: ' "$EVENTS_TMP" | grep '"label":' | tail -n 1 || true)"
if [ -z "$LAST_EVENT_LINE" ]; then
  LAST_EVENT_LINE="$(grep '^EVENT: ' "$EVENTS_TMP" | tail -n 1 || true)"
fi

RAW_DESC=""
if [ -n "$LAST_EVENT_LINE" ]; then
  JSON_BODY="${LAST_EVENT_LINE#EVENT: }"
  RAW_DESC="$(extract_field "$JSON_BODY" "label")"
  if [ -z "$RAW_DESC" ]; then
    RAW_DESC="$(extract_field "$JSON_BODY" "task")"
  fi
fi
if [ -z "$RAW_DESC" ]; then
  RAW_DESC="$TASK"  # no EVENT: line at all
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

if [ "$AUTOMATE_EXIT" -ne 0 ]; then
  exit "$AUTOMATE_EXIT"
fi
exit "$SHOT_EXIT"