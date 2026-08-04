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

**To keep evaluation of further archived sessions cheap:** built a
reusable LLM-eval prompt (delivered to user as `session_eval_prompt.md`,
not part of this repo) that scores one transcript at a time against a
fixed rubric (task completion, verification discipline, model-vs-reality
grounding, pedagogical clarity, error recovery, efficiency, internal
consistency) and outputs a comparable structured summary — so future
sessions get evaluated by a separate LLM call instead of full reads in
this context window. User is running it now against the three sessions
above (with the "unsatisfactory" label stripped from the transcript first,
to keep that one's evaluation unbiased) and will bring back the outputs.

---

## RELATED PROJECT (preview only — do not treat as fully known)

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

### Confirmed real failure patterns (from transcript post-mortem, this session)
Three concrete instances, all with transcript evidence, all the same root
cause — **MCP writes to/reads from the Live Object Model; nothing confirms
the rendered UI matches, and the human's manual actions happen in the
actual UI, which can diverge from the data model:**
1. `add_notes_to_clip` has no read-back tool — agent explicitly stated
   contents were "as-written, not re-queried."
2. User manually double-clicked a drum kit in the browser to replicate an
   MCP-driven step; Ableton spawned a **new track** instead of loading
   onto the selected one. Went undetected for ~700 transcript lines across
   multiple user messages ("I can't hear anything") before `get_track_info`
   on the intended track showed `devices: []`.
3. Agent narrated in raw MIDI pitch numbers (36/38/42) instead of the
   pad names actually rendered on a Drum Rack — user confusion until
   corrected.
This is now evidence for, not just a theory about, this project's UIA tree
(`automation_id`s, structural and checkable without a screenshot) serving
as a **verification layer** for case 2 specifically — a UIA dump of
`SessionView.Track[N]` right after `load_drum_kit` would show immediately
whether a device landed on the intended track. Cases 1 and 3 are softer
fits (1 may not be UIA-checkable at all — individual clip notes are
custom-drawn, likely no per-note automation_id; 3 is a prompting issue,
not an automation gap).

### Next session: pending, waiting on user
Built a reusable LLM-eval prompt (given to the user directly, not stored in
this repo) that scores one archived session transcript at a time against a
fixed rubric, to evaluate the rest of the user's archived sessions cheaply
without full reads in this context window. **User is running it now** on
the three sessions already read (transcript pre-scrubbed of the
"unsatisfactory" label for an unbiased read) and will bring back the
structured outputs. When that happens:
- Read the eval outputs (not raw transcripts) to check whether the three
  failure patterns above generalize across more sessions, or whether
  those three were unusual.
- Only then resume the actual planning task: where the two projects
  overlap, what each does better, where they complement (the verification-
  layer idea above is the leading candidate, not yet a conclusion), and
  integration challenges (two live control channels into one Ableton
  instance could race; WSL2 mirrored-networking only affects the MCP path;
  whose "trust" is authoritative if both act on the same session).
- Do not start implementation work on a combined approach yet — still in
  the evidence-gathering/planning phase.

---

## User preferences to keep applying
- Python developer — code-level detail welcome, no need to oversimplify.
- Wants documentation/explanations in Markdown.
- Runs every script iteration on their own Windows machine and pastes raw
  terminal output — treat that as ground truth over any theory proposed;
  be explicit when a theory gets disproven rather than quietly moving on.
