# Context Handoff: `ableton-gui-grounding` V2 Audit

This file tracks **current project state** across sessions — what's been verified, what's decided, what's still open. Standing rules that don't change session-to-session (environment setup, audience assumptions, architecture/routing policy) now live in **`AGENTS.md`** — read that first, this file second.

Keep this file actively maintained: update the agenda checklist and findings as work progresses, prune stale detail. The user's own testing/observations are ground truth over any theory proposed here.

---

### Project Goal

An AI agent teaches a student Ableton Live 12 hands-on. Every action taken on the student's behalf must be **grounded**: verified against the actual UI state (not assumed) and shown to the student step-by-step via screenshots (not just a before/after outcome).

This is the standard every audit finding in this file is judged against ("does this serve grounded, step-by-step teaching"), rather than DAW/Ableton feature-completeness for its own sake.

---

### Known Issues Worth Examining

_These are open risks surfaced by code inspection and live testing, not yet fully resolved by process or tooling. Full evidence for each is in "Findings So Far" below._

1. **MCP writes report success without proof.** `_set_device_parameter` in `uisato/ableton-mcp-extended` returns a calculated target value, not a value re-read from Ableton after the write — so an MCP "success" response isn't actually evidence the change happened. `_resolve_device` also indexes tracks in a way that can silently point at the wrong track when group tracks are folded/hidden. Worth treating any MCP-path result as unconfirmed until a separate read-back step is added and exercised — this is currently a gap, not yet a solved problem.
2. **`solo_tour` vs `orchestrate.sh ... solo_one` naming is confusing and currently unsafe.** They sound like two ways to do the same thing, but only running through `orchestrate.sh` produces screenshots — calling `solo_tour` directly silently skips them. Worth either renaming one of them, adding a guard, or documenting this loudly somewhere more visible than a note, since it's an easy trap for a future session (or a CLI agent without full context) to fall into.
3. **Browser drag-and-drop has no working path on UIA.** `DataItem` nodes have empty `automation_id` values and the list is virtualized, so there's currently no reliable UIA target for "browse sounds → drag into track." Not clear yet whether this is worth a different automation technique (e.g. coordinate-based drag, or an MCP-assisted path with read-back) or should just stay a documented limitation of the teaching flow. Flagged here as something to revisit rather than a closed dead end.

---

### Goal of THIS Audit

V2 adds `scritps/` (`automate_ableton_task.py`, `orchestrate.sh`, `take_shot.sh` v6, tests) on top of the V1 stack (MCP server via `ableton-mcp-extended` + OpenCode + `take_shot.sh`). V1's known weakness: the student saw the _outcome_ of an action, not the _steps_ that produced it.

This audit's job, before finalizing `AGENTS.md`, is to:

1. Inventory every tool/capability actually present in V2 code.
2. Map how tools chain together (and where they break).
3. Identify low-effort gaps to close.
4. Codify routing policies between UIA-direct and MCP paths in `AGENTS.md`.

---

### Docs in Scope for This Audit

- `context.md` (this file)
- `docs/v2_observations.md` (verification log for the 8-item agenda)
- `docs/ableton_ai_educational_risk_framework.md` (secondary — design doc; code wins on conflict)
- `docs/opencode-ableton-mcp-setup.md` (secondary — V1 setup & MCP architecture reference)

`docs/archived/*` is out of scope — do not read, cite, or treat as current.

---

### File Status Table

| File                                                        | Role                                                                                                                                                                                                          | Status                                                                                                               |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `dump_ableton_pywinauto.py`                                 | Read-only UIA tree dump. Canonical `find_ableton_window()` & `ensure_window_ready()`.                                                                                                                         | Mature, imported by all automation tools.                                                                            |
| `dump_ableton_states.py`                                    | Session/Arrangement view switching + Browser category switching.                                                                                                                                              | Mature. All 6 browser categories verified live.                                                                      |
| `grep_dump.py`                                              | Stdlib substring search over saved JSON tree dump.                                                                                                                                                            | Solid, zero external dependencies.                                                                                   |
| `automate_ableton_task.py`                                  | UIA Action engine (8 tasks). `resolve()` never caches controls. `click_by_id()` = Mouse→Keyboard→Human ladder. `set_checkbox_by_id()` = click→re-read→retry→raise. Emits structured `EVENT:` JSON per action. | Solid engine. `--list-tasks`/`--list-tracks` work offline without Ableton running.                                   |
| `keyboard_shortcuts.py`                                     | Sourced shortcut registry with `blocked` safety flags.                                                                                                                                                        | Built, but currently unwired to `click_by_id()` call sites (L2 keyboard escalation unexercised in production tasks). |
| `orchestrate.sh`                                            | Coordination layer for single live action + 1 screenshot (`SINGLE_ACTION_TASKS`). Handles drift checking via `--list-tasks`. Loops per-track on `solo_one`.                                                   | Mature front door.                                                                                                   |
| `take_shot.sh` (v6)                                         | WSL→PowerShell screen capture. Auto restore/focus/maximize. Standalone-capable CLI (`<lab_dir> <seq> <description>`).                                                                                         | Mature.                                                                                                              |
| Test suite (`test_phase0_events.py`, `test_orchestrate.py`) | Stub-based test suite (28/28 passing).                                                                                                                                                                        | Verified live in Linux sandbox.                                                                                      |

---

### Findings So Far

_(`AGENTS.md` states the resulting rules tersely. This section is where the full reasoning, evidence, and code-level detail behind each rule lives — consult this before revising or arguing with anything in `AGENTS.md`.)_

1. **`solo_tour` screenshot behavior (Agenda #1 — verified live):** Direct bypass of `orchestrate.sh` runs `solo_tour` without capturing screenshots — `take_shot.sh` is only ever invoked _from inside_ `orchestrate.sh`; `solo_tour` called on its own has no screenshot step in its code path at all. State restoration on tracks 0 & 1 (the two tracks exercised in the live test) was verified clean afterward — no solo state left engaged. This is a **naming trap**: `solo_tour` and `orchestrate.sh ... solo_one` sound like the same feature but only the latter is grounded/screenshotted. → codified as a gotcha in `AGENTS.md`.
2. **Teaching scenario tracing (Agenda #2 — completed):** Three realistic teaching moments were traced end-to-end through the actual code paths (not just theorized) to see whether each is actually groundable today.
   - _Scenario A (Arm track + Monitor In):_ Fully supported on the UIA path. Produces exactly 1 final screenshot under current per-task granularity (see Agenda #4 decision below re: this being too coarse).
   - _Scenario B (Browse Sounds → Drag Kick into track):_ Hard dead end on UIA, not a gap that more engineering effort closes cheaply. Root cause: `DataItem` nodes in the Ableton Browser tree have empty-string `automation_id` values, and the list itself is virtualized (only visible rows exist in the UI tree at any time), so there's no stable UIA target to select or drag. → codified as a known limitation in `AGENTS.md` so future sessions don't re-attempt it from scratch.
   - _Scenario C (Solo tour track comparison):_ Supported, but only via `orchestrate.sh ... solo_one` looped per-track — this is the correct screenshotted way to do a solo comparison; direct CLI `solo_tour` is the naming trap from Finding 1, not an alternative way to do the same thing.
3. **MCP verification gap (feeds Agenda #3/#8):** Code inspection of `uisato/ableton-mcp-extended`'s `AbletonMCP_Remote_Script/__init__.py`, specifically `_set_device_parameter`, confirmed MCP does **not** read back the live parameter value after writing it — the value returned to the caller (`clamped`) is a calculated target computed before the write, not a re-read of Ableton's actual state after. Separately, `_resolve_device` resolves tracks via `self._song.tracks[index]` in the Live Object Model directly; this index can diverge from the visible 0-based Session View track index whenever group tracks are folded or hidden, because the LOM includes tracks the UI is currently not displaying. Both issues mean an MCP "success" response is not trustworthy as grounding evidence on its own. → codified as the hard MCP routing rule in `AGENTS.md`: never report an MCP write as verified without an explicit post-write read-back.
4. **Historical doc references purged:** In-code citations of retired docs (pointing at `docs/archived/*` or earlier doc names) were cleaned across 8 files as part of this audit's cleanup pass; test suite reran and remains 28/28 passing after the change, confirming no functional dependency on the removed references.

---

### Agenda Status

**Completed:**

- [x] Item 1: Verify `solo_tour` screenshot behavior live.
- [x] Item 2: Trace 3 teaching scenarios through code.
- [x] Item 3: Decide v1 `AGENTS.md` scope for UIA gaps. **Decision:** do not blindly fall back to MCP. Any MCP use for device params/browser loading must be paired with an explicit post-write read-back. Full detail in `docs/v2_observations.md` §3.
- [x] Item 4: Decide screenshot-granularity policy. **Decision:** move to per-sub-click granularity (not current per-task). `orchestrate.sh`'s `run_one_task()` today takes one screenshot per task, labeled from only the _last_ `EVENT:` line — confirmed this loses intermediate state on multi-substep tasks (e.g. `arm_track`'s arm-checkbox step vs its Monitor→In step). The per-substep `action_start`/`action_result` events already exist in `automate_ableton_task.py`'s `EVENT:` stream, so this is an `orchestrate.sh`-side (consumer) change, not an engine change. Item #7 is a committed implementation task, sequenced after #5 and #6 per user's explicit request to keep agenda order. Full detail in `docs/v2_observations.md` §4.

**Open (Ordered Easiest → Hardest):**

5. **Wire `keyboard_shortcuts.py` into `click_by_id()` Call Sites (Item #5):** Pass `load_shortcut()` at unblocked call sites so L2 of the escalation ladder is active in production tasks.
6. **Baseline-Test OpenCode Routing (Item #6):** Prompt OpenCode with a scenario without `AGENTS.md` present to establish baseline tool selection behavior (orchestrator vs raw Python vs MCP), for comparison now that `AGENTS.md` exists.
7. **Implement Per-Click Screenshots (Item #7):** Modify `orchestrate.sh` to parse the `EVENT:` stream and take a screenshot after each `action_start`/`action_result`, not just once per task. Needs: a `seq` counter that increments per sub-step (not per task), and `desc` derivation that keys off each event as it fires rather than grepping the last labeled line.
8. **Finalize UIA-vs-MCP Arbitration Policy in `AGENTS.md` (Item #8):** Baseline routing rule is already codified (see `AGENTS.md`); this item is to revisit and refine it once #5–#7 land and more MCP edge cases are observed.
