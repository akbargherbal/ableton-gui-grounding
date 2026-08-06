# Connecting OpenCode (WSL) to Ableton Live 12 (Windows) — via ableton-mcp-extended

**Upgraded from the original `ahujasid/ableton-mcp` to `uisato/ableton-mcp-extended`**
(https://github.com/uisato/ableton-mcp-extended) — same two-hop shape, but a much larger
tool surface: real device-parameter read/write (EQ, compressor, reverb values — not just
"a device exists"), MIDI note transpose/quantize/batch-edit, scene management, clip envelope
info, browser-path sample/instrument loading, and an optional ElevenLabs voice-generation
integration. Unlike the original, this one isn't a `uvx`-installed package — you clone the
repo and run `MCP_Server/server.py` directly with `python`.

## The architecture

```
┌───────────────────────┐        TCP socket        ┌──────────────────────────┐
│  Ableton Live 12      │◄────(localhost:port)────►│  ableton-mcp-extended    │
│  (Windows)            │      JSON commands       │  MCP_Server/server.py    │
│  + AbletonMCP Remote  │                          │  spawned by OpenCode     │
│    Script loaded as   │                          │  as an MCP tool, via     │
│    a Control Surface  │                          │  stdio                   │
└───────────────────────┘                          └──────────────────────────┘
                                                              ▲
                                                              │ stdio (MCP protocol)
                                                    ┌──────────────────┐
                                                    │  OpenCode (WSL)  │
                                                    └──────────────────┘
```

Two hops only:

- **OpenCode ↔ MCP server**: normal MCP over stdio (same process OpenCode spawns).
- **MCP server ↔ Ableton**: a TCP socket opened by the Remote Script — this is the one
  hop that crosses the Windows/WSL boundary. Same networking story as before, so your
  mirrored-networking fix from Step 4 below still applies unchanged.

---

## Step 1 — Verify the Remote Scripts folder is actually clean

```powershell
tree "C:\ProgramData\Ableton\Live 12 Suite\Resources\MIDI Remote Scripts" -I "*.log|*.tmp|node_modules|bin|*pyc|*_pycache*"
```

Confirm `AbletonOSC` / `LiveOSC` are gone. Also check **both** places the old setup may have
left a script:

```powershell
tree "C:\Users\DELL\AppData\Roaming\Ableton\Live 12.1\Preferences\User Remote Scripts"
tree "C:\Users\DELL\Documents\Ableton\User Library\Remote Scripts"
```

If you had the original `ahujasid/ableton-mcp` script installed under **Preferences\User
Remote Scripts**, remove that `AbletonMCP` folder — the extended fork's own docs specify the
**Documents\Ableton\User Library\Remote Scripts** location instead (this is also the path
Ableton's own docs recommend for third-party scripts, so it's the more correct target either
way). Both should be free of leftovers before you install the new one.

## Step 2 — Get the code and install the Remote Script (Windows + WSL)

Clone the repo somewhere in WSL (this also gives you the MCP server itself, in the same tree):

```bash
git clone https://github.com/uisato/ableton-mcp-extended.git ~/ableton-mcp-extended
cd ~/ableton-mcp-extended
```

**Don't run `pip install -e .`** — the repo's `pyproject.toml` lists a package
(`AbletonMCP_UDP`) that doesn't actually exist at the repo root (it's only nested under
`Ableton-MCP_hybrid-server/`, for an unrelated optional UDP variant). This makes the editable
install fail every time with `error: package directory 'AbletonMCP_UDP' does not exist`,
even on a totally clean clone — it's an upstream packaging bug, not anything wrong on your end.

You don't need `-e .` anyway — `MCP_Server/server.py` is a plain script; it only needs its
dependencies importable, not the project installed as a package. So just install the
dependencies directly instead:

```bash
pip install "mcp[cli]>=1.3.0" elevenlabs python-dotenv --break-system-packages
```

If you'd rather use a venv, that's fine too — just make sure OpenCode's config (Step 5) points
at that venv's `python` explicitly, not a bare `"python"`. If OpenCode's `command` just says
`"python"`, it resolves to whatever's on OpenCode's own `PATH`, which may not be the venv you
installed into — installing with `--break-system-packages` into the system Python sidesteps
that mismatch entirely.

Then, on the **Windows** side:

1. Create a folder named `AbletonMCP` inside:
   `C:\Users\DELL\Documents\Ableton\User Library\Remote Scripts\`
2. Copy `AbletonMCP_Remote_Script\__init__.py` from the cloned repo into that folder
   (from WSL this repo is reachable at `\\wsl$\<distro>\home\<you>\ableton-mcp-extended\...`,
   or just copy the file over directly from the GitHub page).
3. Launch Ableton Live 12.
4. **Settings → Link, Tempo & MIDI** → Control Surface → select `AbletonMCP`. Input/Output → `None`.

## Step 3 — Confirm your Python setup (WSL)

Per your `AGENTS.md` rule, everything should run on `python`, not `python3`. Confirm it
resolves to 3.10+ (the fork's minimum):

```bash
python --version
```

## Step 4 — Test the bridge manually, before touching OpenCode

With Ableton open and `AbletonMCP` selected as Control Surface, run in WSL:

```bash
python ~/ableton-mcp-extended/MCP_Server/server.py
```

This should connect straight to the Remote Script's socket. Leave it running a few seconds,
then Ctrl+C. If it connects cleanly, WSL2's localhost forwarding is fine and you're done with
networking entirely.

**If it fails to connect** (refused/timeout) — that's WSL2 networking, not the Remote Script.
Enable mirrored networking mode in `%UserProfile%\.wslconfig` on Windows:

```ini
[wsl2]
networkingMode=mirrored
```

Then from PowerShell: `wsl --shutdown`, and reopen your WSL terminal.

**If you hit an MCP-SDK version error** (e.g. `ModuleNotFoundError` referencing
`mcp.server.fastmcp` or `FastMCP`/`MCPServer` naming) — this was the failure mode with the
original package when the `mcp` SDK jumped to v2. Check `pip show mcp` in the repo's
environment and, if needed, pin it per whatever the repo's `pyproject.toml` specifies.

## Step 5 — Register it in OpenCode

Edit OpenCode's config (e.g. `~/.config/opencode/opencode.json`):

```json
{
  "mcp": {
    "AbletonMCP": {
      "type": "local",
      "command": [
        "python",
        "/home/<you>/ableton-mcp-extended/MCP_Server/server.py"
      ]
    }
  }
}
```

Replace `<you>` with your actual WSL username. The repo ships a `.env.example` — check it
for any environment variables worth setting (e.g. an `ELEVENLABS_API_KEY` if you want the
optional voice-generation integration for Module 4); copy relevant ones into an
`"environment": {}` block the same way your old config did.

Restart OpenCode.

## Step 6 — Verify end to end

With Ableton open, ask OpenCode:

> "Use the AbletonMCP tool to get info about the current Ableton session."

Real track names / tempo / devices back = confirmed working, start to finish.

## Daily Startup (after the one-time setup above)

Everything in Steps 1–5 only needs doing once. From day two onward, this is all it takes:

1. **Open Ableton Live 12.**
2. **Check the Control Surface is still set.** Settings → Link, Tempo & MIDI → confirm
   `AbletonMCP` is still selected (Input/Output → `None`). This is saved per-project/per-install
   and normally sticks, but it's worth a glance the first few times until you trust it.
3. **Open OpenCode.** You don't need to manually run `server.py` yourself — OpenCode
   spawns it automatically from the config you set up in Step 5, the moment it needs the tool.
4. **Ask OpenCode something that uses the tool**, e.g.:

   > "Use the AbletonMCP tool to get info about the current Ableton session."

   If it comes back with real track names / tempo, the connection came up cleanly and you're
   good to go.

If step 4 fails, it's almost always one of two things: Ableton wasn't open yet when OpenCode
tried to connect (just ask again), or the WSL2 networking dropped back to NAT mode after a
Windows update/reboot (re-check `%UserProfile%\.wslconfig` still has `networkingMode=mirrored`
and run `wsl --shutdown` once).

## Troubleshooting quick reference

| Symptom                                                          | Likely cause                                                                                                                                                                                          |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `error: package directory 'AbletonMCP_UDP' does not exist`       | Upstream `pyproject.toml` bug — don't run `pip install -e .` at all; install deps directly per Step 2                                                                                                 |
| `ModuleNotFoundError` referencing `mcp.server.fastmcp`/`FastMCP` | `mcp` SDK version mismatch — check `pip show mcp` in the repo's environment, see Step 4                                                                                                               |
| OpenCode shows the tool as "failed"/"Disabled" with no detail    | Run `python /path/to/MCP_Server/server.py` manually first to see the real traceback — often a `python`/venv PATH mismatch between what you installed into and what OpenCode's config actually invokes |
| OpenCode doesn't list the AbletonMCP tool                        | Config path/syntax wrong (check the absolute path to `server.py`), or OpenCode not restarted                                                                                                          |
| Tool loads but times out / connection refused reaching Ableton   | Remote Script not selected as Control Surface, Ableton not running, or (on WSL2) networking mode — see Step 4                                                                                         |
| Works via manual `python server.py`, not through OpenCode        | Wrong Python interpreter/path in OpenCode's config, or the `-e .` install didn't register                                                                                                             |
| Connects, then drops on complex requests                         | Same quirk as before — break big asks into smaller steps                                                                                                                                              |
| Automation points behave oddly                                   | The repo's own README flags automation-point placement as not fully working yet — treat with caution                                                                                                  |

## Limits worth remembering (from the project's own docs)

- Automation point placement is flagged by the repo as **not working perfectly yet** — don't
  rely on it for precision automation lessons until it's fixed upstream.
- Arrangement View (full timeline control) is listed as a **planned**, not yet complete,
  feature — Session View is the reliable ground for now, which matches your curriculum anyway.
- It's a community project, not an official Ableton integration — save your work before heavy
  experimentation.
- Complex requests may still need breaking into smaller steps, same as before.
