#!/usr/bin/env python3
"""Focused tests for prompt-stack file discovery."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("audit_prompt_stack.py")
SPEC = importlib.util.spec_from_file_location("audit_prompt_stack", MODULE_PATH)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class CandidateDiscoveryTests(unittest.TestCase):
    def test_standard_prompt_surfaces_are_included(self) -> None:
        self.assertTrue(AUDIT.is_candidate(Path("AGENTS.md")))
        self.assertTrue(AUDIT.is_candidate(Path(".codex/hooks.json")))
        self.assertTrue(AUDIT.is_candidate(Path(".agents/skills/demo/SKILL.md")))

    def test_framework_surfaces_are_included(self) -> None:
        self.assertTrue(AUDIT.is_candidate(Path(".superpowers/plans/feature.md")))
        self.assertTrue(AUDIT.is_candidate(Path("docs/superpowers/plans/feature.md")))
        self.assertTrue(AUDIT.is_candidate(Path("docs/compound-engineering/workflow.md")))
        self.assertTrue(AUDIT.is_candidate(Path(".codex-plugin/plugin.json")))
        self.assertTrue(AUDIT.is_candidate(Path(".claude-plugin/plugin.json")))

    def test_unrelated_docs_are_not_included(self) -> None:
        self.assertFalse(AUDIT.is_candidate(Path("docs/architecture/overview.md")))
        self.assertFalse(AUDIT.is_candidate(Path("packages/example/plugin.json")))

    def test_sensitive_files_stay_excluded(self) -> None:
        self.assertFalse(AUDIT.is_candidate(Path(".codex/auth.json")))
        self.assertFalse(AUDIT.is_candidate(Path(".superpowers/private-key.md")))


if __name__ == "__main__":
    unittest.main()
