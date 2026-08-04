# ableton-gui-grounding

AI-agent-controllable **Ableton Live 12** via Windows UI Automation
(`pywinauto`). Reads and acts on Ableton's live UIA tree directly — no
plugin, no Remote Script, no MIDI bridge — so an agent can see what's
actually on screen and click/type against it like a person would.

## Why this exists

Ableton's Session View is deeply custom-drawn and UI-virtualized:
controls that aren't currently rendered on screen simply don't exist in
the accessibility tree yet, even though their identifiers are well-defined
once they *are* visible. That single fact broke several naive approaches
before this project settled on its current shape.

The core discipline here isn't "can it click a button" (that part is
easy). It's **grounding**: never trusting a captured UI state without
verifying it, and never issuing an action without confirming it actually
landed. Every bug this project has hit so far turned out to be a trust
problem, not a mechanism problem.

## What's here

### Read-only / introspection

| File | Role |
|---|---|
| `dump_ableton_pywinauto.py` | Walks Ableton's UIA tree, writes a timestamped JSON dump. Canonical home of `find_ableton_window()` and `ensure_window_ready()`. |
| `dump_ableton_states.py` | Switches Ableton between named states (Session View, Arrangement View, each Browser panel category) and writes a labeled dump for each. Supports `--states all`. |
| `grep_dump.py` | Pure-stdlib substring search over an existing JSON dump — find controls without touching Ableton again. |

### Automation

| File | Role |
|---|---|
| `automate_ableton_task.py` | Acts on Live — solo/arm tracks, set tempo, run diagnostics. Every control is re-resolved fresh immediately before it's touched. **Phase 0:** emits structured `EVENT:` JSON lines for every action. |
| `keyboard_shortcuts.py` + `.md` | Lookup table for `click_by_id()`'s L2 keyboard escalation tier, sourced from Ableton's official manual. Entries marked `blocked=True` guard against shortcuts that depend on unresolved state. |

### Coordination & screenshot capture

| File | Role |
|---|---|
| `orchestrate.sh` | **Phase 1** coordination layer. Runs one automation task against live Ableton, auto-derives screenshot labels from Phase 0 `EVENT:` lines, auto-increments sequence counters. Handles error branching (takes `_FAILED` screenshots, never retries). |
| `take_shot.sh` | Captures the Ableton Live window as a screenshot, saved into a lab directory. |

### Tests

| File | Role |
|---|---|
| `scritps/test_phase0_events.py` | 14 tests: `emit_event()` shape, checkbox toggle, click-by-id escalation ladder, `run_task()` start/done wrapping. |
| `scritps/test_orchestrate.py` | 14 tests: arg parsing, task rejection, seq counters, error branching, label derivation, drift detection. Uses stub scripts — no Windows/Ableton needed. |

### Reference

| File | Role |
|---|---|
| `AGENTS.md` | Agent instructions (Python version, file roles, automation_id scheme, source-of-truth for confirmed status). |
| `docs/phased_plan.md` | Archived: the phased implementation plan that drove Phases 0–3. |
| `docs/screenshot_orchestration_analysis.md` | Archived: initial analysis of screenshot capture strategies and shortcomings. |

## How it works

Ableton exposes stable, structural `automation_id`s under Session View:

```
SessionView.Track[N].Mixer.Arm                       CheckBox
SessionView.Track[N].Mixer.Activator                 CheckBox (mute)
SessionView.Track[N].Mixer.Solo                      CheckBox
SessionView.Track[N].Mixer.Monitoring.Buttons[0..2]  RadioButton (In/Auto/Off)
SessionView.Track[N].Mixer.Stop                      Button (clip stop)
SessionView.Track[N].Slot[M]                         Group (clip slot)
SessionView.ReturnTrack[N].Mixer.*                   same shape, return tracks
Transport.Tempo                                      Slider
Transport.Play / Transport.Stop
```

Every control lookup is a manual recursive `.children()` walk — not a
`descendants(...)` query. `pywinauto`'s `descendants(auto_id=...)` doesn't
exist, and a single `descendants(control_type=...)` query returns nothing
against Ableton's deeply nested, custom-drawn tree.

### Automation architecture

```
                  +---------------------------+
                  |     orchestrate.sh        |  Phase 1: coordination
                  +-------------+-------------+
                                | calls
                  +-------------v-------------+
                  |  automate_ableton_task.py |  Phase 0: emits EVENT lines
                  |   +---------------------+ |
                  |   | click_by_id()       | |  L1 Mouse -> L2 Keyboard -> L3 Human
                  |   | set_checkbox_by_id()| |  post-click verify + retry
                  |   | emit_event()        | |  structured, versioned, greppable
                  |   +---------------------+ |
                  +-------------+-------------+
                                | stdout (EVENT: lines)
                  +-------------v-------------+
                  |      take_shot.sh         |  labeled screenshots, auto-numbered
                  +---------------------------+
```

Every action is **verified after clicking**. Checkbox controls (Solo, Arm,
Activator) confirm their toggle state changed. Button controls (Play, Stop)
are clicked and trusted with an explicit warning — a documented gap, not a
silent one.

## Architecture phases (completed)

| Phase | Status | Description |
|---|---|---|
| **Phase 0** | Done | Structured `EVENT:` JSON events — `emit_event()` wired into `click_by_id()`, `set_checkbox_by_id()`, `run_task()`. Schema versioned (`"v": 1`). |
| **Phase 1** | Done | `orchestrate.sh` coordination layer. Single-action tasks with auto-labeling, seq counters, error handling (`_FAILED` captures), output tagging. |
| **Phase 2** | Done | Atomic decomposition: `solo_one` (single-track solo→play→stop→unsolo cycle) + `solo_tour` refactored as thin loop. Per-track screenshot granularity via orchestrator. |
| **Phase 3** | Done | Introspection / drift detection: `--list-tasks` JSON with schema version + task metadata. Orchestrator validates once per lab run before any action. |

### Phase 2 open question

`solo_one` is internally multi-step (solo click → play click → stop click
→ unsolo click). It was intentionally kept at **per-track** granularity,
not split further into individual click steps, because:

- `Transport.Play` and `Transport.Stop` have `verify=None` — no structural
  signal to confirm the action landed.
- Restoring state across sub-steps (solo off, play stopped) would be
  fragile without per-step verification.

If per-click screenshot granularity is ever needed, `solo_one` should be
split into `solo_click`, `play_click`, `stop_click`, and `unsolo_click`.
That decision is deferred — solve it when the use case appears.

## Task catalog

All 8 tasks recognized by the automation script:

```
arm_track                Arm track + set monitor to In          atomic
solo_one                 Solo→play→stop→unsolo one track        atomic
solo_tour                Solo tour across N tracks (loop)       multi-step
set_tempo                Set session tempo to BPM               atomic
probe_toggle             Diagnostic: toggle state reading       atomic
probe_solo_transport     Diagnostic: solo + transport           atomic
probe_keyboard_activator Diagnostic: keyboard shortcut path     atomic
read_solo_states         Read solo states of tracks             atomic
```

`--list-tasks` outputs the full registry as JSON with schema version:

```bash
python.exe scritps/automate_ableton_task.py --list-tasks
# {"schema_version": 1, "tasks": {...}}
```

## Requirements

- **Windows 10/11** with Ableton Live 12+ running and a project open
- **Python 3.12** (`python`, not `python3` — the latter is a stale 3.10)
- `pip install pywinauto`
- WSL: `python.exe` is the Windows Python (cross-call via WSL interop)

The test suite (`test_phase0_events.py`, `test_orchestrate.py`) runs on
Linux/WSL without pywinauto or Ableton — they use stub/fake modules.

## Usage

```bash
# Read-only tree dump
python dump_ableton_pywinauto.py --label baseline

# Sweep every known state in one run
python dump_ableton_states.py --states all

# Search a prior dump
python grep_dump.py dumps/ableton_uia_..._session.json solo

# Discover what track indices exist right now
python automate_ableton_task.py --list-tracks

# List all tasks with metadata (no Ableton needed)
python automate_ableton_task.py --list-tasks

# Safe: prints the plan, clicks nothing
python automate_ableton_task.py --task arm_track --tracks 1

# Actually perform it
python automate_ableton_task.py --task arm_track --tracks 1 --live

# Solo one track for 3 seconds (standalone)
python automate_ableton_task.py --task solo_one --tracks 2 --seconds 3 --live

# Solo tour across tracks 0,1,2
python automate_ableton_task.py --task solo_tour --tracks 0 1 2 --seconds 2 --live
```

### Orchestrator

```bash
# Single action: arm track + screenshot
./orchestrate.sh LABS/experiment arm_track --tracks 0

# solo_one loop: one screenshot per track (auto-numbered 01, 02, 03)
./orchestrate.sh LABS/experiment solo_one --tracks 0 1 2 --seconds 2

# Drift check runs automatically before any action — aborts on mismatch
```

### Tests

```bash
# 14 tests: event shapes, checkbox/click-by-id, escalation ladder
python scritps/test_phase0_events.py

# 14 tests: arg parsing, task rejection, seq counters, error branching, drift
python scritps/test_orchestrate.py
```

## Lessons learned

- **UI virtualization.** A backgrounded or non-maximized window can expose
  ~60 controls instead of ~201, with no error — just a silently incomplete
  tree. Fixed by `ensure_window_ready()` before every read or action.
- **Stale references.** Holding a resolved control across a
  click → wait → click sequence produced a wrong read in testing. Every
  control is now re-resolved fresh, immediately before each touch.
- **Trusting an unverified baseline is its own bug class.** A track stayed
  soloed after a "restore" step — not because the click or the read was
  unreliable, but because the script trusted a snapshot of state captured
  at the start. The fix: **print/distrust captured baselines, verify after
  every state-changing action**.
- **A no-op looks identical to a working click.** An early test of Browser
  switching "passed" because the target category happened to already be
  selected — proving nothing. Always re-run transition tests from a
  genuinely different starting state.
- **JSON events beat parsing stdout wording.** Free-form `print()` lines
  drift over time and depend on exact wording. Structured `EVENT:` lines
  with a version field let the orchestrator consume only the fields it
  recognizes, ignore the rest, and detect schema drift before it silently
  breaks.

## Status

| Capability | Verified |
|---|---|
| Session ↔ Arrangement View switching | Live |
| All 6 Browser panel categories | Live |
| Solo/arm/mute checkbox toggle (post-click verify) | Live |
| Tempo control (double-click + type) | Live |
| Transport Play/Stop (no verify, documented gap) | Live |
| Keyboard shortcut L2 escalation (F1–F8 on Activator) | Live |
| Orchestrator + auto-labeled screenshots + drift check | Live |
| 28/28 tests (stub-based, no Ableton needed) | CI-safe |
| Clip launching (SessionView.Track[N].Slot[M]) | Not yet exercised |
| Device parameter read/write | Not yet |
| Browser item selection / plugin loading | Not yet |

## A note on scope

This project deliberately stays at the UI Automation layer — no Remote
Script, no MIDI bridge, no plugin install inside Ableton. That's a
tradeoff: it can't reach into device-internal parameter values the way a
Live Object Model-based integration can, but it has no moving parts inside
Ableton itself and works against exactly what's on screen, which makes the
verify-after-every-action model straightforward to apply everywhere.
