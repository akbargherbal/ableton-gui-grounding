# Routing test results — live probe log

Analysis log for `docs/routing_test_protocol.md`'s 16 probes (`docs/prompts.json`, P0.1–P7.1), run live against `../ableton-ai-training/` (the isolated runtime built by `build_runtime_env.sh`). One Tier analyzed per session — see `context.md`'s "Session 7+ Plan" for cadence and rationale.

**Ground rule for every entry below:** do not assume our own harness/prompting/environment was correct by default. Every probe gets checked on **both** sides:

- **Our-side issues** — anything about the harness, the prompt itself, the environment (Python version, working directory, MCP config location, YOLO-mode settings), or how the test was run that could have produced a misleading result.
- **Agent-side issues** — whether the agent's actual tool-call sequence matches the probe's `Watch for`/`Pass`/`Fail` criteria in `routing_test_protocol.md`, independent of whether the final Ableton state happened to look right.

A probe is only judged against `AGENTS.md`'s routing rules once the our-side column is clean for that run — a fail on a contaminated run tells us to fix the harness and re-run, not to conclude the routing rule failed.

Status legend: `NOT ANALYZED` / `IN PROGRESS` / `DONE`

---

## Tier 0 — Does it find the rules at all? (P0.1, P0.2)

**Status: NOT ANALYZED**

**Source transcripts:** TBD — need to confirm which of `result_01.md`–`result_07.md` correspond to P0.1/P0.2 (not yet confirmed to be in probe order).

### P0.1 — Cold-start routing discovery

**Our-side issues:**

**Agent-side issues:**

**Verdict:** —

### P0.2 — Drift-check awareness

**Our-side issues:**

**Agent-side issues:**

**Verdict:** —

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

- **`python3`/`python` precedence bug in `orchestrate.sh`** (surfaced: pre-Tier-0, session 7, code-read not transcript-derived) — see `context.md` "Known open threads." Not yet fixed in code.
