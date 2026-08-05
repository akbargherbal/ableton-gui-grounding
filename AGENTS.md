# AGENTS.md — `ableton-gui-grounding`

Read `context.md` first for current project state and known issues. This file is standing rules only.

## Environment

- Use `python`, not `python3` (`python3` = stale 3.10, `python` = active 3.12).
- Automation runs from WSL, shelling out to `python.exe`/PowerShell for anything touching the live Windows Ableton UI.

## Audience

Don't assume the user knows Ableton, DAW or music theory. Explain plainly.

## Docs

- `context.md` — project goal, current state, agenda, known issues. Read first.
- `docs/v2_observations.md` — verification log behind those decisions.
- `docs/ableton_ai_educational_risk_framework.md` — design doc; code wins on conflict.
- `docs/opencode-ableton-mcp-setup.md` — MCP architecture reference.
- `docs/archived/*` — out of scope, ignore.

## Control paths

- **UIA-direct** (primary): `automate_ableton_task.py` → `orchestrate.sh` → `take_shot.sh`.
- **MCP**: OpenCode → `ableton-mcp-extended` → TCP → Ableton Remote Script.
- Don't mix paths mid-task without a reason. See `context.md` for known issues with each path before choosing one.

## Working rule

Read code and verify live rather than asking the user to recall implementation details.
