---
name: simplify
license: BSD-3-Clause
description: Review a repository or target path for safe deletion, reuse, consolidation, or retention when subtraction may satisfy the current requirement with less code or less system complexity. Use this skill for read-only review. Stop if the repository root, revision, worktree overlay, or in-scope inventory cannot be bound.
argument-hint: "[TARGET]"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Simplify review

Use this skill when you need a subtraction-first review. Do not use it for implementation.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to
all prose that it produces.

Use the [shared review contract](../../docs/review/common.md) and the
[review framework overview](../../docs/review/README.md).

## When to use

- The task asks if an existing module, abstraction, interface, dependency, configuration path, or
  state owner can be removed, reused, consolidated, simplified, or retained.
- The task asks for a read-only review.
- The host can bind the repository root, revision, worktree overlay, and in-scope inventory.
- Stop if a required binding or capability is missing.

## Required inputs

- Repository root.
- Revision.
- Worktree overlay or other mutable view.
- Target path, if one exists.
- Validation evidence that binds the review to the current revision.

## Principles

Use the [canonical engineering-principles catalog](../../docs/principles/README.md) for the
principle definitions. Use only these principles because they materially affect this workflow:

- [P001 KISS](../../docs/principles/README.md#p001): Choose the smallest evidence-backed result
  that fits the requirement.
- [P002 YAGNI](../../docs/principles/README.md#p002): Do not keep or add a mechanism for a future
  use only.
- [P003 DRY](../../docs/principles/README.md#p003): Treat duplicate authority as a consolidation
  candidate.
- [P007 Subtraction Over Addition](../../docs/principles/README.md#p007): Start with remove, reuse,
  consolidate, or simplify before you ask for a new addition.
- [P008 Understand Before Subtracting](../../docs/principles/README.md#p008): Verify purpose,
  consumers, history, tests, and contracts before deletion.
- [P013 AHA](../../docs/principles/README.md#p013): Do not invent a new abstraction when evidence
  does not show a stable repeated need.
- [P074 Prefer Existing Mechanisms](../../docs/principles/README.md#p074): Reuse the current
  repository mechanism if it meets the requirement.
- [P088 Delete Dead Code](../../docs/principles/README.md#p088): Remove unreachable, superseded, or
  obsolete code after safety evidence.
- [P089 Delete Obsolete Configuration and Dependencies](../../docs/principles/README.md#p089):
  Remove obsolete config, dependencies, tests, docs, and scaffolding after no consumer remains.
- [P090 Prefer Negative Code](../../docs/principles/README.md#p090): Prefer less code, state,
  config, and maintenance when options are equally clear.

## Workflow

1. Bind the repository root, revision, worktree overlay, and full in-scope inventory before
   analysis.
2. If no target is given, inspect the complete bound repository and worktree overlay. Do not
   sample.
3. If a module or directory target is given, start there. Expand only to connected callers, tests,
   exports, configuration, dependencies, and documentation. Report each scope expansion.
4. Compare concepts, control flow, interfaces, dependencies, configuration, state, and code.
5. Collect evidence about consumers, behavior, purpose, contracts, history, risk, and validation.
6. Before you classify a deletion or breaking interface change, check if it affects a published
   public API.
7. If a candidate affects a published public API, identify the published surface, current
   consumers, required deprecation notice or compatibility bridge, migration path, supported
   version or removal window, and validation evidence.
8. If the repository has no documented deprecation policy for that published public API, stop and
   request maintainer direction.
9. Until the deprecation and compatibility conditions are complete, classify that published public
   API candidate as `retain` or limit it to deprecation and migration work.
10. Classify each supported candidate as delete, consolidate, reuse, simplify, or retain.
11. Give each candidate a stable ID.
12. For each candidate, report scope, preserved behavior, the smaller alternative, dependencies and
    order, validation, rollback, and expected net reduction.
13. If the repository changes during review, stop and report drift.
14. After the read-only report, stop at a checkpoint. Offer one of these actions:
   - stop;
   - publish one issue for one candidate or a deduplicated tracker with child issues for many
     candidates; or
   - implement only the approved candidate IDs and deletion paths.
15. If no supported candidate exists, report that result and do not create an empty tracker.
16. If a required capability is absent, use the documented safe fallback or stop with the missing
    evidence. Do not guess.

## Review output

Report these items:

- binding: repository root, revision, worktree overlay, and inventory;
- target and any scope expansion;
- candidate list with stable IDs and categories;
- evidence for consumers, behavior, purpose, contracts, history, risk, and validation;
- for any validation success claim, the exact command, bound revision, environment, exit status,
  and unedited output; otherwise report the evidence gap and do not claim success;
- published public API deprecation evidence, when applicable;
- category result for simplification coverage: `finding`, `clear`, or `not applicable`;
- the checkpoint action list;
- drift, if any; and
- the unsupported evidence or capability gap, if any.

For each simplification finding, tag it with `category: simplification` and keep the normal
severity, disposition, location, impact, evidence, and remediation fields.

## Failed approaches

- Do not treat zero direct callers or a raw line count as proof that removal is safe.
- Do not classify published public API removal or a breaking interface change as immediately
  executable without the documented deprecation and compatibility evidence.
- Do not sample the bound scope when the full scope is available.
- Do not guess a missing capability or invent a tracker when no supported candidate exists.
- Do not continue after drift.
- Do not modify files, issues, branches, or pull requests in the initial workflow.

## Attribution

This skill follows the Athena review contract, the development policy, and GitHub issue #165.
