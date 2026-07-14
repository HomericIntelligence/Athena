# Development and delivery policy

## Git

- `main` is protected. All changes go through short-lived feature branches and pull requests.
- Use Conventional Commit subjects.
- Every commit must be cryptographically signed and include a DCO `Signed-off-by` trailer.
- Never use `--no-verify` or force-push. Fix the underlying problem.
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
- Apply KISS, YAGNI, TDD, DRY, SOLID, modularity, and least astonishment.

## Human review required

Require explicit human review for workflow or required-check changes, accepted-ADR supersession,
release/publishing changes, dependency trust-boundary changes, ambiguous desired state, and any
request to weaken permissions or validation.
