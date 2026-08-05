# V2 audit — session observations log

Working log for the 8-item agenda in `context.md` ("Next session agenda"). One section per agenda item. Each entry is dated and tagged with its evidence source (code-read vs. user's live verification), since the two carry different weight per `context.md`'s own rule: user's live testing/observations are ground truth over any theory proposed here.

Status legend: `NOT STARTED` / `IN PROGRESS` / `DONE`

---

## 1. Verify `solo_tour`'s screenshot behavior

**Status: DONE**

**2026-08-05 — live verification (user, this session):**

Ran the three-step test directly against a live Ableton session (same session already open, not freshly restarted):

1. `read_solo_states --tracks 0 1 2 3` → baseline clean, all four tracks `off`. No leftover solo state from any earlier run.
2. `solo_tour --tracks 0 1 --seconds 2 --live` (direct bypass of `orchestrate.sh`) → ran to completion. For each track: solo on (verified), Play (click-and-trust, no verify available — documented gap, not a new finding), 2s wait, Stop (click-and-trust), solo off (verified), then the `finally`-block restore step correctly **skipped** because the track was already back to `off` — i.e. no double-toggle, no mismatch.
3. `read_solo_states --tracks 0 1` afterward → both `off`, matching step 1 exactly.

**Conclusions:**

- The historical "solo_tour bug" referenced in the probe docstrings (solo state not restored correctly) **did not reproduce**. The `solo_one` atomic split + its `finally`-block restore appears to have fixed it, at least for this run. Treating this as resolved but not exhaustively — only 2 tracks, 1 run, same Ableton session throughout.
- Zero screenshots were produced during the direct-bypass run (user reported no `take_shot.sh`/lab-folder activity), confirming the code-read from earlier: `take_shot.sh` is only ever invoked from inside `orchestrate.sh`, so calling `automate_ableton_task.py` directly — as this test did — inherently produces no screenshots. This is guard-rail behavior working as designed, not a bug.
- `Transport.Play`/`Transport.Stop` show the documented "click-and-trust, `verified: false`" gap live, exactly as flagged in code comments and the README's Status table — not new information, just confirmed live rather than taken on trust.

**Not covered by this run** (flag for later if it ever matters): only tracks 0/1 tested, only one pass, within a single already-open Ableton session (not a fresh restart). If the bug was session-state-dependent rather than logic-dependent, this run wouldn't catch that. Not treating this as a live risk right now — just noting the boundary of what was actually verified.

---

## 2. Trace 2–3 real teaching scenarios through the code by hand

**Status: DONE**

Method: pure code trace, no Ableton needed — following the actual function bodies and orchestrate.sh dispatch logic already read in the audit, applied to a specific student scenario instead of read in the abstract.

### Scenario A — "student arms a track and sets monitor to In"

- Single call: `task_arm_track(window, track_index, dry_run)` in `automate_ableton_task.py`. Internally two sub-steps: (1) checkbox `Track[N].Mixer.Arm` via `set_checkbox_by_id` — structurally verified, (2) `Monitoring.Buttons[0]` ("In") via `click_by_id` with an explicit `verify=` lambda checking `get_toggle_state(...) is True` — also a real structural check, not click-and-trust (confirmed by the code comment: this RadioButton's state was validated against a real dump).
- Reachable via `orchestrate.sh`: **yes** — `arm_track` is in `SINGLE_ACTION_TASKS`.
- Screenshots: **one**, taken by `run_one_task` after both sub-steps complete (arm + monitor together). No intermediate shot showing "armed but monitor not yet set" — confirms the granularity gap already noted from `screenshot_orchestration_analysis.md`, now traced through an actual concrete case rather than read as a general claim.
- Chain: clean, no gap. Fully supported end to end today.

### Scenario B — "student browses Sounds for a kick and drags it into a track"

- Browser category switching (e.g. selecting the "Sounds" sidebar category) **is** implemented — `dump_ableton_states.py`, confirmed live for all 6 categories (see `context.md`'s Resolved section from session 1).
- Everything past that point — searching/scrolling within a category, selecting a specific item (e.g. a kick sample), and drag-and-drop (or any equivalent) into a track/slot — **does not exist in the code at all**. Grepped `automate_ableton_task.py` and `dump_ableton_states.py` for `drag`, `drop`, browser item selection, and any interaction with `SessionView.Track[N].Slot[M]` — the only hit is that automation*id string appearing in a docstring's \_reference list* of the ID scheme, never actually touched by any function.
- This matches — and is now confirmed at the code level, not just taken from — the README's own Status table: "Browser item selection / plugin loading" and "Clip launching" are both listed **Not yet**.
- Chain: **breaks immediately after category selection.** This scenario is currently impossible to complete via the UIA path. Real question for `AGENTS.md` (agenda item 3): should this route to MCP instead (if `AbletonMCP`/LOM can do item selection/placement — not yet checked), or should `AGENTS.md` just say "not supported, don't attempt" for the UIA path here?

### Scenario C — "student compares two takes via a solo tour"

- Already effectively traced via agenda item 1's live test. Two viable paths:
  - `orchestrate.sh ... solo_one --tracks A B` — the intended path. Built-in per-track loop, **one screenshot per track** (seq-numbered), so the student sees each take isolated in its own captured image.
  - Direct `automate_ableton_task.py --task solo_tour --tracks A B --live` — works (verified live, item 1), but **zero screenshots** — useless for a teaching flow where the student needs to _see_ each take.
- Chain: clean **only if the orchestrator's `solo_one` loop path is used**; the standalone `solo_tour` CLI path is a trap for this use case specifically — it looks like the "compare tracks" primitive by name, but produces no visual record. Worth flagging explicitly for `AGENTS.md`: an agent naively reaching for `solo_tour` because it matches "solo tour across tracks" in the task catalog would silently produce a screenshot-less run. `AGENTS.md` should point this scenario at `orchestrate.sh ... solo_one` by name, not just "solo tasks" in general.

### Root-cause follow-up — why the gaps exist, and whether avoidable

Prompted by a direct question: not just _what's_ possible/impossible, but _where exactly_ the shortfall is in the code, and whether it could have been avoided. Verified by inspecting an actual dump file (`scritps/dumps/ableton_uia_20260804_083419_sounds.json`), not just reading function bodies.

**Scenario B (browser item selection / drag-drop) — root cause:**

- Individual browser items **do exist** in the UIA tree today — e.g. the Sounds list contains real `DataItem` nodes with real names (confirmed: `"3D Reso Percussion.adg"`, `"5ths Detuned Pad.adv"`, etc.). So this isn't "UIA can't see it."
- The actual blocker: every one of these `DataItem` nodes has an **empty `automation_id`** — checked directly in the dump. The entire existing control-lookup mechanism, `resolve()` in `automate_ableton_task.py`, is built exclusively around looking up controls **by `automation_id`** (see its docstring: `"Resolve one control by automation_id, right now, freshly"`). Browser items structurally cannot be found this way — a name-matching lookup strategy would be needed instead, and none exists in the codebase.
- Compounding factor: the list's own label says "Sounds List, 1001 Items," but the dump's tree only contains **22** child nodes — i.e. UI virtualization (the same phenomenon already documented in the README's "Lessons learned") applies here too. Reaching an arbitrary item would additionally require scroll-and-rescan logic that doesn't exist yet either.
- **Was it avoidable?** Split judgment:
  - _Item selection_ (click/select a specific browser item) looks plausibly buildable using the project's existing patterns (fresh resolve, verify-after-action, virtualization-aware rescan) — it just needs a name-based lookup function that doesn't exist yet. Not fundamentally hard, just never attempted.
  - _Drag-and-drop placement onto a track/slot_ is a genuinely harder problem on top of that: `pywinauto`'s drag simulation is known to be unreliable against custom-drawn, virtualized UI like Ableton's, and the drop target (`Track[N].Slot[M]`) has the same virtualization exposure as the source item.
  - Searched all 5 docs (`README.md`, `phased_plan.md`, `screenshot_orchestration_analysis.md`, `ableton_ai_educational_risk_framework.md`, `opencode-ableton-mcp-setup.md`) for any mention of browser item selection or drag-drop scope — **zero hits everywhere.** This was never a deliberate, documented scope decision (unlike, say, the Phase 2 solo*one/solo_click granularity question, which \_was* explicitly raised and deferred in `phased_plan.md`). It was simply never reached, not consciously excluded.

**Scenario C (`solo_tour` screenshot trap) — root cause:**

- Not a technical limitation at all — an **architectural blind spot** from combining two independently reasonable decisions with no link between them:
  1. `task_solo_tour()` was kept as a standalone CLI entry point for backward compatibility after the Phase 2 `solo_one` split (its own docstring says so).
  2. `take_shot.sh` was wired to be callable only from inside `orchestrate.sh` (also a reasonable choice on its own — keeps screenshot capture centralized).
  - Nothing connects these two facts anywhere in the code or in `--list-tasks` metadata. A caller (human or agent) has no way to discover "this specific task, if run standalone, will silently produce zero screenshots" short of already knowing the codebase's internal wiring.
- **Was it avoidable?** Yes, comparatively easily — two low-cost fixes that don't require solving anything new:
  - Add a `"screenshot_capable": false` (or similar) field to `solo_tour`'s entry in the `--list-tasks` JSON registry, so any caller (including an `AGENTS.md`-following agent) can check before choosing a task.
  - Or: have `task_solo_tour()` itself warn/refuse when invoked outside an `orchestrate.sh`-managed run, mirroring the guard `orchestrate.sh` already applies from its own side.
- **Action item for later code work:** flag this as a concrete, low-effort fix candidate — not filed as its own agenda item yet, but worth surfacing when we get to code changes (agenda items 5/7 or general cleanup), since it's cheap to fix and actively misleading as-is.

---

## 3. Decide what's out of scope for v1 `AGENTS.md`

**Status: DONE**

**2026-08-05 — code audit & risk analysis (`uisato/ableton-mcp-extended` inspection):**

Evaluated whether the 3 main UIA gaps (browser item selection/drag-drop, clip launching, device parameters) should fall back to MCP in `AGENTS.md` or be documented as _"not supported in v1"_.

- **Code Audit of MCP Server (`uisato/ableton-mcp-extended`):**
  - Inspected `_set_device_parameter()` in `AbletonMCP_Remote_Script/__init__.py` directly. Confirmed it executes `param.value = raw_value` and returns `{"new_value": round(clamped, 4)}`. **It never re-reads `param.value` from Ableton after writing.** It echos the calculated target value regardless of whether Ableton accepted, clamped, or rejected the change. This guarantees a 100% false-positive "success" response.
  - Inspected `_resolve_device()`. Confirmed track resolving uses `self._song.tracks[track_index]` (Live Object Model array order). In projects with collapsed/hidden group tracks, LOM array indexing diverges from visible 0-based Session View track rendering (`SessionView.Track[N]`).
- **Screenshot Coordination Risk:**
  - `take_shot.sh` is technically callable standalone (`./take_shot.sh <lab_dir> <seq> <description>`), allowing screenshot capture after MCP calls.
  - However, MCP calls produce no `EVENT:` JSON stream, risking `seq` counter collisions and generating screenshots labeled on unverified trust—defeating the core project goal of grounded verification.
- **Decision & Rule for `AGENTS.md`:**
  - **Do not blindly fall back to MCP for these gaps in v1.**
  - If MCP is used for device parameters or browser loading, it **must be paired with an explicit post-write read-back verification call** (reading the state back via MCP or UIA), rather than accepting MCP's unverified response ack.
  - Final arbitration policy details are deferred to Item 8 (UIA-vs-MCP arbitration testing).

---

## 4. Decide the screenshot-granularity policy for v1

**Status: DONE**

**2026-08-05 — code audit & decision (user + AI, this session):**

- **Code audit finding:** `orchestrate.sh`'s `run_one_task()` currently takes **one** screenshot per task run, and derives its label from only the **last** `EVENT:` line carrying a `label` field (see `orchestrate.sh` lines ~179-181: `grep '^EVENT: ' ... | tail -n 1`). Confirmed concretely against `task_arm_track()` (Scenario A, agenda item #2), which has two real sub-steps (arm checkbox, then Monitor→In click) but produces a single final screenshot labeled only from the second sub-step.
- **Infrastructure already in place:** `automate_ableton_task.py` already emits granular `action_start`/`action_result` events (with per-substep `label`) for every `click_by_id()`/`set_checkbox_by_id()` call (lines ~356-487). The data needed for finer-grained screenshots already exists in the `EVENT:` stream — closing this gap is a consumer-side (`orchestrate.sh`) change, not an engine-side one.
- **Decision: per-sub-click screenshot granularity.** Accept the added cost (more screenshots, more complex `seq` counter handling, `desc` derivation needs to key off each event as it happens rather than the last one) in exchange for closing V2's core gap — showing the student *how* an outcome was reached, not just the outcome. This directly matches the project's stated grounding standard in `context.md`.
- **Scope note:** this only materially changes behavior for `SINGLE_ACTION_TASKS` with more than one actual sub-step (e.g. `arm_track`). Tasks that are already a single action (e.g. `set_tempo`) are unaffected in practice.
- **Sequencing agreed with user:** decision recorded now; actual implementation deferred to **Item #7**, in agenda order (after #5 and #6), rather than jumping ahead. Item #7 is no longer conditional — it is now a committed follow-on to this decision, not an "if #4 chose fix it" branch.

---

## 5. Wire `keyboard_shortcuts.py` into `click_by_id()` call sites

**Status: NOT STARTED**

---

## 6. Baseline-test OpenCode's default tool routing with NO `AGENTS.md`

**Status: NOT STARTED**

---

## 7. (If #4 chose "fix it") Implement per-click screenshot capability

**Status: NOT STARTED**

---

## 8. Define and codify the UIA-vs-MCP arbitration policy

**Status: NOT STARTED**
