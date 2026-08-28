# Development and delivery policy

## Technical English

Apply the [ASD-STE100 technical-English policy](../../skills/TECHNICAL_ENGLISH.md) to all English technical
prose in this document. Do not remove or weaken a technical, safety, security, evidence, permission,
or failure requirement to make text shorter.

## Git

- `main` is protected. Send all changes through short-lived feature branches and pull requests.
- Use Conventional Commit subjects.
- Sign each commit cryptographically. Include a Developer Certificate of Origin (DCO)
  `Signed-off-by` trailer.
- Do not use `--no-verify`.
- Do not use an unguarded force-push.
- If a workflow requires rewritten history, you can update a feature branch with
  `--force-with-lease --force-if-includes`.
- Never force-push a protected branch or a default branch.
- Stage intentional paths. Do not include unrelated user changes in a commit.
- Accepted architecture decision records (ADRs) are append-only. To change an accepted decision,
  write a new ADR that links to the prior decision.

## Pull requests

- Target `main`.
- Keep the scope aligned with one issue or one coherent maintenance objective.
- If an issue tracks the work, put `Closes #N` on its own line in the body.
- Run required checks against the current head revision. The checks must be successful, current, and
  not incorrectly skipped.
- Do not say that a check passed in the PR description unless the description can cite the current
  head receipt that supports the claim.
- Before auto-merge or merge, get an independent strict review.
- Use a merge method that the repository supports. Do not guess or impose an organization-wide
  fallback.

## Safety

- Never commit credentials, tokens, `.env` files, private keys, or personal data.
- Get explicit user authority before a filesystem-destructive command or before you discard changes.
- Never use `git reset --hard`.
- You can use constructive Git, GitHub command-line interface (CLI), and Hephaestus operations when
  both conditions are true:

  - The requested task permits the operation.
  - The repository contract permits the operation.

- For branch and worktree cleanup, prefer guarded Hephaestus tools.
- Preserve unrelated worktree changes. If safe isolation is not possible, stop.
- Never bypass a failed validation, security, review, or policy gate.
- Apply the canonical [engineering principles](../principles/README.md) as decision rules. Select only
  the principles that apply to the change. For routine Athena development, use these groups:

  - Bind scope and design choices to [P001](../principles/README.md#p001),
    [P002](../principles/README.md#p002), and [P010](../principles/README.md#p010).
  - Keep one authority and one state owner under [P003](../principles/README.md#p003) and
    [P078](../principles/README.md#p078).
  - Follow the established architecture and contracts under
    [P004](../principles/README.md#p004), [P005](../principles/README.md#p005),
    [P006](../principles/README.md#p006), [P015](../principles/README.md#p015), and
    [P019](../principles/README.md#p019).
  - Verify changed behavior under [P022](../principles/README.md#p022),
    [P026](../principles/README.md#p026), [P064](../principles/README.md#p064),
    [P065](../principles/README.md#p065), and [P091](../principles/README.md#p091).

- Repository, security, evidence, user, and system contracts take precedence over a general
  principle. A principle never grants authority. It never expands the requested scope or weakens a
  stricter safety or validation rule.

## Durable-artifact and test policy

- Create or change an artifact only when it has one or more of these direct purposes:

  - implement the repository product;
  - verify the repository product;
  - distribute the repository product;
  - operate the repository product;
  - secure the repository product; or
  - explain the repository product.

- Do not generate documents or unrelated files only to make the repository appear complete.
- Do not introduce these manually maintained artifacts when source discovery or an existing
  authority can give the information:

  - changelogs;
  - generated documents;
  - duplicated catalogs;
  - registries;
  - inventories;
  - counts; or
  - file lists.

- Add such an artifact only when a current consumer requires it. The owner and update method must be
  explicit.
- Use this sequence for each change: remove, reuse, consolidate, simplify, then add. Add only when
  the earlier choices cannot meet the requirement.
- Tests must verify computable behavior, data contracts, security properties, or executable artifact
  structure.
- Do not test prose wording, headings, paragraph presence, document counts, or duplicated text
  strings.
- Markdown lint and link checks can verify document syntax and link resolution. They must not freeze
  editorial content.
- Prefer stable public outcomes to these types of assertions:

  - implementation-detail assertions;
  - snapshot assertions;
  - timing assertions;
  - network assertions;
  - ambient-environment assertions; or
  - ordering assertions.

- A test must fail for the product defect that it claims to find.
- For document-only changes, use the existing Markdown lint and link checks. Do not create a new test
  harness or application code only to test documents.

## Human review routing

Human review and Code Owner review are optional for Athena changes. They are not required.
`CODEOWNERS` records advisory ownership. The baseline ruleset does not require an approval count or a
Code Owner approval. Workflow, release, dependency, and security-control changes remain subject to
the required checks and requested-scope boundaries of the repository.
