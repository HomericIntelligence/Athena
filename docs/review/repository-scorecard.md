# Repository review scorecard

This scorecard is the authoritative inventory for `repo-review`. Apply the
[shared review contract](common.md) before scoring: architecture is a blocking
pre-score gate, and repository guidance plus applicable language routing take
precedence over generic criteria.

Repository review has full-inventory coverage. It does not use a diff to omit a
section. A section can be N/A only when the repository's actual surfaces give a
concrete reason; report that reason and retain the inventory evidence.
Calculate the weighted score with the shared contract's applicable-weight
formula; an N/A section is excluded from the denominator, while a coverage gap
remains applicable and receives no unsupported credit.

1. **Structure:** boundaries, layering, source/test/docs/config separation,
   naming, nesting, discoverability, generated content, and duplication.
2. **Documentation:** purpose, prerequisites, install/use/update/removal,
   examples, architecture, contributing, security, release, rollback, links,
   ownership, and code/doc consistency.
3. **Architecture:** dependency direction, interfaces, configuration, error
   strategy, state ownership, extensibility, ADR coverage, KISS, SOLID,
   modularity, and failure boundaries. A material unexplained violation is a
   blocking finding before scoring.
4. **Source quality:** readability, cohesion, typing, errors, logging, dead
   code, magic values, concurrency, performance hotspots, complexity,
   lint/format scope, DRY, and applicable language idioms.
5. **Testing:** observable unit/integration/end-to-end behavior, error and
   boundary paths, isolation, concurrency, test-target wiring, regression
   proof, and proportionate performance/load evidence. Apply
   [behavior-first testing](behavior-first-testing.md); reject tests that pin
   prose, counts, implementation layout, or flaky ambient conditions.
6. **CI/CD:** required PR/main gates, reproducible builds,
   install/test/security/package stages, immutable actions, permissions,
   caching, artifacts, environments, promotion, deployment strategy, release
   provenance, tested rollback, and live ruleset enforcement.
7. **Dependencies:** correct identities, bounded versions, lock integrity,
   dev/runtime separation, licenses, vulnerability analysis, SBOM, update
   automation, and removal of unused dependencies.
8. **Security:** secrets/PII, validation, injection/deserialization,
   authentication/authorization, TLS, encryption, rate limits, audit logging,
   least privilege, containers, and supply chain.
9. **Reliability:** fail-closed behavior, partial failure, retries, timeouts,
   idempotency, health and readiness checks, graceful shutdown, backup/restore,
   disaster recovery, failure injection, rollback, resource bounds,
   observability, SLOs, and error budgets where applicable.
10. **Planning:** issue/PR templates, roadmap, priorities, definition of done,
    review rules, branch and release process, ownership, debt tracking, and
    evidence of maintained plans.
11. **Agent tooling:** AGENTS/host pointers, skills, MCP/hooks/configuration,
    prompt templates, portability, permission and external-write boundaries,
    human gates, context/memory, and fallbacks.
12. **Packaging:** artifact allowlist, deterministic output,
    install/upgrade/removal, versioning, signatures/checksums, release
    automation, artifact tests, and applicable compatibility.
13. **Developer experience:** one-command bootstrap/checks, locked tools, task
    runner, fast feedback, editor/debug/hot-reload support, scaffolding,
    local/CI parity, and actionable failures.
14. **API/CLI:** naming, schemas, validation, error contracts, versioning,
    authentication, idempotency, pagination, protocol semantics, examples, and
    discoverability.
15. **Governance:** license, attribution, conduct, security disclosure,
    ownership, audit trail, accessibility, internationalization, privacy,
    retention, and third-party SLA obligations.

For every section, record inventory evidence, commands actually run, earned
points, findings, N/A reasons, and coverage gaps. Re-run an available failed or
sampled review section rather than treating it as complete.
