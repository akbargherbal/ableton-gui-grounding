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
- `/mnt/user-data/outputs/dump_ableton_pywinauto.py` — originally the
  user's read-only tree-dump script, now also under active maintenance.
  Exposes `find_ableton_window()` AND `ensure_window_ready()`; both are
  imported by `automate_ableton_task.py` rather than duplicated there.
  This is the canonical source of truth for both "how do we find Live"
  and "how do we make sure its window is fully rendered before we read
  it" -- see "Robustness pass" below.
- `/mnt/user-data/uploads/ableton_uia_20260804_062848_session-view_01.json`
  — a prior full tree dump (from a *different*, uiautomation-based sibling
  script, not the pywinauto one) — used to discover the automation_id
  naming scheme documented below. Verified pixel-accurate against
  `/mnt/user-data/uploads/session_view_1.png` (see bounding-box overlay
  work earlier in this conversation — that part is done/closed, no issues).
- `/mnt/user-data/outputs/automate_ableton_task.py` — the script under
  active development. **This is the live deliverable; keep iterating on
  this file, don't restart from scratch.**
- `/mnt/user-data/outputs/dump_ableton_states.py` — **CONFIRMED WORKING**
  (see "dump_ableton_states.py verification" below). Orchestrates
  switching Ableton between named states (Session/Arrangement so far)
  and writing a labeled dump for each, so the user doesn't have to
  manually alt-tab + switch view + rerun the dump script per state.
- `/mnt/user-data/outputs/grep_dump.py` — pure-stdlib helper, no
  pywinauto/Ableton dependency. Searches an existing JSON dump for nodes
  by substring match on name/automation_id/class_name, to help discover
  new automation_ids (e.g. Browser panel categories) without re-deriving
  them from scratch. **This one IS verified** — tested in this sandbox
  against a hand-built synthetic dump (not real Ableton data, but the
  logic itself doesn't touch Ableton at all, so that test is
  representative).

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

## dump_ableton_states.py verification -- CONFIRMED WORKING
Both assumptions this script was built on were unverified when written
(no dump data existed from Arrangement View, no confirmation Tab-switch
worked via pywinauto's `uia` backend against this app). User then ran
`python dump_ableton_states.py --states session arrangement` on the real
app and pasted back the full output. Both are now confirmed:

1. **Tab switches Session ⇄ Arrangement via `window.type_keys("{TAB}")`**
   — log shows `Currently in Session View; pressing Tab to reach
   Arrangement View` immediately followed by `Already in Arrangement
   View` on the very next check. The switch landed.
2. **`is_session_view()` heuristic holds** — the two dumps have visibly
   different content at the point that matters: Session dump has
   `Group: "Session"` with Track Headers/Slots/Scenes; Arrangement dump
   has `Group: "Arrangement"` with Timeline/Arrangement Controls/Loop
   Brace. The script's own view-detection decisions were all correct
   throughout the run (skipped a redundant switch, pressed Tab exactly
   once when needed, correctly reported "already there" both times it
   actually was).

Bonus finding from this same run: the Browser panel (Sounds, Drums,
Instruments, etc. as `DataItem`s under a `Tree: "Browser Sidebar"`) is
**docked and visible by default** in both dumps captured — no separate
manual "open the browser and select a category" step was needed to
capture that data. Whether those `DataItem`s carry a usable
`automation_id` (vs. being empty, which many non-interactive tree nodes
are) is still unchecked -- that's the next concrete step, see below.

## Robustness pass on dump_ableton_pywinauto.py
Reviewed the read-only dump script against everything learned building
`automate_ableton_task.py`. Found one real gap: it found the Ableton
window and walked its tree immediately, with **no**
`ensure_window_ready()` step -- so a dump taken against a backgrounded or
non-maximized window could silently return a far smaller tree (~60 vs
~201 automation_ids, same failure mode discovered during the solo bug
investigation) with no warning that anything was wrong. Fixed:
- Moved `ensure_window_ready()` (restore-if-minimized, set_focus,
  maximize, small sleep for redraw) into `dump_ableton_pywinauto.py` as
  the single canonical copy, with a `maximize: bool = True` parameter.
- Dump script now calls it before every walk. Added `--no-maximize` to
  opt out, for the rare case of deliberately capturing the window at its
  current size.
- `automate_ableton_task.py` now **imports** `ensure_window_ready` from
  the dump script instead of keeping its own copy -- removes the
  duplication that existed before and closes off a way the two scripts
  could've silently drifted apart on this exact behavior.
- Everything else in the dump script (per-property try/except in
  `walk()`, elevation diagnostics, the retry loop in
  `find_ableton_window()`) was already solid; no other changes needed.
  It was read-only from the start, so the stale-reference and
  bad-baseline lessons from the solo bug don't apply to it.


## What to do next session
1. **`dump_ableton_states.py` is confirmed working** — see "verification"
   section above. Session/Arrangement switching is done, don't reopen it
   without new contradicting evidence.
2. **Immediate next step — waiting on grep output.** User's first attempt
   at `grep_dump.py` omitted the required `query` argument (usage error,
   not a script bug -- it needs two positional args: json_path AND
   query). Correct form, against dumps already captured (Browser panel
   is docked/visible by default, no new dump needed):
   ```
   python .\grep_dump.py .\dumps\ableton_uia_..._arrangement.json sound
   python .\grep_dump.py .\dumps\ableton_uia_..._arrangement.json instrument
   ```
   Once that output comes back: if the `DataItem` nodes for "Sounds" /
   "Instruments" carry a non-empty `automation_id`, wire it into
   `BROWSER_CATEGORY_IDS` in `dump_ableton_states.py`. If
   `automation_id` is empty (plausible -- many non-interactive tree
   nodes are), we'll need a different selection strategy (e.g. typing
   into the Browser's `Edit: "Search"` field instead of clicking a tree
   item directly) -- don't guess which case it is, wait for the actual
   grep output.
3. **Stuck-soloed bug is closed** — confirmed via a clean `off/off`
   baseline + a full `solo_tour --tracks 0 1 --live` run that printed
   `original_state` as all `off` and ended with both tracks `off`,
   user-verified against the real running app. Don't reopen this without
   new contradicting evidence.
4. Open items, not yet started:
   - `click_by_id()` (used for `Transport.Play`/`Stop` and monitor
     RadioButtons) is still "click and trust" — no post-click
     verification, unlike `set_checkbox_by_id()`. Worth the same
     verify-after-click treatment now that the checkbox case is fully
     understood, though nothing has surfaced a concrete bug there yet.
   - `task_arm_track` doesn't capture/print a baseline the way
     `solo_tour` now does — check whether an analogous "silently trust
     current state" pattern applies there, or whether it's not
     applicable (it may not need one, since Arm doesn't get restored).
5. Ask the user what's next functionally — likely candidates: clip
   launching (`SessionView.Track[N].Slot[M]`, not yet exercised beyond
   being visible in the tree dump), device parameters, or hardening
   pass over `click_by_id()` per the point above.
6. Bigger-picture lesson from this whole arc, worth carrying into
   whatever comes next: a real Ableton-controlling agent needs
   **verify-after-every-action** AND **print/distrust your own captured
   baselines**, not open-loop "read once, trust forever." The
   stuck-soloed bug wasn't a flaky click or a flaky read — both were
   reliable the entire time — it was trusting a snapshot of state
   without surfacing it for a sanity check. `dump_ableton_states.py` was
   a live test of whether that lesson was actually absorbed: it was
   handed over *labeled as untested hypothesis*, not presented as done,
   and only marked confirmed after the user ran it and pasted back real
   output showing both underlying assumptions held. Keep applying that
   same discipline to anything new (e.g. clip launching, browser
   selection) -- write it, say plainly what's unverified about it, then
   wait for real terminal output before calling it done.

## User preferences to keep applying
- Python developer — code-level detail is welcome, no need to oversimplify.
- Wants documentation/explanations in Markdown.
- Has been directly running every script iteration on their own Windows
  machine and pasting raw terminal output — keep treating that output as
  ground truth over any theory I propose, and be explicit when a theory
  gets disproven (as with the stale-reference one) rather than quietly
  moving on.
