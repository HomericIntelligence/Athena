---
name: repo-review
description: Perform a full-coverage, strict repository evaluation. Supports quick and default report detail; default is the comprehensive strict review.
argument-hint: "[quick|default]"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Repository review

Evaluate an entire repository against concrete engineering evidence. Every section starts at 0
points and earns percentage credit only from files, commands, history, or live configuration that
the reviewer actually inspected. Assign the letter grade only after calculating the percentage.

## Modes

- `default` (implicit): full coverage, strict grading, detailed evidence and remediation report.
- `quick`: the same full evaluation and strict grading, but a compact report with only decisive
  evidence, blockers, and the top three actions.

There is no lenient mode. “Quick” changes output detail, not coverage or standards.

## Host compatibility

Use the host's native subagent mechanism when available. Assign one independent section to each
subagent, up to the host's safe concurrency limit. If delegation is unavailable, evaluate sections
sequentially in the current agent. Never require a branded model or vendor-specific tool call.

## Required workflow

### 1. Establish scope

1. Confirm the repository root with `git rev-parse --show-toplevel` when Git is present.
2. Inventory every tracked and relevant untracked file. Exclude only generated dependency caches,
   VCS internals, and build outputs that are clearly non-source.
3. Record language, framework, package, deployment, and agent-host surfaces.
4. Read all repository guidance (`AGENTS.md`, linked host pointers, ADRs, contribution/security
   policy) before grading.

### 2. Read all evidence

Full coverage is mandatory. Partition the inventory across the 15 sections below so every file is
opened by at least one reviewer. Read all source, tests, manifests, workflows, and public docs.
Inspect relevant Git history and live GitHub configuration when access exists. Report any read gap;
do not silently sample.

Run safe, repository-defined checks when dependencies are available. Capture commands and exit
codes. A documented command is not evidence until it runs successfully.

### 3. Score from zero

Begin every section at **0%**. Add earned points criterion by criterion, total the percentage, and
only then assign a letter grade. Do not use a provisional letter grade as the scoring baseline.

Use this scale without rounding up:

| Grade | Score | Evidence standard |
|---|---:|---|
| A | 93–100 | Near exemplary; no critical/major issues and at most two minor issues. |
| B | 80–92 | Strong; no critical issues and at most one major issue. |
| C | 70–79 | Functional but contains several material gaps. |
| D | 60–69 | Poor; fundamental practices or contracts are broken. |
| F | 0–59 | Missing, unsafe, or fundamentally unreliable. |

Absence of evidence earns no credit. Intent, TODOs, filenames, and static badges do not prove a
criterion. Mark a criterion N/A only with a project-specific reason.

Establish the product-maturity baseline before scoring. Versioning, migration, and backwards-
compatibility criteria apply only to established supported releases or public contracts. When the
maintainer explicitly identifies the evaluated state as the first supported release, record that
assumption and treat earlier bootstrap interfaces as N/A for compatibility scoring.

### 4. Evaluate all sections

1. **Structure and organization** — domain boundaries, separation of source/tests/docs/config,
   naming, discoverability, unnecessary duplication, nesting.
2. **Documentation** — accurate purpose, prerequisites, per-platform install/use/update/removal,
   contributing, architecture, security, release/rollback, links, single sources of truth.
3. **Architecture and design** — dependency direction, interfaces, error/config strategy,
   proportional complexity, extensibility without speculative abstraction.
4. **Source quality** — readability, cohesion, typing, errors, logging, dead code, hardcoded state,
   lint/format enforcement, DRY and idiomatic implementation.
5. **Testing** — unit/integration/end-to-end contracts, edge/error paths, isolation, coverage scope,
   speed, disabled tests, and test-first history.
6. **CI/CD** — required PR/main gates, reproducible builds, tests/security/build/install stages,
   caching, artifacts, releases, rollback, and actual branch/ruleset enforcement.
7. **Dependencies** — correct package identities, lockfiles, bounded versions, production audits,
   license/SBOM checks, update policy, dev/runtime separation.
8. **Security** — secrets/PII, input and command safety, permissions, supply-chain controls, SAST,
   dependency/secret scanning, disclosure policy, and host-specific guardrails.
9. **Safety and reliability** — fail-closed behavior, partial failure, retries/timeouts, integrity,
   idempotency, recovery/rollback, resource bounds, and observability where applicable.
10. **Planning and project management** — issue/PR templates, roadmap, priorities, review rules,
    commit/branch/release process, technical-debt and definition-of-done evidence.
11. **AI agent tooling** — accurate `AGENTS.md`, host pointers, skills, tool portability, permission
    boundaries, human approval gates, memory/context, and executable host contracts.
12. **Packaging and distribution** — artifact contents, install/upgrade channels, versioning,
    compatibility, release automation, artifact smoke tests.
13. **Developer experience** — one-command bootstrap, reproducible tools, task runner, editor and
    debugging support, fast feedback, actionable failure messages.
14. **API/CLI design** — naming, versioning, validation, errors, idempotency, discoverability, and
    documentation for every public API or command. Mark N/A only if none exists.
15. **Compliance and governance** — valid license, third-party notices, conduct/security policy,
    privacy/accessibility/data rules where relevant, ownership and audit trail.

Apply KISS, YAGNI, TDD, DRY, SOLID, modularity, and least astonishment throughout.

### 5. Calculate the overall score

Weights: architecture 15%, source quality 15%, testing 12%, security 12%, safety 10%, CI/CD 8%,
documentation 7%, AI agent tooling 5%, dependencies 3%, packaging 3%, and each of structure,
planning, developer experience, API/CLI design, and compliance 2% (100% total).

Verdicts:

- **GO**: score ≥80, no critical issues, at most three major issues.
- **CONDITIONAL GO**: score ≥65, at most two critical issues with concrete remediation.
- **NO-GO**: anything else.

## Output contract

### Default report

Produce:

1. Executive scorecard for all 15 sections and weighted overall score.
2. Per section: grade, evidence reviewed, strengths, severity-ranked findings, missing criteria,
   and principle compliance with exact `path:line` citations.
3. Consolidated critical/major/minor list without duplicates.
4. Development-principles matrix.
5. Coverage report: files inventoried, files read, read errors, commands run.
6. GO/CONDITIONAL GO/NO-GO verdict and ordered remediation plan.

### Quick report

Produce:

1. The complete 15-section scorecard and weighted verdict.
2. Critical and major findings with exact citations.
3. Coverage gaps and failed checks.
4. The top three remediation actions.

Do not omit a section merely because quick mode was requested.
