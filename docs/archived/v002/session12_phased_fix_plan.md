# Phased Fix Plan — `ableton-gui-grounding`

Written session 12, following the effort/impact comparison table and the "high impact or low/medium effort" filter agreed on in this session. Ordered lowest-effort/highest-confidence first, so the plan degrades gracefully if a session runs out of budget partway through — whatever's done at the end of any phase is a safe, complete, revertible state, never a half-applied one.

**Ground rule carried from session 11/12:** no phase below is applied until explicitly confirmed in-session. This document is the *sequence*, not a standing authorization to proceed unattended.

---

## Phase 1 — Pure documentation (S effort, zero code risk, no live Ableton needed)

Do this first: no code touched, nothing to break, nothing that needs live verification against Ableton.

| Item | File | Change |
|---|---|---|
| 4.2 | `ABLETON_AGENT_POLICY.md` | Add per-task required-args + 0-based `--tracks` indexing note to the task table |
| 4.2 (python note) | `ABLETON_AGENT_POLICY.md` | Add interpreter note: always invoke `python` (3.12, maintained) directly, never `python3` (stale 3.10) |
| 6.D.1 | `context.md` | Formally record the `AGENTS.md` auto-load ceiling as an accepted, closed testing-protocol limitation — not chased further, not re-flagged as an "open thread" each session |

**Exit criteria for Phase 1:** both doc files read cleanly, no code changed, nothing to test — can be committed standalone at any point, independent of every later phase.

---

## Phase 2 — The three mechanical `orchestrate.sh` bugs (S effort each, high confidence, testable offline)

These are all 1–6 line bash changes, each independently revertible, each already validated once live in a prior session's own transcript (not just theorized).

| # | Fix | File / lines | Confidence basis |
|---|---|---|---|
| 1.1 | Add `< /dev/null` to both `take_shot.sh` call sites | `orchestrate.sh` L228, L274 | Root-caused via isolated FIFO reproduction in session 8 |
| 1.2 | Flip `command -v` order so `python` is tried before `python3` | `orchestrate.sh` L45–48, L125–128 | User-confirmed environment fact: `python`→3.12 (current), `python3`→3.10 (stale) |
| 1.3 | Conditional `TASK_ARGS` expansion (only expand when non-empty) | `orchestrate.sh` L352 | Validated live once already in the P1.3 transcript's own session |

**Exit criteria for Phase 2:** `test_orchestrate.py` and `test_phase0_events.py` pass against the modified `orchestrate.sh`; `bash -n orchestrate.sh` clean.

---

## Phase 3 — The one Python-side bug (S effort, medium-high confidence, needs a live spot-check)

| # | Fix | File / lines | Confidence basis / caveat |
|---|---|---|---|
| 1.4 | Cast `str(bpm)` before `tempo.iface_value.SetValue(bpm)` | `scritps/automate_ableton_task.py` L802 | Type mismatch is confirmed by the exact prior exception (`TypeError: unicode string expected instead of float`) — the cast is clearly correct. **Caveat:** the "fast path" itself has never been proven to succeed live even after casting, because the one prior test ran with tempo already at 120 BPM (no real write exercised). |

**Exit criteria for Phase 3:** test suite still passes (these are stub-based, won't catch the live-only caveat) **and** a live spot-check is run starting from a non-120 BPM tempo, confirming the `RangeValuePattern` fast path actually succeeds post-fix rather than silently falling through to click+type again for a different reason. This live check can only happen outside this sandboxed session — flag it as a to-do for whoever runs the next live probe.

---

## Phase 4 — Judgment-call items (S–M effort, not an effort problem, a decision problem)

These aren't blocked by effort or confidence — they're blocked by an open policy decision that hasn't been made yet. Do this phase only after that decision is explicit.

| # | Item | Status |
|---|---|---|
| 4.1 | Scope-creep rule ("report bugs, don't patch unprompted") in `ABLETON_AGENT_POLICY.md` | **Still open.** Wording not drafted. If approved, this is S effort (prose only) and can move into Phase 1 territory — it's listed here only because the *decision*, not the effort, is the blocker. |

**Exit criteria for Phase 4:** either a wording is agreed and added to `ABLETON_AGENT_POLICY.md`, or the decision is explicitly deferred (not silently dropped) with a one-line note in `context.md` saying so.

---

## Phase 5 — Deferred, lower cost/benefit (M effort, weaker payoff given current constraints)

Not part of the core pass. Revisit only if a future session's priorities change (e.g. the live-test model gains image input, making per-substep screenshots actually useful to the agent, not just to a human reviewer).

| # | Item | Why deferred |
|---|---|---|
| 2.1 (partial) | Instrument `task_read_solo_states` only with `emit_event()` calls | Structurally simpler than `set_tempo` (pure read loop, no retry/escalation logic), but still M-ish new code, and payoff is mostly for human lab-folder review, not the no-vision live-test agent |
| 2.1 (full) | Instrument both `task_read_solo_states` and `task_set_tempo` | Full M effort, same weak payoff reasoning, plus adds a second correctness axis (event *shape*) to what the test suite must cover |

No action planned here unless explicitly revisited.

---

## Cross-phase notes

- **`build_runtime_env.sh` re-run:** only needed after Phase 2 and/or Phase 3 change actual code (`orchestrate.sh` / `automate_ableton_task.py`). Phase 1's doc-only changes to `ABLETON_AGENT_POLICY.md` also require a rebuild if the runtime copy is meant to reflect the new policy text — `build_runtime_env.sh` is what copies `ABLETON_AGENT_POLICY.md` → `AGENTS.md` in the runtime folder.
- **Test suite:** `test_orchestrate.py` / `test_phase0_events.py` are stub-based — they can catch a broken bash syntax or an argparse regression, but **cannot** catch the live-only caveats (Phase 3's fast-path proof, any real UIA behavior). Passing tests after Phases 2–3 means "didn't break what we could check from here," not "proven correct against live Ableton."
- **Session-budget resilience:** if a session only has room for Phase 1 + Phase 2, that's a complete, safe, independently-committable state — Phase 3 doesn't depend on Phase 4 or 5, and none of the phases need to happen in the same session as each other.
- **`context.md` status line:** only move to "Comprehensive fix: DONE" once Phases 1–3 are complete and test-suite-verified. If Phase 4/5 are deferred, say so explicitly in that same status update — per the standing instruction not to let deferred items silently vanish from the handoff record.

---

## Suggested session mapping (adjust freely)

| Session | Phases | Live Ableton needed? |
|---|---|---|
| This session (12) | Phase 1 + Phase 2, and Phase 3's code change (not its live spot-check) | No |
| Next live-probe session | Phase 3's live spot-check (non-120 BPM tempo test) | Yes |
| Whenever Phase 4's decision is made | Phase 4 | No |
| Only if priorities change | Phase 5 | No (code), Yes (verification) |
