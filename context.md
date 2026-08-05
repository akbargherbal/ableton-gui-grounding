# Context Handoff: `ableton-gui-grounding` V2 Audit

This file is written by the AI Assistant for its future self, to restore session context across stateless sessions. Keep it actively maintained with key insights, decisions, and enduring context, while aggressively pruning low-value detail. Record only what will materially help a future session; the user's own testing/observations are ground truth over any theory the AI Assistant proposes.

---

### Project Goal

An AI agent teaches a student Ableton Live 12 hands-on. Every action taken on the student's behalf must be **grounded**: verified against the actual UI state (not assumed) and shown to the student step-by-step via screenshots (not just a before/after outcome).

This is the standard every audit finding in this file is judged against ("does this serve grounded, step-by-step teaching"), rather than DAW/Ableton feature-completeness for its own sake.

---

### Audit Scope — Active vs. Archived Docs

To prevent documentation confusion across sessions:

**Active Docs in Scope:**

- `context.md` (this file — single source of handoff truth)
- `docs/v2_observations.md` (running verification log for the 8-item audit agenda)
- `docs/ableton_ai_educational_risk_framework.md` (secondary — pre-implementation design doc; code wins on conflict)
- `docs/opencode-ableton-mcp-setup.md` (secondary — V1 setup & MCP architecture reference)

**Archived Docs (`docs/archived/*`):**

- `docs/archived/phased_plan.md`
- `docs/archived/screenshot_orchestration_analysis.md`

_Archived docs are strictly out of scope. Do not read, cite, or treat them as current for audit decisions._

---

### Goal of THIS Audit

V2 adds `scritps/` (`automate_ableton_task.py`, `orchestrate.sh`, `take_shot.sh` v6, tests) on top of the V1 stack (MCP server via `ableton-mcp-extended` + OpenCode + `take_shot.sh`). V1's known weakness: the student saw the _outcome_ of an action, not the _steps_ that produced it.

This audit's job, before writing `AGENTS.md`, is to:

1. Inventory every tool/capability actually present in V2 code.
2. Map how tools chain together (and where they break).
3. Identify low-effort gaps to close.
4. Codify routing policies between UIA-direct and MCP paths in `AGENTS.md`.

---

### Two Parallel, Non-Bridged Control Paths

1. **UIA-direct** (this repo): `automate_ableton_task.py` executed via `orchestrate.sh`, screenshots via `take_shot.sh`. Driven from WSL via `python.exe` interop. Fully grounded via post-click UI verification.
2. **MCP** (`docs/opencode-ableton-mcp-setup.md`): OpenCode → `AbletonMCP` (`ableton-mcp-extended`) → TCP socket → Ableton Remote Script.

**Key Structural Audit Finding on MCP Verification:**
Code inspection of `uisato/ableton-mcp-extended` (`AbletonMCP_Remote_Script/__init__.py`: `_set_device_parameter`) confirmed that **MCP does not read back parameter values after a write**. It returns a calculated target value (`clamped`), not the live state re-read from Ableton. Furthermore, `_resolve_device` uses `self._song.tracks[index]`, indexing folded/hidden group tracks in the Live Object Model, which can diverge from the visible 0-based Session View track index.

---

### File Status Table

| File                                                        | Role                                                                                                                                                                                                          | Status                                                                                                               |
| :---------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------------------------------------------------------------------------------------------------------------- |
| `dump_ableton_pywinauto.py`                                 | Read-only UIA tree dump. Canonical `find_ableton_window()` & `ensure_window_ready()`.                                                                                                                         | Mature, imported by all automation tools.                                                                            |
| `dump_ableton_states.py`                                    | Session/Arrangement view switching + Browser category switching (all 6 categories verified in `scritps/dumps/`).                                                                                              | Mature. All 6 browser categories verified live.                                                                      |
| `grep_dump.py`                                              | Stdlib substring search over saved JSON tree dump.                                                                                                                                                            | Solid, zero external dependencies.                                                                                   |
| `automate_ableton_task.py`                                  | UIA Action engine (8 tasks). `resolve()` never caches controls. `click_by_id()` = Mouse→Keyboard→Human ladder. `set_checkbox_by_id()` = click→re-read→retry→raise. Emits structured `EVENT:` JSON per action. | Solid engine. `--list-tasks`/`--list-tracks` work offline without Ableton running.                                   |
| `keyboard_shortcuts.py`                                     | Sourced shortcut registry with `blocked` safety flags.                                                                                                                                                        | Built, but currently unwired to `click_by_id()` call sites (L2 keyboard escalation unexercised in production tasks). |
| `orchestrate.sh`                                            | Coordination layer for single live action + 1 screenshot (`SINGLE_ACTION_TASKS`). Handles drift checking via `--list-tasks`. Loops per-track on `solo_one`.                                                   | Mature front door.                                                                                                   |
| `take_shot.sh` (v6)                                         | WSL→PowerShell screen capture. Auto restore/focus/maximize. Standalone-capable CLI (`<lab_dir> <seq> <description>`).                                                                                         | Mature.                                                                                                              |
| Test suite (`test_phase0_events.py`, `test_orchestrate.py`) | Stub-based test suite (28/28 passing).                                                                                                                                                                        | Verified live in Linux sandbox.                                                                                      |

---

### Key Findings & Decisions Made

1. **Grounding Discipline is Paramount:** Letting an agent fall back to MCP on unverified faith (e.g., accepting `{"status": "success"}` without post-write verification) creates false-positive screenshots, violating the core project goal.
2. **`solo_tour` Screenshot Behavior (Agenda #1 - Verified Live):** Direct bypass of `orchestrate.sh` runs `solo_tour` without capturing screenshots (`take_shot.sh` is only invoked inside `orchestrate.sh`). State restoration on tracks 0 & 1 was verified clean.
3. **Teaching Scenario Tracing (Agenda #2 - Completed):**
   - _Scenario A (Arm track + Monitor In):_ Fully supported on UIA path, produces 1 final screenshot.
   - _Scenario B (Browse Sounds → Drag Kick into track):_ Hard dead end on UIA. Browser item selection/drag-and-drop does not exist because `DataItem` nodes lack `automation_id` (empty strings) and controls are virtualized.
   - _Scenario C (Solo tour track comparison):_ Supported via `orchestrate.sh ... solo_one`, but direct CLI `solo_tour` is a trap (runs without taking screenshots).
4. **Historical Doc References Purged:** In-code citations of retired docs were cleaned across 8 files; test suite remains 28/28 passing.

---

### Working Rules with User (Binding)

1. **Do not ask the user to recall code implementation details.** Read code directly, state claims, and offer live commands for verification.
2. **Domain expertise assumption:** Keep explanations accessible without assuming advanced DAW or music production theory knowledge.

---

### Agenda Status & Next Session Items

**Completed:**

- [x] Item 1: Verify `solo_tour` screenshot behavior live.
- [x] Item 2: Trace 3 teaching scenarios through code (identified Scenario B dead end & Scenario C naming trap).

**Open Agenda (Ordered Easiest → Hardest):**

1. **Decide Scope for v1 `AGENTS.md` (Item #3):** Decide whether UIA gaps (browser item selection, clip launching, device parameters) are explicitly marked _"not supported in v1"_ or routed to MCP with a required manual read-verify step.
2. **Decide Screenshot-Granularity Policy (Item #4):** Accept current per-track/per-task granularity or decide to implement per-sub-click screenshots.
3. **Wire `keyboard_shortcuts.py` into `click_by_id()` Call Sites (Item #5):** Pass `load_shortcut()` at unblocked call sites so L2 of the escalation ladder is active in production tasks.
4. **Baseline-Test OpenCode Routing (Item #6):** Prompt OpenCode with a scenario without `AGENTS.md` to establish baseline tool selection behavior (orchestrator vs raw Python vs MCP).
5. **(Conditional) Implement Per-Click Screenshots (Item #7):** If required by Item #4, parse the `EVENT:` stream to take screenshots after intermediate clicks.
6. **Define UIA-vs-MCP Arbitration Policy & Draft `AGENTS.md` (Item #8):** Codify routing rules between UIA and MCP paths based on verified post-action grounding capabilities.
