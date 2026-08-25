# Repository review scorecard

**Why:** A repository review needs a complete, architecture-first inventory so a strong area cannot hide
an unsafe boundary or an unreviewed surface.

Use the [ASD-STE100 writing policy](../../skills/TECHNICAL_ENGLISH.md) for all technical prose and review
output.

Use these prerequisites before you calculate the score:

1. Apply the [shared review contract](common.md).
2. Complete the architecture pre-score gate.
3. Treat a material architecture violation as a blocker.
4. Follow repository guidance and applicable language routing before generic criteria.
5. Review every in-scope file.
6. Include every scorecard section, even when the input is a diff.
7. Mark a section not applicable (N/A) only when a repository-surface reason supports that result.
8. Retain the inventory evidence for each N/A result.
9. Exclude an N/A weight from the applicable-weight denominator.
10. Keep a coverage-gap weight in the denominator.
11. Give a coverage gap no unsupported credit.
12. Calculate the score with the shared applicable-weight formula.

Use the linked application profiles in the shared contract for each section. Apply only the catalog
entries that the repository surface activates. If an omitted entry could cause a material coverage
gap, record why that entry is not applicable.

The abbreviation `CI/CD` means continuous integration and continuous delivery. The abbreviation
`API/CLI` means application programming interface and command-line interface.

1. **Structure:**

   - Inspect boundaries, layering, separation of source, tests, documents, and configuration, naming,
     nesting, discoverability, generated content, and duplication.
   - Apply the [architecture and simplicity profile](common.md#architecture-and-simplicity).

2. **Documentation:**

   - Inspect purpose, prerequisites, installation, use, updates, removal, examples, architecture,
     contributing, security, release, rollback, links, ownership, and consistency between code and
     documents.
   - Apply the [architecture and simplicity](common.md#architecture-and-simplicity),
     [errors and reliability](common.md#errors-and-reliability),
     [security, authority, and external writes](common.md#security-authority-and-external-writes), and
     [execution and integrity](common.md#execution-and-integrity) profiles.

3. **Architecture:**

   - Inspect dependency direction, interfaces, configuration, error strategy, state ownership,
     extensibility, architecture decision record (ADR) coverage, KISS, SOLID, modularity, and failure
     boundaries.
   - Treat a material unexplained violation as a blocking finding before you calculate the score.
   - Apply the [architecture and simplicity](common.md#architecture-and-simplicity) and
     [errors and reliability](common.md#errors-and-reliability) profiles.

4. **Source quality:**

   - Inspect readability, cohesion, typing, errors, logging, dead code, magic values, concurrency,
     performance hotspots, complexity, lint and format scope, DRY, and applicable language idioms.
   - Apply the [architecture and simplicity](common.md#architecture-and-simplicity),
     [errors and reliability](common.md#errors-and-reliability), and
     [execution and integrity](common.md#execution-and-integrity) profiles.

5. **Testing:**

   - Inspect observable unit, integration, and end-to-end behavior. Also inspect error paths, boundary
     paths, isolation, concurrency, test-target wiring, regression proof, and proportionate performance
     and load evidence.
   - Apply [behavior-first testing](behavior-first-testing.md).
   - Reject tests of prose, counts, implementation layout, or unstable ambient conditions.
   - Apply the [testing and evidence](common.md#testing-and-evidence) and
     [errors and reliability](common.md#errors-and-reliability) profiles.

6. **CI/CD:**

   - Inspect required pull request and main-branch gates, reproducible builds,
     installation, test, security, and package stages, immutable actions, permissions, caching, artifacts,
     environments, promotion, deployment strategy, release provenance, tested rollback, and live
     ruleset enforcement.
   - Apply the [testing and evidence](common.md#testing-and-evidence),
     [errors and reliability](common.md#errors-and-reliability),
     [security, authority, and external writes](common.md#security-authority-and-external-writes), and
     [execution and integrity](common.md#execution-and-integrity) profiles.

7. **Dependencies:**

   - Inspect correct identities, bounded versions, lock integrity, separation of development and runtime,
     licenses, vulnerability analysis, software bill of materials (SBOM), update automation, and
     unused-dependency removal.
   - Apply the [architecture and simplicity](common.md#architecture-and-simplicity),
     [security, authority, and external writes](common.md#security-authority-and-external-writes), and
     [execution and integrity](common.md#execution-and-integrity) profiles.

8. **Security:**

   - Inspect secrets and personally identifiable information (PII), validation,
     injection and deserialization, authentication and authorization, transport layer security (TLS),
     encryption, rate limits, audit logging, least privilege, containers, and the supply chain.
   - Apply the [errors and reliability](common.md#errors-and-reliability),
     [security, authority, and external writes](common.md#security-authority-and-external-writes), and
     [execution and integrity](common.md#execution-and-integrity) profiles.

9. **Reliability:**

   - Inspect fail-closed behavior, partial failure, retries, timeouts, idempotency, health checks,
     readiness checks, graceful shutdown, backup and restore, disaster recovery, failure injection,
     rollback, resource bounds, observability, service level objectives (SLOs), and error budgets when
     they apply.
   - Apply the [testing and evidence](common.md#testing-and-evidence),
     [errors and reliability](common.md#errors-and-reliability), and
     [execution and integrity](common.md#execution-and-integrity) profiles.

10. **Planning:**

    - Inspect issue and pull request templates, roadmap, priorities, definition of done, review rules,
      branch and release process, ownership, debt tracking, and evidence of maintained plans.
    - Apply the [execution and integrity profile](common.md#execution-and-integrity) and the applicable
      [architecture and simplicity](common.md#architecture-and-simplicity) entries.

11. **Agent tooling:**

    - Inspect AGENTS and host pointers, skills, model context protocol (MCP) tools, hooks, configuration,
      prompt templates, portability, permission and external-write boundaries, human gates,
      context and memory, and fallbacks.
    - Apply the [architecture and simplicity](common.md#architecture-and-simplicity),
      [errors and reliability](common.md#errors-and-reliability),
      [security, authority, and external writes](common.md#security-authority-and-external-writes), and
      [execution and integrity](common.md#execution-and-integrity) profiles.

12. **Packaging:**

    - Inspect the artifact allowlist, deterministic output, installation, upgrade, removal, versioning,
      signatures, checksums, release automation, artifact tests, and applicable compatibility.
    - Apply the [architecture and simplicity](common.md#architecture-and-simplicity),
      [testing and evidence](common.md#testing-and-evidence),
      [errors and reliability](common.md#errors-and-reliability),
      [security, authority, and external writes](common.md#security-authority-and-external-writes), and
      [execution and integrity](common.md#execution-and-integrity) profiles.

13. **Developer experience:**

    - Inspect one-command bootstrap, one-command checks, locked tools, the task runner, fast feedback,
      editor support, debug support, hot-reload support, scaffolding, local and CI parity, and actionable
      failures.
    - Apply the [architecture and simplicity](common.md#architecture-and-simplicity),
      [errors and reliability](common.md#errors-and-reliability), and
      [execution and integrity](common.md#execution-and-integrity) profiles.

14. **API/CLI:**

    - Inspect naming, schemas, validation, error contracts, versioning, authentication, idempotency,
      pagination, protocol semantics, examples, and discoverability.
    - Apply the [architecture and simplicity](common.md#architecture-and-simplicity),
      [errors and reliability](common.md#errors-and-reliability), and
      [security, authority, and external writes](common.md#security-authority-and-external-writes)
      profiles.

15. **Governance:**

    - Inspect license, attribution, conduct, security disclosure, ownership, audit trail,
      accessibility, internationalization, privacy, retention, and third-party service level agreement
      (SLA) obligations.
    - Apply the [architecture and simplicity](common.md#architecture-and-simplicity),
      [errors and reliability](common.md#errors-and-reliability),
      [security, authority, and external writes](common.md#security-authority-and-external-writes), and
      [execution and integrity](common.md#execution-and-integrity) profiles.

For each section, record the inventory evidence, commands that you ran, earned points, findings, N/A
reasons, and coverage gaps. If a failed or sampled section is available, run it again. Do not mark it
complete before that run.
