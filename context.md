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
the student saw the _outcome_ of an action, not the _steps_ that produced
it. This audit's job, before any new code is written, is to:

1. Inventory every tool/capability actually present in V2, from the code,
   not from docs describing intent.
2. Map how they currently chain together (and where they _don't_).
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

| File                        | Role                                                                                                                                                                                                                                                                         | Status                                                                                                                                                                                                                |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dump_ableton_pywinauto.py` | Read-only tree dump. Canonical `find_ableton_window()` + `ensure_window_ready()`.                                                                                                                                                                                            | Mature, imported by everything else — single source of truth for window handling.                                                                                                                                     |
| `dump_ableton_states.py`    | View switching (Session↔Arrangement via Tab) + Browser category switching + dump.                                                                                                                                                                                            | Session/Arrangement: CONFIRMED (verifies before+after via `SessionView.*` id presence). Browser categories: **all 6 confirmed** — evidence in `scritps/dumps/`, docstrings corrected to match (see Resolved section). |
| `grep_dump.py`              | Stdlib substring search over a saved JSON dump.                                                                                                                                                                                                                              | Solid, no dependencies.                                                                                                                                                                                               |
| `automate_ableton_task.py`  | Action engine. 8 tasks. `resolve()` never caches controls. `click_by_id()` = Mouse→Keyboard→Human ladder (**no MCP/LOM tier by design** — deliberately excluded, see its own docstring). `set_checkbox_by_id()` = click→re-read→retry→raise. Emits `EVENT:` JSON per action. | Solid engine. `--list-tasks`/`--list-tracks` work without Ableton running.                                                                                                                                            |
| `keyboard_shortcuts.py`     | Sourced shortcut registry (cites Ableton manual §), `blocked` flag, `load_shortcut()` guard.                                                                                                                                                                                 | **Built but not wired in** — no `click_by_id()` call site in the current code passes a `keyboard_shortcut`. L2 of the ladder is dead in production tasks; only exercised standalone by `probe_keyboard_activator`.    |
| `orchestrate.sh`            | Front door for **single live action + 1 screenshot**, for tasks in its `SINGLE_ACTION_TASKS` list only. Drift-checks schema version via `--list-tasks` before acting. `solo_one` gets per-track looping (1 screenshot/track).                                                | Solid, well-guarded — but see scope exceptions below.                                                                                                                                                                 |
| `take_shot.sh` (v6)         | WSL→PowerShell screen capture. Auto restore/focus/maximize, DrvFs poll, distinct error codes. **Only ever called from inside `orchestrate.sh`.**                                                                                                                             | Mature.                                                                                                                                                                                                               |
| Test suite (28 tests)       | Stub-based, no Windows/Ableton needed.                                                                                                                                                                                                                                       | Solid, CI-safe.                                                                                                                                                                                                       |

---

### `orchestrate.sh` scope — corrected understanding (session 1)

It is the intended front door for live+screenshotted actions, but with
two exceptions that still need direct `python.exe automate_ableton_task.py`:

- Discovery/dry-run calls (`--list-tracks`, `--list-tasks`, any call
  without `--live`) — not `orchestrate.sh`'s job.
- **`solo_tour`** — explicitly rejected by `orchestrate.sh` ("use solo_one
  instead — Phase 2"). Since `take_shot.sh` is _only_ called from inside
  `orchestrate.sh`, a live `solo_tour` run currently produces **zero
  screenshots**. Not yet confirmed whether `solo_tour` has actually been
  run live in V2 — user doesn't know either, needs checking (Open Items).

---

### Archived docs read this session — corroborate, don't contradict, the code read

- **`docs/phased_plan.md`** — the actual Phase 0–3 design doc. Confirms
  Phase 2's `solo_one` split was a _deliberate, scoped_ fix, with the
  deeper `solo_click`/`play_click`/`stop_click`/`unsolo_click` split
  explicitly flagged as an open question the author chose to ask about
  rather than assume — never answered/implemented. This matches (not
  contradicts) what the current code shows.
- **`docs/screenshot_orchestration_analysis.md`** — the earlier options
  analysis (Option B / orchestrator chosen over A/C/D). Shortcoming #1 in
  its own table states outright: _orchestrator "doesn't achieve per-click
  granularity on its own"_ — multi-step tasks only get a before/after
  shot unless paired with Option A (atomic decomposition). This is the
  same gap independently reached by reading the current code (see §3 of
  the prior session's summary) — good corroboration, not new information.
- Both docs are internally consistent with the current code. No further
  discrepancies found in this pass.

### Test suite — actually run in the sandbox this session (not just read)

Both suites execute fully without Windows/Ableton (stub-based, as
documented) and **all 28 pass**:

- `test_phase0_events.py` — 14/14 pass. Confirms L2 keyboard escalation
  logic itself is correct (`test_click_by_id_escalates_to_l2_and_succeeds`)
  — reinforces that the gap is _nothing calls it with a shortcut_, not
  that the ladder is broken.
- `test_orchestrate.py` — 14/14 pass, runs the real `orchestrate.sh` as a
  subprocess against stub `automate`/`take_shot` scripts via its own
  `ORCH_PYTHON_CMD`/`ORCH_AUTOMATE_SCRIPT`/`ORCH_TAKE_SHOT` env-var seams.
  Confirms `solo_tour` rejection, seq counter, drift check, and `_FAILED`
  labeling all behave as documented.

This is independent confirmation of the README's "28/28 tests, CI-safe"
claim — verified directly, not taken on trust.

### Open items — need user verification next session

_(none currently — item 1, `solo_tour` screenshot behavior, resolved
session 2, see below)_

### Resolved this session

- **Agenda item 1 (`solo_tour` screenshot behavior) — done.** Live test
  confirmed: direct bypass of `orchestrate.sh` runs `solo_tour` to
  completion with zero screenshots (expected — `take_shot.sh` only ever
  called from inside `orchestrate.sh`), and solo state was correctly
  restored on both tested tracks — the historical "solo_tour bug"
  referenced in old probe docstrings did not reproduce. Full detail in
  `docs/v2_observations.md` item 1. Caveat: only 2 tracks, 1 pass, one
  already-open Ableton session — not exhaustive.
- **Agenda item 2 (trace 3 teaching scenarios) — done, code-only.**
  Scenario A (arm+monitor) and C (solo tour) fully supported today, C
  _only_ if the student flow uses `orchestrate.sh ... solo_one`, not the
  standalone `solo_tour` CLI (that path exists, runs, but produces zero
  screenshots — a naming trap for an agent). Scenario B (browse Sounds →
  drag a kick into a track) is a **hard dead end** on the UIA path: code
  confirms browser _category_ switching exists but item selection/
  drag-drop into a track does not exist anywhere in the codebase. Full
  trace in `docs/v2_observations.md` item 2. Feeds directly into agenda
  items 3 and 8 (does B route to MCP, or get marked unsupported?). Root
  cause for both gaps also traced (why, not just what) — see
  `docs/v2_observations.md` item 2's "Root-cause follow-up": B is a
  lookup-mechanism gap (browser items lack `automation_id`, `resolve()`
  is automation_id-only), C is a documentation/metadata gap
  (`--list-tasks` doesn't flag `solo_tour` as screenshot-incapable) —
  both concrete, low-effort fix candidates for later code work.
- `docs/v2_observations.md` (new file) — running log for the 8-item
  agenda below, dated entries, code-read vs. live-verified tagged. Detail
  lives there now; keep this file's entries terse and pointer-style.
- **Browser category verification status.** `scritps/dumps/` contains
  tracked (not gitignored-away) real dumps for all six categories,
  timestamped one session (2026-08-04 08:34). Each shows a distinctly-
  named, distinctly-counted list marker (Sounds=1001, Instruments=23,
  Drums=1001, Audio Effects=47, MIDI Effects=15, Plug-Ins=0) — strong
  evidence all six were actually selected and captured correctly, not
  the same state relabeled six times. `dump_ableton_states.py`'s
  docstrings/help text (which claimed only 2/6 verified) were the stale
  side here and have been corrected to reflect all 6 as confirmed.
- **Historical-doc references purged from code.** All 8 in-code
  citations of the retired `context.md`/`phased_plan.md`/session numbers
  (across `automate_ableton_task.py`, `keyboard_shortcuts.py`,
  `dump_ableton_states.py`, `orchestrate.sh`, `test_orchestrate.py`) were
  rewritten to be self-contained. Verified via repo-wide grep (zero
  matches) and both test suites still pass (28/28) after the edits.

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

### Working rule with the user (binding, established session 2)

The user directed this codebase (e.g. via AI-assisted coding in earlier
sessions) rather than hand-writing it line by line, and does not reliably
recall implementation details on request. **Do not ask the user to recall
or confirm specific code behavior from memory.** Instead: read the code
directly, state findings as claims, and ask whether the user wants to
_verify it live_ (run a command, paste output). Live verification is the
only thing the user can reliably supply — not code recall.

---

### Decisions made this session (binding for future sessions unless overridden)

- Where `docs/ableton_ai_educational_risk_framework.md` (a pre-implementation
  design doc) conflicts with current code: **code wins**, doc entry is
  stale, not a real gap.
- **The pre-V2 `context.md` is retired.** It served its purpose across
  earlier sessions and is not to be referenced, quoted, or treated as a
  source of truth going forward — the AI Assistant doing so isn't fair to
  work done in sessions it has no visibility into. **This file
  (`context.md` at the repo root, current version) is the only handoff
  document in effect.** If a discrepancy between this file and the code
  ever needs resolving, resolve it the normal way (verify against the
  code/live app), not by appealing to what an earlier document said.
- Not writing `AGENTS.md` yet — audit first.
- Not writing implementation code yet — this is audit/planning only,
  **except** for the historical-doc-reference cleanup done this session
  (see "Resolved this session" — those 8 locations are fixed, not still
  open).

---

### Next session agenda — ordered easiest → hardest (combined effort, both sides)

Goal of these items collectively: close enough real gaps that `AGENTS.md`
can be written once and be accurate, not revised immediately after.

1. **Verify `solo_tour`'s screenshot behavior.** One live command, paste
   the output/lab folder contents back. Confirms or refutes the
   zero-screenshots read from the code (still the one open item).
2. **Trace 2–3 real teaching scenarios through the code by hand.** No
   Ableton needed — a desk exercise done together in-session. E.g.
   "student arms a track and sets monitor to In," "student browses
   Sounds for a kick and drags it in," "student compares two takes via a
   solo tour." For each: which script/MCP call handles each sub-step,
   does a screenshot exist for it, where does the chain actually break.
   This is what turns "imagine scenarios" into a repeatable method rather
   than ad hoc poking at Ableton.
3. **Decide what's out of scope for v1 `AGENTS.md`.** Clip launching,
   device parameters, browser item selection are all "not yet" in the
   UIA path per README's own Status table. Pure decision, informed by #2
   — should `AGENTS.md` route these to MCP, or say "not supported yet,
   don't attempt"? Staying silent and letting the agent guess is the one
   option to avoid.
4. **Decide the screenshot-granularity policy for v1.** `phased_plan.md`
   left "screenshot every sub-click vs. just per-track" as an open
   question, never answered. Decide on purpose: fix it in code (see #7),
   or document it as an accepted limit in `AGENTS.md` ("granularity
   stops at X"). Informed by #1 and #2.
5. **Wire `keyboard_shortcuts.py` into `click_by_id()` call sites.**
   Mechanical: pass `load_shortcut("transport_play_stop")` /
   `load_shortcut("activator_by_position", ...)` at the unblocked call
   sites so L2 actually gets exercised in production tasks, not just the
   standalone probe. Code change + one live verification pass.
6. **Baseline-test OpenCode's default tool routing with NO `AGENTS.md`
   guidance yet.** Give it one of the #2 scenarios with zero instructions
   about which tool to use, and watch whether it reaches for
   `orchestrate.sh`, raw `python.exe`, or `AbletonMCP`. This tells us how
   much `AGENTS.md` actually needs to constrain vs. what the model
   already gets right unprompted — a real baseline, not a guess.
7. **(If #4 chose "fix it") Implement per-click screenshot capability.**
   The `EVENT:` stream already carries an `action_result` for every
   click; nothing currently turns that into an intermediate screenshot.
   Needs design (tail the stream vs. deeper Option-A-style task
   decomposition) + implementation + live verification. The most
   code-heavy item on this list.
8. **Define and codify the UIA-vs-MCP arbitration policy.** The biggest
   structural gap: no rule anywhere (code or docs) for "use
   `orchestrate.sh`/`automate_ableton_task.py` for X, use `AbletonMCP`
   for Y." Requires understanding both tool surfaces, probably live-
   testing overlapping capabilities on both paths, then writing the
   actual routing rules into a first `AGENTS.md` draft. Once drafted,
   re-run the #6 scenario _with_ the draft and compare behavior against
   the baseline — the hardest item, and the one everything else on this
   list ultimately feeds into.
