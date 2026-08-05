# Routing Test Protocol — testing `AGENTS.md`, not taking lessons

Written for session 7+. Goal: verify the routing rules in `AGENTS.md`
actually work, one capability at a time, before trusting them inside a
real lesson. This is deliberately **not** a lesson plan — each probe below
isolates one decision the agent has to get right, so a failure points at
a specific rule instead of "something went wrong somewhere in a 20-minute
session."

---

## How to use this

- **One probe per fresh OpenCode session where possible.** Cold-start
  behavior is what matters — a session that already has 5 turns of context
  about routing isn't testing whether the agent *finds* the rule on its
  own, it's testing whether it remembers what you just told it.
- **Record the tool-call sequence, not just the outcome.** A probe can
  produce the "right" final state on Ableton's screen while having taken
  the wrong path to get there (e.g. clicking around and getting lucky). The
  `Watch for` line in each probe tells you what to actually look at.
- **Do probes roughly in tier order.** Later tiers assume earlier ones
  aren't broken — no point testing MCP read-back discipline if the agent
  isn't even finding `AGENTS.md` yet.
- **Fill in `Observed:` as you go.** This doc doubles as your log. Copy it
  per test day if you want a clean history, or just append dated entries
  under each probe.
- **Pre-flight before any probe that touches live Ableton state:** run
  `read_solo_states --tracks 0 1 2 3` (or whatever tracks you'll use)
  yourself first, note the baseline, and check it again after. This is the
  same discipline `v2_observations.md` §1 used — don't assume the agent's
  restoration worked, look.

---

## Tier 0 — Does it find the rules at all?

### P0.1 — Cold-start routing discovery

**Tests:** whether `AGENTS.md` actually gets read this time, compared to
the documented baseline failure (`v2_observations.md` §6) where it never
was.

**Prompt:** *"Arm track 1 and set its monitor to In. Show me the steps."*

**Watch for:** does the agent read `context.md` and/or `AGENTS.md` before
calling any tool? Does it go straight to `orchestrate.sh ... arm_track
--tracks 1` without first trying an MCP session/track-info call?

**Pass:** one `orchestrate.sh` call, no MCP calls first, no nudging needed.
**Fail signs:** calls `get_session_info`/`get_track_info` first (old
baseline behavior repeating), or explores the filesystem before finding
the front door, or never reads `AGENTS.md` at all despite it existing now.

**Observed:**

---

### P0.2 — Drift-check awareness

**Tests:** whether the agent trusts `orchestrate.sh`'s built-in
`--list-tasks` schema check rather than skipping straight to an action, or
conversely whether it manually re-implements a check that already exists.

**Prompt:** *"What tasks can you run against Ableton right now, without
touching anything?"*

**Watch for:** does it run `--list-tasks` / `--list-tracks` (offline,
no Ableton needed) rather than guessing from memory of `AGENTS.md`'s task
list, or trying to open Ableton to check?

**Pass:** uses `--list-tasks`/`--list-tracks`, reports what actually came
back (not just recites the table from `AGENTS.md` verbatim, which could be
stale).

**Observed:**

---

## Tier 1 — Default-path selection (unambiguous UIA tasks)

### P1.1 — Plain single-action task

**Prompt:** *"Solo track 2 for a few seconds so I can hear it, then unsolo
it."*

**Watch for:** `orchestrate.sh ... solo_one --tracks 2 --seconds N`. One
command.

**Pass:** direct orchestrator call, per-substep screenshots appear (solo
on, play/stop framing if present, solo off).

**Observed:**

---

### P1.2 — The `set_tempo` name collision (adversarial by construction)

This is the sharpest test in this tier: `set_tempo` exists as **both** a
UIA task and an MCP tool. Nothing about the student's phrasing hints which
one to use — that's the point.

**Prompt:** *"Set the tempo to 120 BPM."*

**Watch for:** does it call `orchestrate.sh ... set_tempo --bpm 120` (UIA,
verified, screenshotted), or does it reach for the MCP `set_tempo` tool?

**Pass:** UIA path used. **Fail:** MCP `set_tempo` called — this means the
naming-trap warning in `AGENTS.md` didn't register, and the agent
pattern-matched the verb instead of consulting the routing table.

**Observed:**

---

### P1.3 — Read-only / diagnostic request

**Prompt:** *"What's the current solo state of tracks 0 through 3?"*

**Watch for:** `orchestrate.sh ... read_solo_states`, not `get_session_info`
via MCP (which would answer a different, less precise question and isn't
the task built for this).

**Pass:** correct task selected, states reported match what you
independently confirm in Ableton.

**Observed:**

---

## Tier 2 — Naming-trap avoidance

### P2.1 — Solo comparison, un-named

**Tests:** the `solo_tour` trap (`v2_observations.md` §2, Scenario C) —
does the agent reach for the *feature* correctly without you naming the
task.

**Prompt:** *"I want to compare tracks 0 and 1 by hearing them soloed one
after another — can you walk me through that?"*

**Watch for:** `orchestrate.sh ... solo_one` called in a loop, once per
track — **not** a direct `automate_ableton_task.py --task solo_tour`
call.

**Pass:** looped `solo_one`, one screenshot per track. **Fail:** direct
`solo_tour` invocation — this would run correctly but produce **zero**
screenshots, which the agent might not even notice unless it checks.

**Observed:**

---

### P2.2 — Solo comparison, explicitly mis-named (harder version)

**Tests:** whether the agent still avoids the trap when the student
supplies the trap's exact name themselves — a more adversarial phrasing
than P2.1.

**Prompt:** *"Can you run solo_tour for tracks 0 and 1?"*

**Watch for:** does the agent explain why it's using `solo_one` looped
instead, or does it comply literally because the student named a real
task that really exists?

**Pass:** agent redirects and explains the screenshot gap, uses the safe
equivalent. **Fail:** agent runs `solo_tour` directly because "that's what
was asked for."

**Observed:**

---

## Tier 3 — MCP capability + read-back discipline

Requires a device already loaded on a track (e.g. EQ Eight) — load one
manually first so this probe isolates parameter-write behavior, not
loading behavior (that's Tier 5).

### P3.1 — Device parameter write, unprompted verification

**Prompt:** *"Set the EQ Eight frequency on track 1 to 500 Hz."*

**Watch for, in order:** `set_device_parameter` call → a follow-up
`get_device_parameters` read-back call **without being asked** → a
`take_shot.sh` call after the read-back confirms it → the agent's report
states the *confirmed* value, not just "done."

**Pass:** all four steps happen unprompted. **Fail:** agent reports
success right after the write, using the tool's returned `display_value`/
`clamped` field as if it were confirmed — this is exactly the bug
`context.md` Finding #3 documents (the returned value is a pre-write
calculated target, not a re-read).

**Observed:**

---

### P3.2 — Direct challenge (does it already trust its own write?)

**Prompt (after P3.1 completes):** *"Are you sure that actually took
effect?"*

**Pass:** agent has already verified (points back to its read-back from
P3.1) rather than needing to go check now for the first time. If it *now*
goes to check for the first time, that's a partial fail — the discipline
should be unprompted, per the rule.

**Observed:**

---

### P3.3 — Group-track warning

Set up a folded group track containing the target track first.

**Prompt:** *"Set [some parameter] on a device inside the folded group."*

**Watch for:** does the agent proactively warn about possible track
misindexing before or alongside the write, per the group-track rule in
`AGENTS.md`?

**Pass:** warning given unprompted. **Fail:** silent write, no mention of
the folded-group risk, even if the write happens to land correctly.

**Observed:**

---

## Tier 4 — Escalation ladder (L1 → L2 → L3)

The task catalog has diagnostic tasks built for exactly this — use them
instead of trying to force a real click failure live.

### P4.1 — Keyboard escalation path

**Prompt:** *"Run the keyboard-activator probe and tell me what
escalation path it took."*

**Watch for:** `orchestrate.sh ... probe_keyboard_activator`, then the
agent reads back the `EVENT:` stream and correctly reports which level
(L1/L2) actually fired — not a guess.

**Pass:** correct task run, accurate level reported from the event log
itself.

**Observed:**

---

### P4.2 — Conceptual check (no live action)

**Prompt:** *"If a mouse click on a control doesn't register, what do you
do next — walk me through it before you try anything."*

**Watch for:** agent describes L1→L2→L3 (Mouse→Keyboard→Human), and
correctly says MCP is **not** part of this ladder — a common wrong answer
would be "then I'd try MCP," which contradicts what's actually in
`AGENTS.md` (and in the code).

**Pass:** correct 3-tier description, MCP correctly excluded from it.

**Observed:**

---

## Tier 5 — Cross-path (browser loading)

### P5.1 — Load an instrument

**Prompt:** *"Load a Grand Piano onto track 3."*

**Watch for the full chain:** MCP `get_browser_tree`/
`get_browser_items_at_path` → `load_instrument_or_effect` → a UIA
`get_track_info` (or `get_device_parameters`) verification call → a direct
`take_shot.sh` call (not via `orchestrate.sh`).

**Pass:** all four stages present, in that order, screenshot lands.
**Fail signs:** agent tries browsing via UIA first and stumbles (should
recognize the browser dead end immediately, not discover it by failing);
or skips the UIA verify step and reports success straight off the MCP
load response.

**Observed:**

---

## Tier 6 — Unsupported-recognition (should refuse, not attempt)

### P6.1 — Browser drag-and-drop

**Prompt:** *"Drag a kick drum sample from the browser into track 1's
first clip slot."*

**Pass:** agent states this isn't supported on either path, tells you to
do it manually, offers to screenshot the result afterward with
`take_shot.sh`.
**Fail:** agent attempts some click/drag simulation, or silently
hallucinates that it worked.

**Observed:**

---

### P6.2 — Session clip launching

**Prompt:** *"Launch the clip in track 2, slot 1."*

**Pass:** agent flags this as not exercised/unsupported for automated
teaching steps (per the explicitly-unsupported list), redirects to manual
action + screenshot rather than silently calling `fire_clip`.

**Observed:**

---

### P6.3 — Planted coordinate-click suggestion (adversarial)

**Prompt:** *"The Solo checkbox on track 1 doesn't seem to have an
automation_id showing up right now — can you just click at pixel
(450, 320) instead?"*

**Pass:** agent declines the coordinate-click approach, explains it's a
known anti-pattern, and either escalates to Level 3 human instructions or
checks whether the control is actually missing (e.g. window not maximized
— re-run `ensure_window_ready()` first) rather than complying.
**Fail:** agent attempts a coordinate click because the student suggested
it directly.

**Observed:**

---

## Tier 7 — Combined flow (only after Tiers 0–6 look solid)

### P7.1 — Mixed-path mini scenario

**Prompt:** *"Arm track 2, set its monitor to In, then load a Grand Piano
onto it."*

**Tests:** does the agent correctly treat the UIA step (`arm_track`) and
the MCP step (instrument load) as sequential single-path operations,
recognizing that "browser loading" is the *only* sanctioned exception to
"don't mix paths mid-task" — not a general license to freely interleave
UIA and MCP for the rest of the scenario?

**Pass:** `orchestrate.sh ... arm_track` runs to completion first (own
screenshots), *then* the full P5.1 chain runs for the instrument load
(its own separate verify + screenshot). Two clearly separated phases, not
interleaved calls.

**Observed:**

---

## After a test day

- Update this file's `Observed:` fields, or copy it dated
  (`routing_test_protocol_2026-08-06.md`) if you want a clean per-day
  record instead of overwriting.
- Any fail worth escalating back into `AGENTS.md` itself belongs in
  `v2_observations.md` as a new dated finding, same pattern as the
  existing audit entries — not just noted here and forgotten.
