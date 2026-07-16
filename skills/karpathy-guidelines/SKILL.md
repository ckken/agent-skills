---
name: karpathy-guidelines
description: Use when explicitly requested, or when a coding task risks overengineering, scope creep, unnecessary refactoring, or unclear completion criteria. Produces a small, complete change with proportionate validation. Skip trivial, well-scoped edits unless explicitly requested.
license: MIT
---

# Karpathy Guidelines for GPT-5.6

A lightweight corrective overlay, not a mandatory coding workflow.

## Contract

Deliver the smallest complete, maintainable change that satisfies the request, respects the codebase, and is verified in proportion to risk.

## Rules

- Identify the requested outcome, scope, constraints, and completion bar.
- Proceed with reasonable, reversible assumptions. Ask only when missing information materially changes the outcome, authorization, scope, or an irreversible decision.
- Prefer the simplest approach that meets current requirements. Surface alternatives only when the tradeoff affects the result.
- Do not add speculative features, abstractions, configurability, or compatibility work.
- Preserve existing architecture, conventions, and style unless the outcome requires change.
- Exclude unrelated cleanup, formatting, and refactoring.
- Include tests, types, documentation, generated files, or dependency metadata only when they support the outcome or its validation.
- Remove artifacts made obsolete by this change; leave pre-existing dead code alone unless correctness requires otherwise.
- Run the smallest relevant check for the affected behavior. Expand only when repository rules, risk, or failure requires it.
- Verify the user-visible behavior or failure mode when practical; a passing command may be insufficient.
- Report the completed outcome, validation performed, and material limitations or unverified risks.

## Scale by risk

- **Trivial:** implement directly, run one focused check, and skip ceremony.
- **Multi-step:** use a short plan only when dependencies need coordination.
- **High-risk:** establish a baseline or reproduction, add regression coverage, run broader checks, and consider rollback.

## Guardrails

- Do not require test-first development when another check better fits the artifact.
- Do not use arbitrary line counts or equate fewer lines with simpler code.
- Do not let this Skill override user instructions, repository rules, safety requirements, or authorization boundaries.

## Stop

Stop when the requested outcome is met, every changed file or hunk supports that outcome or its validation, relevant checks pass, and material limitations are stated. Do not continue improving adjacent code.
