#!/usr/bin/env python3
"""只读 Git/CI 体检与可恢复 handoff 生成器。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


CHECK_STATES = {"PASS", "FAIL", "SKIP", "BLOCKED", "UNKNOWN"}


class GitError(RuntimeError):
    pass


def run_git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        message = result.stderr.strip() or "Git 命令执行失败"
        raise GitError(message)
    # Git porcelain 使用行首空格编码 XY 状态，不能在通用层删除前导空白。
    return result.stdout.rstrip()


def optional_git(repo: Path, *args: str) -> str | None:
    try:
        value = run_git(repo, *args)
    except GitError:
        return None
    return value or None


def repo_root(repo: Path) -> Path:
    root = run_git(repo, "rev-parse", "--show-toplevel")
    return Path(root).resolve()


def status_groups(repo: Path) -> dict[str, list[str]]:
    raw = run_git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    groups: dict[str, list[str]] = {
        "staged": [],
        "unstaged": [],
        "untracked": [],
        "conflicted": [],
    }
    conflict_codes = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
    for line in raw.splitlines():
        if len(line) < 3:
            continue
        code, path = line[:2], line[3:]
        if code == "??":
            groups["untracked"].append(path)
            continue
        if code in conflict_codes:
            groups["conflicted"].append(path)
            continue
        if code[0] != " ":
            groups["staged"].append(path)
        if code[1] != " ":
            groups["unstaged"].append(path)
    return groups


def detect_ci(root: Path) -> list[str]:
    candidates = [
        (root / ".github" / "workflows", "GitHub Actions"),
        (root / ".gitlab-ci.yml", "GitLab CI"),
        (root / ".circleci" / "config.yml", "CircleCI"),
        (root / "Jenkinsfile", "Jenkins"),
        (root / ".buildkite" / "pipeline.yml", "Buildkite"),
        (root / "azure-pipelines.yml", "Azure Pipelines"),
        (root / "bitbucket-pipelines.yml", "Bitbucket Pipelines"),
    ]
    return [name for path, name in candidates if path.exists()]


def read_small_text(path: Path, max_bytes: int = 256_000) -> str:
    try:
        if path.stat().st_size > max_bytes:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def detect_checks(root: Path) -> list[str]:
    checks: list[str] = []
    package_json = root / "package.json"
    if package_json.is_file():
        try:
            scripts = json.loads(read_small_text(package_json)).get("scripts", {})
        except (json.JSONDecodeError, AttributeError):
            scripts = {}
        preferred = ("lint", "test", "typecheck", "check", "build")
        for name in preferred:
            if name in scripts:
                checks.append(f"npm run {name}")

    makefile = root / "Makefile"
    if makefile.is_file():
        text = read_small_text(makefile)
        targets = set(re.findall(r"(?m)^([A-Za-z0-9_.-]+)\s*:(?!=)", text))
        for name in ("lint", "test", "typecheck", "check", "build", "verify"):
            if name in targets:
                checks.append(f"make {name}")

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = read_small_text(pyproject)
        if "[tool.pytest" in text or "pytest" in text:
            checks.append("python3 -m pytest")
        if "[tool.ruff" in text:
            checks.append("python3 -m ruff check .")
        if "[tool.mypy" in text:
            checks.append("python3 -m mypy .")

    if (root / "Cargo.toml").is_file():
        checks.extend(["cargo fmt --check", "cargo test"])
    if (root / "go.mod").is_file():
        checks.append("go test ./...")

    return list(dict.fromkeys(checks))


@dataclass
class Snapshot:
    root: str
    branch: str | None
    detached: bool
    head: str | None
    upstream: str | None
    ahead: int | None
    behind: int | None
    status: dict[str, list[str]]
    ci: list[str]
    suggested_checks: list[str]


def inspect_repo(repo: Path) -> Snapshot:
    root = repo_root(repo)
    branch = optional_git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    head = optional_git(root, "rev-parse", "--short=12", "HEAD")
    upstream = optional_git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    ahead: int | None = None
    behind: int | None = None
    if head and upstream:
        counts = optional_git(root, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
        if counts:
            left, right = counts.split()
            ahead, behind = int(left), int(right)
    return Snapshot(
        root=str(root),
        branch=branch,
        detached=branch is None,
        head=head,
        upstream=upstream,
        ahead=ahead,
        behind=behind,
        status=status_groups(root),
        ci=detect_ci(root),
        suggested_checks=detect_checks(root),
    )


def bullet(values: Iterable[str], empty: str = "无") -> str:
    items = list(values)
    if not items:
        return f"- {empty}"
    return "\n".join(f"- `{value}`" for value in items)


def snapshot_markdown(snapshot: Snapshot) -> str:
    relation = "未配置 upstream"
    if snapshot.ahead is not None and snapshot.behind is not None:
        relation = f"ahead {snapshot.ahead} / behind {snapshot.behind}"
    lines = [
        "# Git / CI 体检",
        "",
        f"- 仓库：`{snapshot.root}`",
        f"- 分支：`{snapshot.branch or 'DETACHED'}`",
        f"- HEAD：`{snapshot.head or '无提交'}`",
        f"- Upstream：`{snapshot.upstream or '未配置'}`",
        f"- 同步状态：{relation}",
        f"- CI：{', '.join(snapshot.ci) or '未检测到常见配置'}",
    ]
    for key, title in (
        ("staged", "已暂存"),
        ("unstaged", "未暂存"),
        ("untracked", "未跟踪"),
        ("conflicted", "冲突"),
    ):
        lines.extend(["", f"## {title}", "", bullet(snapshot.status[key])])
    lines.extend(["", "## 候选验证命令", "", bullet(snapshot.suggested_checks)])
    return "\n".join(lines) + "\n"


def parse_checks(values: list[str]) -> list[tuple[str, str]]:
    checks: list[tuple[str, str]] = []
    for value in values:
        if "=" not in value:
            raise ValueError(f"检查项必须使用 name=STATUS：{value}")
        name, state = value.rsplit("=", 1)
        state = state.upper()
        if not name or state not in CHECK_STATES:
            raise ValueError(f"无效检查项：{value}")
        checks.append((name, state))
    return checks


def handoff_markdown(
    snapshot: Snapshot,
    objective: str,
    scope: str,
    checks: list[tuple[str, str]],
    remote_states: list[str],
    decisions: list[str],
    blockers: list[str],
    next_steps: list[str],
) -> str:
    relation = "UNKNOWN（未配置 upstream 或无提交）"
    if snapshot.ahead is not None and snapshot.behind is not None:
        relation = f"ahead {snapshot.ahead} / behind {snapshot.behind}"
    check_lines = [f"- `{name}`：**{state}**" for name, state in checks]
    next_action = next_steps[0] if next_steps else "重新运行只读体检并确认下一步"
    sections = [
        "# Git / CI/CD Handoff",
        "",
        "## 目标与完成标准",
        "",
        objective,
        "",
        "## 授权与边界",
        "",
        scope,
        "",
        "## 仓库快照",
        "",
        f"- 工作目录：`{snapshot.root}`",
        f"- 分支：`{snapshot.branch or 'DETACHED'}`",
        f"- HEAD：`{snapshot.head or '无提交'}`",
        f"- Upstream：`{snapshot.upstream or '未配置'}`",
        f"- 同步状态：{relation}（基于本地 remote-tracking ref）",
        f"- CI：{', '.join(snapshot.ci) or 'UNKNOWN（未检测到常见配置）'}",
    ]
    for key, title in (
        ("staged", "已暂存"),
        ("unstaged", "未暂存"),
        ("untracked", "未跟踪"),
        ("conflicted", "冲突"),
    ):
        sections.extend(["", f"### {title}", "", bullet(snapshot.status[key])])
    sections.extend(
        [
            "",
            "## 验证证据",
            "",
            "\n".join(check_lines) if check_lines else "- `UNKNOWN`：尚未登记验证结果",
            "",
            "## 远端、PR、CI 与发布状态",
            "",
            bullet(remote_states, "UNKNOWN：尚未登记实时远端状态"),
            "",
            "## 关键决策",
            "",
            bullet(decisions, "尚未登记"),
            "",
            "## 恢复入口",
            "",
            f"1. 进入 `{snapshot.root}`。",
            "2. 读取适用的 `AGENTS.md` 和本 handoff。",
            "3. 运行 `git status --short` 与本 Skill 的 `inspect --json`。",
            "4. 重新查询会漂移的 upstream、PR、CI 和部署状态。",
            "",
            "## 下一条原子动作",
            "",
            next_action,
            "",
            "## 后续队列",
            "",
            bullet(next_steps[1:], "完成下一条原子动作后重新评估"),
            "",
            "## 阻塞与风险",
            "",
            bullet(blockers, "UNKNOWN：接手者必须根据实时远端状态更新"),
        ]
    )
    return "\n".join(sections) + "\n"


def write_output(content: str, output: str | None) -> None:
    if output is None:
        sys.stdout.write(content)
        return
    path = Path(output).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(str(path.resolve()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect = subparsers.add_parser("inspect", help="只读检查 Git 和 CI 状态")
    inspect.add_argument("--repo", default=".", help="仓库路径")
    inspect.add_argument("--json", action="store_true", help="输出 JSON")

    handoff = subparsers.add_parser("handoff", help="生成可恢复的 handoff")
    handoff.add_argument("--repo", default=".", help="仓库路径")
    handoff.add_argument("--objective", required=True, help="目标与完成标准")
    handoff.add_argument("--scope", required=True, help="授权与边界")
    handoff.add_argument("--check", action="append", default=[], help="验证项 name=STATUS")
    handoff.add_argument("--remote-state", action="append", default=[], help="远端、PR、CI 或发布状态")
    handoff.add_argument("--decision", action="append", default=[], help="关键决策，可重复")
    handoff.add_argument("--blocker", action="append", default=[], help="阻塞或风险，可重复")
    handoff.add_argument("--next", action="append", default=[], help="下一步，第一项为原子动作")
    handoff.add_argument("--output", help="输出文件；不传则打印到标准输出")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        snapshot = inspect_repo(Path(args.repo).expanduser())
        if args.command == "inspect":
            if args.json:
                print(json.dumps(asdict(snapshot), ensure_ascii=False, indent=2))
            else:
                sys.stdout.write(snapshot_markdown(snapshot))
            return 0
        checks = parse_checks(args.check)
        content = handoff_markdown(
            snapshot,
            args.objective,
            args.scope,
            checks,
            args.remote_state,
            args.decision,
            args.blocker,
            args.next,
        )
        write_output(content, args.output)
        return 0
    except (GitError, ValueError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
