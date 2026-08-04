# Context handoff: Ableton Session View UI-automation project

## Goal
User (Python dev) is building toward an AI-agent-controllable Ableton Live
via Windows UI Automation (pywinauto). Work so far: (1) validate an existing
UIA JSON dump against a screenshot, (2) write a script that *acts* on Live
using that data, (3) debug it against the real, running app on the user's
Windows machine. **I (Claude) cannot run pywinauto/Ableton myself — this
sandbox is Linux with no Windows/Live access.** All real-world testing is
done by the user, who pastes back terminal output.

## Files involved
- `/mnt/user-data/uploads/dump_ableton_pywinauto.py` — user's original,
  read-only tree-dump script (provided by user). Exposes
  `find_ableton_window()`, which the automation script imports and reuses.
- `/mnt/user-data/uploads/ableton_uia_20260804_062848_session-view_01.json`
  — a prior full tree dump (from a *different*, uiautomation-based sibling
  script, not the pywinauto one) — used to discover the automation_id
  naming scheme documented below. Verified pixel-accurate against
  `/mnt/user-data/uploads/session_view_1.png` (see bounding-box overlay
  work earlier in this conversation — that part is done/closed, no issues).
- `/mnt/user-data/outputs/automate_ableton_task.py` — the script under
  active development. **This is the live deliverable; keep iterating on
  this file, don't restart from scratch.**

## Key discovery: automation_id scheme
Ableton exposes stable, structural automation_ids (NOT just repeated
visible names like "In"/"Auto"/"Off"):
```
SessionView.Track[N].Mixer.Arm                     CheckBox
SessionView.Track[N].Mixer.Activator                CheckBox (mute)
SessionView.Track[N].Mixer.Solo                      CheckBox
SessionView.Track[N].Mixer.Monitoring.Buttons[0..2]  RadioButton (In/Auto/Off)
SessionView.Track[N].Mixer.Stop                      Button (clip stop)
SessionView.Track[N].Slot[M]                         Group (clip slot)
SessionView.ReturnTrack[N].Mixer.*                    same shape, return tracks
Transport.Tempo                                      Slider
Transport.Play / Transport.Stop                      (assumed by pattern,
                                                        not yet independently
                                                        confirmed missing in
                                                        this session)
```
Track[0..3] = MIDI/Audio tracks, ReturnTrack[0..1] = A-Reverb/B-Delay, in
the user's current test project (4 tracks + 2 returns).

## Bugs found and fixed this session, in order
1. **`descendants(auto_id=...)` doesn't exist.** Confirmed by downloading
   pywinauto 0.6.9 source: `IUIA.build_condition()` only accepts `process,
   class_name, title, control_type, content_only`. Fixed by building our
   own `automation_id -> control` index via manual recursive
   `control.children()` walk (mirrors what the user's dump script already
   does reliably).
2. **`descendants(control_type=...)` (single FindAll-style query) silently
   returned nothing** against Ableton's deep custom-drawn tree, even though
   manual recursive `.children()` walking works fine. Confirmed indirectly
   — never went back to prove FindAll is *always* broken here, just that
   the manual-walk replacement works.
3. **UI virtualization / focus dependency.** Indexed automation_id count
   varied 51/60/201 across runs depending on whether Ableton's window was
   maximized/foregrounded. Missing controls (e.g. `Track[0].Mixer.Solo`)
   simply don't exist in the tree when not visible/focused — not a lookup
   bug. Fixed with `ensure_window_ready()`: restore-if-minimized, set_focus,
   maximize, before every run.
4. **UNRESOLVED, most important open bug:** `solo_tour` task reliably
   leaves track 1 soloed at the end of the run (track 0 restores fine,
   track 1 doesn't). Reproduced **identically** even after eliminating all
   cross-call control caching (i.e. resolving every control completely
   fresh, right before each click/read, via `resolve()`/`find_control()` —
   see current file). This **disproves** the "stale COM reference" theory
   I had going into that fix. Real cause is still unknown; two live
   hypotheses:
   - `get_toggle_state()` isn't reliably reporting this control's true
     on-screen state (TogglePattern support may be flaky on Ableton's
     custom-drawn RadioButton-style checkboxes), or
   - `click_input()` isn't reliably landing on the real control (stale/
     offset bounding rect at click time), so real Ableton state and our
     internal bookkeeping silently diverge.

## Current state of automate_ableton_task.py (as of last edit)
- Uses `find_control()` / `resolve()` — always-fresh, no cross-call caching
  of `UIAWrapper` objects.
- `set_checkbox_by_id()` now **verifies after clicking**: re-resolves,
  re-reads state, retries once, and **raises loudly** if the click didn't
  actually produce the expected state — this replaces the old "click and
  trust" behavior that let the track-1-stuck-soloed bug pass silently.
- Added `--task probe_toggle --tracks N` diagnostic: clicks a track's Solo
  checkbox 4x with 1s gaps, printing `before -> after` state and the
  control's `bounding_rect` each time, specifically to let the user compare
  printed state against what Ableton visibly shows on screen, and to
  disambiguate the two hypotheses above.
- **Waiting on:** user has NOT yet run `--task probe_toggle --tracks 1` and
  reported output. This is the next concrete step — do not guess further
  without that data.

## What to do next session
1. Ask for / read the `probe_toggle` output if not already provided.
2. If state toggles cleanly and matches the screen → the bug is a timing
   interaction specifically with Play/Stop or the 3s sleep in `solo_tour`,
   not toggle reading itself. Test with Play/Stop removed from the loop.
3. If state doesn't toggle cleanly or disagrees with the screen →
   `get_toggle_state()`'s TogglePattern-based read is untrustworthy for
   this control. Try alternatives: `LegacyIAccessible` pattern
   (`control.legacy_properties()['State']` or similar), or fall back to
   comparing a screenshot pixel/color at the control's bounding_rect
   instead of trusting the accessibility toggle property.
4. Bigger-picture note already given to the user and worth keeping in
   mind: this whole debugging arc is evidence that a real Ableton-
   controlling agent needs **verify-after-every-action** as a hard
   requirement, not open-loop "plan then execute" — exactly the pattern
   now (partially) implemented in `set_checkbox_by_id`. Consider applying
   the same verify-after-click discipline to `click_by_id()` (currently
   still "click and trust", used for Transport.Play/Stop and monitor
   RadioButtons) once the checkbox case is understood.

## User preferences to keep applying
- Python developer — code-level detail is welcome, no need to oversimplify.
- Wants documentation/explanations in Markdown.
- Has been directly running every script iteration on their own Windows
  machine and pasting raw terminal output — keep treating that output as
  ground truth over any theory I propose, and be explicit when a theory
  gets disproven (as with the stale-reference one) rather than quietly
  moving on.
