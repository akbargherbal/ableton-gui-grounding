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
| `automate_ableton_task.py` | Live deliverable — acts on Live (click/type). Source of `build_automation_id_index()`. | CONFIRMED (solo_tour path); `click_by_id()` and `task_arm_track` baseline handling NOT hardened yet (see Open Items) |
| `dump_ableton_states.py` | Switches Ableton between named states, dumps each. | CONFIRMED — Session/Arrangement, and all six Browser categories (`sounds`, `instruments`, `drums`, `audio_effects`, `midi_effects`, `plugins`), verified via `--states all` in one run: each category's `Tree: "<Category> List, N Items"` label + item content matched the requested category. `--states all` preset also confirmed working. |
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
Test project: Track[0..3] = MIDI/Audio, ReturnTrack[0..1] = A-Reverb/B-Delay.

Browser Sidebar `DataItem` nodes carry **no automation_id** (confirmed via
grep_dump.py) — matched by `(control_type, name)` instead; DFS returns the
outermost of 3 identically-named nested nodes, confirmed to be the real
clickable target.

### Open items (not started / not hardened)
- `click_by_id()` (Transport.Play/Stop, monitor RadioButtons) has no
  post-click verification, unlike `set_checkbox_by_id()`. No known bug,
  just inconsistent rigor.
- `task_arm_track` doesn't capture/print a baseline the way `solo_tour`
  does. Unchecked whether it needs to (Arm may not require restoration).
- Clip launching (`SessionView.Track[N].Slot[M]`) — visible in tree dumps,
  never clicked/exercised.
- Device parameters — not started.

### Next session should
No code work in progress on this project's own files right now — active work
has shifted to the RELATED PROJECT comparison/integration task below (see
that section for current status and what's pending). Once that resolves,
functional candidates for this project remain: clip launching, device
params, `click_by_id()` hardening — ask the user which, don't assume.

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

**dump_ableton_states.py, Browser category switching (CONFIRMED, this
session, for `sounds`/`instruments` only).** These edits were written in
a prior session but never run before now. First test
(`--states sounds instruments`) only proved the `instruments` leg —
`sounds` was already selected going in, so that click was indistinguishable
from a no-op. Re-ran `--states instruments sounds` to force a real
transition both ways; tree label + item count + content all changed
correctly in both directions. **Lesson: a test where the starting state
already matches the target proves nothing — always force a state change
before calling a transition confirmed.**

**dump_ableton_states.py, `--states all` preset added and CONFIRMED (this
session).** Added an `ALL_STATES` constant + `--states all` CLI shortcut
expanding to every known state in one command, since the user wanted a
loop over all states without listing them by hand. Ran it against the
real app: all 8 dumps written (session, arrangement, all 6 browser
categories) with no crash, and each browser category's `Tree: "<Category>
List, N Items"` label + item content matched the requested category --
`drums`/`audio_effects`/`midi_effects`/`plugins` (previously untested)
are now genuinely confirmed alongside `sounds`/`instruments`. Minor
observation, not a bug: `drums` and `sounds` happened to show the same
item count (1001) -- coincidental, confirmed by content (drum kit names
vs. sound preset names), not a stale-count issue. **The whole
`dump_ableton_states.py` file is now fully confirmed, no remaining
unverified paths in it.**

**Verified pixel-accuracy of an early uiautomation-based (non-pywinauto)
dump against a screenshot** — closed, no issues, not revisited since.

**RELATED PROJECT investigation (this session, no code touched in this repo).**
Read the MCP project's setup doc + `take_shot.sh`, then read three real
OpenCode session transcripts (one flagged by the user as pedagogically
"unsatisfactory," two earlier attempts at the same module) to post-mortem
concrete failures rather than reason abstractly. Found three real instances
of the same root cause, all evidenced in the transcripts (see RELATED
PROJECT section below for detail): (1) `add_notes_to_clip` is write-only,
no read-back tool exists, agent explicitly stated it couldn't re-verify
notes it wrote; (2) a user manually replicating an MCP-driven step by hand
(double-clicking a drum kit in the browser) caused Ableton to spawn a new
track instead of loading onto the selected one — undetected for ~700 lines
of transcript until the user reported no sound, because the agent had no
way to check rendered UI state against its LOM-level assumption; (3) agent
narrated in raw MIDI pitch numbers (36/38/42) instead of what's actually
rendered (drum-rack pad names), confusing the user until corrected. This
is evidence for, not just theory about, this project's UIA tree serving as
a verification layer for MCP's write-only/blind-to-rendered-UI actions —
see RELATED PROJECT for what's still pending before pursuing that.

**RELATED PROJECT: eval prompt results received and reviewed (this
session).** The 3 sessions from last session's eval-prompt handoff came
back scored 5, 5, 4 — the "unsatisfactory" framing didn't hold up under
blind, evidence-based scoring. Reviewed the outputs and updated the
failure-pattern theory: the eval surfaced a track-indexing bug I'd missed
on my own read (agent itself, not just the user, acted on an unverified
`track_index` after `create_midi_track(index=-1)` and hit a wrong-track
error 3 screenshots deep) — this **sharpens** the verification-layer case
rather than just repeating it, since it shows the same root-cause bug
occurring on the agent's side, not only the user-replication side. The
"no read-back for clip notes" theory was downgraded — the eval found it
wasn't a live issue, just a disclosed limitation. See RELATED PROJECT
section for full detail and current next-step options.

**RELATED PROJECT: integration design discussion (this session, no code,
no approach committed).** User raised two observations from using this
project vs. watching the MCP one: (1) liked watching the mouse actually
move/click, questioned whether keyboard shortcuts might be faster — this
reframed into a spatial-vs-non-spatial distinction (a keyboard shortcut is
just as screen-invisible as an MCP call; the pedagogical value was never
"mouse specifically," it's a visible on-screen locus for spatially
addressable actions); (2) felt the MCP agent was "driving blind," no real
feedback loop — matches the track-indexing pattern already confirmed in
LOG above. Worked out a two-tier verification proposal (UIA read after any
index-targeted MCP write; vision-model+screenshot fallback only for
per-note clip content, which has no automation_id at all) scoped narrowly
to avoid re-introducing the efficiency cost the eval already flagged once.
Confirmed this design is serial (UIA as a sensor after MCP's write, same
agent turn) so it does NOT trigger the earlier-logged "two channels could
race" concern — that concern would only apply to a concurrent design, not
proposed. User was explicit: **do not commit to one integration approach**
— treat this as one candidate among possibly several, evaluated per-idea,
not a decision. See RELATED PROJECT section for full detail.

**RELATED PROJECT: priority framework for action quality/safety (this
session, no code).** User proposed evaluating any action (click, MCP
call, keyboard shortcut) on priority tiers, worst-consequence-first:
Safety > Accuracy > Pedagogy, asked what else belongs. Expanded to six
tentative tiers — Safety (reweighted to factor in reversibility, not
treated as binary damage/no-damage) > Verifiability (new — can the system
cheaply confirm an action landed, distinct from whether it happened to
land correctly; ties directly to the tier-1 UIA-verification design
above) > Transparency-in-the-moment (new — did the human know what was
about to happen before it happened; distinct from Pedagogy, reframes part
of the "MCP panel appears out of nowhere" complaint) > Accuracy > Pedagogy
> Cost (new — latency/tokens, kept explicit rather than omitted so it
can't silently win by default). Ordering is explicitly tentative, not
stress-tested — e.g. Transparency vs. Accuracy ranking still open. Applies
generally, not scoped to one project — a lens for judging both this
project's own click actions and the MCP integration design. See RELATED
PROJECT section for full detail.

---

## RELATED PROJECT (partial, evidence-backed — see status note below)

The user has a **separate, parallel project**: controlling Ableton Live
12 via **OpenCode (running in WSL) talking to `ableton-mcp-extended`**
(https://github.com/uisato/ableton-mcp-extended), an MCP server bridging
to a Remote Script loaded inside Ableton over a TCP socket. This is a
different control mechanism entirely from this project's approach
(Windows UI Automation via pywinauto) — MCP + Remote Script vs. UIA tree
walking + click simulation.

**Status of my knowledge here: PARTIAL BUT EVIDENCE-BACKED**, up from
preview-only. Have now seen: the setup doc, `take_shot.sh`, and three real
OpenCode session transcripts (not just descriptions of the system — actual
transcripts of it running against real Ableton, with real user friction).
Not yet seen: the project's `AGENTS.md` (deliberately withheld by the user —
it's been rewritten many times this project and is considered unreliable/
being redone; **don't ask for it or reason from rule numbers mentioned
inside old transcripts, e.g. "Rule 6," they don't reflect current truth**).
Still preview-only on: the actual `MCP_Server/server.py` code, the full
tool surface beyond what's been exercised in the transcripts I've read.

### What project 2 actually is (clarified this session)
Not just "control Ableton via MCP" — a **tutorial/curriculum generator**.
OpenCode drives Ableton through MCP (LOM-level actions: create track, load
kit, add MIDI notes, fire clip) while teaching a beginner interactively;
`take_shot.sh` screenshots each step afterward to build a `walkthrough.md`
with numbered PNGs for a documentation pass. The MCP server acts and
teaches live; the screenshot pass documents after the fact — it is not a
live verification step during teaching.

### Setup doc facts (still not independently run/confirmed by me)
- Architecture: OpenCode ↔ MCP server via stdio; MCP server ↔ Ableton via
  a TCP socket opened by an `AbletonMCP` Remote Script (Control Surface).
  The WSL/Windows boundary is crossed only at that second hop.
- Tool surface is much broader than this project's current scope: real
  device-parameter read/write (EQ, compressor, reverb values), MIDI note
  transpose/quantize/batch-edit, scene management, clip envelope info,
  browser-path sample/instrument loading, optional ElevenLabs voice-gen.
- Known upstream limits per the doc: automation-point placement flagged
  as not fully working; Arrangement View control listed as planned/
  incomplete (Session View is the reliable surface there too — same as
  this project's current focus); it's a community project, not official.
- Known install gotcha: don't run `pip install -e .` (packaging bug in
  upstream `pyproject.toml`); install deps directly instead.

### Objective eval results (3 sessions scored via the LLM-eval prompt, this session)
Ratings came back **5, 5, 4** — materially better than the "unsatisfactory"
label suggested once evaluated blind, on evidence, without that framing.
This reframes (doesn't discard) the failure-pattern theory below:

- **Confirmed and sharpened — track-indexing verification gap.** The eval
  on session 043d surfaced a bug I'd missed on my own read: during a
  tutorial redo, the **agent itself** called `create_midi_track(index=-1)`,
  assumed the new track landed at index 3, then ran `set_track_name` /
  `load_instrument_or_effect` against `track_index: 1` — an audio track —
  for three screenshots before `create_clip` errored out. This is not the
  user-replication mismatch I'd originally flagged (drum kit double-click
  spawning a wrong track) — it's a **second, distinct instance of the same
  root cause, this time self-inflicted by the agent, not the user.** Two
  independent incidents in one session, same shape: act on `track_index N`
  without confirming what's actually at N first. This is now the strongest,
  best-evidenced case for a UIA verification layer — a `SessionView.Track[N]`
  read after any index-based targeting (agent's own or a user's) would catch
  both variants, not just the user-replication one.
- **Downgraded — "no read-back for clip notes."** The eval did not flag this
  as an issue at all: the agent explicitly disclosed the limitation in
  writing rather than silently trusting it, so it's a documented constraint,
  not a live silent-trust bug. Lower priority than the track-indexing cases.
- **Confirmed, minor — MIDI numbers vs. pad names.** Rated MINOR in the eval
  for session 036c, resolved in 1 turn. Consistent with my original read.
- **New, unrelated to the MCP/UIA theme:** `take_shot.sh` was called once
  with a missing 3rd argument (`short_description`), hit its own `Usage:`
  error, cost a retry turn. An invocation slip, not a design gap in either
  project.

Overall: two of three original theories held up under objective scoring
(track-indexing, MIDI-number jargon); one (no-read-back-for-notes) turned
out to be a non-issue because it was self-disclosed. The track-indexing
pattern is the one worth testing for recurrence across more sessions before
treating it as a settled argument for the verification-layer integration.

### Integration design space (exploratory, this session — no approach committed)
User explicitly does not want to commit to one integration approach yet —
different ideas may suit different situations, evaluate each on its own
merits rather than picking a single unifying design. Two threads opened
this session:

**1. Spatial vs. non-spatial actions — reframes the user's "mouse felt
better, why not test keyboard shortcuts too" question.** The pedagogical
value the user liked in this project (watching the cursor travel to and
click a real element) isn't really "mouse vs. keyboard" — it's that a
*spatially addressable* action (arm this track, click this clip slot) has
a visible on-screen locus the student can learn from and later repeat by
hand. A keyboard shortcut has the same blindness problem MCP has: no
visible screen locus, nothing to watch. This is why MCP's UI "panels
appearing out of nowhere" bothered the user — MCP never simulates any
click/keypress at all; it writes straight into the Live Object Model and
the UI just re-renders. Working principle (not yet implemented): teach
spatially-addressable actions via a real simulated click the student can
watch and repeat; treat non-spatial or setup-only actions (tempo via API,
Spacebar for play/stop) as fair game for a faster, invisible path. Spacebar
specifically flagged as universal enough to hardcode as a shortcut even in
this project, since "seeing where it lives" adds nothing there.

**2. "Driving blind" — the agent has near-zero feedback loop.** MCP's loop
today is: write action → JSON describes the *data-model* result → agent
trusts it, moves on. Nothing sensors "what's actually rendered on screen."
In the 043d session, the only such sensor in the loop was the human,
reporting failures after the fact in natural language the agent then had
to reinterpret — the slowest possible feedback path, and the direct cause
of the ~700-line debugging spiral already logged above.

**Proposed (not committed) fix: two-tier verification, narrowly scoped —**
- **Tier 1 (cheap, structural):** after any MCP write that targets
  something by index (`track_index`, `clip_index` — the exact pattern
  behind both confirmed track-indexing incidents), read the corresponding
  UIA region (e.g. `SessionView.Track[N]`: name, is_midi/is_audio, device
  presence) before the agent claims success. No vision model needed —
  `automation_id`s already give structural ground truth.
- **Tier 2 (expensive, only when tier 1 can't see it):** individual clip
  notes are custom-drawn with no per-note `automation_id` — structurally
  unverifiable through the UIA tree. For that narrow case only, fall back
  to `take_shot.sh` + a vision-model read of the piano roll.
- **Explicitly NOT proposed:** verifying every action. That would hurt the
  bite-sized pacing and re-introduce the "Efficiency: some waste" problem
  the eval already flagged once for an unrelated reason (session 043d).
  Scope verification to the one confirmed high-risk category
  (index-targeted actions); leave low-risk actions (tempo change, view
  switch, a parameter tweak on an already-verified track) as trust-the-
  response, same as today.
- **Resolves an earlier open question, not a new risk:** this design is
  *serial* (MCP writes, then the same agent turn triggers a UIA read as
  its next step) not concurrent, so the "two live control channels could
  race" risk noted earlier doesn't apply here — UIA acts as a sensor, not
  a second simultaneous driver. A real concurrency question would only
  arise under a different design where both act independently at the same
  time; not proposed.
- **Not yet pressure-tested:** what happens if the window isn't
  focused/maximized at verification time — this project already hardened
  that exact failure mode once (`ensure_window_ready()`, LOG above); the
  verification-layer design needs to reuse that, not rediscover it.

### Priority framework for action quality/safety (this session, proposed by user, tentative ordering)
User proposed evaluating any action (click, MCP call, keyboard shortcut)
along priority tiers, worst-consequence-first. Started with Safety >
Accuracy > Pedagogy; expanded this session to six, in tentative order:

1. **Safety** — clicking/calling X while meaning Y, causing damage.
   **Refined this session: not binary — weight by reversibility.**
   Score as (probability of wrong action) × (cost, weighted by how hard
   it is to undo). A wrong Solo click (already logged as a real bug,
   `solo_tour`) is a trivial one-click undo; a wrong `Save`/`Delete Track`
   is not. Same class of indexing mistake, very different severity — the
   current codebase doesn't yet distinguish these.
2. **Verifiability** — new tier, argued to outrank Accuracy. Not just "did
   the click land right" but "can the system tell whether it landed right,
   cheaply, without a human." An action that's usually accurate but
   unverifiable is more dangerous long-run than one that's less accurate
   but self-checking, because the accurate-but-unverifiable one fails
   silently and compounds — this is exactly the shape of the 043d
   track-indexing incident (three wasted screenshots before the error
   surfaced). Directly the argument for the tier-1 UIA-read-after-
   index-write design above.
3. **Transparency to the human, in the moment** — new tier, distinct from
   Pedagogy ("did they learn") — this is "did they know what was about to
   happen before it happened." Reframes the "MCP panel appears out of
   nowhere" complaint as partly this, not only the spatial-click gap
   already logged. Proposed as cheap to satisfy (narrate intent before
   acting) and worth ranking near Safety, since a surprised human can't
   intervene in time if something's about to go wrong.
4. **Accuracy** (user's original P2) — clicking X for Y, no damage done.
5. **Pedagogy** (user's original P3) — method A vs. more-effective method B.
6. **Cost** (latency/tokens) — new tier, deliberately last but explicit
   rather than omitted, so it doesn't silently win by default (that's how
   "driving blind" happens — skipping verification because it's cheaper).

**Tentative ordering, not yet stress-tested:** Safety (× reversibility) >
Verifiability > Transparency > Accuracy > Pedagogy > Cost. Explicitly
flagged as tentative — e.g. still open whether Transparency really
outranks Accuracy, or whether a silent-but-correct action should beat a
narrated-but-slower one. Applies across both this project's own actions
(clicks) and the MCP integration design above (verification tiers) — a
general lens, not scoped to one project.


### Next session
Eval results for the first 3 sessions are in (see the eval-results
subsection above). Design space and priority framework above are both
exploratory only — **user explicitly does not want to commit to
one approach yet**, so don't collapse the ideas above into a single
plan; keep pressure-testing each on its own (e.g. the not-yet-tested
window-focus case for tier 1, whether spatial/non-spatial is the right
split for every action type, or whether the priority ordering itself
holds — e.g. Transparency vs. Accuracy) and let different ideas serve
different situations rather than forcing one unifying design. Open
threads, ask the user which to pursue rather than assuming:
- **Run the eval prompt on more archived sessions** to check whether the
  track-indexing pattern (agent or user acting on an unverified track
  index) recurs, before treating it as a settled argument.
- **Or move to the actual planning task now**, treating track-indexing
  verification as the leading (but singular, 1-session) integration
  candidate: where the two projects overlap, what each does better, where
  they complement (UIA read-after-index-action as the verification layer),
  and remaining integration challenges (WSL2 mirrored-networking only
  affects the MCP path, not this one; whose "trust" is authoritative if
  both act on the same session — the race-condition risk itself is
  resolved for the serial tier-1/tier-2 design above, but would resurface
  under a different, concurrent design).
Do not start implementation work on a combined approach yet either way —
still evidence-gathering/planning.

---

## User preferences to keep applying
- Python developer — code-level detail welcome, no need to oversimplify.
- Wants documentation/explanations in Markdown.
- Runs every script iteration on their own Windows machine and pastes raw
  terminal output — treat that as ground truth over any theory proposed;
  be explicit when a theory gets disproven rather than quietly moving on.
