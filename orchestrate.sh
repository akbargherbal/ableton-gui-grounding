#!/usr/bin/env bash
# orchestrate.sh — coordination layer
#
# Runs ONE automate_ableton_task.py task against real Ableton, then takes ONE
# screenshot of the result via take_shot.sh, auto-numbering and auto-
# labeling the screenshot from the task's own structured EVENT: output.
# Single-action tasks only — see SINGLE_ACTION_TASKS below.
# `solo_tour` is explicitly excluded: it's multi-step internally, so one
# orchestrate.sh call would only get a before/after screenshot pair, not
# one screenshot per click.
#
# Usage:
#   ./orchestrate.sh <lab_dir> <task> [task-args...]

set -uo pipefail

SINGLE_ACTION_TASKS=(arm_track set_tempo probe_toggle probe_solo_transport
                      probe_keyboard_activator read_solo_states solo_one)

EXPECTED_SCHEMA_VERSION=1

usage() {
  echo "Usage: $0 <lab_dir> <task> [task-args...]" >&2
  echo "  <task> must be one of: ${SINGLE_ACTION_TASKS[*]}" >&2
  echo "  (solo_tour is explicitly excluded — multi-step internally, no per-click screenshots)" >&2
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

extract_json_float() {
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
    print(v)
except Exception:
    print("")
' "$json" "$field"
  fi
}

# --- drift detection (Phase 3) ---
drift_check() {
  local tasks_json
  tasks_json="$("$PYTHON_CMD" "$AUTOMATE_SCRIPT" --list-tasks 2>/dev/null || true)"
  if [ -z "$tasks_json" ]; then
    echo "[orchestrator] FATAL: could not retrieve task list from automate_ableton_task.py" >&2
    echo "[orchestrator]        Is the script broken or pywinauto missing? (--list-tasks should work even without it)" >&2
    exit 1
  fi

  local actual_version
  actual_version="$(extract_json_float "$tasks_json" "schema_version")"
  if [ "$actual_version" != "$EXPECTED_SCHEMA_VERSION" ]; then
    echo "[orchestrator] FATAL: EVENT schema version mismatch (expected $EXPECTED_SCHEMA_VERSION, got $actual_version)" >&2
    exit 1
  fi

  log "drift check: schema_version=$actual_version OK"
}

task_is_allowed=0
for t in "${SINGLE_ACTION_TASKS[@]}"; do
  if [ "$t" = "$TASK" ]; then
    task_is_allowed=1
    break
  fi
done
if [ "$task_is_allowed" -ne 1 ]; then
  if [ "$TASK" = "solo_tour" ]; then
    echo "[orchestrator] ERROR: solo_tour is multi-step; use solo_one in a loop instead," >&2
    echo "[orchestrator]        so each track gets its own screenshot." >&2
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

# --- Phase 3 drift detection (once per run, before any action) ---
drift_check

mkdir -p "$LAB_ABS_DIR"
SEQ_FILE="$LAB_ABS_DIR/.orchestrate_seq"
LAST_SEQ=0
if [ -f "$SEQ_FILE" ]; then
  LAST_SEQ="$(cat "$SEQ_FILE")"
  case "$LAST_SEQ" in (*[!0-9]*|'') LAST_SEQ=0 ;; esac
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

# --------------------------------------------------------------------------
# run_one_task — core "run automate script + take screenshot" unit
# --------------------------------------------------------------------------
#
# $1 = seq_padded (e.g. "03"), $2 = fallback label (task name), rest = args
# to automate_ableton_task.py (must include --live for real action).
# Returns the worse of automate exit code and screenshot exit code.

run_one_task() {
  local run_seq_padded="$1"
  local run_fallback_label="$2"
  shift 2
  local auto_args=("$@")

  local events_tmp
  events_tmp="$(mktemp)"

  log "running: ${auto_args[*]}"
  echo "--- automate_ableton_task.py output ---"
  "$PYTHON_CMD" "$AUTOMATE_SCRIPT" "${auto_args[@]}" 2>&1 | tee "$events_tmp"
  local auto_exit="${PIPESTATUS[0]}"
  echo "--- end automate_ableton_task.py output ---"

  if [ "$auto_exit" -eq 0 ]; then
    log "task succeeded (exit 0)"
  else
    log "task FAILED (exit $auto_exit) — not retrying against live Ableton; still capturing a failure screenshot"
  fi

  # derive <short_description> from EVENT: line
  local last_event_line
  last_event_line="$(grep '^EVENT: ' "$events_tmp" | grep '"label":' | tail -n 1 || true)"
  if [ -z "$last_event_line" ]; then
    last_event_line="$(grep '^EVENT: ' "$events_tmp" | tail -n 1 || true)"
  fi

  local raw_desc=""
  if [ -n "$last_event_line" ]; then
    local json_body
    json_body="${last_event_line#EVENT: }"
    raw_desc="$(extract_field "$json_body" "label")"
    if [ -z "$raw_desc" ]; then
      raw_desc="$(extract_field "$json_body" "task")"
    fi
  fi
  if [ -z "$raw_desc" ]; then
    raw_desc="$run_fallback_label"
  fi

  local desc
  desc="$(slugify "$raw_desc")"
  if [ "$auto_exit" -ne 0 ]; then
    desc="${desc}_FAILED"
  fi

  rm -f "$events_tmp"

  log "capturing screenshot: seq=$run_seq_padded desc=$desc"
  echo "--- take_shot.sh output ---"
  "$TAKE_SHOT" "$LAB_DIR" "$run_seq_padded" "$desc"
  local shot_exit=$?
  echo "--- end take_shot.sh output ---"

  if [ "$shot_exit" -ne 0 ]; then
    log "screenshot capture FAILED (exit $shot_exit)"
  fi

  log "done. automate_exit=$auto_exit shot_exit=$shot_exit"

  if [ "$auto_exit" -ne 0 ]; then
    return "$auto_exit"
  fi
  return "$shot_exit"
}

# --------------------------------------------------------------------------
# solo_one: Phase 2 loop over multiple tracks (one seq + screenshot each)
# --------------------------------------------------------------------------

if [ "$TASK" = "solo_one" ]; then
  # Parse --tracks and --seconds from TASK_ARGS
  solo_tracks=()
  solo_seconds=3.0
  parse_mode=""
  for arg in "${TASK_ARGS[@]}"; do
    if [ "$arg" = "--tracks" ]; then
      parse_mode="tracks"
    elif [ "$arg" = "--seconds" ]; then
      parse_mode="seconds"
    elif [ "$parse_mode" = "tracks" ]; then
      solo_tracks+=("$arg")
    elif [ "$parse_mode" = "seconds" ]; then
      solo_seconds="$arg"
    fi
  done

  if [ ${#solo_tracks[@]} -eq 0 ]; then
    echo "[orchestrator] ERROR: solo_one requires at least one --tracks index" >&2
    usage
  fi

  log "solo_one loop: ${#solo_tracks[@]} track(s), seconds=$solo_seconds"
  overall_exit=0
  for solo_track in "${solo_tracks[@]}"; do
    SEQ=$((LAST_SEQ + 1))
    SEQ_PADDED="$(printf "%02d" "$SEQ")"

    log "solo_one: Track[${solo_track}] (seq=$SEQ_PADDED)"

    run_one_task "$SEQ_PADDED" "solo_one" \
      --task solo_one --tracks "$solo_track" \
      --seconds "$solo_seconds" --live

    local_exit=$?
    [ "$local_exit" -ne 0 ] && overall_exit=$local_exit

    printf '%s' "$SEQ" > "$SEQ_FILE"
    LAST_SEQ=$SEQ
  done

  log "done. exit=$overall_exit"
  exit "$overall_exit"
fi

# --------------------------------------------------------------------------
# Standard single-action path (all tasks except solo_one)
# --------------------------------------------------------------------------

SEQ=$((LAST_SEQ + 1))
SEQ_PADDED="$(printf "%02d" "$SEQ")"
printf '%s' "$SEQ" > "$SEQ_FILE"

log "task=$TASK args=${TASK_ARGS[*]:-<none>} lab_dir=$LAB_DIR seq=$SEQ_PADDED"
log "running automate task (--live, no dry-run — this is a real action)"

run_one_task "$SEQ_PADDED" "$TASK" \
  --task "$TASK" --live "${TASK_ARGS[@]:-}"

exit $?