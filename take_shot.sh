#!/usr/bin/env bash
# take_shot.sh — capture ONLY the Ableton Live window from WSL and save it
# directly into the caller-specified lab folder inside the project.
#
# Usage:
#   ./take_shot.sh <lab_dir> <seq> <short_description>
#
# <lab_dir> is a path relative to the project root, pointing at the specific
# self-contained lab folder for this run — e.g.
#   LABS/MOD_02_2026-08-03_1430/creating-drum-loop
#
# Example:
#   ./take_shot.sh LABS/MOD_02_2026-08-03_1430/creating-drum-loop 03 clip_created_slot1
#
# Produces:
#   LABS/MOD_02_2026-08-03_1430/creating-drum-loop/03_clip_created_slot1.png
#
# The script does not assume or construct any part of this path beyond what
# is passed in — no "tutorials/" prefix, no module-number convention baked
# in. The caller (the agent, per AGENTS.md) owns the folder naming.
#
# Requires: WSL2 with Windows interop enabled (default). No installs needed —
# uses .NET types already present in Windows via PowerShell.
#
# v5 CHANGE — auto-focus/auto-restore (was fail-fast-only in v1-v4):
#   - Ableton minimized       -> restored (ShowWindow SW_RESTORE), then re-checked
#   - Ableton not foreground  -> brought to front (SetForegroundWindow), then re-checked
#   - Ableton not found at all -> still a hard failure, nothing to bring forward
#
# This is ON by default. To restore the old v1-v4 fail-fast-only behavior
# (never touch window state, just error out and let the caller/human fix it),
# set ABLETON_AUTO_FOCUS=0:
#   ABLETON_AUTO_FOCUS=0 ./take_shot.sh LABS/MOD_02_2026-08-03_1430/creating-drum-loop 03 clip_created_slot1
#
# After any restore/focus attempt, the script re-checks IsIconic/
# GetForegroundWindow rather than assuming the fix worked, and waits briefly
# (300ms) first so the window manager finishes any restore animation before
# CopyFromScreen runs. If the fix genuinely didn't take, distinct error codes
# (MINIMIZED_RESTORE_FAILED / FOCUS_FAILED) are emitted so the calling agent
# can tell "auto-fix was tried and failed" apart from "auto-fix was skipped".
#
# v6 CHANGE — auto-maximize (new):
#   - Once the window is confirmed not-minimized and foreground, if it isn't
#     already maximized (IsZoomed), the script now also maximizes it
#     (ShowWindow SW_MAXIMIZE) before capturing.
#   - Rationale: restoring a minimized window returns it to whatever size it
#     was *before* minimizing (often a small windowed size, especially on a
#     multi-monitor setup with other apps arranged around it) — that alone
#     does not guarantee a clean, legible, full-window capture. Maximizing
#     does.
#   - This is BEST-EFFORT and NON-BLOCKING, unlike restore/focus: a window
#     that stays un-maximized is still fully capturable (just smaller), so a
#     failed maximize does not abort the screenshot. On success or failure it
#     proceeds to capture at whatever size the window ends up at, and reports
#     which happened via a NOTE: line on stdout (not an ERROR:), so the
#     calling agent can mention it if relevant but should not treat it as a
#     failure.
#   - Toggle with ABLETON_AUTO_MAXIMIZE (default 1). Set to 0 to leave window
#     size exactly as-is, e.g. if you deliberately want to demonstrate a
#     windowed (non-maximized) Ableton layout in a screenshot:
#   ABLETON_AUTO_MAXIMIZE=0 ./take_shot.sh LABS/MOD_02_2026-08-03_1430/creating-drum-loop 03 clip_created_slot1
#
# All hard-failure error paths (still): ERROR:NOT_FOUND / ERROR:MINIMIZED /
# ERROR:MINIMIZED_RESTORE_FAILED / ERROR:NOT_FOCUSED / ERROR:FOCUS_FAILED /
# ERROR:BAD_SIZE / ERROR:FILE_MISSING — see AGENTS.md's "Error codes:
# take_shot.sh" section for how the agent should react to each. Maximize is
# informational only (NOTE:, not ERROR:) and never blocks the capture.

set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "Usage: $0 <lab_dir> <seq> <short_description>" >&2
  exit 1
fi

LAB_DIR="$1"
SEQ="$2"
DESC="$3"

AUTO_FOCUS="${ABLETON_AUTO_FOCUS:-1}"
AUTO_MAXIMIZE="${ABLETON_AUTO_MAXIMIZE:-1}"

# Default PROJECT_ROOT is wherever this script itself lives (not a hardcoded
# absolute path) — keeps the script correct if the course folder is ever
# moved or renamed. Override with ABLETON_PROJECT_ROOT if the lab output
# should land somewhere other than alongside the script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${ABLETON_PROJECT_ROOT:-$SCRIPT_DIR}"
TUTORIAL_DIR="$PROJECT_ROOT/$LAB_DIR"
mkdir -p "$TUTORIAL_DIR"

WIN_USER="$(cmd.exe /c "cd /d C:\ && echo %USERNAME%" 2>/dev/null | tr -d '\r' | grep -v '^$' | tail -n 1)"
if [ -z "$WIN_USER" ]; then
  echo "ERROR:NO_WIN_USER: Could not detect Windows username via cmd.exe — is WSL interop enabled?" >&2
  exit 1
fi
if ! [[ "$WIN_USER" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "ERROR:BAD_WIN_USER: cmd.exe returned an unexpected value for %USERNAME%: '$WIN_USER'" >&2
  echo "This usually means cmd.exe printed a warning (e.g. about UNC paths) that got captured" >&2
  echo "along with the username. Try running from a /mnt/c/... directory, or run manually:" >&2
  echo "  cd /mnt/c && cmd.exe /c \"echo %USERNAME%\"" >&2
  exit 1
fi

WSL_TMP_DIR="/mnt/c/Users/${WIN_USER}/ableton_screenshots"
mkdir -p "$WSL_TMP_DIR"

FILENAME="${SEQ}_${DESC}.png"
WIN_TMP_PATH="C:\\Users\\${WIN_USER}\\ableton_screenshots\\${FILENAME}"

PS_OUTPUT="$(powershell.exe -NoProfile -Command "
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WinFinder {
    [DllImport(\"user32.dll\")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
    [DllImport(\"user32.dll\")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
    [DllImport(\"user32.dll\")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport(\"user32.dll\")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport(\"user32.dll\")] public static extern bool IsIconic(IntPtr hWnd);
    [DllImport(\"user32.dll\")] public static extern bool IsZoomed(IntPtr hWnd);
    [DllImport(\"user32.dll\")] public static extern bool SetProcessDPIAware();
    [DllImport(\"user32.dll\")] public static extern IntPtr GetForegroundWindow();
    [DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
    public static IntPtr Found = IntPtr.Zero;
    public static bool Minimized = false;
    public static bool Callback(IntPtr hWnd, IntPtr lParam) {
        if (!IsWindowVisible(hWnd)) return true;
        var sb = new StringBuilder(256);
        GetWindowText(hWnd, sb, 256);
        string title = sb.ToString();
        if (title.IndexOf(\"Ableton Live\", StringComparison.OrdinalIgnoreCase) >= 0) {
            Found = hWnd;
            Minimized = IsIconic(hWnd);
            return false;
        }
        return true;
    }
}
'@
[WinFinder]::SetProcessDPIAware() | Out-Null
[WinFinder]::EnumWindows([WinFinder+EnumWindowsProc]{ param(\$h,\$l) [WinFinder]::Callback(\$h,\$l) }, [IntPtr]::Zero) | Out-Null

if ([WinFinder]::Found -eq [IntPtr]::Zero) {
    Write-Output 'ERROR:NOT_FOUND: Ableton Live window not found. Is it open?'
    exit 1
}

\$autoFocus = '${AUTO_FOCUS}' -eq '1'
\$SW_RESTORE = 9

if ([WinFinder]::Minimized) {
    if (\$autoFocus) {
        [WinFinder]::ShowWindow([WinFinder]::Found, \$SW_RESTORE) | Out-Null
        Start-Sleep -Milliseconds 300
        if ([WinFinder]::IsIconic([WinFinder]::Found)) {
            Write-Output 'ERROR:MINIMIZED_RESTORE_FAILED: Ableton Live was minimized and auto-restore (ShowWindow) did not un-minimize it.'
            exit 1
        }
    } else {
        Write-Output 'ERROR:MINIMIZED: Ableton Live window is minimized.'
        exit 1
    }
}

\$fg = [WinFinder]::GetForegroundWindow()
if (\$fg -ne [WinFinder]::Found) {
    if (\$autoFocus) {
        [WinFinder]::SetForegroundWindow([WinFinder]::Found) | Out-Null
        Start-Sleep -Milliseconds 300
        \$fg2 = [WinFinder]::GetForegroundWindow()
        if (\$fg2 -ne [WinFinder]::Found) {
            Write-Output 'ERROR:FOCUS_FAILED: Ableton Live was not the active window and auto-focus (SetForegroundWindow) did not bring it to front — Windows sometimes blocks a background process from stealing focus.'
            exit 1
        }
    } else {
        Write-Output 'ERROR:NOT_FOCUSED: Ableton Live is not the active window — something else may be covering it.'
        exit 1
    }
}

\$autoMaximize = '${AUTO_MAXIMIZE}' -eq '1'
\$SW_MAXIMIZE = 3
\$maxNote = 'NOTE:MAXIMIZE_SKIPPED (ABLETON_AUTO_MAXIMIZE=0)'

if (\$autoMaximize) {
    if ([WinFinder]::IsZoomed([WinFinder]::Found)) {
        \$maxNote = 'NOTE:ALREADY_MAXIMIZED'
    } else {
        [WinFinder]::ShowWindow([WinFinder]::Found, \$SW_MAXIMIZE) | Out-Null
        Start-Sleep -Milliseconds 300
        if ([WinFinder]::IsZoomed([WinFinder]::Found)) {
            \$maxNote = 'NOTE:MAXIMIZED'
        } else {
            \$maxNote = 'NOTE:MAXIMIZE_FAILED (captured at current window size instead)'
        }
    }
}
Write-Output \$maxNote

\$rect = New-Object WinFinder+RECT
[WinFinder]::GetWindowRect([WinFinder]::Found, [ref]\$rect) | Out-Null
\$width = \$rect.Right - \$rect.Left
\$height = \$rect.Bottom - \$rect.Top

if (\$width -le 0 -or \$height -le 0) {
    Write-Output 'ERROR:BAD_SIZE: Got an invalid window size — window may be off-screen.'
    exit 1
}

\$bmp = New-Object System.Drawing.Bitmap \$width, \$height
\$g = [System.Drawing.Graphics]::FromImage(\$bmp)
\$g.CopyFromScreen(\$rect.Left, \$rect.Top, 0, 0, (New-Object System.Drawing.Size(\$width, \$height)))
\$bmp.Save('${WIN_TMP_PATH}')
\$g.Dispose(); \$bmp.Dispose()
Write-Output 'OK'
")" || true
PS_OUTPUT="$(echo "$PS_OUTPUT" | tr -d '\r')"

if ! echo "$PS_OUTPUT" | grep -q "^OK$"; then
  # Surface a clean, single-line, machine-parseable reason so the calling
  # agent can turn it into one specific ask instead of guessing.
  echo "$PS_OUTPUT" | grep "^ERROR:" >&2 || echo "$PS_OUTPUT" >&2
  exit 1
fi

# Maximize is informational, never fatal — pull it out to report alongside
# the final success line rather than silently discarding it.
MAX_NOTE="$(echo "$PS_OUTPUT" | grep "^NOTE:" | head -n 1 || true)"

SRC="${WSL_TMP_DIR}/${FILENAME}"
# WSL's /mnt/c (DrvFs) can briefly lag behind Windows-side writes due to
# directory-entry caching, even after the writing process has fully closed
# the file. Poll for up to ~3s instead of checking once immediately.
FOUND_SRC=0
for _ in 1 2 3 4 5 6; do
  if [ -f "$SRC" ]; then
    FOUND_SRC=1
    break
  fi
  sleep 0.5
done
if [ "$FOUND_SRC" -ne 1 ]; then
  echo "ERROR:FILE_MISSING: PowerShell reported success but file not found at $SRC after polling for 3s" >&2
  exit 1
fi

cp "$SRC" "${TUTORIAL_DIR}/${FILENAME}"
echo "Saved: ${TUTORIAL_DIR}/${FILENAME}"
[ -n "$MAX_NOTE" ] && echo "$MAX_NOTE"
