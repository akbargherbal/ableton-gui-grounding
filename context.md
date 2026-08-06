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
- `docs/v2_observations.md` (running verification log for the 8-item audit agenda — that agenda is closed; kept for history)
- `docs/routing_test_protocol.md` (the 16-probe, Tier 0–7 test protocol; the answer key — never shipped to the agent's runtime folder)
- `docs/routing_test_results.md` (NEW, session 7 — running log of live probe results, one Tier per session; see "Session 7+ Plan" below)
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

**No open agenda items remain from the original 8-item audit.** The 8-item audit is closed. Session 7 opened a new, separate agenda: live-testing `AGENTS.md`'s routing rules via `docs/routing_test_protocol.md`.

---

### Session 7+ Plan: Tier-by-Tier Routing Test Analysis

**Setup (done, session 7):** `build_runtime_env.sh ../ableton-ai-training/` produced the isolated agent-facing runtime. The user ran the first 7 of 16 probes (`docs/prompts.json`, generated via `docs/make_prompt.py`) — each probe in its own fresh OpenCode session, against a fresh Ableton session, per `routing_test_protocol.md`'s cold-start requirement. Each session's chat transcript was exported from OpenCode to `../RESULTS/result_01.md` … `result_07.md`. These 7 map to Tier 0 (P0.1, P0.2) + Tier 1 (P1.1–P1.3) + Tier 2 (P2.1–P2.2) — the user then paused before Tier 3, having noticed execution-quality issues that need addressing before trusting further results.

**Rule for this agenda (explicit user correction, session 7):** do not assume the 8-item audit's "DONE" findings or the harness itself were built correctly just because they're marked done. Every session's analysis must look for shortcomings on **both** sides — ours (harness/prompting/environment/isolation setup) and the agent's (routing correctness per each probe's Pass/Fail criteria in `routing_test_protocol.md`) — never default to blaming the agent alone.

**Cadence:** one Tier analyzed per session (matches the user's own token-budget concern — reading all 7 transcripts in one session was explicitly rejected). Findings go in `docs/routing_test_results.md`, one dated section per Tier, each split into an "Our-side issues" and "Agent-side issues" subsection, mirroring `routing_test_protocol.md`'s own Tier structure so a result maps directly back to its probe's Watch-for/Pass/Fail criteria.

**Order:**

1. Tier 0 (P0.1, P0.2) — `result_01.md`, `result_02.md` (exact mapping to be confirmed against filenames/content when uploaded — not yet verified they're in probe order).
2. Tier 1 (P1.1–P1.3) — `result_03.md`–`result_05.md`.
3. Tier 2 (P2.1–P2.2) — `result_06.md`, `result_07.md`.
4. Tiers 3–7 (P3.1–P7.1) — not yet run live; needs fresh probe sessions after Tier 0–2 findings are addressed, same one-probe-per-session discipline.

**Known open threads, not yet resolved (flag for whichever session reaches the relevant Tier):**

- **`python3`/`python` bug (code-confirmed, session 7):** `orchestrate.sh`'s two JSON-extraction helpers (`extract_json_float`, `extract_field`, lines ~45 and ~125) both prefer `python3` first via `command -v`, contradicting README.md:157's documented rule ("`python`, not `python3` — the latter is a stale 3.10"). This is a harness bug independent of any agent behavior — not yet fixed in code, just diagnosed. Fix candidate: flip the `command -v` precedence in both functions.
- **MCP config edit during a "sandboxed" run (user-reported, session 7, not yet transcript-verified):** user observed the agent editing MCP server config/settings during a run against `ableton-ai-training/`. Confirmed by inspecting `build_runtime_env.sh`'s whitelist: it copies zero MCP-related files into the runtime folder, so whatever got edited was **not** inside the isolated runtime — it was either OpenCode's own global/user config or some other out-of-repo location. User to confirm where OpenCode's MCP config actually lives on their machine; this is the real isolation boundary to audit, not `build_runtime_env.sh` (which looks correct as written).
- **Agent scope creep (user-reported, session 7, not yet transcript-verified):** user observed the agent "fixing" bugs in the project's own scripts unprompted during a YOLO-mode run — not authorized behavior (agent should use tools as-is, not patch them). Needs transcript confirmation of which run and what was changed.
- **Directory-listing anomalies spotted in `../ableton-ai-training/` (session 7, not yet explained):**
- `p08.txt` at the runtime root — not part of `build_runtime_env.sh`'s whitelist, origin unknown.
- `LABS/arm-track-monitor-in_2026-08-06_0923/` has screenshots numbered `01_01`, then `04_01`–`04_03` — sub-steps `02`/`03` are missing from the sequence. Could be a retry reusing the lab dir, or a real numbering gap in item #7's FIFO per-substep pipeline. That lab's `SESSION_LOG.md` should explain it.
- ~~`LABS/` also has both `solo-compare-0-1_...` and `solo-compare-tracks0-1_...`~~ **Resolved (session 10):** confirmed against the transcripts — P2.1 wrote `solo-compare-tracks0-1_...`, P2.2 wrote `solo-compare-0-1_...`. Two independent cold-start sessions freely naming their own lab dir; not a bug or duplicate.

**Filename fix, session 7 (done):** `AGENTS.md` was renamed to `ABLETON_AGENT_POLICY.md` **in this dev repo only**. Reason: `AGENTS.md` is a filename convention agentic coding tools (OpenCode, Claude Code, etc.) auto-read as instructions directed at *themselves*. An assistant working in this dev repo (auditing/editing the project, like the current audit) would otherwise risk misreading the Ableton-teaching-agent's routing rules as instructions for itself — the two are unrelated. `build_runtime_env.sh` now copies `ABLETON_AGENT_POLICY.md` → `AGENTS.md` on build (source and destination names deliberately differ for this one file; every other whitelisted file keeps the same relative path both sides) — verified live: `./build_runtime_env.sh /tmp/test-runtime-check` correctly produces `AGENTS.md` in the target with identical content, `bash -n` clean. `README.md`'s file table updated to match and explain the rename. **Action for the user:** merge this rename into the real repo (rename the file, pull the updated `build_runtime_env.sh` and `README.md`), then re-run `build_runtime_env.sh` against `../ableton-ai-training/` to refresh it — the already-built runtime folder still has the old copy under the correct `AGENTS.md` name, so it isn't broken, but any future rebuild needs the updated script.

**Note on filename-to-probe mapping:** `result_01.md`–`result_07.md` are assumed to map to P0.1–P2.2 in order, but this is **not verified** — `docs/make_prompt.py` requires manually typing a selection number (1–16) each run, so export order could be run order, not probe order. Don't trust the filename; when a result file is opened, first confirm which probe it actually is by matching its prompt text against `docs/prompts.json`, before filing any finding under a Tier.

**Tier 0: DONE (session 8).** `result_01.md` confirmed = P0.1 (arm track 1 + monitor→In), `result_02.md` confirmed = P0.2 (task inventory) — confirmed by matching each transcript's restated prompt understanding + session title against `docs/prompts.json`, not by filename. Full findings in `docs/routing_test_results.md`'s Tier 0 section. Headline results:

- **P0.1 verdict: contaminated, not a clean Pass/Fail.** The session uncovered and fixed a real, previously-undiagnosed harness bug (see below) but in doing so deviated heavily from a clean cold-start routing probe. Recommend re-running P0.1 fresh now that the bug's fixed, with an explicit "report bugs, don't fix them" instruction for the test day.
- **P0.2 verdict: partial Pass.** Agent correctly avoided reciting `AGENTS.md`'s UIA task table from memory (checked source instead) but never actually ran `--list-tasks`/`--list-tracks` as the protocol expects, and its MCP tool list in the final answer *was* pure unverified recitation — the exact failure mode this probe exists to catch.
- **Open thread resolved — screenshot-numbering gap:** `LABS/arm-track-monitor-in_2026-08-06_0923`'s `01_01`, `04_01`-`04_03` gap (missing `02`/`03`) is now fully explained: seq 01–03 were runs truncated by the newly-found bug below (1 screenshot each), seq 04 is the clean post-fix run (3 screenshots). Not a bug in item #7's per-substep pipeline as originally suspected.
- **Open thread resolved — `p08.txt`:** per the user directly, this is a leftover prompt file from probe 8, which they started but paused mid-session (stopped after Tier 2). Not a harness anomaly.
- **Open thread confirmed — agent scope creep:** the P0.1 transcript shows the agent editing `orchestrate.sh` (real source, unprompted) to fix a bug it found mid-task. Previously only user-reported/unverified; now transcript-confirmed. No `AGENTS.md` rule currently forbids this — worth deciding whether to add one.
- **New bug found + fixed (in the transcript's session, not yet merged into this repo):** `orchestrate.sh`'s screenshot loop lost every `EVENT:` line after the first screenshot trigger on multi-step tasks, because `take_shot.sh`'s `cmd.exe`/`powershell.exe` calls inherited the loop's FIFO as stdin and drained it. Root-caused via isolated FIFO reproduction; fixed by adding `< /dev/null` to both `take_shot.sh` call sites in `orchestrate.sh`. **Action for the user:** apply this same fix to the real repo's `orchestrate.sh` (see `docs/routing_test_results.md` Tier 0 / P0.1 for the exact diff description) — this bug would have silently corrupted screenshot records on every multi-step UIA task, not just `arm_track`.
- **Still open, unresolved:** MCP `get_track_info`'s `arm` field read `false` both before and after a UIA-verified armed state, with no group track involved — a real divergence with no explanation yet. Needs a dedicated session, not chased further here. Also still open: the `python3`/`python` precedence bug (not exercised either way by this session's transcripts) and the MCP-config-isolation / directory-listing questions from session 7 (not addressed by Tier 0 data).

**Tier 1: DONE (session 9).** `result_03.md` confirmed = P1.1 (solo track 2), `result_04.md` confirmed = P1.2 (set tempo 120 — the `set_tempo` name-collision trap), `result_05.md` confirmed = P1.3 (read solo states, tracks 0–3) — confirmed by matching each transcript's opening thinking/session title against the literal prompt text in `docs/prompts.json`, not filename order. Full findings in `docs/routing_test_results.md`'s Tier 1 section. Headline results:

- **Pre-Tier-1 status check (done at the start of session 9, per explicit instruction):** confirmed by direct inspection that **none** of the two bugs diagnosed in Tier 0 (`take_shot.sh` stdin-drain fix, `python3`/`python` precedence fix) are merged into the real GitHub repo's `orchestrate.sh` — both still only exist in the isolated runtime folder / transcript sessions. Flagged to the user before any Tier 1 analysis began.
- **P1.1 verdict: clean Pass.** Best-behaved of the three Tier 1 runs — single `orchestrate.sh ... solo_one` call, no MCP-first instinct, no scope creep, no unauthorized edits. Some pre-call source exploration (resolving an undocumented 0-based-vs-1-based `--tracks` convention), but justified and not a routing failure.
- **P1.2 verdict: Pass on the core adversarial test, but grounding quality undercut by our-side gaps.** The agent correctly used the UIA `set_tempo` path and never touched the colliding MCP `set_tempo` tool — the cleanest possible signal on the naming-trap this tier exists to test. But the test itself was weak (tempo was already 120 BPM before the run, so no real write was proven), and it surfaced a genuine unfixed code bug: `task_set_tempo`'s `SetValue(bpm)` call always raises a `TypeError` (float vs. expected string), so the "fast, exact" RangeValuePattern path silently never works and every call falls through to click+type.
- **P1.3 verdict: correct final routing, but contaminated by a repeat of the P0.1 scope-creep pattern.** Agent correctly used `read_solo_states` (not MCP) once arguments were right, but needed two attempts: the first call (missing `--tracks`) hit a genuine `orchestrate.sh` bug — empty `TASK_ARGS` expands to a stray empty-string arg that `argparse` rejects — which the agent diagnosed and patched unprompted, mid-probe, after explicitly weighing (and rejecting) the option of just calling `automate_ableton_task.py` directly instead.
- **New open thread — scope creep is now a repeated pattern, not a one-off:** confirmed in 2 of 5 analyzed transcripts (`result_01.md`/P0.1, `result_05.md`/P1.3), both unprompted `orchestrate.sh` edits mid-probe, both technically-correct fixes. `ABLETON_AGENT_POLICY.md` still has no rule on this. Not decided/edited this session per your instruction to discuss first — just noting the evidence has strengthened.
- **New open thread — screenshot-instrumentation gap.** Only `arm_track` and `solo_one` emit per-substep `EVENT:` lines and get true per-click screenshots; `set_tempo` and `read_solo_states` only emit `task_start`/`task_done` and fall back to one generic post-task screenshot each. Item #7's "per-click granularity" work from the original 8-item audit isn't wired into every `SINGLE_ACTION_TASKS` entry — worth a dedicated fix pass, informed by whichever tasks Tier 2+ probes touch next.
- **New open thread — the live-test model can't see screenshots.** All three Tier 1 transcripts (and apparently Tier 0) run `DeepSeek V4 Flash` via OpenCode, which has no image input in this configuration. `result_04.md`/P1.2 shows the agent trying to `read` a saved PNG and concluding it can't view it, falling back to a text-based MCP read-back instead. Given the project's core goal is *visual*, step-by-step grounding for the student, an agent that can never look at its own screenshots is a real gap — flag for a decision (acceptable since screenshots are for the human, or worth switching to a vision-capable model for future live probes, especially before Tier 6's pixel-coordinate clicking).
- **New minor thread — undocumented per-task required args / index convention.** `ABLETON_AGENT_POLICY.md`'s task table lists task names but not required arguments (e.g. `read_solo_states` needs `--tracks`) or whether `--tracks` is 0- or 1-based. Both P1.1 and P1.3 had to resolve this via source reads rather than the policy file — a minor but recurring contributor to the "explores before the front door" pattern.
- **New bugs found this session, still unfixed anywhere (unlike the two Tier-0 bugs, which are at least fixed in the runtime copy):** `orchestrate.sh`'s empty-`TASK_ARGS` expansion bug (fixed in the P1.3 transcript's session only — not yet merged anywhere) and `task_set_tempo`'s `SetValue(bpm)` type bug (not fixed anywhere yet, including the runtime copy). Both detailed in `docs/routing_test_results.md`'s cross-tier findings.

**Tier 2: DONE (session 10).** `result_06.md` confirmed = P2.1 (solo comparison, un-named — "I want to compare tracks 0 and 1 by hearing them soloed one after another"), `result_07.md` confirmed = P2.2 (solo comparison, explicitly mis-named — "Can you run solo_tour for tracks 0 and 1?", literal prompt text confirmed via a grep tool result inside the transcript, not just title/paraphrase). Full findings in `docs/routing_test_results.md`'s Tier 2 section. Headline results:

- **Pre-Tier-2 status check (done at the start of session 10, per standing instruction):** confirmed by direct inspection that **none** of the four accumulated fixes are merged into the real GitHub repo — the two Tier-0 fixes (`take_shot.sh` stdin-drain, `python3`/`python` precedence), the Tier-1 empty-`TASK_ARGS` fix, and the `task_set_tempo` `SetValue` type bug all remain open in `orchestrate.sh`/`automate_ableton_task.py` on GitHub. Flagged to the user before any Tier 2 analysis began. Per the user's explicit instruction, all four are deliberately deferred to one consolidated fix-and-verify session after Tier 2 — this audit studies, it doesn't patch.
- **P2.1 verdict: clean Pass.** Single `orchestrate.sh ... solo_one --tracks 0 1 --seconds 4` call, using the orchestrator's own multi-track loop (one `run_one_task` per track). No MCP-first instinct, no scope creep, full 18-screenshot coverage (this task is already instrumented for per-substep events).
- **P2.2 verdict: clean Pass — arguably the stronger run.** The prompt names `solo_tour` directly, and the agent not only avoided it but explicitly grepped the project for `solo_tour` before acting, surfacing and quoting `ABLETON_AGENT_POLICY.md`'s own "naming trap" prose in its reasoning before making any live call. Same routing shape as P2.1 (`solo_one --tracks 0 1 --seconds 3`), zero MCP calls, zero scope creep.
- **Open thread resolved — the `solo-compare-0-1` vs `solo-compare-tracks0-1` LABS anomaly.** Both dirs are legitimate: P2.1 wrote to `solo-compare-tracks0-1_...`, P2.2 to `solo-compare-0-1_...` — two independent cold-start sessions each freely choosing their own lab-dir slug (nothing in the harness dictates this). Not a bug, not a retry/duplicate.
- **Zero scope creep this tier — first fully clean tier on that front.** Running tally: 2 of 7 analyzed transcripts show unprompted agent edits to project source (`result_01.md`/P0.1, `result_05.md`/P1.3), unchanged this session. Worth noting neither Tier 2 probe happened to trip a live bug the way P0.1/P1.3 did, so this may partly reflect "no bug was hit" rather than a change in the agent's underlying impulse — still an open decision for `ABLETON_AGENT_POLICY.md`, not touched this session per your instruction not to propose the edit without discussing first.
- **New observation — this naming trap looks "solved" for this model/policy combination.** Both the un-named (P2.1) and explicitly-named (P2.2) versions passed cleanly, with P2.2 showing the agent actively consulting the policy file's specific "Gotcha" prose rather than relying on a vague pre-loaded summary. Worth keeping in mind for Tiers 3–7: this particular trap may no longer be a discriminating test unless a harder variant is designed later.
- **No new code bugs surfaced this session** — both transcripts ran cleanly against the already-known-buggy `orchestrate.sh`/`automate_ableton_task.py` without hitting either the stdin-drain or empty-`TASK_ARGS` failure conditions.

**Next step (session 11): full synthesis review before any fix, per the user's explicit instruction.** Not a straight patch session — session 11 opens a new, separate step: re-review **all** findings across Tier 0, Tier 1, and Tier 2 (`docs/routing_test_results.md`'s Our-side + Agent-side sections and cross-tier findings, plus this file's headline summaries) as a single synthesis, before applying any fix. The comprehensive fix should be *informed by* that synthesis, not just a checklist run through the four known bugs in isolation — e.g. checking whether any of the four fixes interact with each other, whether the screenshot-instrumentation gap or the doc gaps (required args / `--tracks` indexing) should be bundled into the same pass, and whether the scope-creep question needs a decision before or alongside the code fix. The four known code fixes remain the concrete floor of the pass:
1. `take_shot.sh` stdin-drain fix (`< /dev/null` at both call sites in `orchestrate.sh`).
2. `python3`/`python` precedence fix (flip `command -v` order in both `orchestrate.sh` helpers).
3. Empty-`TASK_ARGS` expansion fix (conditional array expansion at `orchestrate.sh`'s standard single-action path).
4. `task_set_tempo`'s `SetValue(bpm)` type fix (cast `bpm` to `str` before calling `SetValue`, in `scritps/automate_ableton_task.py`).

Also on the table for this session, per the accumulated evidence, but not to be decided unilaterally — flag and discuss, per standing instruction not to propose `ABLETON_AGENT_POLICY.md` edits without the user first:
- Whether to add a "report bugs, don't patch them unprompted" rule (scope creep confirmed in 2 of 7 analyzed transcripts: `result_01.md`/P0.1, `result_05.md`/P1.3).
- Whether to document per-task required args / the `--tracks` indexing convention in the policy file (recurring friction in P1.1, P1.3).
- Whether the screenshot-instrumentation gap (`set_tempo`/`read_solo_states` lacking per-substep `EVENT:` emission, unlike `arm_track`/`solo_one`) belongs in this same fix pass or a separate one.

After the fix pass is applied and verified (re-run `build_runtime_env.sh` to refresh the runtime copy, confirm all four fixes present, spot-check with a quick live task), Tiers 3–7 (P3.1–P7.1) can begin — these need fresh live probe sessions against a running Ableton instance, one probe per session per the established cold-start discipline; no transcripts exist yet for these tiers.