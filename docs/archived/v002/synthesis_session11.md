# Session 11 Synthesis — Tier 0–2 findings, pre-fix review

Consolidates every finding logged across `context.md` and `docs/routing_test_results.md` for Tier 0 (session 8), Tier 1 (session 9), and Tier 2 (session 10), before the comprehensive fix pass. Source of truth for each item is cited by transcript/probe. This document does not itself decide anything — items under "Policy/behavior questions" are explicitly left open for the user.

**v2 addition (still session 11):** Section 6 below inventories every *architectural or environmental* limitation identified so far — things no code fix in this repo can resolve, as distinct from Sections 1–4's fixable bugs/gaps. The purpose is to keep the eventual fix pass from being planned as if it could solve problems it structurally cannot. This is a first pass at that inventory (built from a full context.md + routing_test_results.md re-read plus direct code checks); the user is reviewing it before a full joint discussion next session on which path to take, so nothing here should be read as a final or exhaustive list.

---

## 1. Code bugs

### 1.1 `take_shot.sh` stdin-drain bug — `orchestrate.sh`
- **Symptom:** `take_shot.sh`'s `cmd.exe`/`powershell.exe` calls inherit `run_one_task`'s FIFO as stdin (nothing redirects it) and drain buffered `EVENT:` lines while running. Every event fired after the first screenshot trigger is silently lost from the loop's view on multi-step tasks — the python engine keeps working correctly, but only the first sub-step gets recorded/screenshotted.
- **Surfaced:** Tier 0, `result_01.md`/P0.1 (session 8). Diagnosed and fixed by the agent inside its own session via isolated FIFO reproduction; this fix exists only in `../ableton-ai-training/` (runtime copy), never merged to GitHub.
- **Explains:** `LABS/arm-track-monitor-in_2026-08-06_0923`'s `01_01`, `04_01`–`04_03` screenshot-numbering gap (context.md, resolved).
- **Fix:** add `< /dev/null` to both `"$TAKE_SHOT" ...` call sites in `orchestrate.sh` (lines 228 and 274 in current GitHub source).
- **Status on GitHub (verified this session):** **NOT merged.** Neither call site redirects stdin.

### 1.2 `python3`/`python` precedence bug — `orchestrate.sh`
- **Symptom:** `extract_json_float()` and `extract_field()` both try `python3` before `python` via `command -v`, contradicting `README.md`'s documented rule that `python`, not `python3`, is the correct interpreter in this environment (`python3` is described as a stale 3.10).
- **Surfaced:** pre-Tier-0, session 7 (code read, not transcript-derived). Not exercised either way by any Tier 0–2 transcript (the WSL test environment happens to have a working `python3`, so the wrong-precedence path never visibly failed).
- **Fix:** flip the `command -v` order in both functions so `python` is tried first.
- **Status on GitHub (verified this session):** **NOT fixed.** Both helpers (lines 45 and 125) still check `python3` first.
- **Risk note:** because no transcript has ever exercised the failure mode, this fix is unverified-by-observation — it should be spot-checked after the pass (see Fix Plan, verification section) rather than assumed safe purely from README's say-so.

### 1.3 Empty-`TASK_ARGS` expansion bug — `orchestrate.sh`
- **Symptom:** the standard single-action path (`--task "$TASK" --live "${TASK_ARGS[@]:-}"`, line 352) expands to a single stray empty-string positional argument whenever `TASK_ARGS` is empty (i.e. any task called with no extra flags), which `argparse` rejects as `unrecognized arguments:`.
- **Surfaced:** Tier 1, `result_05.md`/P1.3 (session 9). Agent hit this on its first `read_solo_states` call (before adding `--tracks`), diagnosed it, and patched it via conditional array expansion — again only in the runtime copy.
- **Fix:** conditionally expand `TASK_ARGS` only when non-empty, e.g.:
  ```bash
  if [ ${#TASK_ARGS[@]} -gt 0 ]; then
    run_one_task "$SEQ_PADDED" "$TASK" --task "$TASK" --live "${TASK_ARGS[@]}"
  else
    run_one_task "$SEQ_PADDED" "$TASK" --task "$TASK" --live
  fi
  ```
- **Status on GitHub (verified this session):** **NOT fixed.** Line 352 still does unconditional `"${TASK_ARGS[@]:-}"` expansion.
- **Interaction to check:** this path and the `solo_one` path (line 300's own `for arg in "${TASK_ARGS[@]}"` loop) are separate code paths — the `solo_one` loop already handles zero-arg iteration safely since it's a `for` loop, not an expansion into a command. No interaction expected, but worth a quick sanity check during the fix pass since both touch `TASK_ARGS`.

### 1.4 `task_set_tempo`'s `SetValue(bpm)` type bug — `automate_ableton_task.py`
- **Symptom:** `tempo.iface_value.SetValue(bpm)` passes a Python `float` to a pywinauto control wrapper that expects a `str`, raising `TypeError: unicode string expected instead of float instance`. The "fast, exact, no simulated typing" `RangeValuePattern` path documented in the function's own docstring therefore never succeeds — every `set_tempo` call silently falls through to click+type.
- **Surfaced:** Tier 1, `result_04.md`/P1.2 (session 9). Not fixed anywhere yet, including the runtime copy — this is the one bug with zero existing fix to port over.
- **Fix:** cast to string before calling: `tempo.iface_value.SetValue(str(bpm))`.
- **Status on GitHub (verified this session):** **NOT fixed.** Line 802 still passes `bpm` directly.
- **Compounding factor:** P1.2's test ran with tempo already at 120 BPM, so the write path was never actually proven to work even via the fallback. Recommend a post-fix live re-test starting from a non-120 tempo (see Fix Plan verification section) — this is a test-design gap, not something the code fix itself resolves.

**Pre-existing GitHub status, confirmed directly this session (2026-08-06):** all four bugs above are present exactly as described — none merged. This matches every prior session's "confirmed still unmerged" check (sessions 9, 10) — the divergence between the runtime copy and the real repo has now persisted across three consecutive audit sessions without action.

### 1.5 Other issues noticed during this review (not new fixes, flagged for completeness)
- **MCP `arm` read never reflects UIA-verified armed state** (Tier 0, `result_01.md`/P0.1) — `get_track_info`'s `arm` field read `false` both before and after a UIA-confirmed arm click, no group track involved. Still unexplained; not actionable as a code fix without a dedicated diagnostic session against live Ableton (can't be reproduced from static code reading alone). **Not included in this pass** — flagging only, per `context.md`'s own note that it "needs a dedicated session, not chased further here."
- **No new bugs found by this session's own code re-read of `orchestrate.sh` / `automate_ableton_task.py` beyond the four already logged.** I re-read the `run_one_task` FIFO/tee pipeline, the `solo_one` arg-parsing loop, and `task_read_solo_states` directly (see Fix Plan for exact line references) specifically looking for anything unlinked across tiers — nothing additional surfaced. This should be read as "nothing new was found by inspection," not "nothing else exists" — no live Ableton access was available to this session to exercise runtime-only failure paths.

---

## 2. Harness / instrumentation gaps

### 2.1 Per-substep screenshot instrumentation only wired for 2 of ~7 tasks
- `arm_track` and `solo_one` call `emit_event("action_start"/"action_result", ...)` internally (via the shared `click_by_id()`/`set_checkbox_by_id()` helpers), producing true per-click screenshots.
- `set_tempo` and `read_solo_states` call neither helper (tempo uses direct `double_click_input()`/`type_keys()`; solo-state reads are a pure read loop with no clicks at all), so both fall back to a single generic post-task screenshot (`sub_steps=0`).
- **Surfaced:** Tier 1, `result_04.md`/P1.2 and `result_05.md`/P1.3 (session 9). Confirmed again structurally this session by re-reading `task_read_solo_states` (lines 595–608) and `task_set_tempo` (lines 781–811) directly — neither touches `emit_event`.
- **Consequence:** Item #7's "per-click granularity" goal from the original 8-item audit is not actually uniform across `SINGLE_ACTION_TASKS` — it's opt-in per task, and only 2 tasks opted in.
- **Not yet checked against Tier 2:** `probe_toggle`, `probe_solo_transport`, `probe_keyboard_activator` haven't been probed live yet (Tiers 3–7), so it's unknown whether they share this gap. Worth confirming once those tiers run.
- **Decision needed:** whether to close this gap in the same pass as the four code bugs, or defer — see Policy/behavior questions below.

### 2.2 Live-test model cannot view its own screenshots
- `DeepSeek V4 Flash` via OpenCode (used across all Tier 0–2 sessions) has no image input in this configuration. `result_04.md`/P1.2 shows the agent trying to `read` a saved PNG, concluding it can't view images, and falling back to a text-based MCP read-back instead.
- **Consequence:** the agent driving the lesson can confirm a screenshot file exists but never that it shows the right thing — a real gap against the project's core "grounded, visual, step-by-step" goal, most consequential ahead of Tier 6 (pixel-coordinate clicking).
- **Not a code bug** — this is an environment/model-selection question, listed under Policy/behavior questions below since it doesn't have a "fix," only a decision (accept it, or switch models for future live probes).

### 2.3 `p08.txt` and other directory-listing anomalies
- `p08.txt` at the runtime root: **resolved** — user-confirmed leftover from a paused probe-8 session, not a harness bug. No action needed.
- `LABS/solo-compare-0-1` vs `solo-compare-tracks0-1`: **resolved** — two independent cold-start sessions (P2.1, P2.2) each freely chose their own lab-dir slug; nothing in the harness dictates naming. Not a bug or duplicate.
- Both closed; listed here only so this synthesis is a complete account of every open thread, not because either needs further action.

---

## 3. Documentation gaps

### 3.1 `ABLETON_AGENT_POLICY.md`'s task table lists task names but not required arguments or indexing convention
- Confirmed directly this session: line 34 of `ABLETON_AGENT_POLICY.md` reads `Today's supported tasks: arm_track, set_tempo, probe_toggle, probe_solo_transport, probe_keyboard_activator, read_solo_states, solo_one.` — a bare name list, no per-task required-args column, no statement of whether `--tracks` is 0-based or 1-based.
- **Surfaced:** Tier 1, P1.1 (`result_03.md`) and P1.3 (`result_05.md`), session 9. Both sessions had to resolve this via source inspection or cross-referencing a prior session's `SESSION_LOG.md` rather than the policy file itself.
- **Consequence:** contributes directly to the "explores filesystem before finding the front door" fail-sign pattern seen in multiple probes — not because the agent doesn't trust the front door, but because the front door's own documentation is incomplete.
- **Established convention (from transcript cross-checks, not a new finding):** `--tracks` is 0-based, matching Session View's visible track index. This is already implicitly confirmed by P1.3 (`--tracks 0 1 2 3` read back correctly against a 4-track session) and P2.1/P2.2 (`--tracks 0 1`) — just never written down anywhere in the policy file.
- **Decision needed:** whether/how to add this — see Policy/behavior questions below (this is a documentation edit to the same file the scope-creep policy question also touches, so bundling the discussion makes sense even if the two questions are independent).

---

## 4. Policy/behavior questions (user decision required — no proposed final wording)

These are carried over verbatim in substance from `context.md`'s "on the table for this session" list; presented with full evidence below, not decided or drafted here.

### 4.1 Agent scope creep — unprompted edits to project source mid-probe
- **Evidence: 2 of 7 analyzed transcripts.**
  - `result_01.md`/P0.1 (Tier 0): agent found the `take_shot.sh` stdin-drain bug mid-task and fixed `orchestrate.sh` unprompted, without being asked, mid a routing-discovery probe.
  - `result_05.md`/P1.3 (Tier 1): agent found the empty-`TASK_ARGS` bug mid-task and patched `orchestrate.sh`'s standard path unprompted — this instance is more deliberate than P0.1's: the transcript shows the agent explicitly weighing "should I modify the orchestrator? I could just run `automate_ableton_task.py` directly... but per `AGENTS.md` I should use the orchestrator" before choosing to patch rather than route around.
  - Tier 2 (P2.1, P2.2): **zero** instances — but neither Tier 2 transcript happened to trip a live bug, so this may reflect "no bug was hit" rather than a change in the agent's underlying impulse. Not counted as counter-evidence.
- **Why this matters for the audit specifically:** both instances contaminated the very probe they occurred in — a routing-discovery or default-path-selection transcript is supposed to isolate tool-selection behavior, and an unplanned live debugging session buries that signal. Separately, both fixes were technically correct, which is what makes this a real policy question rather than a simple "agent misbehaved" case.
- **Options on the table (not a recommendation, not exhaustive):**
  1. Add an explicit rule to `ABLETON_AGENT_POLICY.md`: "if you find a bug in the harness, report it — do not patch it unprompted," at least during test/probe sessions.
  2. Scope the rule more narrowly — allow source fixes in normal teaching use, forbid them only during explicitly-flagged test/audit sessions.
  3. Leave as-is and treat it as acceptable agent initiative, accepting that it will continue to occasionally contaminate routing probes.
  4. Some other split (e.g. allow fixes to `take_shot.sh`/`orchestrate.sh` scaffolding but never to `automate_ableton_task.py`'s task logic) — not evidenced by the transcripts either way, listed only as a logical alternative.
- **No wording proposed. Awaiting your decision.**

### 4.2 Documenting required args / `--tracks` indexing convention in the policy file
- **Evidence:** see Documentation gaps §3.1 above — recurring friction in P1.1 and P1.3, confirmed structurally this session by direct inspection of the current task table.
- **Options on the table:**
  1. Add a per-task required-args column/notes to the existing task list in `ABLETON_AGENT_POLICY.md`, plus one sentence stating the 0-based convention.
  2. Leave the policy file as a name-only index and rely on `--help`/`--list-tasks` output as the single source of truth for arguments (would require confirming `--list-tasks` actually surfaces this — not yet verified either way from the transcripts, since P0.2 never actually ran it).
  3. Leave as-is; treat the one-time source-read cost as acceptable.
- **No wording proposed. Awaiting your decision.**

### 4.3 Screenshot-instrumentation gap — same pass or separate?
- **Evidence:** see Harness gaps §2.1.
- **This is a scoping question, not a content question** — the fix itself (adding `emit_event` calls to `task_set_tempo` and `task_read_solo_states`) is a real code change, not a one-liner like the four bugs, and it touches the same file as bug 1.4 (`automate_ableton_task.py`). Options:
  1. Bundle into this pass — same file, same testing cycle, avoids a second round-trip through `build_runtime_env.sh` + live verification later.
  2. Defer to its own pass — keeps this pass scoped strictly to the four already-diagnosed bugs, lower risk of scope creep in the fix itself (a bit ironic given §4.1, but worth naming: a bigger pass is a bigger single diff to review and revert if something goes wrong).
- **Not decided here. Flagged for your call in the Fix Plan below**, where I've included a *decision point*, not a default inclusion.

### 4.4 Live-test model's lack of image input (context, no action proposed)
- Not a code or policy-file question — a test-environment decision. Flagged for completeness since it's an accumulated, unresolved thread (Harness gaps §2.2), most relevant before Tier 6. No options list drafted here since it's a model/tooling choice outside this repo's code, not a repo edit.

---

## 5. Cross-tier links and previously-unlinked observations

Connections between findings that were logged individually per-tier but not explicitly tied together until this synthesis pass:

- **The two confirmed scope-creep instances (§4.1) both happened on runs where the agent independently discovered a real, previously-undiagnosed bug** (P0.1 found the stdin-drain bug; P1.3 found the empty-`TASK_ARGS` bug). Both bugs are now in this pass's fix list. This means the fix pass itself, if applied, directly removes two of the three known triggering conditions for scope creep observed so far — after this pass, a re-run of P0.1/P1.3-equivalent scenarios should have nothing live to "discover" on those two specific bugs, making it a cleaner test of whether the agent's scope-creep *impulse* persists even with no bug to find, versus only appearing reactively when one exists. Worth designing a deliberate re-test for this once Tiers 3–7 resume, not just an incidental side effect.
- **The instrumentation gap (§2.1) and the doc gap (§3.1) share a root cause pattern, not just a coincidence of both being "gaps."** Both stem from `set_tempo`/`read_solo_states` being implemented via a different code path than `arm_track`/`solo_one` (direct pywinauto calls vs. the shared `click_by_id()`/`set_checkbox_by_id()` helper functions) — the helpers are where both `emit_event()` calls *and* (implicitly) the args each task needs live. A future task added via the helper-based pattern would likely inherit correct instrumentation "for free"; one added via direct calls, like `set_tempo`, would not. This suggests the gap isn't really "two tasks got skipped" so much as "the shared-helper path and the direct-call path are two different implementation patterns with different default behavior," which matters if more tasks get added in Tiers 3–7's wake.
- **The "explores before the front door" fail-sign has fired in every tier so far, but for two different underlying reasons that were being tracked separately.** P0.1/P0.2 (Tier 0) and P1.1 (Tier 1) explored because of genuinely undocumented behavior (task coverage, indexing convention — §3.1). P1.3's exploration was different in kind: it was forced by a live bug (§1.3), not a documentation gap — the agent didn't choose to explore, argparse rejected its first call. Conflating these two into one "exploration" finding across sessions risks over-crediting the doc-gap fix (§4.2) with solving a problem that's actually two problems, one of which (§1.3) is fixed by the code pass regardless of any doc decision.
- **No contradictions found between tiers.** Every "Verdict" line across Tier 0–2 is internally consistent with the cross-tier findings log — e.g. the scope-creep tally (2/7), the runtime-vs-repo divergence confirmation (repeated identically at the start of sessions 9 and 10), and the naming-trap results (Tier 2's clean pass is consistent with, not contradicted by, `AGENTS.md`'s specific "Gotcha" prose being quoted verbatim in `result_07.md`). This is a completeness check, not a new finding — recorded so a future session doesn't have to re-verify it.

---

## 6. Architectural / environmental limitations — no amount of fixing helps

Added at the user's explicit request, after reviewing Sections 1–5: an inventory of constraints that are **inherent** to a design choice, a third-party dependency, or the audit's own vantage point — not bugs, not gaps that a patch closes. The point of separating these out is to stop the eventual fix pass from being scoped as if it could resolve something it structurally cannot. Each item is marked **confirmed** (directly stated or observed in the existing docs/transcripts, or verified by direct code inspection this session) or **inferred** (this session's own read, not yet independently tested) so the reliability of each claim is clear at a glance. This is a first pass, not represented as exhaustive — the user is skimming it now, with a full joint review planned for next session.

### 6.A — Model-choice limits
- **6.A.1 No image input (confirmed).** `DeepSeek V4 Flash` via OpenCode cannot view screenshots at all — `result_04.md`/P1.2 shows the agent trying to `read` a saved PNG and concluding it has no image support, falling back to a text-only MCP read instead. It can confirm a screenshot file exists, never that it shows the right thing. This is a property of the model choice, not of anything in this repo's code, and it directly undercuts the project's stated goal of *visual*, step-by-step grounding — most consequential ahead of Tier 6 (pixel-coordinate clicking).
- **6.A.2 Possible knock-on behavioral effects of model choice (inferred, unconfirmed).** The "explores before the front door" and scope-creep patterns *could* be partly attributable to this specific model's tendencies rather than being independent of it — but every probe so far has run the same model, so nothing isolates model choice from policy-file wording or task design. Not a confirmed limitation; flagged as a confound so it isn't mistaken for a settled fact when planning fixes to the exploration/scope-creep patterns.

### 6.B — GUI-automation architecture limits (inherent to controlling Ableton via UIA, not our scripts)
- **6.B.1 Virtualized/unstable UI targets — the Browser dead end (confirmed).** `context.md`'s Scenario B finding: `DataItem` nodes in Ableton's Browser tree have empty-string `automation_id`, and the list itself is virtualized — only currently-visible rows exist in the UI tree at any moment. There is no stable target to select or drag, structurally, for any virtualized list in Ableton's UI, not just the one case already tested (Browse Sounds → drag Kick). Any future task touching another virtualized list (other browser categories, possibly device-chain browsers) will hit the identical wall.
- **6.B.2 Click-based automation is inherently racy (confirmed by design, not by failure report).** The very existence of `click_by_id()`'s Mouse→Keyboard→Human escalation ladder and `set_checkbox_by_id()`'s click→re-read→retry→raise pattern is evidence that click-then-read is a race against Ableton's own UI thread, not a solved problem. Retries and verification make this *more resilient*; nothing makes it *deterministic* the way a direct API call would be. This is a ceiling on how reliable any UIA-path task can ever be, independent of how well `automate_ableton_task.py` itself is written.
- **6.B.3 Foreground/focus dependency (confirmed).** `take_shot.sh` auto-restores/focuses/maximizes the target window; click-based tasks require Ableton to hold OS focus. The machine cannot be used for anything else during a live probe, and any OS-level interruption (a notification, a popup) can silently corrupt a run mid-task. Inherent to controlling a GUI app via simulated input, not a `take_shot.sh` defect.

### 6.C — Third-party MCP server limits (code we don't own)
- **6.C.1 MCP write-verification gap is architectural, not patchable here (confirmed).** `_set_device_parameter` in `uisato/ableton-mcp-extended` returns a pre-write calculated target value, never a post-write read-back (`context.md`, code-inspection finding). Closing this means patching or forking someone else's project, not touching `automate_ableton_task.py`/`orchestrate.sh`. Our current mitigation — never trust an MCP write without a UIA read-back — is a workaround this repo can maintain, not a fix this repo can ship.
- **6.C.2 LOM-index vs. visible-index divergence on group tracks (confirmed).** `_resolve_device` indexes via `self._song.tracks[index]` in Ableton's Live Object Model, which includes tracks the UI isn't currently displaying (folded groups) — this is Ableton's own object model surfaced through the MCP server, not something either our code or, easily, the MCP server itself can correct, since it reflects how Ableton represents session state internally.
- **6.C.3 MCP's tool coverage is whatever the upstream project shipped (confirmed).** The session-6 baseline test (`context.md` Agenda #6) shows the agent's first instinct hitting a dead end because MCP has no arm/monitor tools at all. UIA covers this gap for the tasks we've built, but we cannot add capability to MCP itself without extending that external dependency.
- **6.C.4 Unexplained `arm`-field divergence — candidate, not yet confirmed as belonging to this category.** Tier 0 found `get_track_info`'s `arm` field reading `false` both before and after a UIA-verified arm click, no group track involved (so 6.C.2 doesn't explain it as-is). Possibly the same class of MCP/LOM issue, possibly something else entirely — flagged here only as a hypothesis pending the dedicated diagnostic session `context.md` already calls for. Do not treat as confirmed-architectural until that session happens.

### 6.D — Testing-methodology limits (properties of *how* this audit works, not of the app under test)
- **6.D.1 `AGENTS.md` auto-load means "does it find the rules" can never actually be tested (confirmed inference).** Tier 0/1 transcripts show the agent citing `AGENTS.md` before any tool call, with no explicit read visible anywhere — consistent with OpenCode auto-loading it into context at session start. If true, no rewording or re-running of a P0.1-style probe can ever test rule *discovery* — only rule *compliance*, since the file's presence is guaranteed by the tool, not earned by the agent's own behavior.
- **6.D.2 This audit has no live Ableton/Windows access (confirmed, stated explicitly in `context.md`'s constraints).** Every fix proposed by whoever is doing this synthesis work is unverified until the user runs it live. Not fixable by better code — it's inherent to the audit's own setup (Linux-sandbox auditor, Windows-only target).
- **6.D.3 Cold-start, one-probe-per-session discipline structurally excludes long-session behavior (by design, confirmed).** Every probe to date is a single fresh session, deliberately, to isolate routing behavior cleanly. This means there is currently zero data on how the agent behaves across a long continuous teaching session with many accumulated actions and context — a different failure surface than anything Tier 0–7's current design can ever surface, no matter how many more single-probe sessions run. Worth naming explicitly since it could be mistaken for "not yet tested" (implying more of the same testing would eventually cover it) rather than "structurally untestable under the current protocol design."

### 6.E — Platform/environment limits (standing design choices, not bugs — but also not something a patch changes)
- **6.E.1 Windows-only, WSL-interop-dependent (confirmed).** The whole pipeline — `take_shot.sh` shelling to `cmd.exe`/`powershell.exe`, `automate_ableton_task.py` targeting a live Windows UIA tree — only works in this specific WSL+Windows+Ableton configuration. Not portable to macOS/Linux-native Ableton, not containerizable, not headless-capable. A foundational choice, not a gap to close.
- **6.E.2 Single-instance, serial-only (confirmed).** Exactly one Ableton window is ever controlled; nothing in the architecture supports parallel probe sessions or parallel students. Every probe, past and future, runs one at a time against one live instance.

**Reading guide for next session:** B, C, and D are the genuine hard ceilings — the GUI-automation-vs-API tradeoff, someone else's MCP server code, and this audit's own vantage point. A and E are standing *design choices* (cheap non-multimodal model, Windows-only architecture) that could theoretically be revisited, but doing so is a different-scale decision than any of the four bugs in Section 1 — it's a project-direction call, not something the comprehensive fix pass should be scoped to attempt.

---

## Summary table

| # | Item | Category | Status |
|---|---|---|---|
| 1.1 | `take_shot.sh` stdin-drain | Code bug | Diagnosed, fixed in runtime only — **not merged** |
| 1.2 | `python3`/`python` precedence | Code bug | Diagnosed, unverified by any transcript — **not merged** |
| 1.3 | Empty-`TASK_ARGS` expansion | Code bug | Diagnosed, fixed in runtime only — **not merged** |
| 1.4 | `task_set_tempo` `SetValue` type | Code bug | Diagnosed, **no fix exists anywhere yet** |
| 2.1 | Per-substep screenshot gap (2 of ~7 tasks) | Harness gap | Open — bundling decision needed (§4.3) |
| 2.2 | Model can't view screenshots | Harness gap | Open — see §6.A.1, environment decision, no repo action |
| 2.3 | `p08.txt`, LABS naming | Harness gap | **Resolved**, no action |
| 3.1 | Required-args / `--tracks` indexing undocumented | Doc gap | Open — decision needed (§4.2) |
| 4.1 | Scope-creep rule | Policy question | Open — decision needed |
| 4.2 | Doc-gap fix decision | Policy question | Open — decision needed |
| 4.3 | Instrumentation-gap bundling decision | Policy question | Open — decision needed |
| 4.4 | Model image-input gap | Policy question | Open — no repo action proposed; see §6.A.1 |
| 6.A–6.E | Architectural/environmental limitations (14 items) | Not fixable in this repo/pass | Cataloged for scoping — full review planned next session |
