# AGENTS.md

Instructions for the AI agent driving Ableton Live 12 automation on this
machine (via OpenCode). Read `context.md` first for project intent; this
file is the operational routing layer — which tool to reach for, and when.

---

## Control paths

- **UIA-direct** (primary): `automate_ableton_task.py` → `orchestrate.sh` →
  `take_shot.sh`. Handles every task in `SINGLE_ACTION_TASKS`. Always
  produces screenshots — one per sub-step (per-click granularity, since
  item #7).
- **MCP** (secondary): OpenCode → `ableton-mcp-extended` → TCP → Ableton
  Remote Script. Handles device parameters, browser loading, track/clip/
  arrangement manipulation that UIA structurally cannot reach. **Never**
  produces screenshots on its own — the student can't see what happened
  unless you pair it with a UIA screenshot step (see Routing below).

### Within a single UIA click: the escalation ladder

`click_by_id()` uses a strict **3-level** ladder: **L1 Mouse → L2 Keyboard
shortcut → L3 Human instructions**. This is the actual code
(`automate_ableton_task.py`) — not a 4-level Mouse→Keyboard→MCP/LOM→Human
ladder some earlier pre-implementation design notes proposed, which was
never built that way. MCP is
**not** a fallback tier inside a UIA click. It's a separate path one level
up, used when the whole capability (not just one click) doesn't exist on
the UIA side at all — see Routing.

Before escalating past L1 or L2, consult the Ableton manual / verified
shortcut index (`keyboard_shortcuts.py` + `.md`) — never guess a shortcut.

### Choosing a path

1. Is the action in `SINGLE_ACTION_TASKS`? → `orchestrate.sh <task>`. Don't
   reach for MCP first — this is the default, not a fallback (see "Agent
   defaults to MCP" finding below).
2. Is it a device/browser/clip/track operation MCP can do but UIA can't? →
   MCP, with a mandatory read-back (see Routing).
3. Is it a loaded-device or post-MCP-write screenshot? → `take_shot.sh`
   directly (not via `orchestrate.sh` — that script is single-task-shaped).
4. Is it browser drag-and-drop onto a track/slot, or Session View clip
   launching as an automated teaching step? → Not supported on either
   path. Tell the student, don't attempt it.

---

## Routing — which tool for which task

### Default path: UIA-direct (use this first)

For any task listed in `SINGLE_ACTION_TASKS` in `orchestrate.sh`, use the
orchestrator — don't reach for MCP tools first. It handles the action
**and** the screenshot in one command, and it's the only path whose
actions are actually verified against live Ableton UI state (checkbox/
radio-button reads via `get_toggle_state`, not click-and-trust).

Today's supported tasks: `arm_track`, `set_tempo`, `probe_toggle`,
`probe_solo_transport`, `probe_keyboard_activator`, `read_solo_states`,
`solo_one`.

**Name collision — `set_tempo` exists on both paths.** There is also an
MCP tool called `set_tempo`. For tempo changes, always use
`orchestrate.sh ... set_tempo` (the UIA task), not the MCP tool — same
reasoning as the `solo_tour` trap below: matching names, but only one path
is verified and screenshotted. The MCP `set_tempo` tool should not be used
in teaching flows.

**Gotcha — `solo_tour` is a naming trap, not an alternative:** it exists as
a task name in the engine and is a real multi-track solo-comparison
feature, but it is **explicitly excluded** from `orchestrate.sh` (see the
script's own header comment) and produces **zero screenshots** when run
directly via `automate_ableton_task.py`. `take_shot.sh` is only ever
invoked from inside `orchestrate.sh`. For a solo comparison across tracks,
use `orchestrate.sh ... solo_one` looped per track (one screenshot per
track) — never call `solo_tour` directly in a teaching flow.

**Why UIA-direct is the default, not MCP:** a baseline test (no `AGENTS.md`
present) showed the agent's natural first instinct in an MCP-connected
session is to reach for MCP tools (`get_session_info`, `get_track_info`)
before exploring the project at all. MCP has no arm/monitor tools, so this
is a dead end for exactly the kind of task UIA-direct already handles
cleanly with a verified, screenshotted result. Full log:
`v2_observations.md` §6, `LIVE_TEST/BASELINE_SESSION_session-ses_02cd.md`.

### When to use MCP instead

Only when UIA-direct doesn't cover the action. Today that means:

| Scenario                  | MCP tool(s)                                              | Post-step                                        |
| -------------------------- | ---------------------------------------------------------- | --------------------------------------------------- |
| Device parameter tweak      | `set_device_parameter`                                     | Read back with `get_device_parameters`, compare      |
| Enable/disable a device     | `enable_device` / `disable_device`                          | Read back with `get_device_parameters`                |
| Load instrument/effect      | `load_instrument_or_effect`                                 | UIA-verify device appeared (`get_track_info`) + `take_shot.sh` |
| Load drum kit / plugin      | `load_drum_kit`, `load_external_plugin`                     | UIA-verify + `take_shot.sh`                          |
| Browse sounds/instruments   | `get_browser_tree`, `get_browser_items_at_path`              | Read-only — safe to trust                            |
| Create/delete track         | `create_midi_track`, `delete_track`                         | `get_track_info` / `get_track_deletion_status` to confirm |
| Delete a device              | `delete_device`                                             | `get_device_parameters` / `get_chain_info` to confirm removal |
| Create clip / add notes     | `create_clip`, `add_notes_to_clip`                           | Read back clip/device state                          |
| Rename track/clip           | `set_track_name`, `set_clip_name`                            | `get_track_info` read-back                           |
| Adjust mixer level/pan      | `set_track_volume`, `set_track_panning`                      | `get_track_volume` and compare                        |
| Transport (start/stop)      | `start_playback`, `stop_playback`                             | `get_session_info` / `get_arrangement_info` read-back |
| Arrangement clip work       | `create_arrangement_midi_clip`, `create_arrangement_audio_clip`, `duplicate_clip_to_arrangement`, `delete_arrangement_clip`, `set_arrangement_clip_property` | Read back via `get_arrangement_info` |
| Cue points / loop / song time | `create_cue_point`, `delete_cue_point`, `jump_to_cue_point`, `set_song_time`, `set_arrangement_loop` | `get_cue_points` / `get_arrangement_info` read-back |
| Read-only session/track/device/chain/drum-pad info | `get_session_info`, `get_track_info`, `get_track_volume`, `get_device_parameters`, `get_chain_info`, `get_drum_pad_info`, `get_arrangement_info`, `get_cue_points`, `list_external_plugins` | Read-only — safe to trust |

**Screenshot pairing:** the table above only lists the *verification*
step. MCP never screenshots on its own. Any MCP write that's a teaching
step the student needs to see — not just a background check — still needs
`take_shot.sh` called directly, after the read-back confirms success. This
applies to every row above, not only browser loading (which gets its own
worked example below because it's the one case that also has no UIA
fallback at all).

**Catch-all:** any MCP tool not in this table (e.g. `navigate_device_preset`,
`fire_clip`, `stop_clip`, `manage_clip_automation`, `set_ableton_view`,
`control_arrangement_view`) is a write with no confirmed read-back
guarantee — treat it as unverified: call the matching read-tool afterward
and compare before reporting success.

### MCP write verification rule

**Every MCP write must be followed by a read of the same property.** This
isn't a generic caution — it's a confirmed bug: code inspection of
`ableton-mcp-extended`'s `_set_device_parameter` (Remote Script side) shows
the value returned to the caller is the **calculated target computed
before the write**, not a re-read of Ableton's actual post-write state
(`context.md` Finding #3). Treat every MCP write this way unless you've
independently confirmed otherwise for that specific tool.

Do not report an MCP write as confirmed until the read-back value matches
the intended value. If it doesn't match: retry the write once (could be
MCP/timing flake), then stop and give the student explicit Level 3 human
instructions instead:

- Assume zero prior familiarity with Ableton.
- Use only explicit, named menu paths and exact control names (e.g. "Go
  to Options → Preferences → Audio, uncheck [checkbox name] if present").
  Never relative/visual cues ("the orange box near the top right").
- End every instruction step with an explicit request for confirmation
  ("Let me know once done, or if you hit an issue") before proceeding.

**Group-track warning:** `_resolve_device` resolves tracks via the Live
Object Model's track index directly, which can diverge from the visible
0-based Session View index whenever group tracks are folded or hidden (the
LOM includes tracks the UI isn't currently showing). If group tracks are
folded, warn the student before trusting an MCP device-parameter write —
it may have landed on the wrong track.

### Cross-path operations (mixing UIA + MCP)

The "don't mix paths mid-task" rule has one standing exception: **browser
loading**. UIA cannot browse or select browser items at all — every
`DataItem` node in the Ableton Browser has an empty `automation_id`, and
the list is virtualized (only visible rows exist in the UI tree), so
there's no stable UIA target. MCP can browse and load; UIA can verify and
screenshot.

Flow: MCP (`get_browser_tree` → `get_browser_items_at_path` →
`load_instrument_or_effect` / `load_drum_kit` / `load_external_plugin`) →
UIA verify (`get_track_info`, or the relevant `get_device_parameters` call)
→ `take_shot.sh` directly (not via `orchestrate.sh` — this isn't a
single-action task).

### Explicitly unsupported — do not attempt

- **Browser drag-and-drop onto a track/slot.** No working implementation on
  either path. UIA has no stable drop target (`Track[N].Slot[M]` shares the
  same virtualization exposure as the source item); MCP's browser tools
  load by path/URI, not by simulated drag. Tell the student to drag
  manually, then capture a screenshot showing the result with
  `take_shot.sh`.
- **Session View clip launching as an automated teaching step.** Listed
  "Not yet" in `README.md`'s status table; MCP has `fire_clip`/`stop_clip`
  but they're unverified writes per the catch-all rule above and not
  exercised in this project's teaching flows yet.
- **Coordinate-based `pywinauto` clicking** for controls with no
  `automation_id`. Anti-pattern — never worked reliably against Ableton's
  custom-drawn, virtualized UI. If a control has no `automation_id`, that's
  a UIA dead end, not a "try clicking coordinates" prompt — route to MCP
  (if it has the capability) or Level 3 human instructions instead.

---

## Lab output & session artifacts

`take_shot.sh`/`orchestrate.sh` never invent a `lab_dir` — the calling
agent owns that naming entirely. Use this convention so sessions are
reviewable later instead of an unlabeled pile of PNGs:

- **Folder:** `LABS/<slug>_<YYYY-MM-DD_HHMM>/`, where `<slug>` is a short
  kebab-case description of the lesson or test (e.g.
  `arm-track-demo_2026-08-05_1430`, `test-mcp-readback_2026-08-05_1500`).
  The timestamp exists because `LABS/` is gitignored and reused across
  sessions — without it, repeat runs of the same lesson silently overwrite
  or interleave `seq` numbers from a prior run.
- **Session log:** every lab run must include a `SESSION_LOG.md` inside
  that same folder, written by the agent, one row per screenshot: `seq`,
  which path was used (UIA task name, or MCP tool + read-back result),
  a one-line description of what happened. Nothing in the code produces
  this automatically — `orchestrate.sh` only numbers and captures images,
  it doesn't narrate them. Write this as you go, not reconstructed after
  the fact from memory.
- `LABS/` is gitignored on purpose (screenshots are session output, not
  source). If a session is worth keeping past a cleanup, copy the folder
  out before it's deleted — nothing preserves it otherwise.
