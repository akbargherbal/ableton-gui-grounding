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
Ask the user what's next functionally (clip launching / device params /
`click_by_id()` hardening are the live candidates), rather than assuming.

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

---

## RELATED PROJECT (preview only — do not treat as fully known)

The user has a **separate, parallel project**: controlling Ableton Live
12 via **OpenCode (running in WSL) talking to `ableton-mcp-extended`**
(https://github.com/uisato/ableton-mcp-extended), an MCP server bridging
to a Remote Script loaded inside Ableton over a TCP socket. This is a
different control mechanism entirely from this project's approach
(Windows UI Automation via pywinauto) — MCP + Remote Script vs. UIA tree
walking + click simulation.

**Status of my knowledge here: PREVIEW ONLY.** The user has shared one
setup doc (`opencode-ableton-mcp-setup.md`) and explicitly said more
detail is coming next session — treat everything below as partial
context, not the full picture, and don't assume the setup is confirmed
working just because the doc describes it in detail. No terminal output
from actually running it has been shared yet in either project's
sessions.

### What the setup doc describes (unverified by me, not yet run/confirmed this-session)
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

### Next session: exploratory comparison (this is the actual next task)
User wants to combine the best of both projects. When more detail on the
MCP project arrives, work through:
- **Where they overlap** — both ultimately want to read/control Session
  View state; is one strictly more capable, or do they cover different
  ground (e.g. MCP's device-parameter read/write vs. this project's
  direct clip-slot/mixer control)?
- **What each does better** — likely candidates to check: MCP may be
  faster/more semantic (structured commands vs. simulated clicks) and
  reach deeper into device internals; pywinauto/UIA may be more general
  (works on anything with a UIA tree, no Remote Script dependency, no
  WSL networking layer) and more transparent about *why* something
  failed (this project's whole verify-after-every-action discipline).
  Don't assume either of these without checking — confirm from what the
  user shares next session.
- **Where they could complement each other** — e.g. MCP for
  device-parameter/audio-engine-level control, UIA for anything MCP
  doesn't expose or for validating that an MCP command actually produced
  the expected UI state (a verification layer, playing to this project's
  established strength).
- **Challenges specific to combining them**: two live control channels
  into the same running Ableton instance could race or conflict if used
  concurrently; WSL2 networking (mirrored-mode requirement) only affects
  the MCP path, not this one; different processes own "trust" in each
  project (verify-after-click here vs. MCP's own correctness) — worth
  deciding which is authoritative if both act on the same session.
- Don't start implementation work on a combined approach until the
  exploratory session has actually happened — this is a planning/
  comparison task first.

---

## User preferences to keep applying
- Python developer — code-level detail welcome, no need to oversimplify.
- Wants documentation/explanations in Markdown.
- Runs every script iteration on their own Windows machine and pastes raw
  terminal output — treat that as ground truth over any theory proposed;
  be explicit when a theory gets disproven rather than quietly moving on.
