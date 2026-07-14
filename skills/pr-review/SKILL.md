---
name: pr-review
description: Perform a strict, full-coverage pull-request review against its issue, repository architecture, tests, security, and current target branch.
argument-hint: "[PR_NUMBER_OR_URL]"
allowed-tools: [Read, Bash, Grep, Glob, Agent, WebFetch]
---

# Pull-request review

Review a PR read-only by default. Never post comments, submit a review, edit issues, merge, close,
rebase, or push without explicit user approval after presenting the report.

## Resolve the PR

1. If the user supplied a PR number or URL, resolve it with `gh pr view <value>`.
2. Otherwise inspect the current branch:

   ```bash
   branch=$(git branch --show-current)
   gh pr view --json number,url,state,headRefName,baseRefName 2>/dev/null || \
     gh pr list --state open --head "$branch" --json number,url,state,headRefName,baseRefName --limit 2
   ```

3. Accept exactly one open PR for the current branch. If there is none, stop and ask the user for
   a PR number or URL. If there are multiple candidates, show them and ask the user to choose.
4. Confirm repository identity and fetch the PR head and base before reviewing.

Do not guess a PR from title similarity or recent activity.

## Host compatibility

Use native subagents when available, one per independent review dimension. If the host lacks
delegation, run the dimensions sequentially. Use capability terms, not branded models or fixed
vendor APIs.

## Evidence collection

Collect and retain:

```bash
gh pr view <PR> --json number,title,body,state,isDraft,author,baseRefName,headRefName,commits,files,reviews,statusCheckRollup,closingIssuesReferences,url
gh pr diff <PR> --name-only
gh pr checks <PR>
```

Read every changed file in full, not only diff hunks. Read linked issues, acceptance criteria,
`AGENTS.md`, ADRs, public contracts, and affected tests. Treat the PR body and issue as claims that
must be verified against code and executable evidence.

### Use both diff lenses

First measure staleness:

```bash
git rev-list --count <head-ref>..<base-ref>
```

- **Author intent:** `git diff $(git merge-base <base-ref> <head-ref>)..<head-ref>` (equivalent to
  three-dot) shows work introduced since the merge base.
- **Current-main impact:** `git diff <base-ref>..<head-ref>` (two-dot) shows the literal difference
  from the current base and reveals revert/deletion risk on a stale branch.

Never substitute one lens for the other. If the branch is behind, require a rebase and fresh CI
before declaring it merge-ready. Detect already-landed or zombie work by checking current base
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
   assertions, clean check results, no fabricated evidence.
5. **Security and safety (10%)** — secrets/PII, untrusted inputs, permissions, destructive actions,
   supply chain, rollback and failure behavior.
6. **Integration and release readiness (10%)** — base staleness, conflicts, CI, packaging, docs,
   applicable backwards compatibility, and operational handoff.

For each dimension, begin at **0%**, add earned points criterion by criterion, total the percentage,
and only then map it to this strict scale: A 93–100, B 80–92, C 70–79, D 60–69, F 0–59. A requires
no critical or major findings. B requires no critical findings and at most one major finding. Never
award or deduct points merely because a letter grade is the starting assumption.

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

## Output contract

Return:

1. PR identity, base/head, behind count, files reviewed, linked issue and acceptance criteria.
2. Findings first, ordered CRITICAL → MAJOR → MINOR → NITPICK. Every finding states what, where,
   impact, and a concrete fix.
3. Six-dimension scorecard and weighted overall grade.
4. Commands run with pass/fail status and any coverage gaps.
5. Explicit GO, CONDITIONAL GO, or NO-GO verdict.
6. A short list of strengths only after findings.

If there are no findings, say so and identify residual risks or unverified assumptions. End by
asking whether the user wants the report posted only when posting is relevant; do not post by
default.
