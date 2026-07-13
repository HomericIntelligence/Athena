# Contributing to Athena

Thanks for your interest in Athena. The repository is a **plugin and skill
distribution** repo — the host-side surface of AI agents. Most contribution
is in the form of new skills, marketplace entries, or background assets.

## Quick links

- [AGENTS.md](AGENTS.md) — AI-agent behavioural contract (authoritative for
  automated commits)
- [CLAUDE.md](CLAUDE.md) — Project conventions for AI agents in this repo
- [ADR 0001](docs/adr/0001-plugin-distro-scope-policy.md) — Why Athena does
  not own library code
- [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) — The
  catalogue Athena advertises

## Adding a skill

1. **File a tracking issue** describing the use-case the skill serves. Include
   one or two example invocations and the shape of the result the user wants.
   The issue number goes into your branch name and PR title.

2. **Create the branch.** Branch names follow
   `<scope>/<issue-number>-<slug>` — for example,
   `skills/12-verification`. Create from `main`:

   ```bash
   git fetch origin main
   git checkout -b skills/12-verification origin/main
   ```

3. **Author `skills/<name>/SKILL.md`.** Follow the frontmatter + body-section
   contract documented in [CLAUDE.md](CLAUDE.md#authoring-a-skill). Frontmatter
   must declare `description` (one-line) and `allowed-tools` (default empty).

4. **Add the skill to `.claude-plugin/marketplace.json`** under `plugins`. The
   `name` field MUST match the `skills/<name>/` folder. The `description` is
   what users see in the marketplace picker — be specific.

5. **Run `just check` locally before pushing.** If the gate fails on `lint`,
   `format-check`, `typecheck`, or `test`, your PR will not be mergeable.

6. **Push and open the PR.**

   ```bash
   git push -u origin skills/12-verification
   gh pr create --repo HomericIntelligence/Athena \
     --title "skills: add <skill-name> (#<issue>)" \
     --body "Closes #<issue>"
   ```

   Do not arm auto-merge. Athena is a cross-repo dependency of Odysseus; the
   operator signs off on the resulting `.gitmodules` SHA bump once the PR
   merges.

## Style guide

- **Markdown.** Run `markdownlint` before committing. `.markdownlint.yaml`
  disables `MD013` (line length) because skill bodies contain embedded prompts
  with long natural-language lines.
- **Python.** `ruff format`, `ruff check`. The configuration in
  `pyproject.toml [tool.ruff]` is the single source of truth.
- **Commit messages.** `<type>(<scope>): <short summary>` — wrap at 100.

## What we will reject

- PRs that touch `hephaestus/` files (boundary enforced on library side; we do
  not own the namespace here).
- PRs that bump the Hephaestus pin in `pyproject.toml` without a coordination
  comment in the PR body referencing the cross-repo integration issue.
- Skills that promise capabilities the upstream library does not have.
- Logs, metrics, or test-output files committed to a PR — these are not
  evidence (see [Odysseus ADR-014](https://github.com/HomericIntelligence/Odysseus/blob/main/docs/adr/014-runnable-evidence-for-metric-claims.md)).

## Release process

Athena follows the same tagged-release model as Hephaestus. The bump is
coordinated through the Odysseus myrmidon pipeline. See
[`docs/release-notes/`](docs/release-notes/) for the most recent changes.
