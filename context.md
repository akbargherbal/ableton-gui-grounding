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

**Constraint:** the AI Assistant has no direct access to Ableton/Windows — Linux sandbox only. All live verification is done by the user; pasted terminal/screenshot output is ground truth. Audit is expected to span 2–3 sessions (long back-and-forth per verification), hence this file.

---

### Goal of THIS Audit

V2 adds `scritps/` (`automate_ableton_task.py`, `orchestrate.sh`, `take_shot.sh` v6, tests) on top of the V1 stack (MCP server via `ableton-mcp-extended` + OpenCode + `take_shot.sh`). V1's known weakness: the student saw the _outcome_ of an action, not the _steps_ that produced it.

This audit's job, before writing `AGENTS.md`, is to:

1. Inventory every tool/capability actually present in V2 code.
2. Map how tools chain together (and where they break).
3. Identify low-effort gaps to close.
4. Codify routing policies between UIA-direct and MCP paths in `AGENTS.md`.

---

### File Status Table

| File | Role | Status |
| --- | --- | --- |
| `dump_ableton_pywinauto.py` | Read-only UIA tree dump. Canonical `find_ableton_window()` & `ensure_window_ready()`. | Mature, imported by all automation tools. |
| `dump_ableton_states.py` | Session/Arrangement view switching + Browser category switching. | Mature. All 6 browser categories verified live. |
| `grep_dump.py` | Stdlib substring search over saved JSON tree dump. | Solid, zero external dependencies. |
| `automate_ableton_task.py` | UIA Action engine (8 tasks). `resolve()` never caches controls. `click_by_id()` = Mouse→Keyboard→Human ladder. `set_checkbox_by_id()` = click→re-read→retry→raise. Emits structured `EVENT:` JSON per action. | Solid engine. `--list-tasks`/`--list-tracks` work offline without Ableton running. |
| `keyboard_shortcuts.py` | Sourced shortcut registry with `blocked` safety flags. | Wired to `click_by_id()` call sites (Transport.Play/Stop via `load_shortcut`). |
| `orchestrate.sh` | Coordination layer for single live action + 1 screenshot (`SINGLE_ACTION_TASKS`). Handles drift checking via `--list-tasks`. Loops per-track on `solo_one`. | Mature front door. |
| `take_shot.sh` (v6) | WSL→PowerShell screen capture. Auto restore/focus/maximize. Standalone-capable CLI (`<lab_dir> <seq> <description>`). | Mature. |
| Test suite (`test_phase0_events.py`, `test_orchestrate.py`) | Stub-based test suite (28/28 passing). | Verified live in Linux sandbox. |

---

### Findings So Far

1. **`solo_tour` screenshot behavior (Agenda #1 — verified live):** Direct bypass of `orchestrate.sh` runs `solo_tour` without capturing screenshots — `take_shot.sh` is only ever invoked _from inside_ `orchestrate.sh`; `solo_tour` called on its own has no screenshot step in its code path at all. State restoration on tracks 0 & 1 (the two tracks exercised in the live test) was verified clean afterward — no solo state left engaged. This is a **naming trap**: `solo_tour` and `orchestrate.sh ... solo_one` sound like the same feature but only the latter is grounded/screenshotted. → codified as a gotcha in `AGENTS.md`.
2. **Teaching scenario tracing (Agenda #2 — completed):** Three realistic teaching moments were traced end-to-end through the actual code paths (not just theorized) to see whether each is actually groundable today.
- _Scenario A (Arm track + Monitor In):_ Fully supported on the UIA path. Produces exactly 1 final screenshot under current per-task granularity (see Agenda #4 decision below re: this being too coarse).
- _Scenario B (Browse Sounds → Drag Kick into track):_ Hard dead end on UIA, not a gap that more engineering effort closes cheaply. Root cause: `DataItem` nodes in the Ableton Browser tree have empty-string `automation_id` values, and the list itself is virtualized (only visible rows exist in the UI tree at any time), so there's no stable UIA target to select or drag. → codified as a known limitation in `AGENTS.md` so future sessions don't re-attempt it from scratch.
- _Scenario C (Solo tour track comparison):_ Supported, but only via `orchestrate.sh ... solo_one` looped per-track — this is the correct screenshotted way to do a solo comparison; direct CLI `solo_tour` is the naming trap from Finding 1, not an alternative way to do the same thing.
3. **MCP verification gap (feeds Agenda #3/#8):** Code inspection of `uisato/ableton-mcp-extended`'s `AbletonMCP_Remote_Script/__init__.py`, specifically `_set_device_parameter`, confirmed MCP does **not** read back the live parameter value after writing it — the value returned to the caller (`clamped`) is a calculated target computed before the write, not a re-read of Ableton's actual state after. Separately, `_resolve_device` resolves tracks via `self._song.tracks[index]` in the Live Object Model directly; this index can diverge from the visible 0-based Session View track index whenever group tracks are folded or hidden, because the LOM includes tracks the UI is currently not displaying. Both issues mean an MCP "success" response is not trustworthy as grounding evidence on its own. → codified as the hard MCP routing rule in `AGENTS.md`: never report an MCP write as verified without an explicit post-write read-back.
4. **Historical doc references purged:** In-code citations of retired docs (pointing at `docs/archived/*` or earlier doc names) were cleaned across 8 files as part of this audit's cleanup pass; test suite reran and remains 28/28 passing after the change, confirming no functional dependency on the removed references.
5. **OpenCode baseline routing test (Agenda #6 — verified live, separate session):** A fresh session in a copy of this project with `AGENTS.md` removed was given the prompt "Arm track 1 and set its monitor to In. Show them the steps." The agent's behavior without routing guidance:
- **Phase 1**: Tried MCP tools (`get_session_info`, `get_track_info`) — natural first instinct in an MCP-connected session. Concluded MCP lacks arm/monitor tools. Offered to extend the MCP server or suggested manual steps. Did NOT explore the project directory or read any local files.
- **Phase 2** (after user nudge "check other tools"): Ran `ls`, found `automate_ableton_task.py`, read it, discovered `task_arm_track`. But then gave up with "it's Windows-only and this environment is Linux" — never tried `python.exe` from WSL interop. Did NOT read `orchestrate.sh`, `take_shot.sh`, or `context.md`.
- **Phase 3** (after second nudge "we're in WSL, Windows is accessible"): Read `orchestrate.sh` and `take_shot.sh`, verified `python.exe`/`cmd.exe`/`powershell.exe` interop, ran `orchestrate.sh LABS/arm_track_demo arm_track --tracks 1` — perfect execution. Task ran, both steps verified live, screenshot captured.
- **What it never did**: Read `context.md` at any point. Even when exploring project files, it went straight to reading `.py`/`.sh` files without checking the project's state/intent document.

**Conclusion**: Without `AGENTS.md`, the agent hits two dead ends (MCP lacking the right tools, assuming Windows-is-impossible-from-Linux) and requires explicit nudging through both. With `AGENTS.md`, it would know immediately: read `context.md` → `orchestrate.sh` is the front door → `arm_track` is allowed → one command, one screenshot. The routing rules are load-bearing, not cosmetic. Full session log at `LIVE_TEST/BASELINE_SESSION_session-ses_02cd.md`.

---

### Agenda Status

**Completed:**

- [x] Item 1: Verify `solo_tour` screenshot behavior live.
- [x] Item 2: Trace 3 teaching scenarios through code.
- [x] Item 3: Decide v1 `AGENTS.md` scope for UIA gaps. **Decision:** do not blindly fall back to MCP. Any MCP use for device params/browser loading must be paired with an explicit post-write read-back. Full detail in `docs/v2_observations.md` §3.
- [x] Item 4: Decide screenshot-granularity policy. **Decision:** move to per-sub-click granularity (not current per-task). `orchestrate.sh`'s `run_one_task()` today takes one screenshot per task, labeled from only the _last_ `EVENT:` line — confirmed this loses intermediate state on multi-substep tasks (e.g. `arm_track`'s arm-checkbox step vs its Monitor→In step). The per-substep `action_start`/`action_result` events already exist in `automate_ableton_task.py`'s `EVENT:` stream, so this is an `orchestrate.sh`-side (consumer) change, not an engine change. Item #7 is a committed implementation task, sequenced after #5 and #6 per user's explicit request to keep agenda order. Full detail in `docs/v2_observations.md` §4.
- [x] Item 5: Wire `keyboard_shortcuts.py` into `click_by_id()` Call Sites. **Done.** Wired `transport_play_stop` (`{VK_SPACE}`) into Transport.Play and Transport.Stop call sites in `task_solo_one`. 28/28 tests pass. Full detail in `docs/v2_observations.md` §5.
- [x] Item 6: Baseline-Test OpenCode Routing (without `AGENTS.md`). **Done.** Key finding: agent needed two nudges and hit two dead ends (MCP missing arm/monitor tools, assumed Windows unreachable from Linux) before finding `orchestrate.sh`. Never read `context.md` on its own. Confirms routing rules in `AGENTS.md` are load-bearing. Full detail in `docs/v2_observations.md` §6 and `LIVE_TEST/BASELINE_SESSION_session-ses_02cd.md`.
- [x] Item 7: Per-Click Screenshots. **Done.** Rewrote `orchestrate.sh`'s `run_one_task()` to use a FIFO-based pipeline: reads `EVENT:` stream in real time, triggers `take_shot.sh` on every `action_start`/`action_result` (not just once per task). Sub-step numbering (`01_01`, `01_02`, ...). Fallback screenshot when zero action events emitted. 15/15 tests pass.
- [x] Item 8: Finalize UIA-vs-MCP Arbitration Policy. **Done (session 6).** `AGENTS.md` did not exist anywhere before this session — `item_8_plan.md` was a design doc, not a diff against a real file. Wrote `AGENTS.md` from scratch (repo root), scoped to Control paths + Routing only (file roles/automation_id-scheme sections deferred, per explicit user decision). Grounded in `v2_observations.md` findings + a fresh code check, not just the plan's draft text:
- Corrected a stale design assumption: `docs/ableton_ai_educational_risk_framework.md` describes a 4-tier escalation ladder (Mouse→Keyboard→MCP/LOM→Human); the actual `click_by_id()` code only has 3 tiers (Mouse→Keyboard→Human) — MCP was never wired in as a per-click fallback. `AGENTS.md` documents the real 3-tier ladder and clarifies MCP is a separate task-level path, not a click-level tier.
- Verified all MCP tool names in the routing table against the real `uisato/ableton-mcp-extended` server code (cloned fresh, 46 `@mcp.tool()` functions extracted) rather than trusting the plan's table by name alone. Found and fixed one gap (`delete_device` wasn't covered) and one false-safe collision (`set_tempo` exists as both a UIA task name in `SINGLE_ACTION_TASKS` *and* an MCP tool — flagged as a naming trap in `AGENTS.md`, same pattern as the existing `solo_tour` trap).
- Added a screenshot-pairing rule: MCP never screenshots on its own, so any MCP write that's a teaching step (not just a background verification) needs `take_shot.sh` called directly after the read-back succeeds — this was missing from the plan's table and only surfaced by dry-running the plan's own verification examples.
- Full content: `AGENTS.md` at repo root.
- **Session 6, continued:** two follow-on requests after item #8 closed — neither is a numbered agenda item, noted here for continuity:
1. Added a `## Lab output & session artifacts` section to `AGENTS.md` — `take_shot.sh` explicitly leaves `lab_dir` naming to the calling agent but nothing specified a convention. Now: `LABS/<slug>_<YYYY-MM-DD_HHMM>/` + a per-session `SESSION_LOG.md` the agent writes alongside screenshots (nothing in code produces this automatically — it's a manual discipline, not a script).
2. Wrote `docs/routing_test_protocol.md` — an incremental, tier-by-tier probe protocol for testing `AGENTS.md`'s routing rules in isolation (naming-trap avoidance, MCP read-back discipline, escalation ladder, unsupported-recognition, etc.) before trusting them inside a full lesson. Not yet run — next session should execute Tier 0/1 probes and log results back into `v2_observations.md`.
3. Built `build_runtime_env.sh` (repo root) — a whitelist-based script that copies only the agent-necessary files (`AGENTS.md`, `orchestrate.sh`, `take_shot.sh`, and the 5 scripts under `scritps/` that `automate_ableton_task.py`'s import chain actually needs) into a separate sibling folder (`../ableton-runtime` by default), which is what OpenCode's working directory should point at for real lessons — not this dev repo. Fixed a real bug this surfaced: `AGENTS.md` had two live cross-references into `docs/ableton_ai_educational_risk_framework.md` (a dev-only doc); inlined the Level 3 human-instruction protocol content directly into `AGENTS.md` instead so it's fully self-contained with zero dependency on `docs/`. Verified the whitelist is dependency-complete by grepping actual imports (not filenames) and by running the script + `py_compile`/`bash -n` against the output in this sandbox. `docs/routing_test_protocol.md` is deliberately excluded from the whitelist — it's the answer key for live agent tests and must never be readable by the agent under test.

**Open (Ordered Easiest → Hardest):**

5. ~~**Wire `keyboard_shortcuts.py` into `click_by_id()` Call Sites (Item #5):** Pass `load_shortcut()` at unblocked call sites so L2 of the escalation ladder is active in production tasks.~~ **DONE.** Wired `transport_play_stop` (`{VK_SPACE}`) into both Transport.Play and Transport.Stop call sites in `task_solo_one`. The other unblocked shortcut (`activator_by_position`) targets Activator, which no production `click_by_id()` call site uses. 28/28 tests pass.
6. ~~**Baseline-Test OpenCode Routing (Item #6):** Prompt OpenCode with a scenario without `AGENTS.md` present to establish baseline tool selection behavior (orchestrator vs raw Python vs MCP), for comparison now that `AGENTS.md` exists.~~ **DONE.** Agent defaulted to MCP, needed two nudges to discover `orchestrate.sh`. Never read `context.md` on its own. Confirms routing rules in `AGENTS.md` are load-bearing. Full log: `LIVE_TEST/BASELINE_SESSION_session-ses_02cd.md`.
7. ~~**Implement Per-Click Screenshots (Item #7):** Modify `orchestrate.sh` to parse the `EVENT:` stream and take a screenshot after each `action_start`/`action_result`, not just once per task. Needs: a `seq` counter that increments per sub-step (not per task), and `desc` derivation that keys off each event as it fires rather than grepping the last labeled line.~~ **DONE.** FIFO-based real-time pipeline. 15/15 tests pass.
8. ~~**Finalize UIA-vs-MCP Arbitration Policy in `AGENTS.md` (Item #8):**~~ **DONE (session 6).** `AGENTS.md` written from scratch — see completed-items entry above for details.

**No open agenda items remain from the original 8-item audit.** Next session should decide what's next: extend `AGENTS.md` with the file-roles/automation_id-scheme content that was deliberately deferred this session, or open a new agenda based on live use of the routing rules.