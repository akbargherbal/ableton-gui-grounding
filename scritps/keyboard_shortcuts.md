# Keyboard shortcut index

Backing reference for `click_by_id()`'s Level-2 escalation tier
(`automate_ableton_task.py`). Built to answer "checked the manual, no
alternate path, escalating" with an actual lookup instead of a memory guess.

**Source:** Ableton's official online manual, Live 12, "Live Keyboard
Shortcuts" chapter — https://www.ableton.com/en/manual/live-keyboard-shortcuts/
(fetched 2026-08-04). This documents Live's **factory-default** key map, not
this machine's actual current one.

**Not yet resolved:** whether this machine's Key Map has ever been
customized (Preferences > Key Map). If it has, `Preferences > Key Map >
Save As...` exports the real `.akeymap` and that should be reconciled
against this table before trusting it. If it hasn't, this table already
reflects the live state, sourced from Ableton's own canonical copy rather
than a local export.

**Nothing in this table has been run against a live Ableton instance yet.**
Per project discipline, "sourced from the manual" and "confirmed" are
different things — status column tracks that distinction explicitly.

## Index

| Control | `automation_id` | Win | Mac | Manual section | Status |
|---|---|---|---|---|---|
| Play/Stop transport | `Transport.Play` / `Transport.Stop` | `Space` | `Space` | §41.20 Transport | Sourced, not live-tested. Single key toggles both directions — needs a live check that `get_toggle_state(Transport.Play)` reads cleanly right after a `Space` press, the same way `Monitoring.Buttons[0]` did in session 4. |
| Solo selected track | `SessionView.Track[N].Mixer.Solo` | `S` | `S` | §41.19 Commands for Tracks | Sourced, **BLOCKED**. Acts on whichever track is currently *selected*, not on an arbitrary `Track[N]`. No automation_id in this project's scheme exposes selected-track state (open item, session 4). Do not wire into a call site until that's resolved. |
| Arm selected track | `SessionView.Track[N].Mixer.Arm` | `C` | `C` | §41.19 | Sourced, **BLOCKED**. Same selected-track dependency as Solo. |
| Activate/deactivate track by position 1–8 | `SessionView.Track[N].Mixer.Activator` | `F1`…`F8` | `F1`…`F8` | §41.20 Transport | Sourced, **not selection-blocked** — positional (F-key N ↔ track position N), not tied to current selection. Best candidate to test first. Unverified: (a) whether position counts audio+MIDI tracks only or return tracks too, (b) whether `Track[0]` (0-indexed automation_id) maps to `F1` (1-indexed shortcut) or off-by-one, (c) undefined behavior for track index ≥ 8 (only 8 keys exist). |
| Deactivate selected track (alt path) | `SessionView.Track[N].Mixer.Activator` | `0` | `0` | §41.19 | Sourced, **BLOCKED**. Selection-based alternative to the F1–F8 path above; same selected-track dependency as Solo/Arm. |
| Monitoring In/Auto/Off | `SessionView.Track[N].Mixer.Monitoring.Buttons[0..2]` | — | — | — | **No shortcut found** anywhere in the manual's shortcut chapter. Not confirmed absent, just absent from this chapter — no fallback exists for this control at L2 until/unless that changes. |
| Launch selected clip/slot | `SessionView.Track[N].Slot[M]` | `Enter` | `Enter` | §41.15 Session View | Sourced, out of scope (clip launching not started yet). Same selected-slot dependency shape as Solo/Arm — logged here so it's not rediscovered from scratch when that work starts. |

## Open items this surfaces
1. **F1–F8 → Activator is the one shortcut here not blocked by the
   selected-track gap.** Candidate to test live before anything
   selection-dependent.
2. Confirm whether this machine's Key Map has ever been customized; if so,
   export and reconcile the real `.akeymap` against this table.
3. Position-vs-index mapping for F1–F8 (audio/MIDI only? return tracks
   included? off-by-one?) needs a real dump/test, not assumed from the
   manual text alone.
4. Monitoring has no known shortcut path at all — either accept that as a
   permanent L1-only control, or investigate further (Settings dialog,
   context menu) before concluding that.
