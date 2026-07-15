# Development and delivery policy

## Git

- `main` is protected. All changes go through short-lived feature branches and pull requests.
- Use Conventional Commit subjects.
- Every commit must be cryptographically signed and include a DCO `Signed-off-by` trailer.
- Never use `--no-verify` or an unguarded force-push. A feature branch may be updated with
  `--force-with-lease --force-if-includes` only when the workflow requires rewritten history and the
  user has explicitly authorized it. Never force-push a protected or default branch.
- Stage intentional paths; do not sweep unrelated user changes into a commit.
- Accepted ADRs are append-only. Supersede one with a new ADR that links to the prior decision.

## Pull requests

- Target `main` and keep scope aligned with one issue or coherent maintenance objective.
- When tracked by an issue, the body contains `Closes #N` on its own line.
- Required checks run against the current head revision and must be successful, not stale or
  incorrectly skipped.
- Auto-merge and merge actions require explicit operator authority and an independent strict review.
- Use a repository-supported merge method; do not guess or impose an organization-wide fallback.

## Safety

- Never commit credentials, tokens, `.env` files, private keys, or personal data.
- Destructive commands, publishing, releases, merges, branch deletion, and external writes require
  the authority stated by the user and repository contract.
- Preserve unrelated worktree changes. Stop when safe isolation is not possible.
- Never bypass a failing validation, security, review, or policy gate.
- Apply these development principles as decision rules:
  - **KISS:** choose the smallest design that satisfies the demonstrated requirement.
  - **YAGNI:** do not add speculative features, abstraction, compatibility, or process artifacts.
  - **TDD:** drive executable behavior changes with a failing behavior test, minimal implementation,
    and refactoring only after green.
  - **DRY:** keep one authoritative implementation or fact; link to it instead of duplicating it.
  - **SOLID and modularity:** keep responsibilities focused, dependencies directed through narrow
    interfaces, and components independently replaceable where the product needs that flexibility.
  - **Principle of least astonishment:** preserve intuitive interfaces, explicit failures, and
    behavior consistent with repository precedent.

## Durable-artifact and test policy

- Create or change an artifact only when it directly implements, verifies, distributes, operates,
  secures, or explains the repository's actual product. Do not generate documentation or unrelated
  files merely to make the repository appear complete.
- Do not introduce manually maintained changelogs, generated documentation, duplicated catalogs,
  registries, inventories, counts, or file lists when source discovery or an existing authority can
  answer the question. Add such an artifact only when a current consumer requires it and ownership
  and update mechanics are explicit.
- Tests assert computable behavior, data contracts, security properties, or executable artifact
  structure. Do not test prose wording, headings, paragraph presence, documentation counts, or
  duplicated text strings. Markdown lint and link checking may validate document syntax and link
  resolution; they must not freeze editorial content.
- Prefer stable public outcomes over implementation-detail, snapshot, timing, network, ambient
  environment, or ordering assertions. A test must fail for the product defect it claims to catch.
- Documentation-only changes use the repository's existing lint and link checks. Do not create a
  new test harness or application code solely to test documentation.

## Human review routing

Request explicit human review for workflow or required-check changes, accepted-ADR supersession,
release/publishing changes, dependency trust-boundary changes, ambiguous desired state, and any
request to weaken permissions or validation. CODEOWNERS routes these requests; the ecosystem
baseline ruleset intentionally does not make an approval count a server-side merge requirement.
