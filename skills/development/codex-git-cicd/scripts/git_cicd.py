#!/usr/bin/env python3
"""只读 Git/worktree/CI 体检、生命周期规划与 handoff 生成器。"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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


def git_succeeds(repo: Path, *args: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def repo_root(repo: Path) -> Path:
    root = run_git(repo, "rev-parse", "--show-toplevel")
    return Path(root).resolve()


def status_groups(repo: Path) -> dict[str, list[str]]:
    raw = run_git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    groups: dict[str, list[str]] = {
        "staged": [],
        "unstaged": [],
        "untracked": [],
        "conflicted": [],
    }
    conflict_codes = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
    records = raw.split("\0")
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if len(record) < 3:
            continue
        code, path = record[:2], record[3:]
        if code[0] in {"R", "C"} or code[1] in {"R", "C"}:
            # porcelain v1 -z 在 rename/copy 后追加原路径；分组只展示目标路径。
            index += 1
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
            package_data = json.loads(read_small_text(package_json))
            scripts = package_data.get("scripts", {})
        except (json.JSONDecodeError, AttributeError):
            package_data = {}
            scripts = {}
        package_manager = str(package_data.get("packageManager", "")).split("@", 1)[0]
        if package_manager not in {"npm", "pnpm", "yarn", "bun"}:
            if (root / "pnpm-lock.yaml").is_file():
                package_manager = "pnpm"
            elif (root / "yarn.lock").is_file():
                package_manager = "yarn"
            elif (root / "bun.lock").is_file() or (root / "bun.lockb").is_file():
                package_manager = "bun"
            else:
                package_manager = "npm"
        preferred = ("lint", "test", "typecheck", "check", "build")
        for name in preferred:
            if name in scripts:
                checks.append(f"{package_manager} run {name}")

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
class WorktreeInfo:
    path: str
    head: str | None
    branch: str | None
    detached: bool
    bare: bool
    locked: str | None
    prunable: str | None
    current: bool
    status: dict[str, list[str]] | None
    dirty: bool | None
    status_error: str | None


@dataclass
class Snapshot:
    captured_at: str
    root: str
    git_common_dir: str
    branch: str | None
    detached: bool
    head: str | None
    upstream: str | None
    ahead: int | None
    behind: int | None
    status: dict[str, list[str]]
    worktrees: list[WorktreeInfo]
    worktree_warnings: list[str]
    ci: list[str]
    suggested_checks: list[str]


def common_git_dir(root: Path) -> Path:
    value = Path(run_git(root, "rev-parse", "--git-common-dir"))
    if not value.is_absolute():
        value = root / value
    return value.resolve()


def inspect_worktrees(root: Path) -> tuple[list[WorktreeInfo], list[str]]:
    raw = run_git(root, "worktree", "list", "--porcelain", "-z")
    records: list[dict[str, str | bool]] = []
    current: dict[str, str | bool] = {}
    for token in raw.split("\0"):
        if not token:
            if current:
                records.append(current)
                current = {}
            continue
        key, separator, value = token.partition(" ")
        current[key] = value if separator else True
    if current:
        records.append(current)

    worktrees: list[WorktreeInfo] = []
    current_root = root.resolve()
    for record in records:
        path = Path(str(record.get("worktree", ""))).resolve()
        bare = bool(record.get("bare", False))
        prunable = str(record["prunable"]) if "prunable" in record else None
        status: dict[str, list[str]] | None = None
        dirty: bool | None = None
        status_error: str | None = None
        if not bare and prunable is None and path.is_dir():
            try:
                status = status_groups(path)
                dirty = any(status.values())
            except GitError:
                status_error = "worktree 状态不可读取"
        else:
            status_error = "bare 或路径不可访问"
        branch_ref = str(record["branch"]) if "branch" in record else None
        branch = branch_ref.removeprefix("refs/heads/") if branch_ref else None
        worktrees.append(
            WorktreeInfo(
                path=str(path),
                head=str(record["HEAD"]) if "HEAD" in record else None,
                branch=branch,
                detached=bool(record.get("detached", False)) or branch is None,
                bare=bare,
                locked=str(record["locked"]) if "locked" in record else None,
                prunable=prunable,
                current=path == current_root,
                status=status,
                dirty=dirty,
                status_error=status_error,
            )
        )

    warnings: list[str] = []
    branch_paths: dict[str, list[str]] = {}
    for worktree in worktrees:
        if worktree.branch:
            branch_paths.setdefault(worktree.branch, []).append(worktree.path)
        if worktree.locked:
            warnings.append(f"worktree 已锁定：{worktree.path}")
        if worktree.prunable:
            warnings.append(f"worktree 元数据可清理：{worktree.path}")
        if worktree.dirty:
            prefix = "当前" if worktree.current else "非当前"
            warnings.append(f"{prefix} worktree 存在未提交改动：{worktree.path}")
    for branch, paths in branch_paths.items():
        if len(paths) > 1:
            warnings.append(f"分支被多个 worktree 占用：{branch}")
    return worktrees, warnings


def inspect_repo(repo: Path) -> Snapshot:
    root = repo_root(repo)
    branch = optional_git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    head = optional_git(root, "rev-parse", "HEAD")
    upstream = optional_git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    ahead: int | None = None
    behind: int | None = None
    if head and upstream:
        counts = optional_git(root, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
        if counts:
            left, right = counts.split()
            ahead, behind = int(left), int(right)
    worktrees, worktree_warnings = inspect_worktrees(root)
    return Snapshot(
        captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        root=str(root),
        git_common_dir=str(common_git_dir(root)),
        branch=branch,
        detached=branch is None,
        head=head,
        upstream=upstream,
        ahead=ahead,
        behind=behind,
        status=status_groups(root),
        worktrees=worktrees,
        worktree_warnings=worktree_warnings,
        ci=detect_ci(root),
        suggested_checks=detect_checks(root),
    )


def bullet(values: Iterable[str], empty: str = "无") -> str:
    items = list(values)
    if not items:
        return f"- {empty}"
    return "\n".join(f"- `{markdown_code(value)}`" for value in items)


def markdown_code(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("|", "\\|")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def worktree_markdown(worktrees: list[WorktreeInfo]) -> str:
    lines = [
        "| 当前 | 路径 | 分支 | HEAD | 状态 | 元数据 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for worktree in worktrees:
        if worktree.dirty is True:
            state = "DIRTY"
        elif worktree.dirty is False:
            state = "CLEAN"
        else:
            state = "UNKNOWN"
        metadata = []
        if worktree.locked:
            metadata.append("LOCKED")
        if worktree.prunable:
            metadata.append("PRUNABLE")
        if worktree.bare:
            metadata.append("BARE")
        lines.append(
            "| {current} | `{path}` | `{branch}` | `{head}` | {state} | {metadata} |".format(
                current="是" if worktree.current else "否",
                path=markdown_code(worktree.path),
                branch=markdown_code(worktree.branch or "DETACHED"),
                head=worktree.head[:12] if worktree.head else "无提交",
                state=state,
                metadata=", ".join(metadata) or "-",
            )
        )
    return "\n".join(lines)


def snapshot_markdown(snapshot: Snapshot) -> str:
    relation = "未配置 upstream"
    if snapshot.ahead is not None and snapshot.behind is not None:
        relation = f"ahead {snapshot.ahead} / behind {snapshot.behind}"
    lines = [
        "# Git / CI 体检",
        "",
        f"- 快照时间：`{snapshot.captured_at}`",
        f"- 仓库：`{snapshot.root}`",
        f"- 共同 Git 目录：`{snapshot.git_common_dir}`",
        f"- 分支：`{snapshot.branch or 'DETACHED'}`",
        f"- HEAD：`{snapshot.head or '无提交'}`",
        f"- Upstream：`{snapshot.upstream or '未配置'}`",
        f"- 同步状态：{relation}（基于本地 remote-tracking ref）",
        f"- CI：{', '.join(snapshot.ci) or '未检测到常见配置'}",
        "",
        "## Worktree 拓扑",
        "",
        worktree_markdown(snapshot.worktrees),
        "",
        "### Worktree 风险",
        "",
        bullet(snapshot.worktree_warnings),
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


def resolve_target_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def create_worktree_plan(
    snapshot: Snapshot,
    path_value: str,
    branch: str | None,
    base: str,
    detach: bool,
) -> dict[str, object]:
    root = Path(snapshot.root)
    target = resolve_target_path(root, path_value)
    blockers: list[str] = []
    warnings: list[str] = []
    command: list[str] = []

    registered_paths = {Path(item.path).resolve() for item in snapshot.worktrees}
    occupied_branches = {item.branch: item.path for item in snapshot.worktrees if item.branch}
    if target == root.resolve():
        blockers.append("目标路径不能是当前 worktree")
    if target in registered_paths:
        blockers.append("目标路径已注册为 worktree")
    if target.exists():
        blockers.append("目标路径已存在；为避免覆盖，规划器不会复用")
    if not git_succeeds(root, "rev-parse", "--verify", f"{base}^{{commit}}"):
        blockers.append(f"基线 ref 不存在或不是 commit：{base}")

    if detach:
        if branch:
            blockers.append("detached worktree 不应同时指定 branch")
        command = ["git", "worktree", "add", "--detach", str(target), base]
    else:
        if not branch:
            blockers.append("创建分支 worktree 必须指定 branch")
        elif not git_succeeds(root, "check-ref-format", "--branch", branch):
            blockers.append(f"分支名称无效：{branch}")
        elif branch in occupied_branches:
            blockers.append(f"分支已被其他 worktree 占用：{occupied_branches[branch]}")
        elif git_succeeds(root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"):
            command = ["git", "worktree", "add", str(target), branch]
        else:
            command = ["git", "worktree", "add", "-b", branch, str(target), base]

    try:
        relative = target.relative_to(root)
    except ValueError:
        relative = None
    if relative is not None and not git_succeeds(root, "check-ignore", "--quiet", "--", str(relative)):
        warnings.append("目标位于当前仓库内且未被 ignore，创建后可能显示为未跟踪目录")

    return {
        "action": "create",
        "ready": not blockers,
        "target": str(target),
        "branch": branch,
        "base": base,
        "detached": detach,
        "command": command if not blockers else [],
        "blockers": blockers,
        "warnings": warnings,
    }


def close_worktree_plan(
    snapshot: Snapshot,
    path_value: str,
    integrated_into: str,
) -> dict[str, object]:
    root = Path(snapshot.root)
    target = resolve_target_path(root, path_value)
    blockers: list[str] = []
    warnings: list[str] = []
    match = next((item for item in snapshot.worktrees if Path(item.path).resolve() == target), None)
    if match is None:
        blockers.append("目标路径不是已注册 worktree")
    else:
        if match.current:
            blockers.append("不能从当前 worktree 规划删除自身")
        if match.locked:
            blockers.append("worktree 已锁定，必须先确认锁定原因")
        if match.dirty is not False:
            blockers.append("worktree 不是已验证的干净状态")
        if match.prunable:
            blockers.append("worktree 路径不可访问；应先 dry-run 检查 prune")
        if not git_succeeds(root, "rev-parse", "--verify", f"{integrated_into}^{{commit}}"):
            blockers.append(f"集成目标不存在或不是 commit：{integrated_into}")
        elif match.head and not git_succeeds(
            root, "merge-base", "--is-ancestor", match.head, integrated_into
        ):
            blockers.append(f"worktree HEAD 尚未包含在 {integrated_into}")
        if match.branch:
            warnings.append("删除 worktree 不会删除分支；分支回收必须单独审查")

    return {
        "action": "close",
        "ready": not blockers,
        "target": str(target),
        "branch": match.branch if match else None,
        "integrated_into": integrated_into,
        "command": ["git", "worktree", "remove", str(target)] if not blockers else [],
        "blockers": blockers,
        "warnings": warnings,
    }


def plan_markdown(plan: dict[str, object]) -> str:
    command = plan.get("command") or []
    lines = [
        f"# Worktree {plan['action']} 计划",
        "",
        f"- 状态：{'READY' if plan['ready'] else 'BLOCKED'}",
        f"- 目标：`{markdown_code(str(plan['target']))}`",
    ]
    if plan.get("branch"):
        lines.append(f"- 分支：`{markdown_code(str(plan['branch']))}`")
    lines.extend(
        [
            "",
            "## 计划命令",
            "",
            f"```bash\n{shlex.join(command)}\n```" if command else "- 无",
            "",
            "## 阻塞",
            "",
            bullet(plan.get("blockers", [])),
            "",
            "## 警告",
            "",
            bullet(plan.get("warnings", [])),
        ]
    )
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
        f"- 快照时间：`{snapshot.captured_at}`",
        f"- 工作目录：`{snapshot.root}`",
        f"- 共同 Git 目录：`{snapshot.git_common_dir}`",
        f"- 分支：`{snapshot.branch or 'DETACHED'}`",
        f"- HEAD：`{snapshot.head or '无提交'}`",
        f"- Upstream：`{snapshot.upstream or '未配置'}`",
        f"- 同步状态：{relation}（基于本地 remote-tracking ref）",
        f"- CI：{', '.join(snapshot.ci) or 'UNKNOWN（未检测到常见配置）'}",
        "",
        "## Worktree 拓扑",
        "",
        worktree_markdown(snapshot.worktrees),
        "",
        "### Worktree 风险",
        "",
        bullet(snapshot.worktree_warnings),
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
            "3. 运行 `git worktree list --porcelain`、`git status --short` 与本 Skill 的 `inspect --json`。",
            "4. 确认当前路径、分支与 handoff 中的目标 worktree 一致。",
            "5. 重新查询会漂移的 upstream、PR、CI 和部署状态。",
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

    worktree = subparsers.add_parser("worktree", help="只读规划 worktree 创建或回收")
    worktree_actions = worktree.add_subparsers(dest="worktree_action", required=True)

    create = worktree_actions.add_parser("create", help="规划创建 worktree")
    create.add_argument("--repo", default=".", help="仓库路径")
    create.add_argument("--path", required=True, help="新 worktree 路径")
    create.add_argument("--branch", help="新建或复用的本地分支")
    create.add_argument("--base", default="HEAD", help="新分支或 detached worktree 的基线")
    create.add_argument("--detach", action="store_true", help="规划只读 detached worktree")
    create.add_argument("--json", action="store_true", help="输出 JSON")

    close = worktree_actions.add_parser("close", help="规划安全回收 worktree")
    close.add_argument("--repo", default=".", help="仓库路径")
    close.add_argument("--path", required=True, help="待回收 worktree 路径")
    close.add_argument("--integrated-into", required=True, help="用于证明 HEAD 已集成的目标 ref")
    close.add_argument("--json", action="store_true", help="输出 JSON")

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
        if args.command == "worktree":
            if args.worktree_action == "create":
                plan = create_worktree_plan(snapshot, args.path, args.branch, args.base, args.detach)
            else:
                plan = close_worktree_plan(snapshot, args.path, args.integrated_into)
            if args.json:
                print(json.dumps(plan, ensure_ascii=False, indent=2))
            else:
                sys.stdout.write(plan_markdown(plan))
            return 0 if plan["ready"] else 3
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
