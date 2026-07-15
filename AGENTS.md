# AGENTS.md — Athena

This is the authoritative contract for every AI coding harness operating in Athena. Host-specific
files point here rather than duplicate it.

## Purpose and scope

Athena is a self-contained, host-neutral distribution of workflow skills for Claude Code, Codex,
and Pi. The product is the top-level `skills/` corpus plus its host manifests and documentation. It
does not publish a Python package.

Athena owns:

- `skills/`: canonical portable skill sources.
- `.claude-plugin/`, `.codex-plugin/`, and `.agents/plugins/`: host metadata.
- `scripts/`: typed repository validation, CI-policy, and packaging tools; not a distributable
  runtime library.
- `tests/unit/`: behavior tests for executable repository and skill-local scripts.
- `docs/`, `assets/`, and `.github/`: policy, documentation, media, ownership, and automation.

`skills/` is the only skill source. Do not create a nested plugin mirror or host-specific copy.
Runtime repository requirements belong in the relevant skill descriptions and workflows, not in
this repository-agent contract.

## Multi-harness contract

- Express capabilities, not fixed vendor APIs.
- Use coordinator, specialist, executor, skill invocation, and subagent rather than branded model
  tiers.
- Use the host default model when tier selection is unavailable.
- Run independent work sequentially when the host cannot delegate.
- Treat invocation syntax as an example: Claude uses `/athena:<skill>`, Codex uses `$<skill>` or
  natural language, and Pi uses `/skill:<skill>`.
- Read `AGENTS.md` for repository guidance. `CLAUDE.md` is only a pointer.
- Frontmatter tool names describe required capabilities; every skill documents a safe failure or
  fallback when a host lacks one.

## Permitted actions

Agents may read repository files, edit files within the user's requested scope, run deterministic
validation, and create isolated local branches or worktrees needed for that work. Read-only GitHub
inspection is allowed when relevant.

External writes, PR creation, publishing, releases, merges, auto-merge, destructive operations, and
changes outside the requested repositories require explicit authority.

## Prohibited actions

- Never fabricate logs, metrics, tests, benchmarks, releases, or successful command output.
- Never commit secrets, credentials, private keys, `.env` files, or personal data.
- Never bypass hooks or required checks with `--no-verify`, silent shell fallbacks, or
  `continue-on-error: true`.
- Never force-push, merge, release, delete branches/worktrees, or weaken permissions without the
  required authority.
- Never edit an accepted ADR in place; write a superseding ADR.
- Never overwrite unrelated user changes or silently retarget an existing dependency checkout.

## Evidence and delivery

Follow the local policies:

- [`docs/policies/evidence-integrity.md`](docs/policies/evidence-integrity.md)
- [`docs/policies/development.md`](docs/policies/development.md)
- [`docs/policies/required-checks.md`](docs/policies/required-checks.md)

Every completion claim includes runnable evidence. A blocked or timed-out run is reported honestly.
Pull requests use signed, DCO-attested Conventional Commits and must pass the current-head required
gate.

## Authoring a skill

This section and the task entry points below apply to an Athena source checkout. Installed plugin
archives intentionally omit repository-only development tools such as `scripts/`, `tests/`,
`pixi.toml`, and `justfile`.

Create `skills/<name>/SKILL.md`. Put executable helpers in `skills/<name>/scripts/`; reference those
tested files from the skill instead of embedding Bash or Python programs in Markdown.

```yaml
---
name: <skill-name>
description: State the triggering intent, required dependency or capability, and failure behavior.
allowed-tools: []
---
```

The body defines when to use the skill, inputs, a host-neutral verified workflow, dependency and
capability failure behavior, failed approaches, an output contract, and attribution. Use
placeholders for target-repository paths and commands. Keep repository-specific case studies in a
`references/` file and label them as examples. Follow the durable-artifact and behavior-test rules
in [`docs/policies/development.md`](docs/policies/development.md): never direct an agent to pin prose
with text-string tests or create changelogs, generated docs, registries, inventories, or unrelated
files without a demonstrated product consumer.

After editing, run:

```bash
just all
```

## Escalation

Stop and request human direction for conflicting requirements, an unsafe or destructive next step,
workflow/required-check policy changes beyond the requested scope, inability to preserve user work,
an invalid hard-dependency override, or any proposal to weaken a security or evidence control.

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
| `just all` | Run the complete local required-check equivalent. |
