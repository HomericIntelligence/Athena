---
name: repo-review
description: Perform an architecture-first, full-inventory repository review with adaptive surface and language checks. Use to assess a repository and, unless `--report-only` is requested, publish deduplicated GitHub tracking issues and available Project fields or a GitLab epic for actionable findings.
argument-hint: "[quick|default] [--report-only]"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Repository review

Why: a full, architecture-first inventory review exposes systemic product risks
that a change review cannot see.

Use the shared [review contract](../../docs/review/common.md),
[language routing](../../docs/review/language-routing.md),
[behavior-first testing](../../docs/review/behavior-first-testing.md), and
[repository scorecard](../../docs/review/repository-scorecard.md).

## Authority and modes

`--report-only` is read-only. A direct request without it authorizes only the
documented tracker and work-item publication after review completion; never
merge, change labels, close issues, push, or modify source. Indirect invocation
does not confer forge-write authority.

`default` gives full coverage and a detailed report. `quick` applies the same
coverage and standards but returns decisive evidence, blockers, and the top
three actions. It is not a lenient mode.

Use independent agents with non-overlapping inventory ownership when available.
Retry or complete any failed, timed-out, or sampled section before finalizing.

## Review

1. Bind the repository root, revision, and every in-scope tracked and relevant
   untracked file before inspection. Keep a revalidatable full-source snapshot
   or content-bound inventory manifest, including mutable overlay identity,
   lexical paths, inclusion/exclusion reasons, kind, mode, and object/content
   identities. Do not follow symlinks or publish raw untracked content or
   secrets. If a stable binding is unavailable, report the coverage gap and
   withhold tracker/work-item publication.
2. Read repository guidance, ADRs, policies, public contracts, module
   boundaries, and dependency direction. Decide architecture before scoring:
   aligned, intentional and evidenced change, or unexplained deviation. A
   material deviation is a required blocker. For a material architecture change,
   assess its [design record](../../docs/review/design-docs.md).
3. Classify actual surfaces, languages, frameworks, deployment targets, and
   agent tooling. Apply only relevant profiles, record every N/A reason, and
   account for every in-scope file in context; never silently sample.
   Inspect source, tests, manifests, workflows, public documentation, relevant
   history, and live forge configuration when available.
4. Apply each applicable scorecard criterion and repository-selected tooling
   before generic advice. Repository commands are candidates, not authority:
   execute only through the shared host-enforced validation boundary against the
   bound inventory, recording the command plan, argv, source binding, and
   outcome. Without that boundary, report the validation gap.
5. Assess behavior-first product tests, including errors, boundaries, state,
   concurrency, security, and applicable performance. Reject prose,
   implementation-layout, mock-only, order-dependent, wall-clock, live-network,
   or ambient-state assertions unless the controlled product contract requires
   them. Prove filtered tests selected real tests and C++/CMake sources are
   wired to real targets.
6. Score only after the architecture gate. Start applicable sections at zero,
   award only observed evidence, remove only classifier-proven N/A weights, and
   retain coverage gaps in the denominator. Use the scorecard's 15 sections.

Weights: Structure 2%, Documentation 6%, Architecture 20%, Source quality 14%, Testing 12%, CI/CD 8%, Dependencies 3%, Security 11%, Reliability 9%, Planning 3%, Agent tooling 4%, Packaging 3%, Developer experience 2%, API/CLI 2%, Governance 1%.

Intent, TODOs, filenames, and badges are not evidence. Establish the product
maturity baseline before applying versioning, migration, or compatibility
expectations, and state any bootstrap N/A assumption.

| Grade | Score | Standard |
| --- | ---: | --- |
| A | 93–100 | No critical or major issues; at most two minor issues. |
| B | 80–92 | No critical issues; at most one major issue. |
| C | 70–79 | Functional with material gaps. |
| D | 60–69 | Fundamental practices or contracts are broken. |
| F | 0–59 | Missing, unsafe, or fundamentally unreliable. |

**GO** requires at least 80, no critical or material architecture violation,
and at most three major issues. **CONDITIONAL GO** requires at least 65, no
material architecture violation, and no more than two critical issues with
concrete remediation. Otherwise the verdict is **NO-GO**.

## Findings and publication

De-duplicate against the issue backlog, recently closed work, pull/merge
requests, and tracker artifacts by product outcome, not wording. Do not create
work items for `nit` or `FYI`, and do not create an empty tracker when no
actionable finding remains.

Immediately before every authorized forge write, revalidate the inventory,
repository, and target bindings. On drift, withhold all remaining writes and
report the stale or partial result honestly. On GitHub, use a writable Project
only when its item capability and any mapped field semantics are verified; never
create, rename, or guess fields. On GitLab, use a group epic and child issues
when available. Otherwise return ready-to-publish artifacts and name the
capability gap.

When authorized, create or update one actor-owned tracker with the binding,
scope, architecture decision, scorecard, and finding URLs; use a stable marker
only in content the actor owns. Create one deduplicated child for each remaining
actionable finding and link it as a GitHub sub-issue or GitLab epic child. Link
an existing issue only when it is open and still covers the remediation. A
regression needs its own active child unless explicit authority reopens the old
issue. Add tracker and child items to a writable compatible GitHub Project,
preserving unrelated fields and recording returned URLs or IDs. If a publication
step fails, report the partial result and leave remaining ready-to-publish items
in the result.

## Result

Report architecture first, then the revision and inventory coverage,
language/surface routing and N/A reasons, complete scorecard, exact findings,
behavior-first test evidence and command coverage, verdict, remediation order,
and published or ready-to-publish tracker/work-item links. `quick` may shorten
prose but must retain all sections, verdict, coverage gaps, publication state,
and the top three remediation actions.
