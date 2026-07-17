#!/usr/bin/env python3
"""Compare two static prompt-stack audit reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


METRICS = [
    ("files", "文件数"),
    ("characters", "字符数"),
    ("approx_tokens", "近似 Token"),
    ("directive_lines", "指令行"),
    ("directive_density", "指令密度"),
    ("duplicate_groups", "重复规则组"),
    ("potential_conflicts", "潜在冲突"),
]


def format_number(value) -> str:
    if isinstance(value, float) and not value.is_integer():
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return f"{int(value):,}"


def change(before: float, after: float) -> str:
    if before == 0:
        return "新增" if after else "0%"
    delta = (after - before) / before * 100
    return f"{delta:+.1f}%"


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or "totals" not in data:
        raise ValueError(f"unsupported audit report: {path}")
    return data


def render(before: dict, after: dict) -> str:
    rows = [
        "| 指标 | 优化前 | 优化后 | 变化 | 数据类型 |",
        "|---|---:|---:|---:|---|",
    ]
    for key, label in METRICS:
        first = before["totals"].get(key, 0)
        second = after["totals"].get(key, 0)
        rows.append(
            f"| {label} | {format_number(first)} | {format_number(second)} | "
            f"{change(float(first), float(second))} | 静态估算 |"
        )
    rows.extend([
        "",
        "> 该表只比较静态提示词结构；任务质量、安全、延迟、成本和工具行为必须通过相同任务集实测。",
    ])
    return "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    output = render(load(args.before), load(args.after))
    if args.markdown_out:
        args.markdown_out.write_text(output, encoding="utf-8")
        print(f"Wrote comparison: {args.markdown_out}")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
