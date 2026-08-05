# Item #8: UIA-vs-MCP Arbitration Policy — Implementation Plan

## Goal

Finalize the routing rules in `AGENTS.md` so an AI agent (with zero prior knowledge of this project) makes the correct UIA-direct vs MCP decision on the first try, for every teaching scenario the system supports today. The baseline test (`LIVE_TEST/BASELINE_SESSION_session-ses_02cd.md`) proved the rules are load-bearing, not cosmetic.

## Background (where we stand today)

### What's already in AGENTS.md

```markdown
## Control paths
- **UIA-direct** (primary): `automate_ableton_task.py` → `orchestrate.sh` → `take_shot.sh`.
- **MCP**: OpenCode → `ableton-mcp-extended` → TCP → Ableton Remote Script.
- Don't mix paths mid-task without a reason.
```

This is correct as a structural summary but lacks two things:
1. **When** to choose which path (decision logic, not just architecture)
2. **How** to combine them safely when a task spans both worlds

### Findings that inform this item

| Finding | Source | Implication for AGENTS.md |
|---------|--------|---------------------------|
| **#3: MCP writes are unverified** | `v2_observations.md` §3 — `_set_device_parameter` returns calculated target, not re-read. `_resolve_device` can misindex when groups are folded. | Any MCP write path must include an explicit read-back step. Codify that. |
| **#5: Agent defaults to MCP** | Baseline test — agent tried `get_session_info` → `get_track_info` first, never explored UIA path without nudging. | `AGENTS.md` must state that UIA-direct (`orchestrate.sh`) is the **default** path; MCP is the fallback/exotic path. |
| **Scenario B: Browser drag-and-drop** | Code-trace confirmed empty `automation_id` on DataItem nodes + virtualized list → UIA can't browse items. MCP **can** browse but loads have no verification. | Browser item loading via MCP is allowed but must be paired with a post-load UIA read-back (does the device/track actually show the loaded item?). |
| **Item #5: keyboard shortcuts wired** | `transport_play_stop` → `{VK_SPACE}` now works in `task_solo_one`. | UIA can now do transport control. Less reason to route to MCP for play/stop. |
| **Item #7: per-click screenshots** | Every `action_start`/`action_result` now gets its own screenshot. | UIA-direct path now produces step-level visual evidence. MCP has no screenshot capability. Teaching tasks should prefer UIA for visual artifacts. |

### MCP capabilities: what's safe vs. what needs verification

| MCP operation | Risk profile | Rule |
|---------------|-------------|------|
| `get_session_info`, `get_track_info`, `get_arrangement_info` | Read-only → safe | Trust as-is |
| `get_device_parameters`, `get_drum_pad_info`, `get_chain_info` | Read-only → safe | Trust as-is |
| `get_browser_tree`, `get_browser_items_at_path` | Read-only → safe | Trust as-is |
| `set_track_volume`, `set_track_panning` | Write — unverified | Must read back (`get_track_volume`) and compare |
| `set_device_parameter` | Write — unverified + known misindexing risk | Must read back (`get_device_parameters`) and compare. Warn if group tracks folded. |
| `load_instrument_or_effect`, `load_drum_kit`, `load_external_plugin` | Write — unverified load | Must UIA-verify post-load (check device appears in track info) |
| `set_tempo` | Write — likely safe (simple LOM property) | Verify with `get_session_info` read-back |
| `start_playback`, `stop_playback` | Action — transport state is observable | Verify with arrangement/session info read-back |
| `create_clip`, `create_midi_track`, `delete_track` | Structural mutation | Must read back from session/arrangement info to confirm |
| `set_track_name`, `set_clip_name` | Trivial LOM write | Verify with `get_track_info` read-back |

### What UIA-direct handles today

`SINGLE_ACTION_TASKS`: `arm_track`, `set_tempo`, `probe_toggle`, `probe_solo_transport`, `probe_keyboard_activator`, `read_solo_states`, `solo_one`

Plus `solo_tour` (excluded from orchestrator, direct CLI only, no screenshots).

### What MCP handles that UIA cannot

- Device parameter read/write (EQ, compressor, reverb values)
- Device loading/browsing (instruments, effects, drum kits, plugins)
- Clip creation and note editing (MIDI)
- Track creation/deletion
- Arrangement clip placement
- Scene management

### What NEITHER handles today

- Browser drag-and-drop placement onto track slots (UIA: no stable target; MCP: not verified to work)
- Clip launching in Session View (listed as "Not yet" in README)

---

## Decisions to make (the actual work)

### Decision 1: Default path ordering

**Current**: `AGENTS.md` says UIA-direct is "primary" but doesn't make that actionable.

**Options**:
- **(A) UIA-first**: For any task whose verb appears in `SINGLE_ACTION_TASKS`, use `orchestrate.sh`. Fall back to MCP only if the task fails or isn't in the list.
- **(B) Declarative matrix**: A table in `AGENTS.md` mapping teaching verbs → exact path (tool + command). No decision-theater — just follow the table.

**Recommend**: **(A)** with a lightweight table. A full matrix overfits today's state and rots. A simple "check `SINGLE_ACTION_TASKS` first" rule + a small table for the 2-3 common exceptions (device adjustments, browser loading) is maintainable.

### Decision 2: MCP write verification protocol

**Current**: `context.md` Finding #3 states MCP writes need read-back. Not yet codified in `AGENTS.md`.

**What to codify**:
1. After any MCP write, call the corresponding read tool and compare.
2. If mismatch → retry once (MCP timing), then escalate to human instructions.
3. If group tracks are folded → warn the student before relying on MCP device parameter writes (misindexing risk).

### Decision 3: Browser loading flow (MCP load → UIA verify)

When a teaching scenario requires loading a device/instrument:
1. MCP: `get_browser_tree` → `get_browser_items_at_path` → `load_instrument_or_effect`
2. UIA: `get_track_info` (or `get_device_parameters`) to verify the device actually appeared
3. Screenshot: `take_shot.sh` directly (not via orchestrate, since it's not a single-action task)

This is the first "mixed path" flow codified in `AGENTS.md`. The rule "don't mix paths mid-task" needs an exception for this.

### Decision 4: Explicitly unsupported — don't attempt

Scenarios the agent should recognize as out-of-scope and tell the student are unsupported:
- Browser drag-and-drop (neither path works)
- Session clip launching in teaching flow (unreliable)
- Anything requiring coordinate-based `pywinauto` clicking (anti-pattern, never worked)

---

## Proposed AGENTS.md additions

Add a new section `## Routing` between `## Docs` and `## Control paths`, containing:

```markdown
## Routing — which tool for which task

### Default path: UIA-direct (use this first)

For any task listed in the `SINGLE_ACTION_TASKS` array in `orchestrate.sh`, use the
orchestrator. That means: **don't** reach for MCP tools — run `orchestrate.sh` with the
task name. It handles the action **and** the screenshot in one command.

Today's supported tasks: `arm_track`, `set_tempo`, `probe_toggle`, `probe_solo_transport`,
`probe_keyboard_activator`, `read_solo_states`, `solo_one`.

These are the actions the engine can **verify** against live Ableton UI state — this is
"grounding" as defined by the project. MCP cannot verify these actions.

### When to use MCP instead

Only when UIA-direct doesn't cover the action. Today that means:

| Scenario               | MCP tools to use                  | Post-step                  |
|------------------------|-----------------------------------|----------------------------|
| Device parameter tweak | `set_device_parameter`            | Read back immediately, compare |
| Load instrument/effect | `load_instrument_or_effect`       | UIA-verify device appeared + `take_shot.sh` |
| Browse sounds/instruments | `get_browser_tree`, `get_browser_items_at_path` | Read-only, safe to trust |
| Create track           | `create_midi_track`               | `get_track_info` to confirm |
| Create clip / add notes | `create_clip`, `add_notes_to_clip` | Read back clip state |
| Adjust mixer level      | `set_track_volume`                | `get_track_volume` and compare |
| Transport (read-only)   | `get_session_info`                | Safe to trust |

### MCP write verification rule

**Every MCP write must be followed by a read of the same property.** Do not report an
MCP write result as "confirmed" until the read-back value matches the intended value.
If it doesn't match, retry once, then escalate to Level 4 (human instructions).

### Cross-path operations (mixing UIA + MCP)

The rule "don't mix paths" has one exception: **browser loading**. When loading a device
or instrument, the load itself happens via MCP (UIA can't browse), but the verification
and screenshot must happen via UIA tools.

Flow: MCP load → `get_track_info` (verify) → `take_shot.sh` (capture).

### Explicitly unsupported — do not attempt

- Browser drag-and-drop onto a track slot. No working implementation on either path.
  Tell the student to drag manually, then capture a screenshot showing the result.
- Coordinate-based `pywinauto` clicking for controls with no `automation_id`.
- Session View clip launching as an automated teaching step.
```

### Also update the Control paths section

The current "Don't mix paths mid-task without a reason" should become:

```markdown
## Control paths

- **UIA-direct** (primary): `automate_ableton_task.py` → `orchestrate.sh` → `take_shot.sh`.
  Handles all `SINGLE_ACTION_TASKS`. Always produces screenshots.
- **MCP**: OpenCode → `ableton-mcp-extended` → TCP → Ableton Remote Script.
  Handles device parameters, browsing, track/clip manipulation. NEVER produces screenshots
  on its own — the student can't see what happened.

### Choosing a path

1. Is the action in `SINGLE_ACTION_TASKS`? → `orchestrate.sh <task>`.
2. Is it a device/browser/clip operation? → MCP, with read-back (see Routing section).
3. Is it a loaded-device screenshot? → `take_shot.sh` directly.
4. Is it browser drag-and-drop or session clip launching? → Not supported. Tell the student.
```

---

## Verification plan

Once the `AGENTS.md` changes are written:

1. **Code review**: Does every MCP tool available in the session appear in the risk table? (Check `list_mcp_resources` + grep `AGENTS.md` for coverage.)

2. **Dry-run trace**: Pick 2-3 teaching scenarios (from Finding #2) and walk through the decision logic:
   - "Arm track 1" → in `SINGLE_ACTION_TASKS` → `orchestrate.sh LABS/x arm_track --tracks 1` ✓
   - "Set EQ8 frequency to 500Hz on track 1" → not in `SINGLE_ACTION_TASKS` → MCP `set_device_parameter` → read back → `take_shot.sh` ✓
   - "Load a Grand Piano instrument" → MCP `load_instrument_or_effect` → `get_track_info` verify → `take_shot.sh` ✓

3. **Gap check**: Are there MCP tools in the `ableton-mcp-extended` surface that aren't mentioned in the routing rules? If so, the agent may reach for them without guidance. Either add them to the table or add a catch-all rule: "For any MCP tool not listed above, treat as unverified write — read back before confirming."

4. **Update `context.md`**: Mark item #8 done, strike from Open section. Update `File Status Table` if `AGENTS.md` gained significant scope.

---

## Sequence

1. Read current `AGENTS.md` in full (already loaded above).
2. Write the new Routing section into `AGENTS.md`.
3. Update the Control paths section.
4. Verify with the 3 dry-run traces above.
5. Mark item #8 done in `context.md` and `v2_observations.md`.
