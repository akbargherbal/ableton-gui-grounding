# Screenshot Documentation Strategy: Orchestrator Script (Option B)

**Status:** Recommended
**Author:** [your name]
**Context:** `automate_ableton_task.py` (runs under native Windows `python.exe`, drives Ableton via `pywinauto`) and `take_shot.sh` (runs under WSL bash, captures the Ableton window via PowerShell/.NET) currently operate as two fully independent scripts. This document evaluates how to add per-action screenshot documentation without merging their internals.

---

## 1. Problem

We want a screenshot after (ideally) every UI action the automation performs — not just a single "after" shot per task — so tutorial/lab output reflects the actual process, not just the end state. `automate_ableton_task.py` and `take_shot.sh` currently know nothing about each other and run in different environments (Windows-native Python vs. WSL bash), which rules out a naive in-process call from one to the other.

## 2. Options Considered

| Option | Description |
|---|---|
| A — Atomic CLI | Split multi-step tasks into one-click-per-invocation commands; document manually, calling each script by hand |
| **B — Orchestrator script** | **A new third script that calls both tools alternately from the outside, without editing either** |
| C — File-signal + watcher | Automate script writes a marker file per action; a separate WSL watcher process picks it up and fires the screenshot |
| D — Event log only | Automate script logs actions with timestamps; screenshots taken manually/after the fact based on the log |

Full comparison matrix available on request; summary below focuses on the recommended option.

## 3. Recommendation: Option B (Orchestrator Script)

Introduce a new script (e.g. `run_and_capture.py` or `.bat`) that sits outside both existing tools and coordinates them:

- Invokes `automate_ableton_task.py` via `python.exe` (Windows)
- Invokes `take_shot.sh` via `wsl.exe` (from Windows) or directly (from WSL)
- Detects which host environment it's running in and adapts accordingly

### Why this is the right default

- **Non-invasive.** Neither existing script is modified. Both remain independently correct, independently testable, and safe to keep using standalone (e.g. `take_shot.sh` for manual screenshots unrelated to automation, or `automate_ableton_task.py` run without any documentation step at all).
- **Disposable.** The orchestrator can be deleted at any time with zero impact on either underlying tool. It owns 100% of the coupling logic, so removing coupling later is a one-file deletion, not a refactor.
- **Environment-flexible.** A single orchestrator can run from either WSL or native Windows and dispatch correctly to each tool's expected environment, rather than forcing the user to remember which shell to open for which script.
- **Clear separation of concerns.** `automate_ableton_task.py` stays focused on driving Ableton; `take_shot.sh` stays focused on capture; the orchestrator's only job is sequencing. This keeps each script's blast radius small when something breaks.

## 4. Known Shortcomings (Acknowledged)

This recommendation comes with real limitations the team should plan around before treating it as "solved":

1. **Doesn't achieve per-click granularity on its own.** Multi-step tasks like `solo_tour` run as a single Python process internally (solo → play → sleep → stop → unsolo, looped). The orchestrator only regains control once that whole subprocess exits, so it can capture "before task" / "after task," not each individual click inside it. Reaching true per-click screenshots requires pairing B with Option A — splitting multi-step tasks into atomic sub-commands the orchestrator can loop over individually.

2. **Synchronization is inherently fragile.** The orchestrator needs to know *when* an action completed. Without touching `automate_ableton_task.py`, the only signal available is stdout — which means parsing print output not designed as a stable contract. A cosmetic wording change in the automate script's output could silently break the orchestrator with no corresponding change to that script itself.

3. **Latency and timing risk per screenshot.** Each capture spins up `wsl.exe`/`powershell.exe`/.NET types from scratch. Doing this immediately after every action adds real overhead, and a completed click doesn't guarantee Ableton has finished re-rendering — screenshots can land mid-transition. The two timing sources (Python's click completion, PowerShell's capture) aren't synchronized to a shared event.

4. **Combined failure surface.** If a screenshot step throws (e.g. `ERROR:FOCUS_FAILED`, possibly because the *capture itself* stole window focus), the orchestrator must decide whether to abort, retry, or skip — and that decision logic lives only in the orchestrator. A wrong call here risks leaving Ableton in a bad state (e.g., mid-`solo_tour`'s restore step interrupted) with nothing in either original script aware anything went wrong.

5. **Cross-OS detection is itself a maintenance liability.** "Am I on WSL or native Windows" logic (checking `$WSL_DISTRO_NAME`, `/proc/version`, etc.) effectively creates two divergent code paths under one filename, each needing separate testing.

6. **Path/format mismatches compound.** `take_shot.sh` already handles `/mnt/c/...` ↔ `C:\...` translation and DrvFs caching lag internally. The orchestrator adds a second layer that must agree with both scripts on lab-folder naming across two path conventions — another place for off-by-one or slash-direction bugs.

7. **Debugging spans three scripts and two OS boundaries.** A failure could originate in the automate script's logic, the orchestrator's coordination layer, the WSL↔Windows bridge, or `take_shot.sh` itself — stack traces get diluted across extra subprocess layers.

8. **Silent drift risk.** Because the orchestrator is deliberately decoupled (calling both scripts as black boxes), nothing enforces that it stays in sync if `automate_ableton_task.py`'s task names, flags, or output format change later. It will fail at runtime rather than at review time.

## 5. Shortcomings Evaluated: Blast Radius, Effort, and Where to Fix Them

None of the eight shortcomings above are fixed facts — each can be reduced, and it's worth being precise about *how bad it is if ignored* versus *how much work it takes to fix it, and in which script*. This is the basis for the phased plan in Section 6.

| # | Shortcoming | Blast Radius | Elimination Effort | Where it must be fixed |
|---|---|---|---|---|
| 1 | No per-click granularity for multi-step tasks | **Low** — contained to `solo_tour`-style tasks only, doesn't affect single-action tasks at all | **Medium** — requires splitting `solo_tour` into atomic sub-commands (solo, play, stop, unsolo as separate CLI invocations) | `automate_ableton_task.py` (this *is* Option A) — orchestrator can't fix this alone |
| 2 | Fragile stdout-parsing synchronization | **High** — silent breakage on any wording change, no test would catch it until a documentation run visibly fails or mis-times | **Low–Medium** — add a stable, versioned structured event (e.g. one `EVENT:<name>:<status>` line, or `--json-events` flag) after each action | `automate_ableton_task.py` (small, additive, non-breaking change) — the single highest-leverage fix on this list |
| 3 | Timing/mid-transition captures | **Medium** — degrades screenshot quality, doesn't corrupt state or crash anything | **Low** — add a short settle delay before invoking the screenshot call, or better: wait on the same structured "action complete" event from #2 | Orchestrator only (if a fixed delay is enough); or piggybacks on #2's fix for a real readiness signal instead of a guessed sleep |
| 4 | Combined failure surface (screenshot error mid-automation) | **High** — worst-case leaves Ableton in a bad live state (track stuck soloed, transport running) | **Medium** — wrap each screenshot call in try/except that logs-and-continues rather than propagating; keep `automate_ableton_task.py`'s own `finally`-based restore logic as the sole safety net | Orchestrator only — doesn't require touching either existing script, since the automate script's restore-on-error logic already exists and just needs to stay untouched/authoritative |
| 5 | Cross-OS (WSL/Windows) detection logic | **Low** — self-contained bug surface, doesn't leak into either tool's correctness | **Low** — one well-tested detection block (`$WSL_DISTRO_NAME` / `uname` check), written once, rarely touched again | Orchestrator only |
| 6 | Path/format mismatches (`/mnt/c/...` vs `C:\...`) | **Medium** — silent wrong-folder writes are easy to miss until someone looks for a screenshot that isn't there | **Low** — orchestrator should never re-derive paths itself; always pass the lab path through in whichever format the receiving script already expects (deferring entirely to `take_shot.sh`'s own conventions) | Orchestrator only — mostly discipline, not new code |
| 7 | Debugging spans three scripts / two OS boundaries | **Medium** — developer friction and slower incident response, not a runtime correctness risk | **Medium** — tag each layer's output distinctly (e.g. prefix `[automate]`, `[shot]`, `[orchestrator]`) so failures are attributable at a glance | Orchestrator (wraps both); largely "free" since both existing scripts already use `ERROR:`/`NOTE:` prefixes |
| 8 | Silent drift (task renames/flag changes break orchestrator unnoticed) | **High** — invisible until it fails in front of someone trying to document a lab, worst possible timing | **Medium–High** — needs an actual contract: a `--list-tasks`/`--schema` introspection flag the orchestrator checks before running, or a CI smoke test against the automate script's current CLI | Primarily `automate_ableton_task.py` (expose a stable introspection surface) + orchestrator (consume it) — the most cross-cutting fix on the list |

**Reading the table:**

- **Cheapest, highest-leverage fix:** #2 (structured stdout events). Small, additive, non-breaking change to `automate_ableton_task.py` that also substantially de-risks #3 (real readiness signal instead of a guessed delay) and reduces the surface area of #7 for free.
- **Contained to the orchestrator, zero risk to the other two scripts:** #3 (with a sleep fallback), #4, #5, #6, #7 — five of the eight can be meaningfully reduced without opening either existing file at all.
- **Requires deliberately touching `automate_ableton_task.py`:** #1 and #8. These are the two structural ones — #1 because atomic-task decomposition is a real feature addition, and #8 because "don't silently drift" needs something on the producing side to check against, not just orchestrator-side defensiveness.
- **Highest risk if left alone:** #2, #4, and #8 — these are the three where "ignore it" doesn't fail loudly; it fails as a wrong or missing screenshot, or a stuck Ableton session, discovered only later.

## 6. Recommended Path Forward

Treat Option B as the **coordination layer**, not the full solution, and sequence the work by leverage rather than by shortcoming number:

1. **Phase 0 (highest ROI, do first):** Add structured events to `automate_ableton_task.py` (shortcoming #2's fix). One small, additive, backward-compatible change that also weakens #3, #7, and lays the groundwork for #8's contract.
2. **Phase 1:** Ship the orchestrator as a thin wrapper for tasks that are already single-action (`arm_track`, `set_tempo`, `probe_*`) — works cleanly today with none of the granularity caveats. Contain all failure handling, path handling, OS detection, and logging conventions to the orchestrator itself (#3–#7), touching neither existing script beyond Phase 0.
3. **Phase 2:** For multi-step tasks (`solo_tour` and future equivalents), apply Option A — break them into atomic sub-commands — then let the orchestrator loop over those atomic calls with a screenshot after each. This directly resolves #1.
4. **Phase 3 (as the toolset grows):** Add an introspection surface (`--list-tasks`/`--schema`) or CI smoke test so the orchestrator can detect drift in `automate_ableton_task.py`'s CLI before it fails silently mid-documentation-run (#8).
5. **Throughout:** Treat orchestrator failures conservatively — on any screenshot error, log and continue rather than retry-loop against a live Ableton session, to avoid leaving automate-side state (armed tracks, soloed tracks, transport running) stuck mid-sequence (#4).

## 7. Summary

Option B best satisfies the constraint of keeping `automate_ableton_task.py` and `take_shot.sh` untouched and independently disposable, while remaining flexible across the WSL/Windows split our environment already has to deal with. Its real costs — synchronization fragility, incomplete granularity for multi-step tasks, and silent-drift risk — are all addressable, and five of the eight identified shortcomings can be resolved entirely within the orchestrator itself, with zero risk to either existing script. The two that do require touching `automate_ableton_task.py` (atomic task decomposition and CLI introspection) are also the two with the highest payoff, and should be prioritized accordingly rather than treated as optional polish.
