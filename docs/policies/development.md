# Development and delivery policy

## Git

- `main` is protected. All changes go through short-lived feature branches and pull requests.
- Use Conventional Commit subjects.
- Every commit must be cryptographically signed and include a DCO `Signed-off-by` trailer.
- Never use `--no-verify` or an unguarded force-push. A feature branch may be updated with
  `--force-with-lease --force-if-includes` when the workflow requires rewritten history. Never
  force-push a protected or default branch.
- Stage intentional paths; do not sweep unrelated user changes into a commit.
- Accepted ADRs are append-only. Supersede one with a new ADR that links to the prior decision.

## Pull requests

- Target `main` and keep scope aligned with one issue or coherent maintenance objective.
- When tracked by an issue, the body contains `Closes #N` on its own line.
- Required checks run against the current head revision and must be successful, not stale or
  incorrectly skipped.
- Auto-merge and merge actions require an independent strict review and the repository-supported
  merge method.
- Use a repository-supported merge method; do not guess or impose an organization-wide fallback.

## Safety

- Never commit credentials, tokens, `.env` files, private keys, or personal data.
- Filesystem-destructive commands and discarding changes require explicit user authority. `git
  reset --hard` is prohibited. Treat constructive Git, GitHub CLI, and Hephaestus operations as
  in-scope when the requested task and repository contract permit them; prefer guarded Hephaestus
  tooling for branch and worktree cleanup.
- Preserve unrelated worktree changes. Stop when safe isolation is not possible.
- Never bypass a failing validation, security, review, or policy gate.
- Apply the canonical [engineering principles](../principles/README.md) as decision rules, selecting
  only those relevant to the change. For routine Athena development, bind scope and design choices to
  [P001](../principles/README.md#p001), [P002](../principles/README.md#p002), and
  [P010](../principles/README.md#p010); keep authority and state ownership singular under
  [P003](../principles/README.md#p003) and [P078](../principles/README.md#p078); follow the established
  architecture and contracts under [P004](../principles/README.md#p004),
  [P005](../principles/README.md#p005), [P006](../principles/README.md#p006),
  [P015](../principles/README.md#p015), and [P019](../principles/README.md#p019); and verify changed
  behavior under [P022](../principles/README.md#p022), [P026](../principles/README.md#p026),
  [P064](../principles/README.md#p064), [P065](../principles/README.md#p065), and
  [P091](../principles/README.md#p091).
- Repository, security, evidence, user, and system contracts take precedence over a general
  principle. A principle never grants authority, expands requested scope, or weakens a stricter
  safety or validation rule.

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

Human and Code Owner review are optional, not required, for Athena changes. CODEOWNERS records
advisory ownership; the baseline ruleset intentionally requires neither an approval count nor a
Code Owner approval. Workflow, release, dependency, and security-control changes remain subject to
the repository's required checks and requested-scope boundaries.
