"""
test_orchestrate.py

Pure control-flow tests for orchestrate.sh (Phase 1 — see phased_plan.md /
context.md). Runs the real orchestrate.sh as a subprocess against STUB
automate/take_shot scripts (via the ORCH_PYTHON_CMD / ORCH_AUTOMATE_SCRIPT /
ORCH_TAKE_SHOT env-var seams orchestrate.sh exposes for exactly this
purpose) — no Windows, no Ableton, no real screenshot needed.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATE_SH = REPO_ROOT / "orchestrate.sh"

FAKE_PYTHON_SRC = r"""#!/usr/bin/env bash
# Stub for ORCH_PYTHON_CMD. Args: <automate_script_path> --task X --live [...]
set -u
if [ -n "${FAKE_AUTOMATE_CALLS_FILE:-}" ]; then
  echo "call" >> "$FAKE_AUTOMATE_CALLS_FILE"
fi
echo "  [click L1/mouse] ${FAKE_AUTOMATE_LABEL:-some_control}"
if [ -n "${FAKE_AUTOMATE_TASK_EVENT:-}" ]; then
  echo "EVENT: {\"v\":1,\"type\":\"task_start\",\"task\":\"${FAKE_AUTOMATE_TASK_EVENT}\",\"tracks\":[]}"
fi
if [ -n "${FAKE_AUTOMATE_LABEL_EVENT:-}" ]; then
  echo "EVENT: {\"v\":1,\"type\":\"action_result\",\"label\":\"${FAKE_AUTOMATE_LABEL_EVENT}\",\"level\":\"L1\",\"result\":\"success\"}"
fi
exit "${FAKE_AUTOMATE_EXIT:-0}"
"""

FAKE_TAKE_SHOT_SRC = r"""#!/usr/bin/env bash
# Stub for ORCH_TAKE_SHOT. Args: <lab_dir> <seq> <desc>
set -u
if [ -n "${FAKE_TAKE_SHOT_CALLS_FILE:-}" ]; then
  echo "$1|$2|$3" >> "$FAKE_TAKE_SHOT_CALLS_FILE"
fi
echo "Saved: fake/${2}_${3}.png"
exit "${FAKE_TAKE_SHOT_EXIT:-0}"
"""


def _make_executable(path: Path, src: str) -> None:
    path.write_text(src)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


class Sandbox:
    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orchestrate_test_"))
        self.fake_python = self.tmp / "fake_python.sh"
        self.fake_take_shot = self.tmp / "fake_take_shot.sh"
        _make_executable(self.fake_python, FAKE_PYTHON_SRC)
        _make_executable(self.fake_take_shot, FAKE_TAKE_SHOT_SRC)
        self.automate_calls_file = self.tmp / "automate_calls.log"
        self.take_shot_calls_file = self.tmp / "take_shot_calls.log"
        self.project_root = self.tmp / "project_root"
        self.project_root.mkdir()
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run(
        self,
        lab_dir: str,
        task: str,
        *task_args: str,
        env_overrides: dict | None = None,
    ):
        env = dict(os.environ)
        env.update(
            {
                "ORCH_PYTHON_CMD": str(self.fake_python),
                "ORCH_AUTOMATE_SCRIPT": "/dev/null",
                "ORCH_TAKE_SHOT": str(self.fake_take_shot),
                "ABLETON_PROJECT_ROOT": str(self.project_root),
                "FAKE_AUTOMATE_CALLS_FILE": str(self.automate_calls_file),
                "FAKE_TAKE_SHOT_CALLS_FILE": str(self.take_shot_calls_file),
            }
        )
        if env_overrides:
            env.update(env_overrides)
        proc = subprocess.run(
            ["bash", str(ORCHESTRATE_SH), lab_dir, task, *task_args],
            cwd=str(self.tmp),
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc

    def take_shot_calls(self) -> list[tuple[str, str, str]]:
        if not self.take_shot_calls_file.exists():
            return []
        out = []
        for line in self.take_shot_calls_file.read_text().splitlines():
            parts = line.split("|")
            if len(parts) == 3:
                out.append(tuple(parts))
        return out

    def automate_call_count(self) -> int:
        if not self.automate_calls_file.exists():
            return 0
        return len(self.automate_calls_file.read_text().splitlines())


# --------------------------------------------------------------------------
# Arg parsing / task validation
# --------------------------------------------------------------------------


def test_usage_error_when_too_few_args():
    with Sandbox() as sb:
        result = subprocess.run(
            ["bash", str(ORCHESTRATE_SH), "only_one_arg"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode != 0
        assert "Usage:" in result.stderr


def test_rejects_solo_tour_explicitly():
    with Sandbox() as sb:
        proc = sb.run("LABS/x", "solo_tour")
        assert proc.returncode != 0
        assert "solo_tour" in proc.stderr
        assert sb.automate_call_count() == 0
        assert sb.take_shot_calls() == []


def test_rejects_unknown_task():
    with Sandbox() as sb:
        proc = sb.run("LABS/x", "not_a_real_task")
        assert proc.returncode != 0
        assert "unknown or unsupported task" in proc.stderr
        assert sb.automate_call_count() == 0


# --------------------------------------------------------------------------
# Happy path + description derivation
# --------------------------------------------------------------------------


def test_happy_path_derives_desc_from_label_and_passes_lab_dir_unchanged():
    with Sandbox() as sb:
        lab_dir = "LABS/MOD_02_2026-08-03_1430/creating-drum-loop"
        proc = sb.run(
            lab_dir,
            "arm_track",
            "--tracks",
            "1",
            env_overrides={
                "FAKE_AUTOMATE_LABEL_EVENT": "Track[1].Mixer.Arm",
                "FAKE_AUTOMATE_TASK_EVENT": "arm_track",
            },
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        calls = sb.take_shot_calls()
        assert len(calls) == 1
        got_lab_dir, got_seq, got_desc = calls[0]
        assert got_lab_dir == lab_dir
        assert got_seq == "01"
        assert got_desc == "track_1_mixer_arm"


def test_desc_falls_back_to_task_field_when_no_label():
    with Sandbox() as sb:
        proc = sb.run(
            "LABS/x",
            "set_tempo",
            "--bpm",
            "128",
            env_overrides={"FAKE_AUTOMATE_TASK_EVENT": "set_tempo"},
        )
        assert proc.returncode == 0
        _, _, desc = sb.take_shot_calls()[0]
        assert desc == "set_tempo"


def test_desc_falls_back_to_task_name_when_no_event_lines_at_all():
    with Sandbox() as sb:
        proc = sb.run("LABS/x", "read_solo_states", "--tracks", "0", "1")
        assert proc.returncode == 0
        _, _, desc = sb.take_shot_calls()[0]
        assert desc == "read_solo_states"


# --------------------------------------------------------------------------
# Seq counter
# --------------------------------------------------------------------------


def test_seq_increments_across_calls_same_lab_dir():
    with Sandbox() as sb:
        lab_dir = "LABS/same"
        sb.run(lab_dir, "arm_track", "--tracks", "0")
        sb.run(lab_dir, "arm_track", "--tracks", "1")
        sb.run(lab_dir, "arm_track", "--tracks", "2")
        seqs = [seq for (_, seq, _) in sb.take_shot_calls()]
        assert seqs == ["01", "02", "03"]


def test_seq_independent_per_lab_dir():
    with Sandbox() as sb:
        sb.run("LABS/lab_a", "arm_track", "--tracks", "0")
        sb.run("LABS/lab_b", "arm_track", "--tracks", "0")
        sb.run("LABS/lab_a", "arm_track", "--tracks", "1")
        calls = sb.take_shot_calls()
        by_lab = {}
        for lab_dir, seq, _ in calls:
            by_lab.setdefault(lab_dir, []).append(seq)
        assert by_lab["LABS/lab_a"] == ["01", "02"]
        assert by_lab["LABS/lab_b"] == ["01"]


# --------------------------------------------------------------------------
# Error branching
# --------------------------------------------------------------------------


def test_automate_failure_still_takes_a_failed_screenshot_and_does_not_retry():
    with Sandbox() as sb:
        proc = sb.run(
            "LABS/x",
            "arm_track",
            "--tracks",
            "1",
            env_overrides={
                "FAKE_AUTOMATE_EXIT": "1",
                "FAKE_AUTOMATE_LABEL_EVENT": "Track[1].Mixer.Arm",
            },
        )
        assert proc.returncode == 1
        assert sb.automate_call_count() == 1
        calls = sb.take_shot_calls()
        assert len(calls) == 1
        _, _, desc = calls[0]
        assert desc == "track_1_mixer_arm_FAILED"


def test_take_shot_failure_surfaces_when_automate_succeeded():
    with Sandbox() as sb:
        proc = sb.run(
            "LABS/x",
            "arm_track",
            "--tracks",
            "1",
            env_overrides={"FAKE_TAKE_SHOT_EXIT": "1"},
        )
        assert proc.returncode == 1
        assert sb.automate_call_count() == 1
        assert len(sb.take_shot_calls()) == 1


# --------------------------------------------------------------------------
# Output tagging
# --------------------------------------------------------------------------


def test_orchestrator_own_lines_are_tagged_and_wrap_sub_output():
    with Sandbox() as sb:
        proc = sb.run(
            "LABS/x",
            "arm_track",
            "--tracks",
            "1",
            env_overrides={"FAKE_AUTOMATE_LABEL_EVENT": "Track[1].Mixer.Arm"},
        )
        lines = proc.stdout.splitlines()
        orchestrator_lines = [l for l in lines if l.startswith("[orchestrator]")]
        assert any("task=arm_track" in l for l in orchestrator_lines)
        assert any("done." in l for l in orchestrator_lines)
        assert "--- automate_ableton_task.py output ---" in lines
        assert "--- take_shot.sh output ---" in lines


if __name__ == "__main__":
    tests = [
        (name, fn)
        for name, fn in list(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    passed, failed = 0, 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
            passed += 1
        except Exception:
            print(f"FAIL  {name}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
