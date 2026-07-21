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
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class GitCicdTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
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
        self.assertEqual(len(payload["worktrees"]), 1)
        self.assertTrue(payload["worktrees"][0]["current"])
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
        self.assertIn("## Worktree 拓扑", content)

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

    def test_inspect_reports_other_dirty_worktree(self) -> None:
        worktree = self.root / "feature-worktree"
        git(self.repo, "worktree", "add", "-b", "feature", str(worktree))
        (worktree / "tracked.txt").write_text("feature change\n", encoding="utf-8")
        result = run("inspect", "--repo", str(self.repo), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        feature = next(item for item in payload["worktrees"] if item["branch"] == "feature")
        self.assertFalse(feature["current"])
        self.assertTrue(feature["dirty"])
        self.assertTrue(any("非当前 worktree" in item for item in payload["worktree_warnings"]))

    def test_worktree_create_plan_blocks_occupied_branch(self) -> None:
        planned = self.root / "planned"
        result = run(
            "worktree",
            "create",
            "--repo",
            str(self.repo),
            "--path",
            str(planned),
            "--branch",
            "codex/planned",
            "--base",
            "main",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["command"][3], "-b")

        occupied = self.root / "occupied"
        git(self.repo, "worktree", "add", "-b", "feature", str(occupied))
        blocked = run(
            "worktree",
            "create",
            "--repo",
            str(self.repo),
            "--path",
            str(self.root / "duplicate"),
            "--branch",
            "feature",
            "--json",
        )
        self.assertEqual(blocked.returncode, 3)
        self.assertIn("分支已被其他 worktree 占用", blocked.stdout)

    def test_worktree_close_plan_requires_clean_integrated_head(self) -> None:
        worktree = self.root / "close-me"
        git(self.repo, "worktree", "add", "-b", "close-me", str(worktree))
        ready = run(
            "worktree",
            "close",
            "--repo",
            str(self.repo),
            "--path",
            str(worktree),
            "--integrated-into",
            "main",
            "--json",
        )
        self.assertEqual(ready.returncode, 0, ready.stderr)
        self.assertTrue(json.loads(ready.stdout)["ready"])

        (worktree / "tracked.txt").write_text("dirty\n", encoding="utf-8")
        blocked = run(
            "worktree",
            "close",
            "--repo",
            str(self.repo),
            "--path",
            str(worktree),
            "--integrated-into",
            "main",
            "--json",
        )
        self.assertEqual(blocked.returncode, 3)
        self.assertIn("不是已验证的干净状态", blocked.stdout)

    def test_worktree_close_requires_integration_target(self) -> None:
        result = run(
            "worktree",
            "close",
            "--repo",
            str(self.repo),
            "--path",
            str(self.root / "missing"),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--integrated-into", result.stderr)

    def test_worktree_close_plan_blocks_locked_worktree(self) -> None:
        worktree = self.root / "locked"
        git(self.repo, "worktree", "add", "-b", "locked", str(worktree))
        git(self.repo, "worktree", "lock", "--reason", "active-agent", str(worktree))
        result = run(
            "worktree",
            "close",
            "--repo",
            str(self.repo),
            "--path",
            str(worktree),
            "--integrated-into",
            "main",
            "--json",
        )
        self.assertEqual(result.returncode, 3)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ready"])
        self.assertTrue(any("已锁定" in item for item in payload["blockers"]))

    def test_worktree_close_plan_blocks_unintegrated_commit(self) -> None:
        worktree = self.root / "ahead"
        git(self.repo, "worktree", "add", "-b", "ahead", str(worktree))
        (worktree / "tracked.txt").write_text("committed ahead\n", encoding="utf-8")
        git(worktree, "add", "tracked.txt")
        git(worktree, "commit", "-m", "ahead commit")
        result = run(
            "worktree",
            "close",
            "--repo",
            str(self.repo),
            "--path",
            str(worktree),
            "--integrated-into",
            "main",
            "--json",
        )
        self.assertEqual(result.returncode, 3)
        payload = json.loads(result.stdout)
        self.assertTrue(any("尚未包含" in item for item in payload["blockers"]))

    def test_nul_status_and_package_manager_detection(self) -> None:
        unusual = "line\nbreak.txt"
        (self.repo / unusual).write_text("new\n", encoding="utf-8")
        (self.repo / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
        result = run("inspect", "--repo", str(self.repo), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn(unusual, payload["status"]["untracked"])
        self.assertEqual(payload["suggested_checks"], ["pnpm run lint", "pnpm run test"])


if __name__ == "__main__":
    unittest.main()
