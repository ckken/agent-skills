#!/usr/bin/env python3
"""Inventory prompt-stack files without echoing their contents."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path


ALLOWED_SUFFIXES = {".md", ".txt", ".yaml", ".yml", ".json", ".toml"}
KNOWN_NAMES = {"AGENTS.md", "CLAUDE.md", "GEMINI.md", "SKILL.md"}
CONTEXT_DIRS = {".codex", ".agents", ".claude", "prompts"}
IGNORED_DIRS = {
    ".git", "node_modules", "dist", "build", ".next", "target", "vendor",
    "coverage", ".venv", "venv", "__pycache__",
}
SENSITIVE_NAMES = re.compile(r"(?:^|[._-])(env|secret|token|credential|password|private|auth|key)(?:$|[._-])", re.I)
DIRECTIVE = re.compile(
    r"\b(must|should|shall|never|always|only|prefer|require|required|do not|don't|before|after|if|use|run|read|keep)\b"
    r"|必须|应当|应该|不得|禁止|不要|永远|始终|只能|仅限|优先|需要|如果|之前|之后|使用|运行|读取|保留",
    re.I,
)
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
CONFLICT_RULES = [
    (
        "ask-before-vs-act-directly",
        re.compile(r"ask|confirm|approval|询问|确认|批准|审批", re.I),
        re.compile(r"without asking|do not ask|直接执行|无需询问|不要询问|不必确认", re.I),
    ),
    (
        "read-only-vs-modify",
        re.compile(r"do not (?:edit|modify|implement)|read.?only|不要修改|不得修改|只读|不实施", re.I),
        re.compile(r"make (?:the )?changes|implement|fix|修改|实施|修复|落盘", re.I),
    ),
    (
        "concise-vs-exhaustive",
        re.compile(r"concise|brief|short|简洁|精简|简短", re.I),
        re.compile(r"exhaustive|comprehensive|detailed|完整详尽|全面|详细", re.I),
    ),
    (
        "browse-required-vs-forbidden",
        re.compile(r"must browse|must search|必须浏览|必须搜索|必须联网", re.I),
        re.compile(r"do not browse|do not search|不要浏览|不得搜索|禁止联网", re.I),
    ),
]


def is_candidate(path: Path) -> bool:
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        return False
    if SENSITIVE_NAMES.search(path.name):
        return False
    if path.name in KNOWN_NAMES or "prompt" in path.name.lower():
        return True
    return bool(set(path.parts) & CONTEXT_DIRS)


def normalize_line(line: str) -> str:
    line = re.sub(r"^\s*(?:[-*+] |\d+[.)]\s+)", "", line.strip())
    line = re.sub(r"[`*_#>]", "", line)
    return re.sub(r"\s+", " ", line).lower()


def approximate_tokens(text: str) -> int:
    cjk_count = len(CJK.findall(text))
    remainder = CJK.sub("", text)
    return cjk_count + math.ceil(len(remainder.encode("utf-8")) / 4)


def within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
        return True
    except ValueError:
        return False


def discover(root: Path, max_files: int, max_bytes: int) -> tuple[list[Path], list[dict]]:
    files: list[Path] = []
    skipped: list[dict] = []
    for path in sorted(root.rglob("*")):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if not path.is_file() or not within_root(path, root):
            continue
        relative_path = path.relative_to(root)
        if not is_candidate(relative_path):
            continue
        size = path.stat().st_size
        if size > max_bytes:
            skipped.append({"path": str(path.relative_to(root)), "reason": "size-limit", "bytes": size})
            continue
        files.append(path)
        if len(files) >= max_files:
            skipped.append({"path": "*", "reason": "file-limit", "limit": max_files})
            break
    return files, skipped


def audit(root: Path, max_files: int, max_bytes: int) -> dict:
    files, skipped = discover(root, max_files, max_bytes)
    entries: list[dict] = []
    duplicate_index: dict[str, list[dict]] = defaultdict(list)
    conflict_hits: dict[str, dict[str, list[dict]]] = {
        name: {"side_a": [], "side_b": []} for name, _, _ in CONFLICT_RULES
    }

    for path in files:
        relative = str(path.relative_to(root))
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped.append({"path": relative, "reason": "non-utf8"})
            continue

        lines = text.splitlines()
        directive_lines = 0
        for line_number, line in enumerate(lines, 1):
            normalized = normalize_line(line)
            if len(normalized) < 12 or not DIRECTIVE.search(normalized):
                continue
            directive_lines += 1
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
            duplicate_index[digest].append({"path": relative, "line": line_number})
            for name, side_a, side_b in CONFLICT_RULES:
                if side_a.search(normalized):
                    conflict_hits[name]["side_a"].append({"path": relative, "line": line_number})
                if side_b.search(normalized):
                    conflict_hits[name]["side_b"].append({"path": relative, "line": line_number})

        entries.append({
            "path": relative,
            "bytes": len(text.encode("utf-8")),
            "characters": len(text),
            "lines": len(lines),
            "approx_tokens": approximate_tokens(text),
            "directive_lines": directive_lines,
        })

    duplicates = [
        {"rule_hash": digest, "occurrences": occurrences}
        for digest, occurrences in sorted(duplicate_index.items())
        if len(occurrences) > 1
    ]
    conflicts = [
        {"rule": name, **hits}
        for name, hits in conflict_hits.items()
        if hits["side_a"] and hits["side_b"]
    ]
    totals = {
        key: sum(entry[key] for entry in entries)
        for key in ("bytes", "characters", "lines", "approx_tokens", "directive_lines")
    }
    totals["files"] = len(entries)
    totals["duplicate_groups"] = len(duplicates)
    totals["potential_conflicts"] = len(conflicts)
    totals["directive_density"] = round(
        totals["directive_lines"] / max(totals["lines"], 1), 4
    )
    return {
        "schema_version": 1,
        "root": str(root),
        "totals": totals,
        "files": entries,
        "duplicate_groups": duplicates,
        "potential_conflicts": conflicts,
        "skipped": skipped,
        "notes": [
            "Token counts are heuristic estimates, not provider billing values.",
            "Conflict matches are candidates for human review, not confirmed contradictions.",
            "Rule contents are intentionally omitted; only hashes and locations are emitted.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--max-files", type=int, default=250)
    parser.add_argument("--max-bytes", type=int, default=512_000)
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    report = audit(root, args.max_files, args.max_bytes)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_out:
        args.json_out.expanduser().write_text(payload, encoding="utf-8")
        print(f"Wrote audit report: {args.json_out}")
        print(json.dumps(report["totals"], ensure_ascii=False))
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
