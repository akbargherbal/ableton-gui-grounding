# Context Handoff: `ableton-gui-grounding` V2 Audit

This file is written by the AI Assistant for its future self, to restore session context across stateless sessions. Keep it actively maintained with key insights, decisions, and enduring context, while aggressively pruning low-value detail. Record only what will materially help a future session; the user's own testing/observations are ground truth over any theory the AI Assistant proposes.

---

### Project Goal

An AI agent teaches a student Ableton Live 12 hands-on. Every action taken on the student's behalf must be **grounded**: verified against the actual UI state (not assumed) and shown to the student step-by-step via screenshots (not just a before/after outcome).

This is the standard every audit finding in this file is judged against ("does this serve grounded, step-by-step teaching"), rather than DAW/Ableton feature-completeness for its own sake.

---

To prevent documentation confusion across sessions:

**Active Docs in Scope:**

- `context.md` (this file — single source of handoff truth)
- `docs/routing_test_protocol.md` (the 16-probe, Tier 0–7 test protocol; the answer key — never shipped to the agent's runtime folder)

**Archived Docs (`docs/archived/*`):**
_Archived docs are strictly out of scope. Do not read, cite, or treat them as current for audit decisions._

---

**Constraint:** the AI Assistant has no direct access to Ableton/Windows — Linux sandbox only. All live verification is done by the user; pasted terminal/screenshot output is ground truth. Audit is expected to span 2–3 sessions (long back-and-forth per verification), hence this file.

---
