---
name: repo-review
description: Perform an architecture-first, full-inventory repository review with adaptive surface and language checks. Use to assess a repository and, unless `--report-only` is requested, publish deduplicated GitHub tracking issues or a GitLab epic for actionable findings.
argument-hint: "[quick|default] [--report-only]"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Repository review

Review the whole repository using the shared [review contract](../../docs/review/common.md),
[language routing](../../docs/review/language-routing.md),
[behavior-first testing](../../docs/review/behavior-first-testing.md), and
[repository scorecard](../../docs/review/repository-scorecard.md).

`--report-only` is read-only. A direct user invocation without it authorizes
only the documented tracker and work-item publication after the review is
complete. An indirect invocation does not confer forge-write authority. Never
merge, change labels, close issues, push, or modify repository source.

## Modes

- `default` (implicit): full coverage, strict grading, detailed evidence and
  remediation report.
- `quick`: the same full evaluation and strict grading, but a compact report
  with decisive evidence, blockers, and the top three actions.

There is no lenient mode. “Quick” changes output detail, not coverage or
standards.

## Host compatibility

Use native subagents when available, assigning independent inventory sections
with non-overlapping file ownership. If delegation is unavailable, evaluate
them sequentially. A failed, timed-out, or sampled section must be retried or
completed sequentially before finalizing; it is not complete merely because it
was assigned.

Use GitHub parent/sub-issues when the forge supports them. On GitLab, use a
group epic and child issues when those capabilities are available. If the forge
cannot safely perform the requested hierarchy, return a ready-to-publish plan
and identify the capability gap rather than guessing an API or claiming a
published artifact.

## Required workflow

### 1. Bind scope and architecture first

1. Confirm the repository root with `git rev-parse --show-toplevel` when Git is
   available. Bind the review to its inspected revision when possible.
2. Inventory every tracked and relevant untracked file. Exclude only generated
   dependency caches, VCS internals, and build outputs that are clearly
   non-source.
3. Read repository guidance, ADRs, contribution and security policy, public
   contracts, module boundaries, and dependency direction before evaluating
   implementation detail.
4. Establish the architecture decision from the shared contract: aligned,
   intentional and evidenced architecture change, or unexplained deviation.
   A material unexplained deviation is a required blocking finding before any
   score or lower-level strength can compensate for it.
5. Classify actual repository surfaces, languages, frameworks, deployment
   targets, and agent-host tooling. Apply only applicable language and surface
   checks, recording every N/A decision and its concrete reason.

### 2. Inspect the complete repository

Full inventory coverage is mandatory. Partition files across the 15 scorecard
sections so every in-scope file is read in context by at least one reviewer.
Read source, tests, manifests, workflows, public docs, and relevant history;
inspect live forge configuration when access exists. Report a read gap rather
than silently sampling.

Apply every applicable scorecard criterion and the shared principles as
decision rules. Follow repository-selected compiler, formatter, linter, type
checker, test, build, packaging, and deployment tooling before generic advice.
The deep Python, C++, Go, and Mojo profiles are mandatory when present; route
the remaining in-scope languages through the shared matrix. An unknown
executable language is a coverage gap, not a generic-checklist pass.

Run safe repository-defined checks when their dependencies are available.
Capture command identity, exit code, revision, and output classification. A
documented command is not evidence until it has run; a successful name-filtered
test command is not evidence until its matching test set is known to be
non-empty.

### 3. Evaluate behavior-first tests

Assess tests as evidence for core product behavior, public contracts, errors,
boundaries, state changes, concurrency, security, and applicable performance
claims. Reject prose-string, documentation-count, implementation-layout,
mock-only, order-dependent, wall-clock, live-network, or ambient-state tests
unless the product contract explicitly requires and controls that condition.

For C++ and CMake, verify test sources are wired to a real test target. For
other filtered test runners, prove that the focused selection exercised a real
test. Documentation-only work uses existing Markdown, link, and executable
example checks; it does not justify a prose assertion harness.

### 4. Score only after the architecture gate

Begin every section at **0%**. Add earned points criterion by criterion, total
the percentage, then assign a letter grade without rounding up:

| Grade | Score | Evidence standard |
| --- | ---: | --- |
| A | 93–100 | Near exemplary; no critical/major issues and at most two minor issues. |
| B | 80–92 | Strong; no critical issues and at most one major issue. |
| C | 70–79 | Functional but contains several material gaps. |
| D | 60–69 | Poor; fundamental practices or contracts are broken. |
| F | 0–59 | Missing, unsafe, or fundamentally unreliable. |

Absence of evidence earns no credit. Intent, TODOs, filenames, and badges do
not prove a criterion. Establish the product-maturity baseline before applying
versioning, migration, and compatibility expectations; state any bootstrap N/A
assumption explicitly.

Weights: Structure 2%, Documentation 6%, Architecture 20%, Source quality 14%, Testing 12%, CI/CD 8%, Dependencies 3%, Security 11%, Reliability 9%, Planning 3%, Agent tooling 4%, Packaging 3%, Developer experience 2%, API/CLI 2%, Governance 1% (100% total).

Verdicts:

- **GO**: score ≥80, no critical issues, no material architecture violation,
  and at most three major issues.
- **CONDITIONAL GO**: score ≥65, no material architecture violation, and no
  more than two critical issues with concrete remediation.
- **NO-GO**: anything else, including a material unexplained architecture
  deviation.

### 5. De-duplicate and deliver actionable findings

Before any external write, search the existing issue backlog, recently closed
work, pull requests, and tracker artifacts for the same failure mode and
remediation. Consolidate duplicate findings by product outcome, not matching
words. Do not create work items for `nit` or `FYI` findings.

If no actionable findings remain after de-duplication, do not create an empty
tracker. Return the clean review result and residual risks instead.

Immediately before publication, re-check the repository and forge identities,
the inspected revision, and tracker targets. Then, when directly authorized:

1. Create or update one actor-owned tracking issue on GitHub, or one GitLab
   epic, that records the review revision, scope, architecture decision,
   scorecard, and finding URLs. Use a stable machine marker only in content the
   authenticated actor owns.
2. Create one deduplicated child issue for each remaining actionable finding,
   with severity, precise evidence, impact, governing contract, remediation,
   and functional verification. Link it to the GitHub tracker as a sub-issue or
   to the GitLab epic as a child issue.
3. Link pre-existing matching issues instead of creating duplicates. Record all
   returned URLs or IDs. If a step fails, report the partial result honestly and
   leave the remaining ready-to-publish items in the report.

Review prose never approves, labels, merges, or triggers implementation. It is
evidence for the repository's human and forge policy.

## Output contract

### Default report

Produce:

1. Architecture decision first, inspected revision, inventory coverage, and
   language/surface routing with N/A reasons.
2. Executive scorecard for all 15 sections and weighted overall score.
3. Per section: evidence reviewed, grade, strengths, severity-ranked findings,
   missing criteria, and exact `path:line` citations.
4. Consolidated findings without duplicates, followed by behavior-first test
   evidence and commands run or coverage gaps.
5. GO/CONDITIONAL GO/NO-GO verdict and ordered remediation plan.
6. The tracking epic/issue and child-item URLs, or a ready-to-publish plan and
   the reason publication was withheld.

### Quick report

Produce the same coverage and tracker outcome in compact form: the complete
scorecard and verdict, critical/major findings with citations, coverage gaps,
the top three remediation actions, and published or ready-to-publish work-item
links. Do not omit a section because quick mode was requested.
