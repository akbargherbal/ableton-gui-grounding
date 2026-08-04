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
4. **RESOLVED & CONFIRMED — was not a click/timing bug.** `solo_tour`
   reliably left track 1 soloed at the end. Root cause, found via a new
   `probe_solo_transport` diagnostic that replays solo-on → Play → sleep
   → Stop → solo-off for one track with a state print after every step:
   **track 1 was already soloed *before* `solo_tour` ran** (leftover from
   an earlier broken run). `solo_tour` captures `original_state` at the
   very start and restores to *that* at the end — so it faithfully
   "restored" track 1 right back to the bad `on` state it found, every
   time. The toggle read (`get_toggle_state`) and the click
   (`click_input`) are both completely reliable on their own — confirmed
   twice, once by `probe_toggle` (4 clicks in isolation, clean
   off/on/off/on, identical rect) and again by `probe_solo_transport`
   (clean off/on across a full solo/Play/sleep/Stop/unsolo cycle). Neither
   original hypothesis (misread toggle state / click missing the control)
   was the cause. Fixed by: (a) `solo_tour` now prints the captured
   `original_state` up front, so a bad baseline is visible immediately
   instead of silently trusted; (b) added `read_solo_states` task — pure
   read, no clicks, no dry-run/live distinction needed — to sanity-check
   solo state on any tracks before trusting them as a baseline.
   **Confirmed fixed**: with a manually-restored clean `off/off` baseline
   (verified via `read_solo_states`), `solo_tour --tracks 0 1 --live`
   printed `original_state` as all `off` and ended with both tracks
   `off` — exact expected behavior, user-verified on the real running
   app. No further action needed on this bug.

## Current state of automate_ableton_task.py (as of last edit)
- Uses `find_control()` / `resolve()` — always-fresh, no cross-call caching
  of `UIAWrapper` objects.
- `set_checkbox_by_id()` **verifies after clicking**: re-resolves, re-reads
  state, retries once, and **raises loudly** if the click didn't actually
  produce the expected state.
- `task_solo_tour()` now **prints the captured `original_state` up front**,
  before doing anything else, so a bad baseline (e.g. a track already
  wrongly soloed from a prior run) is visible immediately instead of being
  silently trusted as "the state to restore to."
- Diagnostics available (all always live-click except `read_solo_states`,
  regardless of `--live` — see their docstrings):
  - `--task probe_toggle --tracks N` — clicks Solo 4x in isolation,
    prints before/after state + rect each time.
  - `--task probe_solo_transport --tracks N` — replays solo-on → Play →
    sleep → Stop → solo-off for one track, printing state after every
    single step. This is what found the real cause of the stuck-soloed
    bug (see bug #4 above).
  - `--task read_solo_states --tracks N [M ...]` — pure read, no clicks,
    prints current Solo state for the given tracks. Use before
    `solo_tour` to sanity-check the baseline it's about to trust.
- **Not yet done:** apply the same "print/verify the assumption instead of
  silently trusting it" fix to `task_arm_track` if it has an analogous
  baseline-capture pattern (it currently doesn't capture prior state at
  all, so probably not applicable — worth a quick check, not a known bug).

## What to do next session
1. **Stuck-soloed bug is closed** — confirmed via a clean `off/off`
   baseline + a full `solo_tour --tracks 0 1 --live` run that printed
   `original_state` as all `off` and ended with both tracks `off`,
   user-verified against the real running app. Don't reopen this without
   new contradicting evidence.
2. Open items, not yet started:
   - `click_by_id()` (used for `Transport.Play`/`Stop` and monitor
     RadioButtons) is still "click and trust" — no post-click
     verification, unlike `set_checkbox_by_id()`. Worth the same
     verify-after-click treatment now that the checkbox case is fully
     understood, though nothing has surfaced a concrete bug there yet.
   - `task_arm_track` doesn't capture/print a baseline the way
     `solo_tour` now does — check whether an analogous "silently trust
     current state" pattern applies there, or whether it's not
     applicable (it may not need one, since Arm doesn't get restored).
3. Ask the user what's next functionally — likely candidates: clip
   launching (`SessionView.Track[N].Slot[M]`, not yet exercised beyond
   being visible in the tree dump), device parameters, or hardening
   pass over `click_by_id()` per the point above.
4. Bigger-picture lesson from this whole arc, worth carrying into
   whatever comes next: a real Ableton-controlling agent needs
   **verify-after-every-action** AND **print/distrust your own captured
   baselines**, not open-loop "read once, trust forever." The
   stuck-soloed bug wasn't a flaky click or a flaky read — both were
   reliable the entire time — it was trusting a snapshot of state
   without surfacing it for a sanity check.

## User preferences to keep applying
- Python developer — code-level detail is welcome, no need to oversimplify.
- Wants documentation/explanations in Markdown.
- Has been directly running every script iteration on their own Windows
  machine and pasting raw terminal output — keep treating that output as
  ground truth over any theory I propose, and be explicit when a theory
  gets disproven (as with the stale-reference one) rather than quietly
  moving on.
