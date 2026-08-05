# Context handoff: ableton-gui-grounding V2 audit

This file is written by the AI Assistant for its future self, to restore
session context across stateless sessions. Keep it actively maintained
with key insights, decisions, and enduring context, while aggressively
pruning low-value detail. Record only what will materially help a future
session; the user's own testing/observations are ground truth over any
theory the AI Assistant proposes.

---

### Goal of THIS audit (not the project's original goal)

V2 of this project adds `scritps/` (automate_ableton_task.py, orchestrate.sh,
take_shot.sh v6, tests) on top of the V1 stack (MCP server via
`ableton-mcp-extended` + OpenCode + `take_shot.sh`). V1's known weakness:
the student saw the *outcome* of an action, not the *steps* that produced
it. This audit's job, before any new code is written, is to:

1. Inventory every tool/capability actually present in V2, from the code,
   not from docs describing intent.
2. Map how they currently chain together (and where they *don't*).
3. Find easy-to-close gaps.
4. Only then write `AGENTS.md` for V2 — deliberately deferred until the
   audit is done, so it references only what's actually confirmed to work.

**Constraint:** the AI Assistant has no direct access to Ableton/Windows —
Linux sandbox only. All live verification is done by the user; pasted
terminal/screenshot output is ground truth. Audit is expected to span
2–3 sessions (long back-and-forth per verification), hence this file.

---

### Two parallel, NON-bridged control paths (established this session)

1. **UIA-direct** (this repo): `automate_ableton_task.py` acted on via
   `orchestrate.sh`, screenshots via `take_shot.sh`. Driven from WSL via
   `python.exe` interop.
2. **MCP** (`docs/opencode-ableton-mcp-setup.md`): OpenCode → `AbletonMCP`
   (`ableton-mcp-extended`) → TCP socket → Ableton Remote Script. **Live
   and configured** — user confirmed `~/.config/opencode/opencode.json`
   registers it as a `"local"` MCP server running `MCP_Server/server.py`.

Nothing in the code bridges these. User's stance: mixing MCP + custom
scripts is fine (V1 did this successfully with MCP + `take_shot.sh`) —
not something the audit needs to "fix," just something `AGENTS.md` will
eventually need to arbitrate (which path for which kind of task).

`AGENTS.md` is deliberately NOT being written yet — waiting until this
audit tells us exactly which tools/MCP servers it should reference.

---

### File status table (verified by direct code read this session)

| File | Role | Status |
|---|---|---|
| `dump_ableton_pywinauto.py` | Read-only tree dump. Canonical `find_ableton_window()` + `ensure_window_ready()`. | Mature, imported by everything else — single source of truth for window handling. |
| `dump_ableton_states.py` | View switching (Session↔Arrangement via Tab) + Browser category switching + dump. | Session/Arrangement: CONFIRMED (verifies before+after via `SessionView.*` id presence). Browser categories: **only sounds/instruments grep-verified per current code's own docstring** — conflicts with an older context.md claiming all 6 confirmed; unresolved, see Open Items. |
| `grep_dump.py` | Stdlib substring search over a saved JSON dump. | Solid, no dependencies. |
| `automate_ableton_task.py` | Action engine. 8 tasks. `resolve()` never caches controls. `click_by_id()` = Mouse→Keyboard→Human ladder (**no MCP/LOM tier by design** — deliberately excluded, see its own docstring). `set_checkbox_by_id()` = click→re-read→retry→raise. Emits `EVENT:` JSON per action. | Solid engine. `--list-tasks`/`--list-tracks` work without Ableton running. |
| `keyboard_shortcuts.py` | Sourced shortcut registry (cites Ableton manual §), `blocked` flag, `load_shortcut()` guard. | **Built but not wired in** — no `click_by_id()` call site in the current code passes a `keyboard_shortcut`. L2 of the ladder is dead in production tasks; only exercised standalone by `probe_keyboard_activator`. |
| `orchestrate.sh` | Front door for **single live action + 1 screenshot**, for tasks in its `SINGLE_ACTION_TASKS` list only. Drift-checks schema version via `--list-tasks` before acting. `solo_one` gets per-track looping (1 screenshot/track). | Solid, well-guarded — but see scope exceptions below. |
| `take_shot.sh` (v6) | WSL→PowerShell screen capture. Auto restore/focus/maximize, DrvFs poll, distinct error codes. **Only ever called from inside `orchestrate.sh`.** | Mature. |
| Test suite (28 tests) | Stub-based, no Windows/Ableton needed. | Solid, CI-safe. |

---

### `orchestrate.sh` scope — corrected understanding (session 1)

It is the intended front door for live+screenshotted actions, but with
two exceptions that still need direct `python.exe automate_ableton_task.py`:

- Discovery/dry-run calls (`--list-tracks`, `--list-tasks`, any call
  without `--live`) — not `orchestrate.sh`'s job.
- **`solo_tour`** — explicitly rejected by `orchestrate.sh` ("use solo_one
  instead — Phase 2"). Since `take_shot.sh` is *only* called from inside
  `orchestrate.sh`, a live `solo_tour` run currently produces **zero
  screenshots**. Not yet confirmed whether `solo_tour` has actually been
  run live in V2 — user doesn't know either, needs checking (Open Items).

---

### Archived docs read this session — corroborate, don't contradict, the code read

- **`docs/phased_plan.md`** — the actual Phase 0–3 design doc. Confirms
  Phase 2's `solo_one` split was a *deliberate, scoped* fix, with the
  deeper `solo_click`/`play_click`/`stop_click`/`unsolo_click` split
  explicitly flagged as an open question the author chose to ask about
  rather than assume — never answered/implemented. This matches (not
  contradicts) what the current code shows.
- **`docs/screenshot_orchestration_analysis.md`** — the earlier options
  analysis (Option B / orchestrator chosen over A/C/D). Shortcoming #1 in
  its own table states outright: *orchestrator "doesn't achieve per-click
  granularity on its own"* — multi-step tasks only get a before/after
  shot unless paired with Option A (atomic decomposition). This is the
  same gap independently reached by reading the current code (see §3 of
  the prior session's summary) — good corroboration, not new information.
- Both docs are internally consistent with the current code. No further
  discrepancies found in this pass (contrast with the old `context.md`'s
  browser-category claim, which does conflict — see Open Items).

### Test suite — actually run in the sandbox this session (not just read)

Both suites execute fully without Windows/Ableton (stub-based, as
documented) and **all 28 pass**:
- `test_phase0_events.py` — 14/14 pass. Confirms L2 keyboard escalation
  logic itself is correct (`test_click_by_id_escalates_to_l2_and_succeeds`)
  — reinforces that the gap is *nothing calls it with a shortcut*, not
  that the ladder is broken.
- `test_orchestrate.py` — 14/14 pass, runs the real `orchestrate.sh` as a
  subprocess against stub `automate`/`take_shot` scripts via its own
  `ORCH_PYTHON_CMD`/`ORCH_AUTOMATE_SCRIPT`/`ORCH_TAKE_SHOT` env-var seams.
  Confirms `solo_tour` rejection, seq counter, drift check, and `_FAILED`
  labeling all behave as documented.

This is independent confirmation of the README's "28/28 tests, CI-safe"
claim — verified directly, not taken on trust.

### Open items — need user verification next session

1. **Browser category discrepancy** (see table above): old `context.md`
   claims 6/6 confirmed; current code's docstring claims 2/6. Needs a
   real `--states all` run + `grep_dump.py` check to settle which is true.
   Not resolved by the archived-docs read — neither `phased_plan.md` nor
   `screenshot_orchestration_analysis.md` mentions browser categories at
   all, so they're silent on this, not corroborating either side.
2. Has `solo_tour` been run live at all in V2? If yes, did it actually
   produce zero screenshots as the code implies, or is there some other
   mechanism catching it that wasn't found in this read-through?

### Audit coverage status

Read directly and cross-checked against each other: all 8 scripts in
`scritps/` + root (`automate_ableton_task.py`, `keyboard_shortcuts.py`,
`dump_ableton_pywinauto.py`, `dump_ableton_states.py`, `grep_dump.py`,
both test files, `orchestrate.sh`, `take_shot.sh`), plus all 4 docs
(`README.md`, `opencode-ableton-mcp-setup.md`,
`ableton_ai_educational_risk_framework.md`, `phased_plan.md`,
`screenshot_orchestration_analysis.md`). Code-level inventory is now
complete. Remaining unknowns are all things that need the user's live
Ableton/OpenCode setup, not more reading (see Open Items above, and the
OpenCode-consistency question from the prior session, still unanswered).

---

### Decisions made this session (binding for future sessions unless overridden)

- Where `docs/ableton_ai_educational_risk_framework.md` (a pre-implementation
  design doc) conflicts with current code: **code wins**, doc entry is
  stale, not a real gap.
- Where any old `context.md`/handoff doc conflicts with current code's own
  docstrings/comments: **current code wins** until live-verified otherwise
  (same rule, same reasoning).
- Not writing `AGENTS.md` yet — audit first.
- Not writing implementation code yet — this is audit/planning only.
