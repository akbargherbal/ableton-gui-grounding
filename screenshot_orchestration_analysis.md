# Screenshot Documentation Strategy: Orchestrator Script (Option B)

**Status:** Recommended (revised)
**Author:** [your name]
**Revision note:** This is a rewrite of the original analysis. The first
draft assumed `automate_ableton_task.py` and `take_shot.sh` sit in two
environments that need active bridging (something has to detect which OS
it's on and dispatch across the boundary). Session 5's real terminal
output disproved that premise: `python.exe automate_ableton_task.py ...`,
run directly from a WSL shell, drove the real Ableton window successfully
via WSL interop. That single fact removes a full shortcoming (cross-OS
detection) and simplifies the recommended design below — this isn't a
softer opinion, it's a correction based on evidence the original draft
didn't have. Everything else in the original (granularity, stdout-parsing
fragility, timing, failure handling, drift) held up and is preserved.

**Context:** `automate_ableton_task.py` (drives Ableton via `pywinauto`,
needs Windows' native Python — confirmed callable as `python.exe` from
inside a WSL shell via interop) and `take_shot.sh` (native WSL bash,
captures the Ableton window via `powershell.exe`/.NET, also via interop)
currently operate as two independent scripts that know nothing of each
other's internals. This document evaluates how to add per-action
screenshot documentation without merging those internals.

---

## 1. Problem

We want a screenshot after (ideally) every UI action the automation
performs — not just a single "after" shot per task — so tutorial/lab
output reflects the actual process, not just the end state.

**Corrected framing:** this is *not* a two-environment bridging problem.
Session 5 confirmed both tools are reachable from a single WSL shell:

```
python.exe automate_ableton_task.py --task probe_keyboard_activator --tracks 0   # Windows Python, via interop
./take_shot.sh LABS/.../04_f1_pressed                                             # native WSL bash
```

Both ran, in the same shell, back to back. The real problem left is
narrower than the original draft framed it: **sequencing and
synchronization** — knowing *when* an automate-side action has finished
so the screenshot fires at the right moment, and handling failures in
either tool without corrupting Ableton's live state.

## 2. Options Considered

| Option | Description |
|---|---|
| A — Atomic CLI | Split multi-step tasks into one-click-per-invocation commands; document manually, calling each script by hand |
| **B — Orchestrator script** | **A new script that calls both tools in sequence, without editing either** |
| C — File-signal + watcher | Automate script writes a marker file per action; a separate watcher process picks it up and fires the screenshot |
| D — Event log only | Automate script logs actions with timestamps; screenshots taken manually/after the fact based on the log |

Full comparison matrix available on request; summary below focuses on the
recommended option.

## 3. Recommendation: Option B (Orchestrator Script)

Introduce a new script — a plain WSL bash script (matching `take_shot.sh`'s
own environment) that:

- Calls `python.exe automate_ableton_task.py ...` directly (Windows Python
  via interop — no `wsl.exe` round-trip needed, no detection logic)
- Calls `./take_shot.sh ...` directly (already native to this shell)
- Sequences the two, one action → one screenshot, in a single script

### Why this is the right default

- **Non-invasive.** Neither existing script is modified. Both remain
  independently correct, independently testable, and safe to keep using
  standalone.
- **Disposable.** The orchestrator can be deleted at any time with zero
  impact on either underlying tool. It owns 100% of the coupling logic, so
  removing coupling later is a one-file deletion, not a refactor.
- **Simpler than originally scoped.** The first draft assumed the
  orchestrator would need to detect its host OS and dispatch accordingly
  (running from either WSL or native Windows). That's no longer necessary
  — one canonical environment (WSL) reaches both tools via interop in the
  directions already confirmed live. Fewer moving parts than "portable
  across two hosts" implied.
- **Clear separation of concerns.** `automate_ableton_task.py` stays
  focused on driving Ableton; `take_shot.sh` stays focused on capture; the
  orchestrator's only job is sequencing.

## 4. Known Shortcomings (Acknowledged)

Real limitations to plan around — six now, not eight; see the note on #5.

1. **Doesn't achieve per-click granularity on its own.** Multi-step tasks
   like `solo_tour` run as a single Python process internally (solo → play
   → sleep → stop → unsolo, looped). The orchestrator only regains control
   once that whole subprocess exits, so it can capture "before task" /
   "after task," not each individual click inside it. Reaching true
   per-click screenshots requires pairing B with Option A — splitting
   multi-step tasks into atomic sub-commands the orchestrator can loop
   over individually.

2. **Synchronization is inherently fragile.** The orchestrator needs to
   know *when* an action completed. Without touching
   `automate_ableton_task.py`, the only signal available is stdout —
   parsing print output not designed as a stable contract. A cosmetic
   wording change in the automate script's output could silently break
   the orchestrator with no corresponding change to that script itself.

3. **Latency and timing risk per screenshot.** Each capture spins up
   `powershell.exe`/.NET types from scratch. Doing this immediately after
   every action adds real overhead, and a completed click doesn't
   guarantee Ableton has finished re-rendering — screenshots can land
   mid-transition. The two timing sources (Python's click completion,
   PowerShell's capture) aren't synchronized to a shared event.

4. **Combined failure surface.** If a screenshot step throws (e.g.
   `ERROR:FOCUS_FAILED`, possibly because the *capture itself* stole
   window focus), the orchestrator must decide whether to abort, retry, or
   skip — and that decision logic lives only in the orchestrator. A wrong
   call here risks leaving Ableton in a bad state (e.g., mid-`solo_tour`'s
   restore step interrupted) with nothing in either original script aware
   anything went wrong.

5. ~~Cross-OS detection is itself a maintenance liability~~ — **eliminated
   by evidence, not just designed around.** The original draft assumed the
   orchestrator would need `$WSL_DISTRO_NAME`/`uname`-style branching to
   run correctly from either host. Session 5 showed both tools are already
   reachable from one canonical shell (WSL), so there is no second code
   path to maintain. Kept here, struck through, so the reasoning trail
   isn't lost — this is exactly the kind of assumption the project's own
   "verify, don't guess" rule exists to catch.

6. **Path/format mismatches compound.** `take_shot.sh` already handles
   `/mnt/c/...` ↔ `C:\...` translation and DrvFs caching lag internally.
   The orchestrator adds a second layer that must agree with it on
   lab-folder naming — another place for off-by-one or slash-direction
   bugs.

7. **Debugging spans multiple scripts and one OS boundary** (down from two
   — see #5). A failure could still originate in the automate script's
   logic, the orchestrator's coordination layer, or `take_shot.sh` itself
   — stack traces get diluted across extra subprocess layers, just across
   one fewer hop than originally assumed.

8. **Silent drift risk.** Because the orchestrator is deliberately
   decoupled (calling both scripts as black boxes), nothing enforces that
   it stays in sync if `automate_ableton_task.py`'s task names, flags, or
   output format change later. It will fail at runtime rather than at
   review time.

## 5. Shortcomings Evaluated: Blast Radius, Effort, and Where to Fix Them

| # | Shortcoming | Blast Radius | Elimination Effort | Where it must be fixed |
|---|---|---|---|---|
| 1 | No per-click granularity for multi-step tasks | **Low** — contained to `solo_tour`-style tasks only | **Medium** — split into atomic sub-commands | `automate_ableton_task.py` (this *is* Option A) |
| 2 | Fragile stdout-parsing synchronization | **High** — silent breakage on any wording change | **Low–Medium** — add a stable, versioned structured event (e.g. `EVENT:<n>:<status>` line, or `--json-events`) | `automate_ableton_task.py` — small, additive, non-breaking; the single highest-leverage fix on this list |
| 3 | Timing/mid-transition captures | **Medium** — degrades screenshot quality only | **Low** — short settle delay, or wait on #2's event instead of guessing | Orchestrator only, or piggybacks on #2 |
| 4 | Combined failure surface | **High** — worst case leaves Ableton in a bad live state | **Medium** — log-and-continue on screenshot error, keep the automate script's own `finally`-based restore as the sole safety net | Orchestrator only — doesn't require touching either existing script |
| 5 | ~~Cross-OS detection~~ | **None — resolved by evidence** | **None** | N/A — one canonical WSL-shell environment reaches both tools already |
| 6 | Path/format mismatches | **Medium** — silent wrong-folder writes | **Low** — orchestrator never re-derives paths, always defers to `take_shot.sh`'s own conventions | Orchestrator only — mostly discipline |
| 7 | Debugging spans multiple scripts / one OS boundary | **Medium** — friction, not a correctness risk | **Medium** — tag each layer's output (`[automate]`, `[shot]`, `[orchestrator]`) | Orchestrator (wraps both); largely free, both scripts already use `ERROR:`/`NOTE:` prefixes |
| 8 | Silent drift (task renames/flag changes break orchestrator unnoticed) | **High** — invisible until it fails mid-documentation-run | **Medium–High** — a `--list-tasks`/`--schema` introspection flag, or a CI smoke test | Primarily `automate_ableton_task.py` (expose the surface) + orchestrator (consume it) |

**Reading the table:**

- **Cheapest, highest-leverage fix:** #2 (structured stdout events) — also
  substantially de-risks #3 and reduces #7's surface for free.
- **Contained to the orchestrator, zero risk to the other two scripts:**
  #3 (with a sleep fallback), #4, #6, #7 — four of the remaining seven can
  be meaningfully reduced without opening either existing file at all.
- **Requires deliberately touching `automate_ableton_task.py`:** #1 and
  #8 — the two structural ones.
- **Highest risk if left alone:** #2, #4, and #8 — these are the three
  where "ignore it" doesn't fail loudly; it fails as a wrong or missing
  screenshot, or a stuck Ableton session, discovered only later.
- **No longer on this list at all:** the original #5 (cross-OS detection).
  Not mitigated — removed, because the premise it was solving for turned
  out not to hold.

## 6. Recommended Path Forward

Treat Option B as the **coordination layer**, not the full solution,
sequenced by leverage:

1. **Phase 0 (highest ROI, do first):** Add structured events to
   `automate_ableton_task.py` (#2's fix). Small, additive,
   backward-compatible; also weakens #3 and #7, and lays groundwork for
   #8's contract.
2. **Phase 1:** Ship the orchestrator as a plain WSL bash script for tasks
   that are already single-action (`arm_track`, `set_tempo`, `probe_*`) —
   works cleanly today, no host-detection branch needed, none of the
   granularity caveats apply. Contain all failure handling, path
   handling, and logging conventions to the orchestrator itself (#3, #4,
   #6, #7), touching neither existing script beyond Phase 0.
3. **Phase 2:** For multi-step tasks (`solo_tour` and future equivalents),
   apply Option A — break them into atomic sub-commands — then let the
   orchestrator loop over those atomic calls with a screenshot after each.
   Directly resolves #1.
4. **Phase 3 (as the toolset grows):** Add an introspection surface
   (`--list-tasks`/`--schema`) or CI smoke test so the orchestrator can
   detect drift in `automate_ableton_task.py`'s CLI before it fails
   silently mid-documentation-run (#8).
5. **Throughout:** Treat orchestrator failures conservatively — on any
   screenshot error, log and continue rather than retry-loop against a
   live Ableton session, to avoid leaving automate-side state (armed
   tracks, soloed tracks, transport running) stuck mid-sequence (#4).

## 7. Summary

Option B best satisfies the constraint of keeping
`automate_ableton_task.py` and `take_shot.sh` untouched and independently
disposable. The original draft treated this as a genuinely cross-platform
bridging problem needing host detection and dual code paths — Session 5's
real terminal output (`python.exe` invoked successfully from inside WSL)
showed that premise was wrong: one WSL shell already reaches both tools in
both directions via interop. That removes a full shortcoming outright,
not just a mitigated one, and simplifies the orchestrator from "detect
host, dispatch accordingly" to "one script, two subprocess calls."

What remains — synchronization fragility, incomplete granularity for
multi-step tasks, and silent-drift risk — is real and still needs the
phased plan above. But four of the seven remaining shortcomings are
containable entirely within the orchestrator with zero risk to either
existing script, and the two that require touching
`automate_ableton_task.py` (atomic task decomposition and CLI
introspection) are also the two with the highest payoff — same
prioritization as before, on a shorter, more accurate list.
