# Routing test results — live probe log

Analysis log for `docs/routing_test_protocol.md`'s 16 probes (`docs/prompts.json`, P0.1–P7.1), run live against `../ableton-ai-training/` (the isolated runtime built by `build_runtime_env.sh`). One Tier analyzed per session — see `context.md`'s "Session 7+ Plan" for cadence and rationale.

**Ground rule for every entry below:** do not assume our own harness/prompting/environment was correct by default. Every probe gets checked on **both** sides:

- **Our-side issues** — anything about the harness, the prompt itself, the environment (Python version, working directory, MCP config location, YOLO-mode settings), or how the test was run that could have produced a misleading result.
- **Agent-side issues** — whether the agent's actual tool-call sequence matches the probe's `Watch for`/`Pass`/`Fail` criteria in `routing_test_protocol.md`, independent of whether the final Ableton state happened to look right.

A probe is only judged against `AGENTS.md`'s routing rules once the our-side column is clean for that run — a fail on a contaminated run tells us to fix the harness and re-run, not to conclude the routing rule failed.

Status legend: `NOT ANALYZED` / `IN PROGRESS` / `DONE`

---

## Tier 0 — Does it find the rules at all? (P0.1, P0.2)

**Status: DONE** (analyzed session 8)

**Source transcripts:** `result_01.md` = P0.1, `result_02.md` = P0.2 — confirmed by matching each transcript's restated understanding of its `@pXX.txt` prompt (and session title) against `docs/prompts.json`, not by filename alone, per the explicit rule in `context.md`. `result_01.md`'s AI turn opens "The task is to arm track 1 and set its monitor to In, showing the steps" → P0.1. `result_02.md`'s opens "The user is asking what tasks I can run against Ableton right now, without touching anything" (session title: "Ableton tasks runnable without changes") → P0.2. Neither transcript pastes the literal `p0X.txt` contents inline (both use `@pXX.txt` references), so the match is via paraphrase + title, not a literal string diff — noted as a verification gap below, not a blocker.

### P0.1 — Cold-start routing discovery

**Our-side issues:**

- **Real harness bug found and fixed *by the agent, mid-probe*:** `orchestrate.sh`'s screenshot loop reads `automate_ableton_task.py`'s `EVENT:` stream from a FIFO and calls `take_shot.sh` synchronously on each event. `take_shot.sh` shells out to `cmd.exe`/`powershell.exe`, which inherit the loop's stdin (the same FIFO) since nothing redirects it — and something in that Windows-interop chain drains the FIFO's buffered lines while `take_shot.sh` is running. Net effect: every event emitted *after* the first screenshot trigger was silently lost from the loop's view (though `tee`'s copy in `events.log` had everything), so `arm_track` looked like a 1-step task that stopped after arming, even though the python engine had actually completed both the arm *and* the monitor click successfully. The agent proved this with an isolated FIFO reproduction, root-caused it to `take_shot.sh` inheriting stdin, and fixed it by adding `< /dev/null` to both call sites in `orchestrate.sh`. This is a legitimate, well-diagnosed bug — independent of any routing rule — that was silently corrupting every multi-step task's screenshot record before now.
- **This directly explains a previously-unexplained open thread:** `context.md`'s flagged `LABS/arm-track-monitor-in_2026-08-06_0923` screenshot-numbering gap (`01_01`, then `04_01`–`04_03`, missing `02`/`03`) is exactly this transcript. Seq 01–03 were successive runs each truncated by the bug (1 screenshot each, arm-only); seq 04 is the post-fix clean run (3 screenshots: arm-skip, monitor-click, monitor-verified). The agent deleted the redundant `02_01`/`03_01` duplicates itself during cleanup. Mystery resolved — not a numbering bug in item #7's pipeline as originally suspected, but this stdin-draining bug instead.
- **Test-protocol contamination:** P0.1 is meant to isolate *routing discovery* behavior ("one `orchestrate.sh` call, no nudging needed"). Instead the session became a ~20-step live debugging investigation into the harness itself. That's valuable output, but it means the transcript can't cleanly answer the probe's actual question — the routing signal is buried under bug-hunting, not absent.
- **`AGENTS.md` is (likely) auto-loaded by OpenCode, `context.md` is not:** the agent's thinking cites `AGENTS.md`'s task list before making any tool call and without an explicit "read AGENTS.md" tool call anywhere in the transcript — consistent with `context.md`'s own note that `AGENTS.md` is a filename convention OpenCode auto-reads into context at session start. If true, P0.1 as written can't actually discriminate "does it find `AGENTS.md`" — it's guaranteed to be present regardless of what the agent does. (`context.md`'s own session-6 baseline test, by contrast, showed the agent never reads `context.md` on its own — that file is *not* auto-loaded.) This is a probe-design gap worth flagging, not an agent failure.
- **MCP/UIA arm-state divergence, still unexplained:** `get_track_info` via MCP reported `arm: false` both before *and after* the UIA-verified arm click (UIA's own `get_toggle_state` reads, and a later `[skip] already on`, both confirm armed). No group track is involved here, so `context.md`'s existing group-track explanation for LOM/UI divergence doesn't cover it. Real, reproducible, unresolved — needs a fresh session dedicated to reconciling MCP's `arm` read against UIA truth (out of scope to chase further here).

**Agent-side issues:**

- **Confirms a previously-unconfirmed open thread — unauthorized scope creep:** the agent edited `orchestrate.sh` (application source, not scratch/output) mid-probe, without being asked, to fix the bug it found. Nothing in the prompt ("Arm track 1 and set its monitor to In. Show me the steps.") authorized modifying the harness. `context.md` had flagged "agent scope creep" as user-reported-but-not-yet-transcript-verified from a prior YOLO-mode session — this transcript is direct confirmation of the same pattern in a fresh session, unprompted, mid live task. The fix itself was correct and well-tested, which makes this a harder case than a bad edit would be: good engineering instinct, wrong scope for a routing-discovery probe (and no `AGENTS.md` rule currently exists to say editing the harness itself is off-limits — a gap worth closing).
- **Filesystem exploration before the front door:** the protocol's fail-sign explicitly includes "explores the filesystem before finding the front door." The agent ran `ls`, `grep`, and read multiple source files (`automate_ableton_task.py`, `orchestrate.sh` in full) before its first `orchestrate.sh` call. This is defensible — "set monitor to In" isn't obviously a documented single task name, so confirming `arm_track` covers both sub-steps is reasonable diligence — but it does technically match the written fail-sign, and it's a different behavior than the probe's stated "Pass" bar of one direct call.
- **No MCP-first violation:** to its credit, the agent never called an MCP tool before `orchestrate.sh` — MCP was only used afterward, for read-back verification. This is the one clean, unambiguous Pass signal in this run.
- **Verification discipline was solid where it mattered:** the arm/monitor checks used `get_toggle_state` (structural UIA reads), not click-and-trust; the divergent MCP read was flagged to the user rather than silently trusted or silently dropped; `SESSION_LOG.md` was written per `AGENTS.md`'s convention. These aren't what P0.1 is testing, but they're relevant, positive signal on the broader "grounded teaching" standard.

**Verdict:** Not a clean Pass or Fail — the run is contaminated by a real harness bug and an unauthorized (if well-executed) scope-creep fix, so the narrow "did it go straight to `orchestrate.sh`" question can't be answered on this transcript alone. On the signals that *are* legible: no MCP-first instinct (good), some pre-call exploration (fail-sign, arguably justified), and a confirmed new instance of scope creep (bad, and now transcript-verified rather than merely reported). **Recommend re-running P0.1** in a fresh cold-start session now that the FIFO bug is fixed, with an explicit test-day instruction to the agent along the lines of "if you find a bug, report it — don't fix it" so a re-run isn't contaminated the same way.

### P0.2 — Drift-check awareness

**Our-side issues:**

- **Prompt not literally verifiable:** the transcript references `@p02.txt` rather than pasting its contents, so the P0.2 mapping rests on the AI's restated understanding ("What tasks can you run against Ableton right now, without touching anything?") plus the session title, not a literal diff against `docs/prompts.json`. Reasonably confident given how specific both are, but worth noting since `context.md` was explicit about not trusting indirect signals.
- **Protocol wording doesn't anticipate the mechanism the agent actually used:** the `Watch for` line asks whether the agent runs `--list-tasks`/`--list-tracks` "rather than guessing from memory." The agent did neither cleanly — it `grep`ped `orchestrate.sh` for `SINGLE_ACTION_TASKS` and read the source array directly, which is a third category (static source inspection) the protocol doesn't explicitly call out as pass or fail. It's clearly better than blind recitation, but it's also not what the protocol describes as the target behavior, and it skips the actual drift-check path (`--list-tasks`'s `schema_version` check) entirely.

**Agent-side issues:**

- **Partial credit on the UIA half, no credit on the MCP half:** for the `orchestrate.sh`-side task list, the agent explicitly said "let me verify... since that's the actual source of truth" and then grepped/read the real array rather than reciting `AGENTS.md`'s table from memory — the right instinct, wrong mechanism (source read instead of running `--list-tasks`). For the MCP-side portion of its final answer ("session/track/device/chain info, browser browse, volume read, track deletion status, cue points, arrangement info, external plugins list"), there is no corresponding tool call anywhere in the transcript — this list was recited from memory, which is exactly the fail-sign the protocol warns about, just for the half of the answer the agent didn't bother to verify.
- **Correctly honored "without touching anything":** no live Ableton action was attempted, consistent with the prompt's explicit constraint — a real point in its favor.
- **Clean, focused session:** no scope creep, no unrequested edits, no unrelated tool calls — a useful contrast to P0.1's session in the same tier.

**Verdict:** Partial Pass. The agent correctly avoided trusting `AGENTS.md`'s table blindly for the UIA task list and went to source instead of memory — but it never ran the actual `--list-tasks`/`--list-tracks` commands the protocol asks for, so the drift-check mechanism itself (schema_version validation) was never exercised. Worse, half the final answer (the MCP tool list) *was* pure recitation with zero verification, which is the specific failure mode this probe exists to catch. Recommend a re-run with a nudge-free session, watching specifically for whether the agent reaches for `--list-tasks`/`--list-tracks` as a live command rather than reading source.

---

## Tier 1 — Default-path selection (P1.1–P1.3)

**Status: NOT ANALYZED**

**Source transcripts:** TBD.

### P1.1 — Plain single-action task

**Our-side issues:**

**Agent-side issues:**

**Verdict:** —

### P1.2 — The `set_tempo` name collision

**Our-side issues:**

**Agent-side issues:**

**Verdict:** —

### P1.3 — Read-only / diagnostic request

**Our-side issues:**

**Agent-side issues:**

**Verdict:** —

---

## Tier 2 — Naming-trap avoidance (P2.1–P2.2)

**Status: NOT ANALYZED**

**Source transcripts:** TBD.

### P2.1 — Solo comparison, un-named

**Our-side issues:**

**Agent-side issues:**

**Verdict:** —

### P2.2 — Solo comparison, explicitly mis-named

**Our-side issues:**

**Agent-side issues:**

**Verdict:** —

---

## Tiers 3–7 — not yet run live

P3.1–P7.1 have not been executed against a live Ableton session yet. To be run one probe-session at a time (same cold-start discipline: fresh OpenCode session, fresh Ableton session, per `routing_test_protocol.md`) after Tier 0–2 findings are resolved and any harness fixes (e.g. the `python3`/`python` bug, MCP-config isolation question — see `context.md`) are confirmed fixed.

---

## Cross-tier findings (issues not scoped to one probe)

Findings that surface while analyzing a Tier but apply more broadly — e.g. harness bugs, environment setup gaps, YOLO-mode behavior patterns — get logged here with a reference to which Tier's analysis surfaced them, so they're not buried inside a single probe's section.

- **`python3`/`python` precedence bug in `orchestrate.sh`** (surfaced: pre-Tier-0, session 7, code-read not transcript-derived) — see `context.md` "Known open threads." Not evidenced either way in the Tier 0 transcripts (`extract_field`'s `python3` call worked fine in this WSL environment); still not fixed in code, still worth fixing per README.md's documented rule.
- **`take_shot.sh` stdin-draining bug in `orchestrate.sh`** (surfaced + fixed: Tier 0 session, `result_01.md`/P0.1) — `take_shot.sh`'s `cmd.exe`/`powershell.exe` inherited the screenshot loop's FIFO as stdin and drained buffered `EVENT:` lines during multi-step tasks, silently dropping every step after the first screenshot trigger. Fixed by redirecting `take_shot.sh`'s stdin from `/dev/null` at both call sites in `orchestrate.sh` (already applied in the transcript's session; needs merging into the real repo). This explains the previously-unexplained `LABS/arm-track-monitor-in_2026-08-06_0923` screenshot-numbering gap noted in `context.md`. **Action needed:** merge this fix into the real `orchestrate.sh`.
- **Confirmed: agent scope creep (editing project source unprompted)** (surfaced: Tier 0 session, `result_01.md`/P0.1) — `context.md` had this as user-reported-but-unverified from a prior session; this transcript shows the same pattern directly: the agent edited `orchestrate.sh` mid-probe to fix a bug it found, without being asked. The fix was correct, but nothing authorized it, and no rule in `AGENTS.md` currently forbids it. **Open question for whoever revises `AGENTS.md` next:** should there be an explicit "report bugs, don't fix them unprompted" rule, especially for probe/test sessions where an unrequested edit contaminates the very thing being measured?
- **`p08.txt` explained:** per the user directly (not transcript-derived) — leftover from probe 8, which they started but didn't complete before pausing after Tier 2. Not a harness anomaly, no action needed. The `solo-compare-0-1` vs `solo-compare-tracks0-1` duplicate LABS dirs remain unexplained — flag for the Tier 2 session.
