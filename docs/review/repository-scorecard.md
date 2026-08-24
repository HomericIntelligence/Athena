# Repository review scorecard

**Why:** A repository review needs a complete, architecture-first inventory so a strong area cannot hide
an unsafe boundary or an unreviewed surface.

Apply the [shared review contract](common.md) before scoring: architecture is a blocking pre-score gate,
and repository guidance plus applicable language routing override generic criteria. Review every in-scope
file; a diff never omits a scorecard section. Mark a section N/A only with a concrete repository-surface
reason and retain inventory evidence. N/A is excluded from the applicable-weight denominator; a coverage
gap remains applicable and earns no unsupported credit. Calculate the score with the shared
applicable-weight formula.

Each section routes through the linked application profiles in the shared contract. Apply only the
catalog entries activated by the repository surface and record why another entry is not applicable
when that omission would otherwise leave a material coverage gap.

1. **Structure:** boundaries, layering, source/test/docs/config separation, naming, nesting,
   discoverability, generated content, and duplication. Apply the
   [architecture and simplicity profile](common.md#architecture-and-simplicity).
2. **Documentation:** purpose, prerequisites, install/use/update/removal, examples, architecture,
   contributing, security, release, rollback, links, ownership, and code/doc consistency. Apply the
   [architecture and simplicity](common.md#architecture-and-simplicity),
   [errors and reliability](common.md#errors-and-reliability),
   [security, authority, and external writes](common.md#security-authority-and-external-writes), and
   [execution and integrity](common.md#execution-and-integrity) profiles.
3. **Architecture:** dependency direction, interfaces, configuration, error strategy, state ownership,
   extensibility, ADR coverage, KISS, SOLID, modularity, and failure boundaries. A material unexplained
   violation is a blocking finding before scoring. Apply the
   [architecture and simplicity](common.md#architecture-and-simplicity) and
   [errors and reliability](common.md#errors-and-reliability) profiles.
4. **Source quality:** readability, cohesion, typing, errors, logging, dead code, magic values,
   concurrency, performance hotspots, complexity, lint/format scope, DRY, and applicable language
   idioms. Apply the
   [architecture and simplicity](common.md#architecture-and-simplicity),
   [errors and reliability](common.md#errors-and-reliability), and
   [execution and integrity](common.md#execution-and-integrity) profiles.
5. **Testing:** observable unit/integration/end-to-end behavior, error and boundary paths, isolation,
   concurrency, test-target wiring, regression proof, and proportionate performance/load evidence. Apply
   [behavior-first testing](behavior-first-testing.md); reject prose, counts, implementation layout, or
   flaky ambient-condition tests. Apply the
   [testing and evidence](common.md#testing-and-evidence) and
   [errors and reliability](common.md#errors-and-reliability) profiles.
6. **CI/CD:** required PR/main gates, reproducible builds, install/test/security/package stages,
   immutable actions, permissions, caching, artifacts, environments, promotion, deployment strategy,
   release provenance, tested rollback, and live ruleset enforcement. Apply the
   [testing and evidence](common.md#testing-and-evidence),
   [errors and reliability](common.md#errors-and-reliability),
   [security, authority, and external writes](common.md#security-authority-and-external-writes), and
   [execution and integrity](common.md#execution-and-integrity) profiles.
7. **Dependencies:** correct identities, bounded versions, lock integrity, dev/runtime separation,
   licenses, vulnerability analysis, SBOM, update automation, and unused-dependency removal. Apply the
   [architecture and simplicity](common.md#architecture-and-simplicity),
   [security, authority, and external writes](common.md#security-authority-and-external-writes), and
   [execution and integrity](common.md#execution-and-integrity) profiles.
8. **Security:** secrets/PII, validation, injection/deserialization, authentication/authorization, TLS,
   encryption, rate limits, audit logging, least privilege, containers, and supply chain. Apply the
   [errors and reliability](common.md#errors-and-reliability),
   [security, authority, and external writes](common.md#security-authority-and-external-writes), and
   [execution and integrity](common.md#execution-and-integrity) profiles.
9. **Reliability:** fail-closed behavior, partial failure, retries, timeouts, idempotency, health and
   readiness checks, graceful shutdown, backup/restore, disaster recovery, failure injection, rollback,
   resource bounds, observability, SLOs, and error budgets where applicable. Apply the
   [testing and evidence](common.md#testing-and-evidence),
   [errors and reliability](common.md#errors-and-reliability), and
   [execution and integrity](common.md#execution-and-integrity) profiles.
10. **Planning:** issue/PR templates, roadmap, priorities, definition of done, review rules, branch and
    release process, ownership, debt tracking, and evidence of maintained plans. Apply the
    [execution and integrity profile](common.md#execution-and-integrity) plus the applicable
    [architecture and simplicity](common.md#architecture-and-simplicity) entries.
11. **Agent tooling:** AGENTS/host pointers, skills, MCP/hooks/configuration, prompt templates,
    portability, permission and external-write boundaries, human gates, context/memory, and fallbacks.
    Apply the
    [architecture and simplicity](common.md#architecture-and-simplicity),
    [errors and reliability](common.md#errors-and-reliability),
    [security, authority, and external writes](common.md#security-authority-and-external-writes), and
    [execution and integrity](common.md#execution-and-integrity) profiles.
12. **Packaging:** artifact allowlist, deterministic output, install/upgrade/removal, versioning,
    signatures/checksums, release automation, artifact tests, and applicable compatibility. Apply the
    [architecture and simplicity](common.md#architecture-and-simplicity),
    [testing and evidence](common.md#testing-and-evidence),
    [errors and reliability](common.md#errors-and-reliability),
    [security, authority, and external writes](common.md#security-authority-and-external-writes), and
    [execution and integrity](common.md#execution-and-integrity) profiles.
13. **Developer experience:** one-command bootstrap/checks, locked tools, task runner, fast feedback,
    editor/debug/hot-reload support, scaffolding, local/CI parity, and actionable failures. Apply the
    [architecture and simplicity](common.md#architecture-and-simplicity),
    [errors and reliability](common.md#errors-and-reliability), and
    [execution and integrity](common.md#execution-and-integrity) profiles.
14. **API/CLI:** naming, schemas, validation, error contracts, versioning, authentication, idempotency,
    pagination, protocol semantics, examples, and discoverability. Apply the
    [architecture and simplicity](common.md#architecture-and-simplicity),
    [errors and reliability](common.md#errors-and-reliability), and
    [security, authority, and external writes](common.md#security-authority-and-external-writes)
    profiles.
15. **Governance:** license, attribution, conduct, security disclosure, ownership, audit trail,
    accessibility, internationalization, privacy, retention, and third-party SLA obligations. Apply
    the [architecture and simplicity](common.md#architecture-and-simplicity),
    [errors and reliability](common.md#errors-and-reliability),
    [security, authority, and external writes](common.md#security-authority-and-external-writes), and
    [execution and integrity](common.md#execution-and-integrity) profiles.

For every section, record inventory evidence, commands actually run, earned points, findings, N/A reasons,
and coverage gaps. Re-run an available failed or sampled section rather than treating it as complete.
