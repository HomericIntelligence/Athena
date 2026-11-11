---
name: simplify
license: BSD-3-Clause
description: Review a repository or target path for safe deletion, reuse, consolidation, or retention when subtraction may satisfy the current requirement with less code or less system complexity. Use this skill for read-only review. Recover missing bindings and continue in batches. Report remaining coverage gaps with supported findings.
argument-hint: "[TARGET]"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Simplify review

Use this skill when you need a subtraction-first review. Use it for review, not implementation.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to
all prose that it produces.

Use the [autonomous workflow policy](../../docs/policies/autonomous-workflows.md) for authority,
recovery, resources, validation, and delivery.

## When to use

- The task asks if an existing module, abstraction, interface, dependency, configuration path, or
  state owner can be removed, reused, consolidated, simplified, or retained.
- The task asks for a read-only review.
- The host can bind the repository root, revision, worktree overlay, and in-scope inventory.
- Recover missing bindings or capabilities where you can. Otherwise proceed and state what is
  missing; note the dependent action as not done rather than blocking unaffected work.

## Inputs

- Repository root.
- Revision.
- Worktree overlay or other mutable view.
- Target path, if one exists.
- Validation evidence, when available. If no current-head receipt exists, report that evidence is
  missing and proceed; state what is missing instead of implying validation succeeded.

## Principles

Use the [canonical engineering-principles catalog](../../docs/principles/README.md) for the
principle definitions. Use only these principles because they materially affect this workflow:

- [P001 KISS](../../docs/principles/README.md#p001): Choose the smallest evidence-backed result
  that fits the requirement.
- [P002 YAGNI](../../docs/principles/README.md#p002): Prefer not to keep or add a mechanism for a
  future use only.
- [P003 DRY](../../docs/principles/README.md#p003): Treat duplicate authority as a consolidation
  candidate.
- [P007 Subtraction Over Addition](../../docs/principles/README.md#p007): Start with remove, reuse,
  consolidate, or simplify before you ask for a new addition.
- [P008 Understand Before Subtracting](../../docs/principles/README.md#p008): Verify purpose,
  consumers, history, tests, and contracts before deletion.
- [P013 AHA](../../docs/principles/README.md#p013): Prefer not to invent a new abstraction when
  evidence does not show a stable repeated need.
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
metric, or a churn metric is only an investigation lead. It is not proof of a finding. Prefer not
to infer the source author from these signals. When that evidence is absent, deliver the lead
labeled with the gap instead of withholding it.

Retain a wrapper, guard, validation step, or compatibility mechanism when it has a necessary
boundary, security, observability, framework, or published-API function. Retain intentional
duplication when it prevents an incorrect shared abstraction.

Use [`realign`](../realign/SKILL.md) when a candidate needs a structural change to error policy,
responsibility, state or invariant ownership, a type model, test architecture, or security
architecture. `simplify` can identify and route this candidate. It leaves the design and the
structural change to `realign`.

## Workflow

1. Bind the repository root, revision, worktree overlay, and full in-scope inventory before
   analysis, when they are available. When a binding is missing, proceed with the parts that can
   run and state what is missing.
2. If no target is given, inspect the bound repository and worktree overlay as fully as available
   coverage permits. Note partial coverage rather than presenting a sample as complete.
3. If a module or directory target is given, start there. Expand only to connected callers, tests,
   exports, configuration, dependencies, and documentation. Report each scope expansion.
4. Compare concepts, control flow, interfaces, dependencies, configuration, state, and code.
5. Collect evidence about consumers, behavior, purpose, contracts, history, risk, and validation.
6. Before you classify a deletion or breaking interface change, check if it affects a published
   public API.
7. If a candidate affects a published public API, identify the published surface, current
   consumers, required deprecation notice or compatibility bridge, migration path, supported
   version or removal window, and validation evidence.
8. If no deprecation policy exists, proceed with the parts the evidence supports and state that
   the migration policy is missing. Request maintainer direction for the missing policy; prefer not
   to infer a migration policy from consumers or release practice.
9. When the deprecation and compatibility conditions are incomplete, classify that published public
   API candidate as `retain` or limit it to deprecation and migration work, and note what is
   missing.
10. Give each supported candidate `category: simplification`. Classify its action as `delete`,
    `consolidate`, `reuse`, `simplify`, or `retain`. Also give it a routing owner.
11. Give each candidate a stable ID.
12. For each candidate, report scope, preserved behavior, the smaller alternative, dependencies and
    order, validation, rollback, and expected net reduction.
13. If source changes during review, refresh affected bindings and findings. Preserve valid evidence.
14. Deliver the read-only report. If the task also authorizes implementation, continue automatically
    through `realign`, `plan-issue`, or the applicable workflow. Keep candidate IDs for tracking.
15. `simplify` itself does not edit source or forge state. The receiving workflow owns authorized
    writes and aims to bind the current source before each affected action; when the binding is
    missing, proceed and state what is missing.
16. Avoid requiring repeated candidate-ID approval or an explicit second skill invocation. Existing
    authority applies to in-scope dependencies, migration, and delivery. Preserve architecture review.

17. If no supported candidate exists, report that result and avoid creating an empty tracker.
18. If a capability is absent, use the documented safe fallback. If recovery fails, report the
    missing evidence and what could not be done. Continue unaffected work. Avoid guessing.

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
  and unedited output; otherwise report that current-head validation evidence is missing, and state
  what is missing;
- published public API deprecation evidence, when applicable;
- category result for simplification coverage: `finding`, `clear`, or `not applicable`;
- the next workflow within task authority;
- drift, if any; and
- the unsupported evidence or capability gap, if any.

For each simplification finding, tag it with `category: simplification` and keep the normal
severity, disposition, location, impact, evidence, and remediation fields.

## Failed approaches

- Avoid treating zero direct callers or a raw line count as proof that removal is safe.
- Avoid treating an AISlop diagnostic, scanner result, score, complexity metric, or churn metric as
  proof of a finding.
- Prefer not to remove necessary boundary, security, observability, framework, or compatibility
  behavior.
- Avoid using `simplify` to make a structural change that belongs to `realign`.
- Avoid classifying published public API removal or a breaking interface change as immediately
  executable while the documented deprecation and compatibility evidence is missing; note the gap
  instead.
- Treat a PR description, earlier run, stale receipt, or unbound host output as non-current-head
  evidence, and label it as such rather than as a current-head success claim.
- Prefer to cover the bound scope fully; when coverage is partial, record it instead of
  presenting the sample as complete.
- Avoid guessing a missing capability or inventing a tracker when no supported candidate exists.
- Avoid using stale evidence after drift; refresh it when possible and note it when not.
- Avoid modifying files, issues, branches, or pull requests in the initial workflow.

## Attribution

This skill follows the Athena development policy and GitHub issue #165.
