# Context: Grounding Text-Based LLMs in Ableton's Actual UI

For future-me picking this up in a fresh session. This is the **sixth**
working document for this project — it supersedes the fifth draft. This
session executed the fifth draft's two-part goal (build+validate the UIA
wrapper, draft the AGENTS.md diff), found and fixed one blocker the fifth
draft didn't know about, and did a repo-structure pass against a series of
real `tree` outputs. **The user is now going to live-test the current
setup and will report back next session what worked and what didn't** —
that report is this project's next real input, more than any further
unprompted work on the open items below.

Everything from prior drafts not explicitly revisited below is still
intact: the problem statement (version drift, not live customization), the
target user (total beginner, first ~4 weeks), the version range (12.x
only), the consumption mechanism (manifest entry -> LLM instruction +
bbox-on-screenshot), and the still-open scope question (does the manifest
need to stay narrow now that UIA removes the original cost constraint —
parked, not forgotten, not touched this session).

## NEW this session: both required files reviewed in full, prior audit confirmed

`AGENTS.md` was read in full this session (a prior session's `view` call
truncated the middle section; that was a tooling artifact, not a real
document gap — the file itself was never actually short a section). The
full read confirmed the fifth draft's audit table was accurate: Rule 6
step 5 (`the agent does not interpret or describe [screenshot] visual
contents`) is about screenshot pixels specifically, not UIA, and correctly
verdicted "no change." Rule 3, Rule 10, and the color rule all read
exactly as the audit described.

`dump_ableton_pywinauto.py` was read in full, resolving item 2 from the
fifth draft's "files needed" list:
- **Parameterizable**: yes (`--max-depth`, `--json`, `--label`,
  `--out-dir`, `--title-contains`, `--no-print`).
- **Not headless**: requires a title-substring window match via
  `Desktop(backend="uia").windows()`; no PID/handle targeting option.
  Has an elevation-mismatch failure mode (`is_elevated()`) that can
  silently return near-nothing if the script and Ableton run at
  different privilege levels.
- **Zero filtering built in**: confirmed by inspection. `walk()` is a
  raw recursive dump — no normalization, no de-dup, no bounds-check.
  All three had to be added fresh in the wrapper (below).
- **Output-path inconsistency vs. `take_shot.sh`**: `--out-dir` defaults
  to a bare relative `"dumps"`, resolved from wherever the script happens
  to be *run from* — unlike `take_shot.sh`, which anchors to its own
  script location (`BASH_SOURCE`) regardless of cwd. Not fixed this
  session; flagged as a real inconsistency, relevant if the two scripts
  ever get merged (see fifth draft's secondary item, still undecided).

## NEW this session: the three re-supplied dumps, cross-checked against prior claims

The `baseline`, `sounds-pane`, and `arrangement-view` dumps (already
characterized in the fifth draft) were re-supplied and machine-checked
against that draft's specific claims, not just re-read.

**Confirmed exactly as claimed:**
- Node counts: 384 / 434 / 729 respectively.
- `DataItem` counts in the non-arrangement dumps: 51 / 89.
- The MIDI-vs-Audio mixer gap: `Track[0]`/`Track[1]` (MIDI) genuinely lack
  `Pan`/`PeakLevel`/`Send[0]`/`Send[1]`/`Volume` automation_ids that
  `Track[2]`/`Track[3]` (Audio) have. **Still an open question** — real,
  not a fluke, but MIDI-vs-Audio vs. render-state isn't resolved.
- The 3-level nested chain: `DataItem -> DataItem -> Text`, verified
  directly on `3D Reso Percussion.adg` in arrangement-view.
- Zero out-of-bounds `DataItem`s in baseline/sounds-pane.
- `take_shot.sh`'s seven error codes all match AGENTS.md's table exactly.

**One correction to a "confirmed consistent" claim:** the fifth draft
said all four dumps were "confirmed consistent... by track count and
title-bar text." Track *count* (4) is consistent. Title-bar *text* is
not: `Track[0]` reads `"1-MIDI"` in baseline/sounds-pane but
`"1-Arr Matey Lead, Armed"` in arrangement-view (a device got loaded and
the track renamed/armed by that point in the session). Expected, given
AGENTS.md's own rule that a rename becomes the new anchor — but worth not
repeating "text is consistent across all four" verbatim again.

**One correction to the virtualized-list numbers themselves:** the fifth
draft reported "249 sample/preset rows loaded... 84 of 249 (34%) land in
bounds." The actual dump shows the browser's file-list `Tree` node
(`"Sounds List, 1001 Items"`) has **84 direct row children**, of which
**29 are in-bounds and 55 are not**. The bug itself is real and correctly
described — the fix (bounds-check filter) was still right — but "84"
appears to have gotten reused between two different meanings (total rows
vs. in-bounds count) somewhere in the prior session's write-up, and "249"
doesn't correspond to anything found in this file. **Use this session's
numbers (84 total / 29 in-bounds / 55 out) as the reference case going
forward, not the fifth draft's.**

## NEW this session: Part 1 built, validated, and one new blocker found+fixed

`uia_wrapper.py` was built implementing the three confirmed-necessary
transforms, then validated against all three real dumps (not just
designed against the narrative description of them):

  a. **Window-relative normalization** — see the offset bug below; this
     step needed a real fix, not just implementation.
  b. **Innermost-of-chain de-dup** — walks same-name descendant chains
     (matching on `name`, regardless of `control_type`, since the real
     chain is `DataItem -> DataItem -> Text`, all three sharing one
     name) to the innermost node. Verified against `3D Reso Percussion.adg`:
     raw 3-level chain collapses to one node with `collapsed_levels: 2`.
  c. **Bounds-check filter** — uses a true rect-intersection test (not a
     single-corner-in-bounds check), and treats zero-area/degenerate
     rects (e.g. an empty placeholder `Text` node) as `in_bounds: None`
     ("no real geometry to judge") rather than a false out-of-bounds flag.

**New blocker, not previously known: a ~75px title-bar/menu-bar origin
offset.** `dump_ableton_pywinauto.py`'s root node comes from pywinauto's
`control.rectangle()`, which turns out to report something narrower than
the full outer window — `take_shot.sh` captures via the native
`GetWindowRect` Win32 API, which is documented to include title bar, menu
bar, and borders. Evidence: the `TitleBar` element sits **exactly 75px
above** the root's own reported top edge, identically, across all three
dumps — including one dump whose window sits on an entirely different
monitor at different absolute coordinates. A constant that survives a
completely different window position isn't coincidence.

**Why it mattered:** left as originally scoped, this would have
misaligned *every* bbox the wrapper produced by ~75px when drawn on an
actual `take_shot.sh` screenshot — not just the browser-list rows. This
is more consequential than the bounds-check bug, since it would have
silently broken the project's core "highlight box on the real screenshot"
mechanism rather than just producing some garbage rows.

**Fix applied:** the wrapper now calibrates its origin off the `TitleBar`
element's own top-left (always present on a real window, immune to the
virtualized-list staleness problem) instead of hardcoding "75" or trusting
the root's self-reported rect. Falls back to the root's rect with a
printed warning if no `TitleBar` is found in a given dump.

**Post-fix validation (final numbers):**

| dump | nodes | chains collapsed | out-of-bounds (final) |
|---|---|---|---|
| baseline | 290 | 35 | 0 |
| sounds-pane | 301 | 54 | 0 |
| arrangement-view | 464 | 122 | 51 (all genuine `DataItem` rows; 0 chrome false-positives) |

**Not yet done:** `device-loaded.json` (the fourth dump, described in the
fifth draft but never actually uploaded until this session's repo-tree
pass put it in `dumps/`) has **not** been run through the wrapper yet —
worth doing next, since it's the one dump in the regression set the
wrapper hasn't personally been validated against.

Delivered: `uia_wrapper.py`, CLI (`python uia_wrapper.py <in.json> --out
<out.json> [--keep-out-of-bounds]`).

## NEW this session: Part 2 diff drafted and delivered

Gated correctly on Part 1 actually working, per the fifth draft's
ordering. Three changes, verified via `diff` that nothing else moved:

1. **System Constraints** — the "no vision" bullet now scopes the claim
   to `AbletonMCP` specifically. The old wording ("The agent has zero
   direct knowledge...") oversold the limitation at the *agent* level,
   which is no longer true now that a second channel exists; the new
   wording keeps `AbletonMCP` itself pixel-blind while noting the
   separate UIA channel.
2. **Rule 5** — widened from "drawn from an actual MCP response" to "...or
   a live, filtered UIA query," with **"filtered" made explicit and
   load-bearing**: raw/unfiltered UIA output must never be cited
   directly, for two concrete reasons now on record (virtualized-list
   garbage rects, and the origin-offset bug above) — only the validated
   wrapper's output counts as verified evidence.
3. **Rule 3** — added a non-binding "consider adding" line about an
   optional filtered-UIA cross-check as a second post-change verification
   step. Explicitly not a required part of the diff, per the fifth
   draft's instruction.

Rule 6 step 5, the color rule, and Rule 10 confirmed untouched (absent
from the diff).

Delivered: `AGENTS.diff` (unified diff) and the full patched `AGENTS.md`.
**Open cosmetic note**: Rule 5's widened text currently describes "the
validated UIA wrapper" generically rather than naming `uia_wrapper.py` —
worth tightening once the file's final repo location is settled (see
below).

## NEW this session: repo-structure pass against real `tree` output

The user pasted several real `tree` outputs over the course of the
session and iterated live. Current state, as of the last `tree` seen:

- **Fixed, confirmed correct**: `LABS/ableton-live-12-manual-en.pdf`. A
  real bug was caught here — the actual file was originally named
  `LABS/ableton-liv-12-manual-en.pdf` (missing the "e" in "live"),
  which did not match AGENTS.md's reference to
  `LABS/ableton-live-12-manual-en.pdf`. A first fix attempt produced a
  botched concatenated name (`LABS/LABSableton-live-12-manual-en.pdf`);
  the final state now matches AGENTS.md correctly.
- **`dumps/` now exists and is populated** with `baseline`,
  `sounds-pane`, `arrangement-view`, and `device-loaded` — the full
  four-dump regression set the fifth draft called for, finally all
  physically present in the repo (not just described in a doc).
- **New, unreviewed file discovered**: `dumps/ableton_uia_20260803_184638_file-menu-open.json`.
  This does not appear anywhere in any prior draft of this document — it
  looks like a fifth capture nobody has looked at yet in any session.
  Not reviewed this session either. Flagged, not forgotten.
- **Left unresolved, by explicit user choice**: `dump_ableton_pywinauto.py`
  and `uia_wrapper.py` currently sit at project **root**, not in a
  `scripts/` directory as this document previously stated they should.
  The user chose to leave the current flat layout alone for now rather
  than restructure. Treat this as the actual current state, not a bug to
  silently "fix" next time — if `scripts/` placement matters later, it
  needs to be a deliberate decision, not an assumed correction.

## NEXT SESSION GOAL

**Primary: incorporate the user's live-test report.** The user is testing
the current setup (wrapper + patched AGENTS.md + repo layout) hands-on and
will come back with what worked and what didn't. That report should drive
next session's actual priorities more than the list below — don't assume
the items below still matter in the same shape once real usage data exists.

**Secondary, worth doing opportunistically if the test report leaves room:**
- Run `device-loaded.json` through `uia_wrapper.py` — the one regression-set
  dump the wrapper hasn't actually been validated against yet.
- Review `ableton_uia_20260803_184638_file-menu-open.json` — unreviewed,
  unknown content, unknown relevance.
- Resolve the MIDI-vs-Audio mixer-strip open question with a live Ableton
  check (still unresolved, now three dumps deep).
- Decide the `scripts/` vs. root placement question for
  `dump_ableton_pywinauto.py` / `uia_wrapper.py`, and if `scripts/` is
  chosen, update Rule 5's wrapper reference in AGENTS.md to the concrete
  filename.
- Decide whether merging `take_shot.sh` and `dump_ableton_pywinauto.py`
  into one focus-locked capture call is a co-requisite of trusting Rule
  5's widened evidence class (raised repeatedly, never yet built).

## Files needed next session, alongside this context.md

1. **Whatever the user's live test surfaces** — most likely to matter of
   anything on this list.
2. **`AGENTS.md`, current state** — to confirm the patched version is
   actually the one in use, and to draft any further diff against it.
3. **`ableton_uia_20260803_184638_file-menu-open.json`** — if review of
   the unknown fifth dump gets picked up.
4. Not strictly needed again, but useful if convenient: the other three
   dumps already in `dumps/` (`baseline`, `sounds-pane`,
   `arrangement-view`) — already fully characterized across two
   sessions now, re-supplying them only matters if something about them
   is suspected to have changed.

Not needed next session: `gui_grounding_benchmark.py` (still out of
scope, unchanged from prior drafts).
