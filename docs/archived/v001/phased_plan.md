## Phase 0 — Structured events in `automate_ableton_task.py`

**Goal:** replace stdout-parsing-by-wording with a stable, greppable, versioned signal. Non-breaking — existing `print()` lines stay untouched.

- Add one helper, e.g. `emit_event(type: str, **fields) -> None`, that prints a single line: `EVENT: {"v":1,"type":"...","...":...}` (JSON body, `EVENT:` prefix for cheap `grep`). Version field lets the schema evolve without breaking an orchestrator that only reads fields it recognizes.
- Event vocabulary (minimum viable set):
  - `task_start` / `task_done` (task, tracks, result) — wraps every `task_*` function
  - `action_start` / `action_result` (label, level: L1/L2/L3, result: success/warn/failed) — inside both `click_by_id()` and `set_checkbox_by_id()`, at the same points where they already `print()` `[click]`/`[warn]`/`[skip]`
  - `escalate` (label, from_level, to_level) — inside `click_by_id()`'s ladder transitions
- Emit to **stdout**, same stream as the human-readable lines — keeps ordering intact for anyone reading raw terminal output, and the orchestrator just filters by prefix.
- **Verifiable without Windows:** I can write `emit_event()` as a pure function and unit-test its JSON shape here in the sandbox (stub `UIAWrapper`, same pattern as Session 4's escalation-ladder stub tests). The real acceptance test — that `EVENT:` lines line up with actual click outcomes — needs your machine, same as always.

## Phase 1 — Orchestrator script (`orchestrate.sh`), single-action tasks only

**Goal:** ship the coordination layer for tasks that are already atomic: `arm_track`, `set_tempo`, `probe_toggle`, `probe_solo_transport`, `probe_keyboard_activator`, `read_solo_states`. Explicitly **not** `solo_tour` yet.

- New file at repo root, next to `take_shot.sh`. Interface: `./orchestrate.sh <lab_dir> <task> [task-args...]`
- Flow per call:
  1. Run `python.exe scritps/automate_ableton_task.py --task ... --live ...`, capture stdout to a temp file.
  2. Check exit code. On failure, still take a screenshot (labeled `_FAILED`) so the failure itself is part of the documentation trail, then log and move on — **never retry against a live Ableton session** (this is shortcoming #4's fix, applied symmetrically to automate-side and screenshot-side failures).
  3. Auto-derive `take_shot.sh`'s `<short_description>` from the last `EVENT:` line's `label`/`task` fields, so you're not hand-typing a description per call.
  4. Call `./take_shot.sh <lab_dir> <seq> <desc>`. Maintain the `<seq>` counter itself so repeated calls for one lab don't need manual numbering.
  5. Tag every orchestrator-owned line `[orchestrator]`; leave `automate`'s and `take_shot`'s own output visibly separated (shortcoming #7).
- Path discipline: the orchestrator **never re-derives** `/mnt/c/...` ↔ `C:\...` — it passes `<lab_dir>` straight through to `take_shot.sh` unchanged (shortcoming #6).
- **Verifiable without Windows:** control flow (arg parsing, seq counter, path passthrough, error branching) can be tested here against stub `automate`/`take_shot` scripts. Real Ableton + PowerShell round-trip still needs your machine.

## Phase 2 — Atomic decomposition of `solo_tour`

**Goal:** resolve shortcoming #1 (no per-click granularity for multi-step tasks), only for the one task that currently needs it.

- Add `--task solo_one --tracks N --seconds S`: one solo→play→wait→stop→unsolo cycle for a single track, then return.
- Keep `solo_tour` itself as a thin in-process loop over `solo_one`, so standalone CLI use doesn't regress.
- Orchestrator, for tutorial generation, calls `solo_one` once per track in its own loop instead of `solo_tour` — regains control between tracks, screenshots each one.
- **Open scope question, not assumed:** even `solo_one` is internally multi-step (solo→play→stop→unsolo). If you want screenshots at _that_ granularity too (not just per-track), it needs a further split into `solo_click`/`play_click`/`stop_click`/`unsolo_click`. I'd rather ask than guess how far you want this to go.

## Phase 3 — Introspection / drift detection

**Goal:** shortcoming #8 — catch a renamed task or changed flag before it fails silently mid-documentation-run.

- Add `--list-tasks` (JSON): task names, required/optional args, atomic-vs-multi-step, current `EVENT` schema version.
- Orchestrator calls this **once per lab run** (not per-call — keep it cheap), checks its own known task list and schema version against it, fails loudly and early on mismatch instead of mid-sequence.
- Optional stretch: a no-Ableton-needed smoke test that imports the script and asserts `--list-tasks` output matches the Phase 0 schema — catches breakage at review time, not runtime.

---

### Sequencing note

This mirrors the doc's own ordering (§6) — Phase 0 is the cheapest, highest-leverage fix, and it's also the only phase I can fully build and stub-test in the sandbox _right now_ without needing anything from your Windows machine. Phases 1–3 each depend on the previous one's contract.

Want me to start writing Phase 0 now (the `emit_event()` helper + wiring it into `click_by_id()` and `set_checkbox_by_id()` + `task_*` boundaries), or do you want to weigh in on the Phase 2 granularity question first since it affects how deep the eventual decomposition goes?
