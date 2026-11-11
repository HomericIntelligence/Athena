# Development and delivery policy

## Technical English

Apply the [ASD-STE100 technical-English policy](../../skills/TECHNICAL_ENGLISH.md) to all English
technical prose in this document. Keep technical, safety, and security requirements when you
shorten text.

Use the [autonomous workflow policy](autonomous-workflows.md) for recovery and continuation.

## Git

- `main` is a protected branch. Short-lived feature branches and pull requests are the usual path
  for changes.
- Before you start feature work, fetch `origin/main`. Create the isolated worktree and feature
  branch at that exact commit. Record the commit as the worktree start commit and initial review
  base.
- After work starts, a rebase because `main` moved or because the branch is behind rarely helps.
  Rebase when required content from `main` blocks the work, or after the work is complete when
  the forge reports a merge conflict to resolve.
- A configured merge queue owns normal target integration and merge-group validation. A branch that
  is behind but has no reported merge conflict does not gain anything from an agent rebase.
- Use Conventional Commit subjects.
- Signed commits with a Developer Certificate of Origin (DCO) `Signed-off-by` trailer make the
  history easier to audit and are the preferred convention.
- Keep `--no-verify` on the shelf; let hooks run where they can.
- Prefer `--force-with-lease` over an unguarded force push.
- If a workflow needs rewritten history, updating a feature branch with
  `--force-with-lease --force-if-includes` is the polite option.
- Protected branches and default branches stay free of force pushes.
- Stage intentional paths. Aim to leave unrelated user changes out of a commit.
- Accepted architecture decision records (ADRs) stay append-only. Changing an accepted decision
  means writing a new ADR that links to the prior decision.

## Pull requests

- Target `main` by default. For dependent knowledge changes, use a documented PR stack that
  preserves each existing change.
- Keep the scope aligned with one issue or one coherent maintenance objective.
- You can publish a pull request before validation finishes. Report pending, failed, and
  unavailable checks accurately. Publication does not establish completion or merge readiness.
- Run each new or changed test with a focused command on a local or hosted runner. Seeing the
  command select that test keeps the run honest. A passing run is the aim before completion or
  merge.
- Continuous integration and continuous delivery (CI/CD) workflows, not pre-commit, run the
  automatic pytest tiers. Focused local validation complements those tiers.
- If an issue tracks the work, put `Closes #N` on its own line in the body.
- Prefer running the applicable checks against the current head revision. Successful, current
  results, without skips, give the clearest picture of the change.
- A check-passed claim reads best when the PR description can cite the current head receipt that
  supports the claim.
- Independent review before auto-merge or merge is always welcome. If it is unavailable, finish
  preparation and report what is missing.
- Use a merge method that the repository supports. Imposing an organization-wide fallback rarely
  helps.

## Safety

- Never commit credentials, tokens, `.env` files, private keys, or personal data.
- Use existing explicit cleanup authority for verified merged branches and clean worktrees with no
  unique work. Destructive actions and discarded changes go best with explicit authority.
- `git reset --hard` discards uncommitted work and is best avoided.
- Constructive Git, GitHub command-line interface (CLI), and Hephaestus operations work well
  within the scope of the requested task and a branch and worktree that fit the task.

- For branch and worktree cleanup, prefer guarded Hephaestus tools.
- Preserve unrelated worktree changes. Integrate compatible edits; conflicting writes are the ones
  to withhold.
- A failed validation, security, or review signal deserves an accurate report; working around the
  signal defeats its purpose.
- Apply the canonical [engineering principles](../principles/README.md) as decision rules. Select
  only the principles that apply to the change. For routine Athena development, use these groups:

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

- Safety and security constraints take precedence over a general principle. A principle grants
  no authority by itself and does not expand the requested scope.

## Durable-artifact and test policy

- Create or change an artifact when it has one or more of these direct purposes:

  - implement the repository product;
  - verify the repository product;
  - distribute the repository product;
  - operate the repository product;
  - secure the repository product; or
  - explain the repository product.

- Avoid documents or unrelated files created only to make the repository appear complete.
- Avoid these manually maintained artifacts when source discovery or an existing tool can give
  the information:

  - changelogs;
  - generated documents;
  - duplicated catalogs;
  - registries;
  - inventories;
  - counts; or
  - file lists.

- Add such an artifact when a current consumer needs it. The owner and update method work
  best when they are explicit.
- The marked development-principles block in root `AGENTS.md` is generated data that the fleet
  agent-contract validator consumes. `docs/principles/README.md` owns its content. The
  agent-contract renderer owns its update method. Update the block through the renderer rather
  than by hand.
- Use this sequence for each change: remove, reuse, consolidate, simplify, then add. Add when
  the earlier choices cannot meet the requirement.
- Tests can best verify computable behavior, data contracts, security properties, or executable
  artifact structure.
- Avoid testing prose wording, headings, paragraph presence, document counts, or duplicated text
  strings.
- Exact machine-consumed fields are data contracts, not editorial prose. This exception includes
  the root `CLAUDE.md` pointer and the generated development-principles block.
- Markdown lint and link checks can verify document syntax and link resolution. Editorial content
  stays free to change.
- Prefer stable public outcomes to these types of assertions:

  - implementation-detail assertions;
  - snapshot assertions;
  - timing assertions;
  - network assertions;
  - ambient-environment assertions; or
  - ordering assertions.

- A test can ideally fail for the product defect it targets.
- For document-only changes, the existing Markdown lint and link checks are the right fit.

## Human review routing

Human review and Code Owner review are optional for Athena changes. `CODEOWNERS` records advisory
ownership. Workflow, release, dependency, and security-control changes benefit from extra care
and a clearly stated scope.
