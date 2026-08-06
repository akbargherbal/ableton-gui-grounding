# Risks Still Present as of 2026-08-06

This file is the product of a direct audit of the repository's code and
docs (fresh clone of `https://github.com/akbargherbal/ableton-gui-grounding`,
latest commit at audit time: `388f487 Audit`) — not a summary of what
`context.md` claims about itself. Every finding below is verified against
the source file/line, or by actually running the test suite. Ordered from
most to least severe with respect to grounded, step-by-step teaching.

---

## 1. Most severe: the L2 (keyboard) escalation path is effectively dead for Play/Stop

**Location:** `scritps/automate_ableton_task.py`, `click_by_id()` (around
lines 418–438) + the call site inside `task_solo_one()` (lines 756–761).

**What the code actually does:** if `verify=None`, `click_by_id()` returns
immediately after the first L1 (mouse) click — *before* it even checks
whether `keyboard_shortcut` was passed. So passing `keyboard_shortcut`
alongside `verify=None` is dead code; it can never fire.

**Where this actually shows up:** in `task_solo_one()`, the
`Transport.Play` and `Transport.Stop` clicks are called with
`keyboard_shortcut=transport_key` (the Space-bar shortcut, `{VK_SPACE}`)
**but no `verify` is passed** (defaults to `None`). As a result:
- The escalation ladder described in `README.md` ("L1 Mouse → L2 Keyboard
  → L3 Human") **does not actually run** for these two controls, even
  though the code reads as if it were correctly "wired."
- The test `test_click_by_id_verify_none_trusts_l1` in
  `scritps/test_phase0_events.py` implicitly proves this behavior
  (successful L1, no verification, `click_count == 1`, no `escalate`
  event ever emitted) — the project's own test suite documents this
  behavior without anything flagging that it makes `keyboard_shortcut` in
  `task_solo_one` pointless.
- The note on `transport_play_stop` in `keyboard_shortcuts.py` literally
  says: *"NOT live-tested: confirm get_toggle_state(Transport.Play) reads
  correctly right after a Space press before trusting this in a verify
  callback"* — which implicitly assumes a `verify` callback is coming,
  but one was never added at the call site.

**Teaching impact:** every Play/Stop click inside `solo_one` is pure
"click-and-trust" with zero safety net — exactly as `README.md` openly
admits ("Button controls... are clicked and trusted with an explicit
warning — a documented gap, not a silent one"). **However**, the
docstring on `click_by_id()` ("Currently wired at Transport.Play /
Transport.Stop call sites via load_shortcut(...)") gives the misleading
impression that the L2 path is actually functional there, which it is
not. Recommendation: either add a real `verify` for these two controls,
or correct the docstring to state plainly that `keyboard_shortcut` is
currently dead code at this call site.

---

## 2. The project's real operation depends on an external MCP integration that `README.md` doesn't mention and that isn't set up by anything in the active `docs/`

**Location:** all of `ABLETON_AGENT_POLICY.md` (the file renamed to
`AGENTS.md` and actually loaded by the agent runtime via
`build_runtime_env.sh`).

**Fact:** more than half of `ABLETON_AGENT_POLICY.md` is built around a
second, entirely non-UIA path, relying on an external MCP server called
`ableton-mcp-extended` (`uisato/ableton-mcp-extended` on GitHub) that
talks to Ableton over a Remote Script/TCP bridge, covering everything UIA
structurally cannot reach: device parameters (`set_device_parameter`),
loading instruments from the browser (`load_instrument_or_effect`),
tracks/clips, etc. The full routing table exists, the "every MCP write
needs a read-back" rule exists, and even a confirmed code-inspection bug
in `ableton-mcp-extended` itself (`context.md` Finding #3, cited by name)
is used as the basis for a safety rule.

**But:**
- `README.md` **never mentions MCP or `ableton-mcp-extended` even once**.
  It describes the entire project as UIA-only ("no plugin, no Remote
  Script, no MIDI bridge"). This sentence itself now directly contradicts
  the actual operational reality documented in
  `ABLETON_AGENT_POLICY.md`, which explicitly states there is an MCP path
  running through a Remote Script.
- The only setup instructions in the repository for actually connecting
  `ableton-mcp-extended`
  (`docs/archived/v002/opencode-ableton-mcp-setup.md`) are **archived**,
  and `context.md` states explicitly about the archive: *"Archived docs
  are strictly out of scope. Do not read, cite, or treat them as current
  for audit decisions."* In other words, the one document that explains
  how to run half of the actual routing architecture is not treated as
  current.
- `build_runtime_env.sh` (which builds the actual agent runtime folder)
  does not set up or check for `ableton-mcp-extended` in any way — its
  whitelist is UIA-only. So if the MCP server hasn't been configured
  manually outside this repo (by following an archived doc), then half of
  `AGENTS.md`'s rules (the entire second path) would be unexecutable,
  with nothing in any active file pointing that out.

**Impact:** anyone relying solely on `README.md` (exactly what the user
asked to be warned about) will come away with a fundamentally wrong
picture of the project's real scope — believing no non-UIA path exists,
while half of the live agent's day-to-day routing decisions
(per `ABLETON_AGENT_POLICY.md`) are about when to use MCP instead of UIA.

---

## 3. Dangling reference in `take_shot.sh` to a section that doesn't exist in `AGENTS.md`

**Location:** `take_shot.sh`, header comment (around line 65):

```
# ERROR:BAD_SIZE / ERROR:FILE_MISSING — see AGENTS.md's "Two-Pass Tutorial
# Capture" section for how the agent should react to each.
```

**Fact:** there is no section titled "Two-Pass Tutorial Capture" (nor even
the phrase "Two-Pass" or "Two Pass") anywhere in the current
`ABLETON_AGENT_POLICY.md` — verified with a full-text search across the
entire repository, and the only hit is this exact line in `take_shot.sh`.
This section appears to have existed in an earlier version of the agent
policy and was removed or renamed without updating the reference in
`take_shot.sh`.

**Impact:** if the agent (or a developer) follows this pointer looking for
how to handle the error codes `ERROR:MINIMIZED_RESTORE_FAILED` /
`ERROR:FOCUS_FAILED` / `ERROR:BAD_SIZE` / `ERROR:FILE_MISSING`, they will
find nothing in `AGENTS.md` matching that title — a real, currently
existing documentation gap.

---

## 4. Wrong test count in both `README.md` and `context.md`

**Verified by actually running the tests (Python 3, no `pywinauto` or
Ableton needed, exactly as the project itself describes):**

```
$ python3 scritps/test_phase0_events.py   → 14 passed, 0 failed   (correct, matches the docs)
$ python3 scritps/test_orchestrate.py     → 15 passed, 0 failed   (docs say 14!)
```

Both `README.md` ("## Tests" and "## Status": "28/28 tests") and
`context.md` (the `test_orchestrate.py` entry: "14 tests covering
`orchestrate.sh` itself") state **14** tests for `test_orchestrate.py`
and a total of **28**. The actual current count is **15** for this file,
and the correct total is **29/29 passing**, not 28/28. Manually counting
`def test_...` functions confirms 15 in `scritps/test_orchestrate.py`
(the last being `test_drift_check_happy_path_passes_and_proceeds`) —
apparently a test added in a later audit pass without the count being
updated in either file.

**Impact:** low from an operational-safety standpoint, but a direct,
measurable indicator that both files (including `context.md`, which is
meant to be the "single source of handoff truth" between sessions) have
not been updated to reflect the latest actual code changes.

---

## 5. Active-scope docs rely on archived docs as their evidentiary source

**Location:** `ABLETON_AGENT_POLICY.md` (active) directly cites:
- `v2_observations.md §6` and
  `LIVE_TEST/BASELINE_SESSION_session-ses_02cd.md` as evidence that the
  agent "naturally" reaches for MCP before `AGENTS.md`.
- `context.md` "Finding #3" as evidence of the `_set_device_parameter`
  bug.

And `docs/routing_test_protocol.md` (also active, per `context.md`)
repeatedly cites `v2_observations.md §1`, `§2 Scenario C`, `§6` as
behavioral references.

**The contradiction:** `v2_observations.md` itself lives only under
`docs/archived/v002/` — meaning, by `context.md`'s own definition, it is
**out of scope**: *"Archived docs are strictly out of scope. Do not read,
cite, or treat them as current for audit decisions."* The active
documents break the scope rule that `context.md` itself sets, by citing
behavioral evidence (baseline tests, session logs) that cannot officially
be treated as "current" — while that evidence is the only practical basis
for a real routing rule ("UIA-direct is the default, not MCP"). This
doesn't mean the rule is wrong, but that its supporting evidence isn't
officially available to anyone auditing the project today using only the
"active" docs.

---

## 6. Risks already acknowledged in `context.md` that are confirmed still open

Cross-checking the "Open items" section of `context.md` against the
current code confirms all three are unchanged:

1. **Browser-category targeting in `dump_ableton_states.py` remains
   unproven** — it still relies on clicking an outer `DataItem` element
   without confirmation that this actually changes the selected category;
   the file's own docstring still says exactly that.
2. **`keyboard_shortcuts.py` and `keyboard_shortcuts.md` are manually
   synced, not derived from one another** — there is no generation or
   consistency check between the two files; a quick check shows both
   currently hold the same keys, but nothing prevents silent drift on a
   future edit to only one of them.
3. **The directory name `scritps/` (a misspelling of `scripts/`)** is
   still used everywhere (`README.md`, `build_runtime_env.sh`,
   `orchestrate.sh`, both test files) — renaming it now is a multi-file
   operation, and it remains deliberately unfixed.

---

## 7. The "selected track" blind spot remains structurally unresolved

**Location:** `keyboard_shortcuts.py` (`solo_selected_track`,
`arm_selected_track`, `deactivate_selected_track`, `launch_selected_slot`
— all `blocked=True`) and §5 of the risk framework in
`ABLETON_AGENT_POLICY.md`.

**Current state:** Ableton's UIA tree exposes no `automation_id`
revealing which track is currently selected on screen. This is not an
assumption but a confirmed fact in the code itself (no reference to any
such auto_id exists anywhere in the repository). The result: four
practically useful keyboard shortcuts (including firing a clip / arming a
track via selection) are permanently locked (`blocked=True`) and cannot be
unlocked until this gap is resolved — and it is a structural gap in the
accessibility interface itself (Ableton's accessibility tree), not in
this code, so there is no internal fix available. The only mentioned
mitigation (MCP) solves a different problem (writing via the Remote
Script), not the "reading current selection" problem specifically.

---

## 8. None of these findings have been live-verified by whoever audits this file

Per `context.md`'s own constraint: *"the AI Assistant has no direct access
to Ableton/Windows — Linux sandbox only."* All findings above are derived
purely from reading the code/docs and running the test suite (which
requires no Windows). Findings related to actual live Ableton behavior
(everything in section 1, for example) are a direct logical inference
from the code path, **not a live verification** — they should be
confirmed on an actual Windows machine before being fully relied upon,
in the same spirit `context.md` itself recommends for every prior audit
finding.

---

## Quick summary (work priority)

| # | Risk | Severity | Estimated fix effort |
|---|---|---|---|
| 1 | `keyboard_shortcut` dead at Play/Stop (no real L2) | Medium–High (contradicts what the code documents about itself) | Small: fix docstring, or add a real `verify` |
| 2 | README doesn't mention the real MCP path, and its setup doc is archived | High (misleads any new reader) | Medium: promote/update the setup doc to active status + update README |
| 3 | Dangling reference to a nonexistent "Two-Pass Tutorial Capture" section | Low | Very small: update the comment or add the section |
| 4 | Wrong test count (14 stated, 15 actual) | Low | Very small: update the number in both files |
| 5 | Active docs cite archived, out-of-scope sources | Medium (undermines "single source of truth" credibility) | Medium: move the actually-cited parts into an active doc |
| 6 | Three known gaps from `context.md` (browser category, manual sync, `scritps/` typo) | Low–Medium | Varies |
| 7 | "Selected track" blind spot is structural and unresolved | Medium (locks 4 useful shortcuts) | Large: requires a structural fix outside this codebase |
