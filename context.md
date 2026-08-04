# Context handoff: Ableton Session View UI-automation project

This file is written by Claude, for Claude, to restore session context.
**STATE is overwritten each session — it should always reflect only the
current truth, never a history of how we got there.** LOG is append-only
and holds the reasoning/investigation trail, kept compressed. When in
doubt about what's true right now, trust STATE, not LOG.

---

## STATE (current truth — overwrite this section each session)

### Goal
AI-agent-controllable Ableton Live via Windows UI Automation (pywinauto).
**Claude cannot run pywinauto/Ableton — Linux sandbox, no Windows/Live
access.** All real-world testing is done by the user on their Windows
machine; terminal output pasted back is ground truth over any theory
Claude proposes.

### Files
| File | Role | Status |
|---|---|---|
| `dump_ableton_pywinauto.py` | Read-only tree dump. Canonical `find_ableton_window()` + `ensure_window_ready()`, imported by the other two. | CONFIRMED |
| `automate_ableton_task.py` | Live deliverable — acts on Live (click/type). Source of `build_automation_id_index()`. | CONFIRMED (solo_tour path); `click_by_id()` escalation ladder (Mouse → Keyboard → Human instructions, no MCP tier — see below) CONFIRMED against real Ableton (arm_track, Track[1].Monitoring=In verified clean on first click, screenshot-matched). `task_arm_track` baseline handling still NOT hardened (see Open Items). |
| `dump_ableton_states.py` | Switches Ableton between named states, dumps each. | CONFIRMED — Session/Arrangement, and all six Browser categories (`sounds`, `instruments`, `drums`, `audio_effects`, `midi_effects`, `plugins`), verified via `--states all` in one run. |
| `grep_dump.py` | Stdlib substring search over a JSON dump. | CONFIRMED |

### automation_id scheme (confirmed structural IDs)
```
SessionView.Track[N].Mixer.Arm                       CheckBox
SessionView.Track[N].Mixer.Activator                 CheckBox (mute)
SessionView.Track[N].Mixer.Solo                      CheckBox
SessionView.Track[N].Mixer.Monitoring.Buttons[0..2]  RadioButton (In/Auto/Off)
SessionView.Track[N].Mixer.Stop                      Button (clip stop)
SessionView.Track[N].Slot[M]                         Group (clip slot) -- NOT YET EXERCISED
SessionView.ReturnTrack[N].Mixer.*                   same shape, return tracks
Transport.Tempo                                      Slider
Transport.Play / Transport.Stop                      assumed by pattern, not independently confirmed
```
**Correction (session 4, from a real dump already in `scritps/dumps/`):**
`Transport.Play` is a confirmed `CheckBox` (toggle-readable, same as Solo/
Arm); `Transport.Stop` is a confirmed plain `Button` (momentary, no toggle
state of its own — only indirectly verifiable via `Transport.Play` reading
`False` afterward). `Monitoring.Buttons[0..2]` also independently confirmed
`RadioButton` from the same dump. Not yet acted on: `task_solo_tour`'s
`Transport.Play`/`Stop` calls still pass `verify=None` deliberately — folding
in real verification there was explicitly scoped OUT of session 4 to keep
the `click_by_id()` hardening isolated and separately testable. Open for a
future session.
Test project: Track[0..3] = MIDI/Audio, ReturnTrack[0..1] = A-Reverb/B-Delay.

Browser Sidebar `DataItem` nodes carry **no automation_id** (confirmed via
grep_dump.py) — matched by `(control_type, name)` instead; DFS returns the
outermost of 3 identically-named nested nodes, confirmed to be the real
clickable target.

### Open items (not started / not hardened)
- ~~`click_by_id()` has no post-click verification~~ — **DONE, session 4.**
  Implemented as a 3-level escalation ladder (Mouse → Keyboard shortcut →
  Human instructions). No MCP/LOM tier: this codebase has no MCP bridge at
  all (that's Project 2's mechanism, not this one's), so a 4th level would
  be dead code, not real design — see LOG for the full reasoning. Verified
  two ways: (1) stub/mock control-flow tests (retry-then-succeed, exhaust-
  then-raise, dry-run no-ops, keyboard level actually invoked) — all pass;
  (2) real run against Ableton (`arm_track --live`), Track[1].Monitoring=In
  verified clean on the first click, cross-checked against a screenshot
  (Monitor="In" highlighted, Arm lit, matching the terminal's silence on
  warnings). `keyboard_shortcut` param exists but no call site populates it
  yet — deliberately, since neither the manual PDF nor a keyboard-shortcut
  index has been consulted yet (see item 4 below); filling one in from
  memory would violate the project's own "don't guess" rule.
- `task_arm_track` doesn't capture/print a baseline the way `solo_tour`
  does. Unchecked whether it needs to (Arm may not require restoration).
- Clip launching (`SessionView.Track[N].Slot[M]`) — visible in tree dumps,
  never clicked/exercised.
- Device parameters — not started.
- **New (session 4, from pressure-testing the tool-selection table):** no
  automation_id anywhere in this project's scheme exposes "which track is
  currently selected." This makes Keyboard-tier actions unusable for any
  track-scoped control (Arm/Solo/Mute) even in principle, since Ableton
  keyboard shortcuts are typically scoped to the selected track and there's
  currently no way to verify that precondition. Not investigated yet —
  don't assume it's absent from the UIA tree entirely, just absent from
  what's been indexed/dumped so far.

---

## RELATED PROJECT (Project 2: Ableton via OpenCode + `ableton-mcp-extended`)

A **separate, parallel project**: OpenCode (WSL) talking to
`ableton-mcp-extended` (https://github.com/uisato/ableton-mcp-extended),
an MCP server bridging to a Remote Script inside Ableton over a TCP
socket — a different control mechanism from this project (LOM writes via
MCP vs. UIA tree-walking + click simulation here). It is a **tutorial/
curriculum generator**: OpenCode drives Ableton live while teaching a
beginner interactively; `take_shot.sh` screenshots each step afterward to
build a `walkthrough.md`.

### Knowledge status
Read directly (not secondhand): `opencode-ableton-mcp-setup.md`,
`take_shot.sh`, `EVAL_01.md`, `EVAL_02.md`, `EVAL_03.md`, and a directory
tree of the live repo. **`take_shot.sh` now lives at the root of
`ableton-gui-grounding` itself (merged in, session 5/6)** — it is no
longer "Project 2's tool, available on request," it's a real dependency
of this repo used by the screenshot-orchestration design below.
**Confirmed to exist but not yet read:**
`ableton-live-12-manual-en.pdf` (in `LABS/`) — will request its content
explicitly when a step needs it, not before. **Deliberately withheld by
the user:** `AGENTS.md` — rewritten many times, considered unreliable;
don't ask for it or reason from rule numbers seen in old transcripts.
**Never seen:** `MCP_Server/server.py`, full tool surface beyond what's
exercised in the read transcripts. **Observed, not investigated:** a
`data/` folder in the same repo with unrelated vocal-separation audio
files — noted, not assumed to matter.
**Standing rule (explicit user instruction, applies generally, not just
to this project): don't guess about anything unseen — ask for the file.**

### Setup facts
Architecture: OpenCode ↔ MCP server via stdio; MCP server ↔ Ableton via a
TCP socket opened by an `AbletonMCP` Remote Script (Control Surface). The
WSL/Windows boundary is crossed only at that second hop (mirrored
networking fix applies there, not to this project's pywinauto path).
Known upstream limits: automation-point placement not fully working;
Arrangement View control incomplete (Session View is the reliable surface
here too); community project, not official. Install gotcha: don't run
`pip install -e .` (upstream packaging bug) — install deps directly.

### Screenshot orchestration design (sessions 5–6, FINALIZED — ready to implement)
Full reasoning and comparison matrix live in
`screenshot_orchestration_analysis.md` (repo root, rewritten in session 5
after a wrong premise was disproven by real terminal output — see its own
revision note). This section is the actionable summary; treat the doc as
source of truth for detail, this as the pointer for what to build.

**Key evidence that reshaped the whole design:** `python.exe
automate_ableton_task.py ...`, run directly from inside a WSL shell, drove
the real Ableton window successfully via WSL interop — so `take_shot.sh`
(native WSL bash) and `automate_ableton_task.py` (needs Windows Python)
are both reachable from **one canonical WSL shell**, no OS-detection
branching needed. This eliminated a full shortcoming outright (was #5,
struck through in the doc, not deleted, per the project's "keep the
reasoning trail" rule).

**Recommended design: Option B — orchestrator script.** A new, disposable
WSL bash script that calls `python.exe automate_ableton_task.py ...` and
`./take_shot.sh ...` in sequence, one action → one screenshot. Neither
existing script is modified; the orchestrator owns 100% of the coupling
logic and can be deleted with zero impact on either tool.

**Phased implementation plan (do in this order):**
1. **Phase 0 (highest ROI, do first):** Add structured stdout events to
   `automate_ableton_task.py` (e.g. `EVENT:<n>:<status>` line or
   `--json-events`) — small, additive, backward-compatible. Fixes the
   single highest-leverage shortcoming (fragile stdout-parsing sync) and
   also de-risks timing/mid-transition captures and cross-script
   debugging for free.
2. **Phase 1:** Ship the orchestrator for tasks that are already
   single-action (`arm_track`, `set_tempo`, `probe_*`) — works cleanly
   today, no granularity caveats apply yet.
3. **Phase 2:** For multi-step tasks (`solo_tour` and future equivalents),
   apply Option A — break them into atomic sub-commands — so the
   orchestrator can loop over them with a screenshot after each click,
   not just before/after the whole task.
4. **Phase 3 (as the toolset grows):** Add `--list-tasks`/`--schema`
   introspection or a CI smoke test so the orchestrator can detect CLI
   drift in `automate_ableton_task.py` before it fails silently
   mid-documentation-run.
5. **Throughout:** on any screenshot error, log and continue rather than
   retry-loop against a live Ableton session — avoids leaving
   automate-side state (armed/soloed tracks, running transport) stuck
   mid-sequence.

**Two-consumer split — decides *when* a screenshot fires, orthogonal to
the taxonomy below. Getting this backwards is a real risk (already caught
once, session 6): the taxonomy narrows the *agent's* screenshot use, and
does NOT apply to the student-facing trigger policy.**

| Consumer | What decides whether a screenshot happens |
|---|---|
| Agent (self-verification, this project's own `click_by_id()`) | Bucket — 1/2 use a text/UIA read, screenshot only for bucket-3 blind spots (cost-driven) |
| Student (Project 2's `walkthrough.md` documentation) | Every action, unconditionally — the bucket a control falls into is irrelevant to the student's need to see the actual pixels |

Practically: same `take_shot.sh` capture mechanism serves both, but the
*trigger policy* differs. Project 2's orchestrator (above) fires on every
action unconditionally. This project's own state-verification code should
stay text-first per the taxonomy below and only escalate to a screenshot
for genuine bucket-3 gaps.

### State-verification taxonomy (this project's own concern — agent self-verification only, NOT the student trigger policy above)
Car-dashboard analogy: some Ableton state is a dedicated gauge, some is
inferred from other signals, some has no gauge at all.

1. **True gauges — directly readable, no inference.** Confirmed
   `CheckBox`/`RadioButton` controls via `get_toggle_state()`:
   `Track[N].Mixer.Arm/Activator/Solo`, `Monitoring.Buttons[0..2]`,
   `Transport.Play`. `Transport.Tempo` (Slider) is a *continuous* gauge,
   not boolean. Once a control lands here, no screenshot is ever needed
   to know its state again.
2. **Inferred state — no dedicated property, but derivable from other
   signals.** Session View vs. Arrangement View: no `CurrentView` field
   exists; `dump_ableton_states.py` infers it from whether a fresh dump
   contains any `SessionView.*` id at all. `Transport.Stop` is the same
   pattern — a momentary button with no toggle state of its own, verified
   indirectly via `Transport.Play` reading `False` afterward.
3. **Blind spots — no gauge, nothing to derive it from.** Currently-
   selected track is the confirmed example (already an Open Item above):
   no `automation_id` anywhere exposes track focus, which is exactly why
   Keyboard-tier is blocked for `Solo`/`Arm` (scoped to "selected track,"
   unverifiable beforehand). **This is the only category where a
   screenshot is the agent's correct fallback** — not because screenshots
   are the default verification method, but because buckets 1–2 run out
   here.

### Eval evidence (3 sessions, objectively scored: 5, 5, 4)
Scores were materially better than an earlier "unsatisfactory" framing
suggested — reviewed on evidence, not the label. Confirmed findings:
- **Track-indexing verification gap — the strongest, best-evidenced
  pattern, seen twice in one session (EVAL_03), two different causes:**
  (1) a user manually replicating an MCP-driven step by hand caused
  Ableton to spawn a new track instead of loading onto the selected one —
  undetected for ~700 lines until the user reported no sound; (2) the
  **agent itself** called `create_midi_track(index=-1)`, assumed the new
  track landed at index 3, then ran `set_track_name`/
  `load_instrument_or_effect` against `track_index: 1` (an audio track)
  for three screenshots before `create_clip` errored out. Same root
  cause both times: acting on an index without confirming what's
  actually there. EVAL_01 and EVAL_02 show the *opposite* — strong
  discipline, `get_track_info` called immediately after every
  `create_midi_track` — so this is an inconsistency in an otherwise-
  present habit, not an architectural absence of one.
- **"No read-back for clip notes" — downgraded.** The agent explicitly
  disclosed this limitation in writing rather than silently trusting it;
  not a live silent-trust bug.
- **MIDI pitch numbers vs. UI pad names — confirmed, minor.** Rated MINOR
  in the eval, resolved in 1 turn once flagged.
- **Unrelated:** `take_shot.sh` called once missing its 3rd argument, hit
  its own `Usage:` error, cost a retry turn — a slip, not a design gap.
- **Not yet done:** running the eval prompt on more archived sessions to
  check whether the track-indexing pattern recurs beyond this one
  session, before treating it as fully settled.

### Priority framework for action quality/safety (tentative, six tiers)
Ordered worst-consequence-first:
1. **Safety × reversibility.** Not binary damage/no-damage — score as
   (probability of the wrong action) × (cost, weighted by how hard it is
   to undo). A wrong Solo click (already a real logged bug, `solo_tour`)
   is a trivial one-click undo; a wrong `Save`/`Delete Track` is not.
2. **Verifiability.** Not "did it land right" but "can the system tell
   cheaply, without a human, whether it landed right." An accurate-but-
   unverifiable action is more dangerous long-run than a less-accurate
   but self-checking one, because failures compound silently — exactly
   the shape of the EVAL_03 track-indexing incident (three wasted
   screenshots before the error surfaced).
3. **Transparency to the human, in the moment** — narrower than it first
   looked. Distinct from Pedagogy ("did they learn"): this is "did they
   know what was about to happen before it happened." **Correction from
   this session's evidence review: its safety function only exists if
   the recipient is authoritative enough to catch a wrong plan before it
   executes.** In project 2 the recipient is a novice being taught from
   scratch — checked all three evals directly and found **zero confirmed
   catches came from narration/transparency**; every real catch was
   either the agent's own post-write verification call, a downstream hard
   error that happened to be loud, or the student reporting a broken
   *outcome* after the fact (never an intent-level "that doesn't sound
   right"). So for this project, Transparency's safety value collapses to
   near-zero — what it still legitimately buys is Pedagogy, a different
   tier. This also **answers the "whose trust is authoritative" question**
   flagged earlier: the student is never authoritative here; only
   tool-level state reads are.
4. **Accuracy** (original P2) — clicking X for Y, no damage done.
5. **Pedagogy** (original P3) — method A vs. more-effective method B.
6. **Cost** (latency/tokens) — deliberately last but kept explicit, so it
   can't silently win by default (that's how "driving blind" happens —
   skipping verification because it's cheaper).

Tentative ordering: **Safety (×reversibility) > Verifiability >
Transparency > Accuracy > Pedagogy > Cost.** Still not fully stress-tested
against every action type (e.g. whether spatial/non-spatial is the right
split for everything) — general lens, applies to both projects, not
scoped to one.

### Tool-selection framework: mouse vs. keyboard vs. MCP
Don't rank the three tools globally — each has a **different risk shape**,
so the needed verification differs by tool, not just "verify more":

| Tool | Targets by | Fails by | Risk scales with |
|---|---|---|---|
| Mouse | geometry (coordinate/bounding box) | hitting the wrong element | **UI density** (e.g. a slider next to a knob) |
| Keyboard | context (current focus/selection) | acting on the wrong context | **state ambiguity** (does assumed focus match reality) |
| MCP | symbol (an index/ID) | acting on the wrong index | **identifier ambiguity** (the `index=-1` failure class above) |

**Decision procedure derived from this:**
1. Does the student need to physically repeat this action later? If yes,
   mouse is default regardless of density (pedagogy) — density changes
   *how you verify*, not whether you use the mouse. If no (transport,
   LOM-only bookkeeping), keyboard/MCP costs nothing pedagogically.
2. Mouse actions: low-density targets get standard post-click
   verification; high-density targets make post-click *structural*
   verification **mandatory** — directly motivates hardening
   `click_by_id()` (Open Items above), and pinpoints exactly where it
   matters most.
3. Reversibility gate: trivially-undoable misses get verify-and-proceed;
   destructive/hard-to-undo actions (delete, overwrite, save) need a hard
   pause requiring explicit confirmation before firing — narration can't
   substitute for this when the recipient isn't authoritative (tier 3
   correction above).
4. Keyboard actions verify *outcome state* (e.g. `is_playing`), since
   there's no widget to check against; MCP actions verify the index
   actually resolved to the intended entity (Tier-1 UIA-read-after-write
   design below) — the direct fix for the `index=-1` class specifically.

**Pressure-tested against this project's real `automation_id` scheme
(session 4) — real bounding_rects pulled from `scritps/dumps/`, not
hypotheticals. The table mostly held up, but surfaced real refinements and
one new gap, not just confirmations:**

1. **Density → mandatory verification, confirmed with real numbers.**
   `Track[N].Mixer.Activator`/`Solo`/`Arm` sit in the *same x-column*,
   stacked with only **2–3px vertical gaps** between them (e.g. Track[0]:
   Activator ends y=700, Solo starts y=702; Solo ends 720, Arm starts 723).
   This retroactively explains why `set_checkbox_by_id()`'s
   verify-after-click design was the right call for Solo/Arm specifically
   — not just general caution.
2. **Density is directional; the table's single scalar undersells this.**
   Same-track vertical gap ≈2-3px; same-control across adjacent tracks
   (e.g. `Track[0].Solo` → `Track[1].Solo`) ≈82px horizontal gap. Real risk
   is "wrong function, same track," not "same function, wrong track."
3. **Density ≠ consequence.** `Monitoring.Buttons[0..2]` (In/Auto/Off) are
   touching (~0-1px gaps) — same density class as #1 — but a miss there
   stays within the same semantic family (wrong monitor mode), not a wrong
   track function. Risk is density × how different the neighbor's
   consequence is, which the table collapses into one row.
4. **Absolute target size is a separate axis from neighbor-proximity
   density.** `Mixer.Stop` (clip stop) is only 15×16px but spatially
   isolated (~270px from the nearest other control) — small-target risk
   with no crowded neighbor, a case the table's density framing doesn't
   name.
5. **Sliders don't fit the Mouse row's stated failure mode.**
   `Transport.Tempo` fails by landing on the *right* element with the
   *wrong value* along its axis, not "the wrong element" — a distinct
   failure mode with no row in the table.
6. **New gap, not just a refinement: the Keyboard row assumes a
   verifiable "current focus/context," but no automation_id anywhere in
   this project's scheme exposes "which track is currently selected."**
   Ableton keyboard actions are typically scoped to the selected track, so
   Keyboard-tier is currently *unusable* for any track-scoped action
   (Arm/Solo/Mute) here — not just unused. **New open item, added below.**
7. **MCP row untestable directly (no MCP in this codebase) but
   cross-validated by Project 2's real eval evidence** — "fails by acting
   on wrong index" is exactly the track-indexing bug pattern already
   confirmed twice in EVAL_03.

### Escalation ladder — PRIORITY FOR NEXT SESSION
User wants no single mandatory solution path for any action — if a
method fails, fall to the next one; the lesson never stops on one failed
method. This is the actual fix for `click_by_id()`'s missing verification
(Open Items above), not just an added check:

1. **Mouse** — default, if pedagogically valuable and not high-density
   (per the tool-selection framework above).
2. **Keyboard shortcut** — only if a well-known, unambiguous shortcut
   exists; verify via outcome state after.
3. **MCP / direct LOM call** — if available; verify via structural
   read-after-write (Tier-1 design below).
4. **Explicit human instructions** — last resort. Must be executable with
   **zero prior UI familiarity**: named menu paths and named states only
   ("Go to menu Y, select X, uncheck the checkbox if present, click
   Apply, then Save"), never relative/visual description ("top right,
   orange arrow icon") — generalizes the tier-3 finding that a novice
   can't disambiguate a vague visual cue either. Must end with an
   explicit request for confirmation ("tell me once done, or if you hit a
   problem").

**Rules that apply regardless of level:**
- Every escalation past level 1 gets logged as an investigation note (why
  did the preferred method fail — missing `automation_id`? hidden/
  disabled element? a virtualization-class bug like the one already fixed
  via `ensure_window_ready()`?) — a future improvement lead, not just a
  bypass.
- Failure at any level is a reason to fall to the next level, never a
  reason to halt. Named failure mode to avoid (observed in project 2):
  the agent sending the student on a vague visual scavenger hunt ("look
  here… no, not that, over there") — level 4's protocol exists
  specifically to prevent this.

**Reference layer — consulted *before* any level-to-level jump, not a 5th
level itself:**
- `ableton-live-12-manual-en.pdf` (confirmed to exist, not yet read) —
  check for a documented alternate path before escalating past level 1/2.
- Keyboard-shortcut index — **proposed, not built yet** (future-session
  task): a searchable command→shortcut file so level 2 stops depending on
  the agent's possibly-unreliable memory and does a real lookup instead.
- Rule: before any ladder jump, check the relevant reference resource
  first, so escalation is evidence-based ("checked the manual, no
  alternate path, escalating to MCP") rather than an unexplained fallback.

### Two-tier verification design for MCP writes (proposed, not committed)
- **Tier 1 (cheap, structural):** after any MCP write targeting something
  by index, read the corresponding UIA region (e.g. `SessionView.Track[N]`:
  name, is_midi/is_audio, device presence) before claiming success. No
  vision model needed — `automation_id`s give structural ground truth.
  This is serial (MCP writes, same agent turn triggers a UIA read as its
  next step), not concurrent, so it doesn't trigger the "two channels
  could race" concern — that would only apply to a genuinely concurrent
  design, not proposed.
- **Tier 2 (expensive, only when tier 1 can't see it):** individual clip
  notes are custom-drawn with no per-note `automation_id`. For that narrow
  case only, fall back to `take_shot.sh` + a vision-model read of the
  piano roll.
- **Explicitly NOT proposed:** verifying every action — that reintroduces
  the "Efficiency: some waste" problem already flagged once in the evals.
  Scope to the one confirmed high-risk category (index-targeted actions).
- **Not yet pressure-tested:** window-focus/maximize state at
  verification time — this project already solved that exact failure mode
  once (`ensure_window_ready()`); the verification layer needs to reuse
  it, not rediscover it.

### Next session — open threads, ask the user which, don't assume
1. ~~Finish the escalation-ladder implementation for `click_by_id()`~~ —
   **DONE, session 4** (see Open Items above).
2. Run the eval prompt on more archived sessions — **user explicitly said
   skip this, not needed** (session 4). Not being pursued unless the user
   raises it again.
3. ~~Apply the tool-selection decision table to this project's real
   `automation_id` scheme~~ — **DONE, session 4.** Pressure-tested against
   real bounding_rects (not hypotheticals); see the tool-selection
   framework section above for the 7 findings (density is directional,
   density≠consequence, sliders don't fit the Mouse row's failure mode,
   and a new gap: no "selected track" read exists anywhere in the scheme).
4. **Build the keyboard-shortcut index** referenced in the escalation
   ladder's reference layer. Now has a concrete first consumer:
   `click_by_id()`'s `keyboard_shortcut` param exists and is wired up, but
   no call site has ever populated it (deliberately — nothing's been
   confirmed against the manual or an index yet).
5. **Broader integration planning** (deferred, lower priority than the
   above): where the two projects overlap/complement beyond the
   verification-layer idea already covered.
6. ~~Screenshot orchestration design for Project 2~~ — **DESIGN FINALIZED,
   sessions 5–6.** See "Screenshot orchestration design" and "State-
   verification taxonomy" sections above. **Not yet implemented in code**
   — next session's actual work is Phase 0 (structured stdout events in
   `automate_ableton_task.py`), per the phased plan above. This is now an
   implementation task, not an open design question.
7. **F1 probe off-by-one question (session 5, still unresolved):**
   `probe_keyboard_activator` confirmed Track[0].Activator toggled
   on→off, but didn't rule out a neighbor track flipping instead. Proposed
   fix (not yet run): extend the probe to read `Track[0..3].Activator`
   before/after the F1 press — a bucket-1 structural check per the
   taxonomy above, no screenshot needed. Still open, pick up whenever the
   user wants to close it.

User explicitly does not want to commit to one integration approach —
evaluate each idea on its own merits. **No implementation work on a
combined cross-project approach yet — still evidence-gathering/planning**,
except for item 1 above (scoped to this project's own file, done) and
item 6 above (design finalized, code work starts next).

---

## LOG (append-only history — compress old entries, don't delete lessons)

**Bug: `descendants(auto_id=...)` doesn't exist.** pywinauto 0.6.9's
`build_condition()` only accepts process/class_name/title/control_type/
content_only. Fixed with a manual recursive `.children()` walk to build
an automation_id index.

**Bug: `descendants(control_type=...)` (single FindAll query) returned
nothing** against Ableton's deep custom-drawn tree. Manual recursive walk
works; never proved FindAll is *always* broken here, just that the
replacement works.

**Bug: UI virtualization.** Indexed automation_id count varied 51/60/201
across runs depending on window minimized/backgrounded/maximized state —
not a lookup bug, elements weren't rendered. Fixed with
`ensure_window_ready()` (restore, focus, maximize) before every run;
consolidated into `dump_ableton_pywinauto.py` as the single canonical copy
so `automate_ableton_task.py` and `dump_ableton_states.py` can't drift.

**Bug: stuck-soloed track (CLOSED).** `solo_tour` left track 1 soloed
after a run. Root cause: track 1 was already soloed *before* the run
(leftover from an earlier broken run) — the read and click were both
reliable the whole time; the bug was trusting an unverified baseline as
"the state to restore to." Fixed: `solo_tour` now prints captured
`original_state` up front; added `read_solo_states` diagnostic task.
Confirmed fixed with a clean baseline + real `--live` run, user-verified.
**Lesson generalized to the whole project: verify-after-every-action, and
print/distrust captured baselines rather than silently trusting a
snapshot.**

**dump_ableton_states.py, session/arrangement switching (CONFIRMED,
earlier session).** Tab toggles views; detected via whether a fresh index
contains any `SessionView.*` id (no dedicated UIA button exists). Verified
against real app: Tab press landed, dumps showed genuinely different
content (`Group: "Session"` vs `Group: "Arrangement"`).

**dump_ableton_states.py, Browser category switching (CONFIRMED).** First
test (`--states sounds instruments`) only proved the `instruments` leg —
`sounds` was already selected going in, so that click was indistinguishable
from a no-op. Re-ran `--states instruments sounds` to force a real
transition both ways; tree label + item count + content all changed
correctly in both directions. **Lesson: a test where the starting state
already matches the target proves nothing — always force a state change
before calling a transition confirmed.**

**dump_ableton_states.py, `--states all` preset added and CONFIRMED.**
Ran against the real app: all 8 dumps written (session, arrangement, all
6 browser categories) with no crash, tree label + item content matched
the requested category in every case. **The whole `dump_ableton_states.py`
file is now fully confirmed, no remaining unverified paths in it.**

**Verified pixel-accuracy of an early uiautomation-based (non-pywinauto)
dump against a screenshot** — closed, no issues, not revisited since.

**RELATED PROJECT investigation history (compressed — see STATE section
above for current understanding, this is the trail of how it was built).**
Read the setup doc + `take_shot.sh`, then three real OpenCode transcripts,
to post-mortem concrete failures rather than reason abstractly — found the
track-indexing pattern, MIDI-number/pad-name confusion, and a disclosed
(not silent) clip-notes read-back limitation. Ran the eval prompt on those
3 sessions; scores (5, 5, 4) came back better than an earlier
"unsatisfactory" label suggested, and the eval surfaced a second,
agent-side instance of the track-indexing bug I'd missed on my own first
read — sharpening rather than repeating the original finding. From there,
worked through: a spatial-vs-non-spatial framing for why the mouse felt
pedagogically better (visible on-screen locus vs. MCP's "panel appears out
of nowhere" complaint); the six-tier priority framework, including a
same-session correction after re-reading the raw evals directly (novice
students don't actually catch errors via narration — only via automated
self-verification or after-the-fact symptom reports, which demoted
Transparency's safety role and resolved the "whose trust is authoritative"
question); the mouse/keyboard/MCP risk-shape table and decision procedure;
and the escalation-ladder design plus its reference layer, prompted by the
user sharing a real directory tree of project 2's repo (which is where the
manual PDF's existence was confirmed). Full current-state detail lives in
the STATE section above — this entry exists only to preserve the order
ideas were tested/revised in, per the "log the reasoning trail" rule.

---

**Session 4: `click_by_id()` escalation ladder implemented and CONFIRMED.**
Scoped as a 3-level ladder (Mouse → Keyboard shortcut → Human
instructions), deliberately with NO MCP/LOM tier — this codebase has no
MCP bridge at all (only Project 2 does), so a 4th level would be dead
code padding out the design, not a real one. Verify callback added as a
first-class param (`verify: Callable[[], bool] | None`); `verify=None` now
prints an explicit `[warn]` instead of silently clicking-and-trusting.
`task_arm_track`'s `Monitoring.Buttons[0]` call given a real `verify` using
`get_toggle_state()`, since a dump already in the repo confirmed it's a
genuine `RadioButton`. `task_solo_tour`'s `Transport.Play`/`Stop` calls
deliberately left `verify=None` — explicitly scoped out of this session to
keep the change isolated, even though the same dump also showed
`Transport.Play` is a real `CheckBox` and could be upgraded the same way
later (see automation_id scheme section above).

Caught one real mistake before shipping: first draft used
`window.send_keystrokes(...)` for the keyboard level. That's a real
pywinauto method, but on `HwndWrapper` (the old win32 backend) — not
`UIAWrapper`, which this project uses throughout. Downloaded pywinauto
0.6.9's actual source (matches the version already confirmed elsewhere in
this project) rather than trusting memory, confirmed `type_keys()`
(`BaseWrapper`) is correct, fixed it before it reached the user. Direct
instance of the project's own "verify, don't guess" principle applied to
writing the automation code itself, not just to Ableton's state.

Verified two ways, in order: (1) stub/mock tests here in the sandbox —
faked `resolve()` and a fake control object, proved retry-then-succeed,
exhaust-then-raise (`EscalationExhausted`), dry-run no-ops, and L2 actually
invoking `type_keys()` all work — pure control-flow, no pywinauto needed;
(2) real run on the user's Windows machine (`arm_track --tracks 1 --live`),
terminal showed `[click L1/mouse] Track[1].Monitoring=In` with no `[warn]`
following it, then a screenshot cross-check showed Track 2 (index 1) with
Monitor="In" highlighted and Arm lit — screen, `verify()`, and terminal all
agreed. This is the strongest confirmation this project's methodology can
produce (real UIA read-back matched against a real screenshot), closing the
one thing the stub tests couldn't prove: that the control-type assumptions
(RadioButton, toggle-readable) hold against the live tree, not just on paper.

User explicitly asked to skip item 2 (re-running the eval prompt on more
Project 2 sessions) this session — not a decision to abandon it, just not
prioritized right now.

**Sessions 5–6: screenshot orchestration + state-verification taxonomy,
FINALIZED (compressed — see STATE sections above for the actionable
result).** Session 5 opened on a WSL/pywinauto dependency failure; the
user's own back-to-back terminal output (`python` fails, `python.exe`
works, same WSL shell) disproved the original analysis doc's premise of
two environments needing active OS-detection bridging — doc rewritten,
one full shortcoming (cross-OS detection) eliminated by evidence, not
just mitigated, six of eight original shortcomings preserved unchanged.
Session 6 (this export) then asked the broader question — is there a
text-based, dashboard-style way to know Ableton's state at all, car-
analogy-driven — which produced the 3-bucket taxonomy (true gauges /
inferred state / blind spots). First pass wrongly framed screenshots as
narrowing to bucket-3-only across the board; user corrected this
mid-session: the taxonomy governs *agent* self-verification only, while
Project 2's student-facing `walkthrough.md` needs a screenshot after
every action unconditionally, regardless of bucket — an orthogonal
"who's the consumer" axis, not a refinement of the same rule. Both now
recorded as separate, clearly-labeled sections in STATE so a future
session doesn't re-merge them the way this one initially did.

**Session 4 (cont'd): tool-selection table pressure-tested against real
geometry.** Pulled actual `bounding_rect`s for Activator/Solo/Arm/
Monitoring.Buttons/Stop/Slot/Tempo straight from `scritps/dumps/
ableton_uia_..._session.json` rather than reasoning abstractly. Table
mostly held up but produced real refinements, not just confirmations: (1)
Activator/Solo/Arm share an x-column with 2-3px vertical gaps — hard
numbers behind the already-existing verify-after-click design; (2) density
turned out directional (2-3px within-track vs 82px across-track) — the
table's single scalar undersells this; (3) density≠consequence — the
Monitor radio buttons are equally dense but a miss stays in-family, unlike
a miss between Activator/Solo/Arm; (4) absolute target size (Stop, 15×16px)
is a separate risk axis from neighbor-density; (5) sliders (Tempo) don't
fit the Mouse row's "wrong element" failure mode at all — they fail by
wrong value on the right element; (6) **new gap, not just a refinement**:
no automation_id in the whole scheme exposes "which track is currently
selected," which makes Keyboard-tier unusable in principle for any
track-scoped action, not just unused — added as a new Open Item; (7) the
MCP row couldn't be tested with this project's own data (no MCP here) but
is cross-validated by Project 2's already-confirmed track-indexing bug
pattern.

---

## User preferences to keep applying
- Python developer — code-level detail welcome, no need to oversimplify.
- Wants documentation/explanations in Markdown.
- Runs every script iteration on their own Windows machine and pastes raw
  terminal output — treat that as ground truth over any theory proposed;
  be explicit when a theory gets disproven rather than quietly moving on.
- **RELATED PROJECT files are available on request.** Don't assume/guess
  about anything in that project (or generally) — if unsure, ask for the
  file rather than reasoning from assumption.
