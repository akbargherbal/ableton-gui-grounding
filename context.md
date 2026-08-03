# Context: Grounding Text-Based LLMs in Ableton's Actual UI

For future-me picking this up in a fresh session. This is the second
working document for this project — it supersedes the first draft in
substance (scope and mechanism are now settled, not open questions) while
keeping the lineage info. This project is a direct spinoff of a prior
6-session project — `gui_grounding_benchmark`
(https://github.com/akbargherbal/gui_grounding_benchmark) — which
benchmarked open-source vision-grounding models against real Ableton Live
12 screenshots. That project is finished and archived. It was re-cloned
and its `context.md`, `report.md`, and Medium article
(`gui-grounding-ableton-article.md`) were reviewed in detail this
session — see "What we confirmed from the benchmarking project" below,
which replaces the earlier draft's secondhand summary of it.

## The problem this project solves (unchanged, now sharper)

A **text-only** LLM (no vision) gives Ableton instructions from a
training-data blend of screenshots/docs across many versions, with no
label on which version any given tutorial came from. It confidently gives
instructions that don't match the user's actual, current-version screen.

**This project targets version drift only** — not live user customization
(hidden panels, rearranged layout, changed themes). That's explicitly out
of scope. The reasoning, settled this session: the target user is a
*beginner*, and a beginner hasn't customized anything yet — their install
is factory-default. If a mismatch ever does occur for this user, the
realistic fix is conversational ("let's reset to factory settings"), not
a manifest feature. Don't build customization-tracking; it solves a
problem this user population mostly doesn't have.

## Who this is for, precisely (settled this session)

Explicitly: a total beginner, first ~4 weeks with Ableton. No music
background, no DAW jargon, no prior mental model to fall back on when an
instruction doesn't match their screen. The user described themselves as
literally fitting this persona for design purposes.

The "tricycle" framing: this is training wheels, not a permanent
accessibility layer. After roughly a month, the user develops enough
internal mapping that "go to Preferences" self-resolves to wherever it
actually lives, the way an experienced user doesn't need to be told. The
manifest's job is to bridge that specific early gap, not to be a
permanent GUI translation layer.

**Why this population changes the failure mode that matters:** for an
experienced user, a stale instruction is a minor annoyance they can
self-correct. For this beginner, a stale instruction reads as personal
failure ("I must be doing something wrong") because they have no prior
knowledge to attribute the mismatch to version drift. The manifest's real
job is protecting that handshake — the moment where the LLM's claim and
the user's screen either agree or don't — not cataloguing UI
comprehensively.

## Scope, settled (was open question #1 in the old draft)

**Not** "every element" and **not** even the earlier-guessed "~30-50
commonly-instructed elements." Narrower: **only elements that appear in
the canonical first tasks** — open a project, drop in a track, browse
for/preview a sound or instrument, hit play, arm/mute/solo a track, save.
If a candidate manifest entry doesn't map to one of those concrete
first-task actions, it's out of scope for v1, even if it would be easy to
capture while we're in there. Exception carved out: enough of
Preferences/Settings to name the path correctly (e.g. audio device setup
is a real beginner blocker), but not the internals of every settings tab.

Test for whether something belongs in the manifest: would getting this
wrong break the LLM/user handshake during one of the canonical first
tasks? If not, it's out.

## Version range, settled (was open question #2 in the old draft)

**Current Ableton 12.x only. No 11.x.** Reasoning: a beginner installed
recently, so they're on a recent 12.x point release by construction —
someone still on 11.x who knows Ableton well enough to still be running
it isn't this project's user. Track point-release granularity (12.0 →
12.1 → 12.2 etc.) only where an element demonstrably moved — don't
pre-catalog all point releases as if they're equally likely to diverge;
most first-task chrome is stable release to release.

## The consumption mechanism, now demonstrated (not just designed)

The old draft proposed a manifest as an LLM-only tool-call fact-base and
separately worried that this leaves the *user* with nothing to visually
verify against, since a beginner can't confirm "yes, that's the button"
from a text description alone. Rebuilding a full interactive HTML mockup
to fix that was considered and rejected — it reintroduces version drift
into a hand-drawn asset instead of solving it, and is expensive to
maintain in parallel with the manifest.

**Resolution: one manifest entry, two derived outputs, both from real
screenshots — no mockup needed.**

```json
{
  "element_id": "solo_button_track4",
  "label": "Solo button",
  "shape": "square button labeled S",
  "location": "bottom of track 4's channel strip, left of the mute dot",
  "version": "12.x",
  "bbox": [999, 944, 1024, 969],
  "source_screenshot": "02_browser-sounds-tab.png"
}
```

- **LLM consumption**: reads `label`/`location` → gives the verbal
  instruction ("click the small 'S' button at the bottom of track 4's
  channel strip").
- **User-facing consumption**: the same `bbox` is drawn as a highlight box
  on the *actual* `source_screenshot` (not a redrawn approximation) and
  shown alongside the text answer.

This was actually built and tested this session against a real uploaded
screenshot (`02_browser-sounds-tab.png`, 1936×1048), for two elements:
the Solo button on track 4, and the Drums category chip + a
double-click-to-preview sound row. Both worked as intended: text answer
plus a real, correctly-positioned highlight, no jargon comprehension
required from the user to verify the match.

**Real finding from doing this by hand, worth remembering:** getting a
`bbox` right took actual work — crop, grid overlay, zoom, cross-check,
then draw. This is the concrete cost case for eventually building the
"click the fake element in a mockup, it emits the bbox" authoring tool
from the original draft — not for the LLM's sake, but to make *this*
step (deriving accurate coordinates) fast instead of manual pixel
archaeology.

**A real version-drift example surfaced accidentally while doing this**:
the bottom of the browser panel in this Live 12 screenshot shows a
**Tuning system panel** (Octave/Note/Ref. Pitch/Freq, "Drop Tuning System
Here") — a feature that didn't exist in the Ableton versions most
existing tutorials were written against, which instead describe a preview
volume knob in roughly that location. This is a genuine, unprompted
instance of exactly the failure mode the whole project exists to prevent
— worth using as the canonical example in any write-up or pitch for this
project, since it wasn't constructed for effect.

**Schema implication confirmed**: `bbox` values are only meaningful
paired with their specific `source_screenshot` — not portable across
screenshots of different resolution. If an element's position differs
across 12.x point releases, that's a second `source_screenshot` +
`bbox` pair, not a reused image with swapped coordinates. The draft
schema's per-version `source_screenshot` field already anticipated this;
this session confirmed it's load-bearing, not optional.

## What we confirmed from the benchmarking project (re-read this session)

Re-cloned and read `context.md`, `report.md`, and
`gui-grounding-ableton-article.md` directly (not from memory). Key
findings, now confirmed rather than recalled secondhand:

- **GTA1-7B is the model to use for any future bulk bbox-extraction
  pass. UI-TARS-1.5-7B should not be run at all going forward** — this
  isn't a soft preference, it's confirmed by both the internal benchmark
  and external literature. In session 6's 30-task run, on the 7 tasks
  that showed sharp model disagreement, GTA1-7B was correct on every one
  and UI-TARS-1.5-7B missed clearly on at least 4 (one prediction landed
  in the literal corner of the screenshot, nowhere near the target
  dialog). This replicates a statistically validated split from **GUI-
  Perturbed: Domain Randomization Reveals Systematic Brittleness in GUI
  Grounding Models** (arXiv:2604.14262): GTA1-7B scores 65.8% vs. UI-
  TARS-1.5-7B's 35.0% on *relational* grounding (identifying an element
  by its relationship to others, not direct naming) — even though UI-
  TARS actually wins the aggregate ScreenSpot-Pro leaderboard (61.6% vs.
  55.5%), so leaderboard rank would have picked the wrong model. GTA1 is
  UI-TARS-1.5 plus extra GRPO reinforcement learning with a direct
  click-reward; that extra RL stage specifically recovers relational/
  spatial reasoning that UI-TARS's SFT/DPO training degrades below even
  the untrained Qwen2.5-VL base (35.0% vs. 45.0%).
- **Practical implication for triage**: GTA1 is reliable on direct-naming
  instructions ("click the Sounds item," "click the Solo button") without
  much extra checking; it should still be manually verified (crop/zoom/
  view, as done by hand this session) specifically on *relational*
  instructions ("the second chain's title," "the title bar of the middle
  device") — that's where the failure risk concentrates, in GTA1 too, per
  the paper's 65.8% (not 100%) score on that category.
- **Reassuring overlap with this project's scope**: almost everything in
  the beginner/first-task curated set (Solo button, browser categories,
  double-click-to-preview) is direct-naming, not relational — exactly the
  category both models handled well in the original benchmark. The
  relational-disambiguation failure cases in the old dataset (chain title
  vs. device title bar; locator flag vs. loop brace) are power-user
  territory already outside this project's scope. So the manifest's
  actual verification burden is lower than the benchmark's worst-case
  numbers might suggest — most future entries should be low-risk to
  extract in bulk.
- **Reuse the debugged Colab script (`gui_grounding_benchmark.py`) as-is
  for any future bulk-extraction pass** — it already has two
  infrastructure bugs fixed that cost real time in the old project's
  sessions 1–2: HF model cache not clearing between model loads (blew
  Colab's disk), and a `transformers` API drift where GTA1's image
  processor moved `min_pixels`/`max_pixels` off direct attributes into a
  nested `.size["shortest_edge"/"longest_edge"]` dict. No need to
  rediscover either.
- **Cost implication of dropping UI-TARS from future runs**: GTA1-7B loads
  in ~86s vs. UI-TARS's ~251s (about 3x), so a GTA1-only bulk pass is both
  cheaper and faster, not just more accurate for this use case — there's
  no longer a reason to pay for the second model at all, since the
  "which one do we trust" question that motivated running both is
  answered.
- **Coordinate-agreement triage is reusable as a technique even with one
  model now** — e.g. running the same instruction phrased two different
  ways through GTA1 and treating close agreement as a self-consistency
  signal, reserving manual crop/zoom verification for cases that
  disagree or are known relational tasks. Not yet tried; worth testing
  before assuming it's a good substitute for the old two-model
  comparison.
- **The 15 shortlisted screenshots and 30 (instruction, coordinate) pairs
  are real, present in the repo, and directly usable** — confirmed by
  browsing the cloned repo this session (`shortlisted_screenshots/`,
  `report.md`'s full coordinate table). These cover browser tabs, device
  views, several menus, automation, locators, and a save dialog, and can
  seed manifest entries for elements that fall in scope without any new
  Colab run.
- **dHash + farthest-point-sampling screenshot curation
  (`select_diverse_screenshots.py`)** remains a reusable tool if a future
  bulk pass needs to select a new, diverse set of raw screenshots (e.g.
  across several 12.x point releases) rather than eyeballing which ones
  to keep.

## First things to do next session

1. **Draft the actual element list** for the "canonical first tasks"
   scope defined above (open project, add track, browse/preview sound,
   play, arm/mute/solo, save, minimal Preferences path). Cross-reference
   against the 30 existing (instruction, coordinate) pairs to see how
   many are already covered vs. need fresh extraction.
2. **Finalize the manifest schema** — the draft shape (`element_id`,
   `label`, `shape`, `location`, `versions` block, `bbox`,
   `source_screenshot`) held up under real use this session; formalize it
   as JSON Schema and decide how per-point-release entries nest under a
   single `element_id`.
3. **Decide the tool-calling convention** — `lookup_ui_element(name, ...,
   ableton_version)`-style shape was assumed throughout this session's
   demos; confirm the actual calling convention before building around
   it, since that affects schema ergonomics.
4. **For any new bulk extraction**: use GTA1-7B only, via the existing
   debugged script; classify each candidate instruction as direct-naming
   vs. relational before running, and only budget manual crop/zoom
   verification time for the relational ones (should be a small minority
   given this project's scope).
5. **Build the highlight-rendering step** as an actual reusable function
   (bbox + screenshot in, cropped/annotated image out) rather than
   redoing the crop/grid/zoom/draw process by hand each time, as was done
   manually this session for two elements.
6. Sketch the authoring-tool UI (the original "mockup" framing, now
   understood as an authoring tool that emits `bbox` values rather than a
   thing shown to end users) only after the schema is finalized per item
   2.
7. Set up this project's own repo/README pointing back to
   `gui_grounding_benchmark` for lineage, copying over only the specific
   reusable assets listed above.
