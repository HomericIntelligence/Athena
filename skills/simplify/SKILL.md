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
- Validation evidence, when available. If no current-head receipt exists, report the evidence gap
  and do not state that validation succeeded.

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

## Candidate signals and ownership

Use these items only as signals for investigation:

- code or another artifact that evidence shows is unreachable, superseded, or obsolete;
- a dependency, configuration item, test, document, or scaffold that has no current purpose or
  consumer;
- a comment that only repeats the code or describes an internal work plan;
- a wrapper or alias that only forwards an operation;
- repeated code or authority that evidence shows represents one stable concept;
- a guard, validation step, or compatibility mechanism that duplicates an authoritative mechanism
  or has completed its supported lifetime; and
- residue from a patch, such as debug output, abandoned branches, unrelated edits, or unnecessary
  file churn.

Confirm each candidate with evidence about its consumers, behavior, contracts, history, and
validation. An AISlop diagnostic, another scanner result, a score, a line count, a complexity
metric, or a churn metric is only an investigation lead. It is not proof of a finding. Do not infer
the source author from these signals.

Retain a wrapper, guard, validation step, or compatibility mechanism when it has a necessary
boundary, security, observability, framework, or published-API function. Retain intentional
duplication when it prevents an incorrect shared abstraction.

Use [`realign`](../realign/SKILL.md) when a candidate needs a structural change to error policy,
responsibility, state or invariant ownership, a type model, test architecture, or security
architecture. `simplify` can identify and route this candidate. It must not design or make the
structural change.

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
10. Give each supported candidate `category: simplification`. Classify its action as `delete`,
    `consolidate`, `reuse`, `simplify`, or `retain`. Also give it a routing owner.
11. Give each candidate a stable ID.
12. For each candidate, report scope, preserved behavior, the smaller alternative, dependencies and
    order, validation, rollback, and expected net reduction.
13. If the repository changes during review, stop and report drift.
14. After the read-only report, stop at a checkpoint. Offer one of these actions:
   - stop;
   - hand off compatible approved candidate IDs through an explicit `realign --apply` request; or
   - hand off approved candidate IDs and deletion paths to `plan-issue` or another
     write-authorized workflow outside `simplify`.
15. `simplify` does not create issues, trackers, or any other forge write. If a write task is
   needed, hand off to a separate workflow with explicit write authority.
16. Candidate approval inside `simplify` authorizes only the specified handoff. The explicit
    `realign --apply` request supplies bounded code-repair authority. Neither action authorizes a
    dependency installation, forge write, published-API migration, or unrelated cleanup. The
    receiving workflow must bind the repository again.
17. If no supported candidate exists, report that result and do not create an empty tracker.
18. If a required capability is absent, use the documented safe fallback or stop with the missing
    evidence. Do not guess.

## Review output

Report these items:

- binding: repository root, revision, worktree overlay, and inventory;
- target and any scope expansion;
- candidate list with stable IDs, `category: simplification`, and actions;
- routing owner for each candidate;
- evidence for consumers, behavior, purpose, contracts, history, risk, and validation;
- for a candidate that can go to `realign`, current head and overlay identity, exact path and lines,
  category, severity, confidence, disposition, affected contract or invariant, applicable
  principle, behavior and consumer evidence, impact, considered counterexample, smallest safe
  correction, validation, rollback, and dependency order;
- for any validation evidence, the exact command, current reviewed head, environment, exit status,
  and unedited output; otherwise report no current-head validation evidence and do not state that
  validation succeeded;
- published public API deprecation evidence, when applicable;
- category result for simplification coverage: `finding`, `clear`, or `not applicable`;
- the checkpoint action list;
- drift, if any; and
- the unsupported evidence or capability gap, if any.

For each simplification finding, tag it with `category: simplification` and keep the normal
severity, disposition, location, impact, evidence, and remediation fields.

## Failed approaches

- Do not treat zero direct callers or a raw line count as proof that removal is safe.
- Do not treat an AISlop diagnostic, scanner result, score, complexity metric, or churn metric as
  proof of a finding.
- Do not remove necessary boundary, security, observability, framework, or compatibility behavior.
- Do not use `simplify` to make a structural change that belongs to `realign`.
- Do not classify published public API removal or a breaking interface change as immediately
  executable without the documented deprecation and compatibility evidence.
- Do not use a PR description, earlier run, stale receipt, or unbound host output as evidence for a
  current-head success claim.
- Do not sample the bound scope when the full scope is available.
- Do not guess a missing capability or invent a tracker when no supported candidate exists.
- Do not continue after drift.
- Do not modify files, issues, branches, or pull requests in the initial workflow.

## Attribution

This skill follows the Athena review contract, the development policy, and GitHub issue #165.
