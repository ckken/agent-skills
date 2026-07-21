#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("git_cicd.py")


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE)


class GitCicdTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "Test User")
        git(self.repo, "config", "user.email", "test@example.com")
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        (self.repo / "package.json").write_text(
            json.dumps({"scripts": {"test": "example", "lint": "example"}}),
            encoding="utf-8",
        )
        git(self.repo, "add", "tracked.txt", "package.json")
        git(self.repo, "commit", "-m", "initial")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_inspect_json_groups_changes_and_checks(self) -> None:
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / "new.txt").write_text("new\n", encoding="utf-8")
        result = run("inspect", "--repo", str(self.repo), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["branch"], "main")
        self.assertIn("tracked.txt", payload["status"]["unstaged"])
        self.assertIn("new.txt", payload["status"]["untracked"])
        self.assertEqual(payload["suggested_checks"], ["npm run lint", "npm run test"])

    def test_handoff_writes_recovery_contract(self) -> None:
        output = self.repo / ".codex" / "handoffs" / "state.md"
        result = run(
            "handoff",
            "--repo",
            str(self.repo),
            "--objective",
            "完成测试",
            "--scope",
            "仅测试仓库",
            "--check",
            "unit=PASS",
            "--decision",
            "保留未跟踪文件",
            "--remote-state",
            "push=UNKNOWN",
            "--blocker",
            "等待远端查询",
            "--next",
            "运行提交前检查",
            "--output",
            str(output),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        content = output.read_text(encoding="utf-8")
        self.assertIn("# Git / CI/CD Handoff", content)
        self.assertIn("`unit`：**PASS**", content)
        self.assertIn("push=UNKNOWN", content)
        self.assertIn("等待远端查询", content)
        self.assertIn("运行提交前检查", content)

    def test_invalid_check_state_is_rejected(self) -> None:
        result = run(
            "handoff",
            "--repo",
            str(self.repo),
            "--objective",
            "x",
            "--scope",
            "y",
            "--check",
            "unit=MAYBE",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("无效检查项", result.stderr)


if __name__ == "__main__":
    unittest.main()
