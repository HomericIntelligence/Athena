# Comprehensive repository-review criteria

Apply every applicable item within the corresponding scored section. N/A requires concrete evidence.

1. **Structure:** boundaries, layering, source/test/docs/config separation, naming, nesting,
   discoverability, generated content, and duplication.
2. **Documentation:** purpose, prerequisites, install/use/update/removal, examples, architecture,
   contributing, security, release, rollback, links, ownership, and code/doc consistency.
3. **Architecture:** dependency direction, interfaces, configuration, error strategy, state ownership,
   extensibility, ADR coverage, KISS, SOLID, modularity, and failure boundaries.
4. **Source quality:** readability, cohesion, typing, errors, logging, dead code, magic values,
   concurrency, performance hotspots, complexity, lint/format scope, DRY, and idioms.
5. **Testing:** unit/integration/end-to-end behavior, error and boundary paths, isolation, concurrency,
   coverage by module, disabled tests, snapshots, test data, performance/load tests where applicable,
   and regression-test proof. Reject tests that pin prose wording, headings, documentation counts,
   or flaky implementation details instead of computable behavior.
6. **CI/CD:** required PR/main gates, reproducible builds, install/test/security/package stages,
   immutable actions, permissions, caching, artifacts, environments, promotion, deployment strategy,
   release provenance, tested rollback, and live ruleset enforcement.
7. **Dependencies:** correct identities, bounded versions, lock integrity, dev/runtime separation,
   licenses, vulnerability analysis, SBOM, update automation, and removal of unused dependencies.
8. **Security:** secrets/PII, validation, injection/deserialization, authentication/authorization,
   TLS, encryption, OWASP, rate limits, audit logging, least privilege, containers, and supply chain.
9. **Reliability:** fail-closed behavior, partial failure, retries, timeouts, idempotency, health and
   readiness checks, graceful shutdown, backup/restore, disaster recovery, failure injection,
   rollback, resource bounds, observability, SLOs, and error budgets where applicable.
10. **Planning:** issue/PR templates, roadmap, priorities, definition of done, review rules, branch and
    release process, ownership, debt tracking, and evidence of maintained plans.
11. **Agent tooling:** AGENTS/host pointers, skills, MCP/hooks/configuration, prompt templates,
    portability, permission and external-write boundaries, human gates, context/memory, and fallbacks.
12. **Packaging:** artifact allowlist, deterministic output, install/upgrade/removal, versioning,
    signatures/checksums, release automation, artifact tests, and applicable compatibility.
13. **Developer experience:** one-command bootstrap/checks, locked tools, task runner, fast feedback,
    editor/debug/hot-reload support, scaffolding, local/CI parity, and actionable failures.
14. **API/CLI:** naming, schemas, validation, error contracts, versioning, authentication,
    idempotency, pagination, HTTP semantics, OpenAPI/SDKs, examples, and discoverability.
15. **Governance:** license, attribution, conduct, security disclosure, ownership, audit trail,
    accessibility, internationalization, privacy, retention, and third-party SLA obligations.

Across all sections, require evidence for KISS, YAGNI, TDD, DRY, SOLID, modularity, and least
astonishment. Flag manually synchronized changelogs, generated documentation, duplicated catalogs,
registries, inventories, counts, or unrelated files unless a current product consumer requires the
artifact and its update mechanism is stable and explicit.

For each section, record evidence read, commands run, earned points, findings, missing criteria,
N/A reasons, and coverage gaps. Retry failed or sampled reviewers before final scoring.
