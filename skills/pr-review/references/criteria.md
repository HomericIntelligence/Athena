# Pull-request review criteria

Apply every applicable item. Mark an item N/A only with a product-specific reason and evidence.

## Requirements and prior work

- Verify standalone issue closure syntax, every acceptance criterion, definition of done, title, and
  body against the actual change.
- Search issue comments, current-base source, default-branch commits, and all-state pull requests for
  already-landed, superseded, duplicate, or zombie work.
- Map every change to stated scope and identify silent additions or reductions.
- Reconcile proposed follow-up issues against the open backlog before recommending a new issue.

## Architecture and implementation

- Check repository guidance, ADRs, module boundaries, dependency direction, naming, placement,
  public contracts, and documentation against code ground truth.
- Check correctness, readability, typing, null/empty/boundary handling, error propagation, logging,
  hardcoded state, dead code, complexity, KISS, YAGNI, TDD, DRY, SOLID, modularity, portability,
  least astonishment, and surprising side effects.

## Tests and evidence

- Require behavior coverage for each new or changed path and a regression test for each bug fix.
- Check error and boundary cases, isolation, order independence, concurrency where relevant, skipped
  tests with tracking issues, justified behavioral snapshots, meaningful assertions, and test
  location. Reject tests that pin prose wording, headings, documentation counts, or flaky
  implementation details instead of computable behavior.
- Run repository-defined validation, tests, lint, formatting, type checking, build, and packaging.
  Bind results to the reviewed head revision and distinguish stale or incorrectly skipped checks.

## Security and operational safety

- Check secrets and PII, input and path validation, command injection, deserialization, authentication
  and authorization, least privilege, OWASP risks where applicable, dependency vulnerabilities,
  container capabilities, transactions/idempotency, rate limits, health checks, and graceful failure.
- Check destructive actions, external writes, publishing, rollback, recovery, and human approval
  gates against the repository contract.

## Integration and hygiene

- Use author-intent and current-base diffs; verify behind count, conflicts, landed work, and current-
  head CI.
- Check hook bypasses, commit signatures, DCO, commit convention, lockfiles, vendored/generated
  artifacts, dependency changes, single-purpose scope, release handoff, and applicable compatibility.
- Reject manual changelogs, generated documentation, duplicated catalogs, registries, inventories,
  counts, or unrelated files unless a current product consumer requires them and the update
  mechanism is stable and explicit.
- Read every changed file, linked issue, cited ADR, and public contract. Retry failed or sampled
  dimension reviews before calculating a score.
