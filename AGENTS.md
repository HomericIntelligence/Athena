# AGENTS.md — Athena

This file is the authoritative contract for each AI coding harness that operates in Athena.
Host-specific files point to this file. They do not copy it.

## Purpose and scope

Athena is a self-contained, host-neutral distribution of workflow skills. It supports Claude Code,
Codex, opencode, and Pi. The product contains the top-level `skills/` corpus, host manifests, and
documentation. Athena does not publish a Python package.

Athena owns:

- `skills/`: the canonical portable skill sources.
- `.claude-plugin/`, `.codex-plugin/`, `.agents/plugins/`, and `npm/athena-opencode/`: host
  metadata.
- `scripts/`: typed repository validation, CI policy, and package tools. These tools are not a
  distributable runtime library.
- `tests/unit/`: behavior tests for repository scripts and skill-local scripts.
- `docs/`, `assets/`, and `.github/`: policy, documentation, media, ownership, and automation.

`skills/` is the only skill source. Do not create a nested plugin mirror or a host-specific copy.
Put runtime repository requirements in the applicable skill descriptions and workflows. Do not put
these requirements in this repository-agent contract.

## Writing standard

Use the [ASD-STE100 writing policy](docs/technical-english.md) for all applicable English technical
prose. This requirement applies to repository directions, skills, shared documents, and prose that a
skill produces. It does not apply to `docs/principles/**` or to the literal-text exceptions in the
policy.

Use the current official issue of ASD-STE100. Do not state that repository checks certify
ASD-STE100 compliance.

## Multi-harness contract

- Express capabilities. Do not require fixed vendor APIs.
- Use the terms coordinator, specialist, executor, skill invocation, and subagent. Do not use
  branded model tiers.
- Use the host default model when tier selection is unavailable.
- Run independent work sequentially when the host cannot delegate.
- Treat invocation syntax as an example. Claude uses `/athena:<skill>`. Codex uses `$<skill>` or
  natural language. opencode uses natural language or its native skill invocation. Pi uses
  `/skill:<skill>`.
- Read `AGENTS.md` for repository guidance. `CLAUDE.md` is only a pointer.
- Use frontmatter tool names to describe required capabilities. Each skill must document a safe
  failure or fallback when a host does not have a required capability.

## Permitted actions

Agents can read repository files and edit files in the user's requested scope. They can run
deterministic validation and create the isolated branches or worktrees that the work needs. They can
also do read-only GitHub inspection when it is relevant.

Always start feature work in an isolated Git worktree. Fetch `origin/main` before you make a change.
Then, create the feature branch at that commit or rebase an existing feature branch onto it. Do not
make feature edits in the primary checkout.

Agents can do constructive Git, GitHub CLI, and Hephaestus operations in the requested scope. These
operations include pushes, pull requests, publishing, releases, merges, deployments, and safe
force-with-lease updates. They do not need an additional approval prompt. External-write scope and
repository policy still apply. Filesystem-destructive commands and discarded changes require
explicit authority.

## Prohibited actions

- Never fabricate logs, metrics, tests, benchmarks, releases, or successful command output.
- Never commit secrets, credentials, private keys, `.env` files, or personal data.
- Never bypass hooks or required checks with `--no-verify`, silent shell fallbacks, or
  `continue-on-error: true`.
- Never run `git reset --hard`.
- Never discard changes without explicit authority. Use the guarded Hephaestus tidy workflow for
  branch and worktree cleanup rather than improvised removal commands.
- Never edit an accepted ADR in place; write a superseding ADR.
- Never overwrite unrelated user changes or silently retarget an existing dependency checkout.

## Evidence and delivery

Follow the local policies:

- [`docs/policies/evidence-integrity.md`](docs/policies/evidence-integrity.md)
- [`docs/policies/development.md`](docs/policies/development.md)
- [`docs/policies/required-checks.md`](docs/policies/required-checks.md)

Include runnable evidence with each completion claim. Report a blocked or timed-out run accurately.
Use signed, Developer Certificate of Origin (DCO)-attested Conventional Commits for pull requests.
Each pull request must pass the required gate for its current head.

## Authoring a skill

This section and the task entry points below apply to an Athena source checkout. Installed plugin
archives intentionally omit repository-only development tools such as `scripts/`, `tests/`,
`pyproject.toml`, `uv.lock`, and `justfile`.

Create `skills/<name>/SKILL.md`. Put executable helpers in `skills/<name>/scripts/`. Reference these
tested files from the skill. Do not put Bash or Python programs directly in Markdown.
Each executable Python helper must construct its command-line interface with
`skills._cli.argument_parser`. This rule also applies to repository tools. The factory keeps help,
usage failures, and the plugin `--version` contract consistent. The repository validator rejects an
executable script that bypasses this factory.

```yaml
---
name: <skill-name>
description: State the triggering intent, required dependency or capability, and failure behavior.
allowed-tools: []
---
```

The body must define when to use the skill and its inputs. It must define a verified, host-neutral
workflow. It must also define dependency failures, capability failures, failed approaches, an output
contract, and attribution.

Use placeholders for paths and commands in a target repository. Put repository-specific case studies
in a `references/` file and identify them as examples. Each skill must link the canonical
[`engineering principles catalog`](docs/principles/README.md). Identify only the stable `PNNN`
principles that have a material effect on the workflow. Describe that effect. Do not copy the general
principle definitions.

Follow the durable-artifact and behavior-test rules in
[`docs/policies/development.md`](docs/policies/development.md). Do not tell an agent to pin prose with
text-string tests. Do not create changelogs, generated documents, registries, inventories, or
unrelated files without a demonstrated product consumer.

After editing, run:

```bash
just all
```

## Escalation

Stop and request human direction in these conditions:

- Requirements conflict.
- The next step is unsafe or destructive.
- A workflow or required-check policy change is outside the requested scope.
- You cannot preserve user work.
- A hard-dependency override is invalid.
- A proposal weakens a security control or an evidence control.

## Task entry points

| Command | Purpose |
| --- | --- |
| `just validate` | Validate canonical skills and host manifests. |
| `just test` | Run isolated validator contracts with the coverage floor. |
| `just lint` | Lint retained repository tooling. |
| `just format-check` | Check retained repository-tool formatting. |
| `just typecheck` | Run strict static typing over repository tooling. |
| `just static` | Run lint, format, and strict type checks over every executable script. |
| `just markdownlint` | Validate public documentation and shipped skill Markdown. |
| `just package` | Build and inspect the portable plugin archive. |
| `just all` | Run the local check suite: validate, test, static, markdownlint, workflow-check, and package. SBOM generation and the dependency scan are required-CI-only gates (`just sbom` / `just sca` need CI-pinned Syft/Grype; see `docs/policies/required-checks.md`). |
