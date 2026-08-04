# Context handoff: Ableton Session View UI-automation project

This file is written by Claude, for Claude, to restore session context.
**STATE is overwritten each session — it should always reflect only the
current truth, never a history of how we got there.** LOG is append-only
and holds the reasoning/investigation trail, kept compressed. When in
doubt about what's true right now, trust STATE, not LOG.

---

## STATE (current truth — overwrite this section each session)

### Goal

AI-agent-controllable Ableton Live via Windows UI Automation (pywinauto).
**Claude cannot run pywinauto/Ableton — Linux sandbox, no Windows/Live
access.** All real-world testing is done by the user on their Windows
machine; terminal output pasted back is ground truth over any theory
Claude proposes.

### Files

| File                            | Role                                                                                                                                                                                                                                                                                                                                      | Status                                                                                                                                                                                                                                              |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dump_ableton_pywinauto.py`     | Read-only tree dump. Canonical `find_ableton_window()` + `ensure_window_ready()`, imported by the other two.                                                                                                                                                                                                                              | CONFIRMED                                                                                                                                                                                                                                           |
| `automate_ableton_task.py`      | Live deliverable — acts on Live (click/type). Source of `build_automation_id_index()`.                                                                                                                                                                                                                                                    | CONFIRMED (solo_tour path); `click_by_id()` escalation ladder (Mouse → Keyboard → Human instructions) CONFIRMED. **Phase 0 structured event instrumentation (`emit_event`, `EVENT:` JSON lines) CONFIRMED live against real Ableton (session 10)**. |
| `orchestrate.sh`                | Phase 1 coordination layer at repo root — drives single-action tasks, auto-derives screenshot labels from Phase 0 `EVENT:` JSON lines, handles errors with `_FAILED` captures, auto-increments sequence counters.                                                                                                                         | **CONFIRMED & VERIFIED live on Windows (session 11)**                                                                                                                                                                                               |
| `scritps/test_phase0_events.py` | Pure control-flow stub tests for Phase 0 event instrumentation (`emit_event`, `set_checkbox_by_id`, `click_by_id`, `run_task`).                                                                                                                                                                                                           | CONFIRMED (14/14 tests passed, session 10)                                                                                                                                                                                                          |
| `scritps/test_orchestrate.py`   | Pure control-flow stub tests for `orchestrate.sh` (arg parsing, seq counter, path passthrough, error branching, JSON label extraction).                                                                                                                                                                                                   | **CONFIRMED (11/11 tests passed, session 11)**                                                                                                                                                                                                      |
| `dump_ableton_states.py`        | Switches Ableton between named states, dumps each.                                                                                                                                                                                                                                                                                        | CONFIRMED — Session/Arrangement, and all six Browser categories (`sounds`, `instruments`, `drums`, `audio_effects`, `midi_effects`, `plugins`), verified via `--states all` in one run.                                                             |
| `grep_dump.py`                  | Stdlib substring search over a JSON dump.                                                                                                                                                                                                                                                                                                 | CONFIRMED                                                                                                                                                                                                                                           |
| `keyboard_shortcuts.py` + `.md` | Level-2 (keyboard) escalation reference layer for `click_by_id()` — see "Escalation ladder reference layer" below. Data-only dict (`.py`) kept in lockstep with a human-readable index (`.md`), sourced from Ableton's official manual. `blocked=True` entries guard shortcuts that depend on the unresolved "selected track" blind spot. | `activator_by_position` (F1–F8 → `Track[N].Activator`) CONFIRMED live, session 8. All other entries still `blocked=True` or unconfirmed.                                                                                                            |

### automation_id scheme (confirmed structural IDs)

```
SessionView.Track[N].Mixer.Arm                       CheckBox
SessionView.Track[N].Mixer.Activator                 CheckBox (mute)
SessionView.Track[N].Mixer.Solo                      CheckBox
SessionView.Track[N].Mixer.Monitoring.Buttons[0..2]  RadioButton (In/Auto/Off)
SessionView.Track[N].Mixer.Stop                      Button (clip stop)
SessionView.Track[N].Slot[M]                         Group (clip slot) -- NOT YET EXERCISED
SessionView.ReturnTrack[N].Mixer.*                   same shape, return tracks
Transport.Tempo                                      Slider
Transport.Play / Transport.Stop                      assumed by pattern, not independently confirmed
```

**Correction (session 4, from a real dump already in `scritps/dumps/`):**
`Transport.Play` is a confirmed `CheckBox` (toggle-readable, same as Solo/
Arm); `Transport.Stop` is a confirmed plain `Button` (momentary, no toggle
state of its own — only indirectly verifiable via `Transport.Play` reading
`False` afterward). `Monitoring.Buttons[0..2]` also independently confirmed
`RadioButton` from the same dump.

Test project: Track[0..3] = MIDI/Audio, ReturnTrack[0..1] = A-Reverb/B-Delay.

### Open items (not started / not hardened)

- ~~`click_by_id()` has no post-click verification~~ — **DONE, session 4.**
- ~~Phase 0 — Structured events in `automate_ableton_task.py`~~ — **DONE & VERIFIED, session 10** (14/14 stub tests passed + live Ableton output confirmed).
- ~~Phase 1 — Orchestrator script (`orchestrate.sh`)~~ — **DONE & VERIFIED, session 11** (11/11 stub tests passed + live Ableton output confirmed).
- `task_arm_track` doesn't capture/print a baseline the way `solo_tour`
  does. Unchecked whether it needs to (Arm may not require restoration).
- Clip launching (`SessionView.Track[N].Slot[M]`) — visible in tree dumps,
  never clicked/exercised.
- Device parameters — not started.
- **Blind Spot:** no automation_id anywhere in this project's scheme exposes
  "which track is currently selected."

---

## RELATED PROJECT (Project 2: Ableton via OpenCode + `ableton-mcp-extended`)

A **separate, parallel project**: OpenCode (WSL) talking to
`ableton-mcp-extended` (https://github.com/uisato/ableton-mcp-extended),
an MCP server bridging to a Remote Script inside Ableton over a TCP
socket. It is a **tutorial/curriculum generator**: OpenCode drives Ableton live while teaching a beginner interactively; `take_shot.sh` screenshots each step afterward to build a `walkthrough.md`.

### Knowledge status

Read directly: `opencode-ableton-mcp-setup.md`, `take_shot.sh`, `EVAL_01.md`, `EVAL_02.md`, `EVAL_03.md`. `take_shot.sh` lives at the root of `ableton-gui-grounding`.

### Screenshot orchestration design (sessions 5–6 FINALIZED; session 9 plan written; session 10 Phase 0 COMPLETED; session 11 Phase 1 COMPLETED)

Full reasoning lives in `screenshot_orchestration_analysis.md`.

**Phased implementation plan:**

1. **Phase 0. STATUS: COMPLETED & VERIFIED (session 10).** Added
   `emit_event(type, **fields)` helper to `automate_ableton_task.py`,
   printing single-line JSON prefixed `EVENT:` (`"v": 1`). Wired into both
   `click_by_id()` and `set_checkbox_by_id()`, and wrapped task dispatches
   via `run_task()`. Tested via `test_phase0_events.py` (14/14 passed) and
   verified live against Ableton (`arm_track --live`).
2. **Phase 1. STATUS: COMPLETED & VERIFIED (session 11).** Shipped
   `orchestrate.sh` (repo root) for single-action tasks:
   `arm_track`, `set_tempo`, `probe_toggle`, `probe_solo_transport`,
   `probe_keyboard_activator`, `read_solo_states`. Explicitly excludes
   `solo_tour`. Flow: run automate → capture stdout → parse `EVENT:` lines →
   derive screenshot description → execute `take_shot.sh` with auto `<seq>` counter.
   Tested via `test_orchestrate.py` (11/11 passed) and verified live against
   real Ableton (`./orchestrate.sh LABS/TEST_RUN arm_track --tracks 1`).
3. **Phase 2. STATUS: Next up (Phase 1 complete).** For `solo_tour`, apply Option A:
   add `--task solo_one --tracks N --seconds S`.
4. **Phase 3. STATUS: Pending Phase 1/2.** Introspection & drift detection via
   `--list-tasks`/`--schema`.

---

## LOG (append-only history — compress old entries, don't delete lessons)

**Session 10: Phase 0 implemented and VERIFIED both in sandbox and live on Windows.**

- Implemented `EVENT_SCHEMA_VERSION = 1` and `emit_event(event_type, **fields)` helper in `scritps/automate_ableton_task.py`.
- Integrated `emit_event` into `set_checkbox_by_id()` (`action_start`, `action_result` for `skip`, `dry_run`, `success`, `warn`, `failed`).
- Integrated `emit_event` into `click_by_id()` (`action_start`, `action_result`, and `escalate` transitions across L1, L2, L3).
- Wrapped all CLI task invocations in `main()` with `run_task()` helper to emit `task_start` and `task_done` (success/failed).
- Created `scritps/test_phase0_events.py` containing 14 unit/stub tests covering `emit_event`, `set_checkbox_by_id`, `click_by_id`, `run_task`, and escalation transitions.
- Fixed dummy module import package resolution (`__path__ = []`) for cross-platform stub testing.
- Verification results:
  1. Unit tests: `python .\test_phase0_events.py` -> **14 passed, 0 failed**.
  2. Live acceptance test: `python automate_ableton_task.py --task arm_track --tracks 1 --live` -> emitted clean, valid `EVENT:` JSON lines for `task_start`, `action_start`/`action_result` (Arm & Monitoring=In), and `task_done`.
- **Phase 0 CLOSED.** Next step: Phase 1 (`orchestrate.sh`).

**Session 11: Phase 1 implemented and VERIFIED both in sandbox and live on Windows.**

- Created Phase 1 orchestrator script `orchestrate.sh` at repo root.
- Integrated single-action tasks (`arm_track`, `set_tempo`, `probe_toggle`, `probe_solo_transport`, `probe_keyboard_activator`, `read_solo_states`) while explicitly excluding `solo_tour`.
- Integrated automatic JSON event parsing (`EVENT:`), slugification, auto-sequencing (`.orchestrate_seq`), error capture tagging (`_FAILED`), and output layer separation (`[orchestrator]`).
- Strictly configured Python execution to `python` (Python 3.12).
- Created `scritps/test_orchestrate.py` containing 11 control-flow unit tests covering arg parsing, task validation, seq counter, path passthrough, description derivation, and error branching.
- Verification results:
  1. Unit tests: `python scritps/test_orchestrate.py` -> **11 passed, 0 failed**.
  2. Live acceptance test: `./orchestrate.sh LABS/TEST_RUN arm_track --tracks 1` -> executed live action on Ableton, extracted description `track_1_monitoring_in`, auto-sequenced to `01`, called `take_shot.sh`, and saved `LABS/TEST_RUN/01_track_1_monitoring_in.png` with `NOTE:ALREADY_MAXIMIZED`.
- **Phase 1 CLOSED.** Next step: Phase 2 (Atomic decomposition of `solo_tour`).

---

## User preferences to keep applying

- Python developer — code-level detail welcome, no need to oversimplify.
- Wants documentation/explanations in Markdown.
- Runs every script iteration on their own Windows machine and pastes raw
  terminal output — treat that as ground truth over any theory proposed.
- Standing rule: don't guess about anything unseen — ask for the file.
