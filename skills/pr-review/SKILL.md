---
name: pr-review
description: Perform a strict, full-coverage pull-request review against its issue, repository architecture, tests, security, and current target branch; supports an operator-authorized CI-free source-review profile.
argument-hint: "[--ci-free] [PR_NUMBER_OR_URL]"
allowed-tools: [Read, Bash, Grep, Glob, Agent, WebFetch]
---

# Pull-request review

Review a PR read-only by default. Never post comments, submit a review, edit issues, merge, close,
rebase, or push without explicit user approval after presenting the report.

## Resolve the PR

1. Preserve a PR number or URL supplied by the user as the helper argument.
2. Keep the target repository as the current working directory. Resolve `scripts/resolve_pr.py`
   against this installed skill directory and invoke that absolute helper path with an optional
   `[PR_NUMBER_OR_URL]`. With no argument, it discovers the target branch and accepts exactly one
   open PR for that branch.
3. Exit status 2 means no PR was found: stop and ask for a number or URL. Exit status 3 means the
   helper printed multiple candidates: show them and ask the user to choose.
4. Confirm repository identity and fetch the PR head and base before reviewing.

Do not guess a PR from title similarity or recent activity.

## CI-free source-review profile

Use this profile only when the operator explicitly requests CI-free source
review. A host may expose it as an optional `--ci-free` argument; use that
host's native invocation syntax from the host-compatibility mapping. It is for
a caller that owns its source-review decision but cannot control, query, or
rely on CI/CD. The profile keeps this skill's full issue, architecture,
implementation, test, security, and source-history review; it excludes only
CI/CD evidence and merge-readiness claims.

When the profile is active:

- Resolve PR identity with `resolve_pr.py`, passing only the optional PR
  identifier to that helper. It verifies the PR URL belongs to the current
  repository and returns the exact base/head OIDs. Do not invoke
  `collect_evidence.py`, `gh pr checks`, `statusCheckRollup`, workflow,
  artifact, deployment, or merge-queue queries.
- Before reviewing, require a clean checkout, verify `git rev-parse HEAD`
  equals the resolved `headRefOid`, and verify `baseRefOid` is a local commit
  object. Use those immutable OIDs, rather than branch names, as the two
  local Git diff-lens inputs. If either commit cannot be verified, stop with a
  source-review coverage gap; never review a stale or mismatched checkout.
- Derive changed paths from those two local Git diff lenses and inspect the
  verified head checkout. Read linked issue and PR metadata only when the
  query excludes CI/CD status fields.
- Record branch staleness and conflicts as source-history facts, but do not
  require a rebase, fresh CI, or external check result before the profile's
  source-review verdict. Never call that verdict "merge-ready."
- Before running a repository task or helper, inspect its definition. Do not
  run one that queries CI/CD, checks/statuses, workflows, artifacts,
  deployments, or merge queues indirectly. Run only local constituent
  validation commands when they are available; otherwise report the local
  validation coverage gap. Do not infer external-check success from local
  command results.
- State that CI/CD evidence was deliberately excluded. A `GO` from this
  profile means the source review passed; it does not authorize a merge or
  assert CI/CD status.

If the requested decision needs CI/CD, merge readiness, deployment evidence,
or an external required-check result, stop and ask the operator to use the
default profile instead.

## Host compatibility

Use native subagents when available, one per independent review dimension. If the host lacks
delegation, run the dimensions sequentially. Use capability terms, not branded models or fixed
vendor APIs.

Every dimension must return a full-coverage result. If a reviewer fails, times out, or samples its
bucket, redispatch that dimension or complete it sequentially before finalizing. A coverage gap may
describe genuinely inaccessible evidence; it may not substitute for retrying available evidence.

## Evidence collection

With the target repository still as the current working directory, resolve
`scripts/collect_evidence.py` against this installed skill directory and invoke that absolute helper
path with `PR_NUMBER_OR_URL`. Retain its JSON output containing PR metadata, changed paths, and
current check output.

This default evidence procedure does not apply to the operator-authorized
CI-free source-review profile. In that profile, use `resolve_pr.py` for
repository identity and immutable base/head OIDs, local Git for changed paths
and the two diff lenses, and only non-CI/CD PR and issue metadata needed to
review the source change.

Read every changed file in full, not only diff hunks. Read linked issues, acceptance criteria,
`AGENTS.md`, ADRs, public contracts, and affected tests. Treat the PR body and issue as claims that
must be verified against code and executable evidence.

Read and apply every item in [`references/criteria.md`](references/criteria.md). The checklist is
part of this skill's required workflow, not optional background material. Before grading, reconcile
the linked issue and proposed follow-ups against issue comments, current-base code, matching commits,
all-state pull requests, and the existing issue backlog.

Read and explicitly apply
[`../../docs/policies/development.md`](../../docs/policies/development.md). Review the change against
KISS, YAGNI, TDD, DRY, SOLID, modularity, least astonishment, durable-artifact discipline, and
behavior-first testing. Treat prose-string/document-count tests, documentation snapshots, flaky
implementation-detail assertions, manual changelogs, generated docs, duplicated registries or
inventories, and unrelated generated files as findings unless a current product consumer and stable
update mechanism justify them.

### Use both diff lenses

With the target repository still as the current working directory, resolve `scripts/diff_context.py`
against this installed skill directory and invoke that absolute helper path with `BASE_REF HEAD_REF`.
It returns the behind count, merge base, author-intent range, and current-base range as JSON.

- **Author intent:** diff the returned `author_intent_range`; it shows work introduced since the
  merge base.
- **Current-main impact:** diff the returned `current_base_range`; it shows the literal difference
  from the current base and reveals revert/deletion risk on a stale branch.

Never substitute one lens for the other. In the default profile, if the branch
is behind, require a rebase and fresh CI before declaring it merge-ready. In
the CI-free source-review profile, report the behind count but do not require a
rebase or fresh CI for the source-review verdict, and do not declare the PR
merge-ready. Detect already-landed or zombie work by checking current base
content, not commit ancestry alone on squash-merge repositories.

## Review dimensions

Score each dimension from 0 points upward with exact `path:line` and command evidence. Award points
only for criteria supported by inspected evidence; do not assign a provisional letter grade before
calculating the percentage:

1. **Issue and scope alignment (25%)** — every acceptance criterion covered; no hidden scope;
   user-visible behavior and docs match the issue.
2. **Architecture and design (20%)** — repository boundaries, ADRs, interfaces, KISS/YAGNI,
   dependency direction, and applicable compatibility or migration requirements.
3. **Implementation quality (20%)** — correctness, error paths, types, maintainability, DRY,
   dead code, portability, surprising behavior.
4. **Testing and evidence (15%)** — behavior-first tests, regression/error coverage, meaningful
   assertions, clean check results, no fabricated evidence. In the CI-free
   source-review profile, assess locally run evidence only and identify CI/CD
   evidence as deliberately excluded and N/A.
5. **Security and safety (10%)** — secrets/PII, untrusted inputs, permissions, destructive actions,
   supply chain, rollback and failure behavior.
6. **Integration and release readiness (10%)** — base staleness, conflicts, CI, packaging, docs,
   applicable backwards compatibility, and operational handoff. In the
   CI-free source-review profile, assess source-level integration only; CI and
   external release readiness are deliberately out of scope and N/A.

For each dimension, begin at **0%**, add earned points criterion by criterion, total the percentage,
and only then map it to this strict scale: A 93–100, B 80–92, C 70–79, D 60–69, F 0–59. A requires
no critical or major findings. B requires no critical findings and at most one major finding. Never
award or deduct points merely because a letter grade is the starting assumption.

In the CI-free source-review profile, mark every CI/CD-only criterion N/A and
normalize the weighted score over the remaining applicable source criteria.
Do not award or deduct points for excluded evidence; identify each N/A portion
and its reason in the scorecard.

Record the product-maturity baseline before scoring. Compatibility, migration, and version-bump
criteria apply only when an established supported release or public contract exists. An explicit
maintainer declaration that the change is the first supported release may make those criteria N/A;
state that assumption in the report instead of treating bootstrap interfaces as backwards-compatible
obligations.

## Required checks

- Run repository-defined formatting, lint, type, unit/integration, validation, and build commands
  relevant to the diff when safe and available.
- Distinguish pre-existing failures from PR-introduced failures using the base branch where needed.
- Do not call a PR merge-ready when required checks are absent, skipped incorrectly, stale, or run
  against an old head SHA.
- Search for stale identifiers after renames and deleted paths after migrations.

For the CI-free source-review profile, run only applicable local commands whose
definitions have been inspected for indirect CI/CD queries. Do not query or
assess required CI/CD checks, and do not make a merge-readiness claim. The
report must separate local command results from the deliberately excluded
CI/CD evidence and any local-validation coverage gap.

## Output contract

Return:

1. PR identity, base/head, behind count, files reviewed, linked issue and acceptance criteria.
2. Findings first, ordered CRITICAL → MAJOR → MINOR → NITPICK. Every finding states what, where,
   impact, and a concrete fix.
3. Six-dimension scorecard and weighted overall grade.
4. Commands run with pass/fail status and any coverage gaps.
5. Explicit GO, CONDITIONAL GO, or NO-GO verdict. The CI-free profile must
   label this a source-review verdict and state that it is not a CI/CD or
   merge-readiness conclusion.
6. A short list of strengths only after findings.

If there are no findings, say so and identify residual risks or unverified assumptions. End by
asking whether the user wants the report posted only when posting is relevant; do not post by
default.
