# ableton-gui-grounding

AI-agent-controllable **Ableton Live 12** via Windows UI Automation
(`pywinauto`). This project reads and acts on Ableton's live UIA tree
directly — no plugin, no Remote Script, no MIDI bridge — so an agent can
see what's actually on screen and click/type against it like a person
would.

The core discipline here isn't "can it click a button" (that part's
easy). It's **grounding**: never trusting a captured UI state without
verifying it, and never issuing an action without confirming it actually
landed. Every bug this project has hit so far turned out to be a
trust problem, not a mechanism problem — see [Lessons learned](#lessons-learned-the-hard-way).

## Why this exists

Ableton's Session View is deeply custom-drawn and UI-virtualized:
controls that aren't currently rendered on screen simply don't exist in
the accessibility tree yet, even though their identifiers are
well-defined once they *are* visible. That single fact broke several
naive approaches before this project settled on its current shape —
see below.

## What's here

| File | What it does |
|---|---|
| `dump_ableton_pywinauto.py` | Read-only: walks Ableton's UIA tree and writes a timestamped JSON dump. Canonical home of `find_ableton_window()` and `ensure_window_ready()`, used by every other script here. |
| `automate_ableton_task.py` | Acts on Live — solo/arm tracks, set tempo, run diagnostics. Every control is resolved fresh immediately before it's touched; nothing is cached across a click/wait/click sequence. |
| `dump_ableton_states.py` | Switches Ableton between named states (Session View, Arrangement View, each Browser panel category) and writes a labeled dump for each. Supports `--states all` to sweep every known state in one run. |
| `grep_dump.py` | Pure-stdlib search over an existing JSON dump — find a control's `automation_id` by substring match on name/class, without touching Ableton again. |

## How it works

Ableton exposes stable, structural `automation_id`s under Session View —
not just repeated visible labels like `"In"` / `"Auto"` / `"Off"`, which
exist 4+ times per project and are locale-dependent:

```
SessionView.Track[N].Mixer.Arm                       CheckBox
SessionView.Track[N].Mixer.Activator                 CheckBox (mute)
SessionView.Track[N].Mixer.Solo                      CheckBox
SessionView.Track[N].Mixer.Monitoring.Buttons[0..2]  RadioButton (In/Auto/Off)
SessionView.Track[N].Mixer.Stop                      Button (clip stop)
SessionView.Track[N].Slot[M]                         Group (clip slot)
SessionView.ReturnTrack[N].Mixer.*                   same shape, return tracks
Transport.Tempo                                      Slider
Transport.Play / Transport.Stop
```

The Browser Sidebar (Sounds, Instruments, Drums, Audio Effects, MIDI
Effects, Plug-Ins) is different: its `DataItem` nodes carry **no**
`automation_id` at all, so selection there falls back to matching on
`(control_type, name)` instead — see `dump_ableton_states.py`.

Every control lookup is a manual recursive `.children()` walk, not a
`descendants(...)` query — `pywinauto`'s `descendants(auto_id=...)`
doesn't exist, and a single `descendants(control_type=...)` FindAll-style
query returns nothing against Ableton's deeply nested, custom-drawn tree.
The manual walk is the only approach that's actually worked.

## Requirements

- Windows 10/11
- Ableton Live 12+, running with a project open
- Python 3.9+
- `pip install pywinauto`

This is Windows-only by nature (`pywinauto`'s `uia` backend). There's no
sandbox/CI path for it — every script here is validated by actually
running it against a live Ableton instance and pasting back real
terminal output. Nothing is marked confirmed on the strength of code
review alone.

## Usage

```bash
# Read-only tree dump
python dump_ableton_pywinauto.py --label baseline

# Sweep every known state in one run (Session, Arrangement, all Browser categories)
python dump_ableton_states.py --states all

# Just the states you want, in order
python dump_ableton_states.py --states session arrangement

# Search a prior dump for a control without touching Ableton again
python grep_dump.py dumps/ableton_uia_..._session.json solo

# Safe by default: prints the plan, clicks nothing
python automate_ableton_task.py --task solo_tour --tracks 0 1 2 3

# Actually perform it
python automate_ableton_task.py --task solo_tour --tracks 0 1 2 3 --live

# Discover what track indices exist right now
python automate_ableton_task.py --list-tracks
```

`automate_ableton_task.py` also ships diagnostic tasks
(`probe_toggle`, `probe_solo_transport`, `read_solo_states`) built
specifically for isolating whether a bug is in the click, the read, or a
stale assumption about prior state — see the script's own docstrings.

## Lessons learned (the hard way)

- **UI virtualization.** A backgrounded or non-maximized window can
  expose a fraction of the controls a maximized/focused one does (~60 vs
  ~201 `automation_id`s observed on the same project), with no error —
  just a silently incomplete tree. Fixed by restoring/focusing/
  maximizing (`ensure_window_ready()`) before every read or action.
- **Stale references.** Holding a resolved control across a
  click → wait → click sequence produced a wrong read in testing. Every
  control is now re-resolved fresh, immediately before each touch.
- **Trusting an unverified baseline is its own bug class.** A track
  stayed soloed after a "restore" step — not because the click or the
  read was unreliable (both were, independently, confirmed rock solid),
  but because the script trusted a snapshot of state captured at the
  start without ever surfacing it for a sanity check. The fix generalizes
  beyond that one bug: **print/distrust captured baselines, and verify
  after every state-changing action** rather than reading once and
  trusting forever.
- **A no-op looks identical to a working click if you don't force a real
  transition.** An early test of Browser-category switching "passed"
  because the target category happened to already be selected — proving
  nothing. Re-run any transition test from a genuinely different starting
  state before calling it confirmed.

## Status

Confirmed end-to-end against a real running Ableton instance:
Session ⇄ Arrangement View switching, all six Browser panel categories,
solo/arm/tempo control with post-action verification. Not yet started:
clip launching (`SessionView.Track[N].Slot[M]` is visible in every dump
but not yet exercised), device-parameter read/write, and
post-click verification for `click_by_id()` (currently "click and
trust," unlike the checkbox path).

## A note on scope

This project deliberately stays at the UI Automation layer — no Remote
Script, no MIDI bridge, no plugin install inside Ableton. That's a
tradeoff: it can't reach into device-internal parameter values the way a
Live Object Model-based integration can, but it also has no moving parts
inside Ableton itself and works against exactly what's on screen, which
makes the verify-after-every-action model straightforward to apply
everywhere.
