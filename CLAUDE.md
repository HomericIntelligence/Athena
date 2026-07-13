# CLAUDE.md — Athena

Project-specific conventions for AI agents operating in this repository. The
authoritative behavioural contract is [`AGENTS.md`](AGENTS.md) (Athena-side);
this file documents the conventions a Claude Code, Codex, or Pi session should
follow when working on Athena specifically.

## Repo role at a glance

Athena is a **plugin and skill distribution** repo. It owns
`.claude-plugin/`, `.codex-plugin/`, `.agents/`, `plugins/`, `skills/`,
`assets/`. It does **not** own `hephaestus/*`. Library-side code lives in
[Hephaestus](https://github.com/HomericIntelligence/Hephaestus).

## Authoring a skill

1. Create `skills/<name>/SKILL.md` with frontmatter:

   ```yaml
   ---
   name: <skill-name>
   description: One-line use-case statement. The first sentence is what the
     agent sees when this skill appears in the advisor picker. Be specific.
   allowed-tools: []           # default; tighten per skill
   ---
   ```

2. Body sections (mirroring Hephaestus's skill convention):

   - `# When to use` — concrete trigger conditions.
   - `# Inputs the skill expects` — every parameter the agent must collect.
   - `# Verified workflow` — the canonical happy path, in numbered steps.
   - `# Failed attempts` — known anti-patterns the agent must NOT retry.
   - `# Output contract` — exact shape of what the skill returns (markdown table,
     JSON, etc.).
   - `# References` — ADR numbers and file paths the agent should cite.

3. Add the skill to [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json)
   under `plugins`. The entry name MUST match the `skills/<name>/` folder.

4. Run `just check` before committing. `just check` runs `lint`, `format-check`,
   `typecheck`, and the skill-catalog validator.

## Quality gates

| Recipe | What it runs |
|--------|--------------|
| `just lint` | `ruff check` |
| `just format` | `ruff format --check` |
| `just typecheck` | `mypy --strict athena/ skills/` |
| `just test` | `pytest tests/` |
| `just audit` | `pip-audit` |
| `just check` | All of the above, sequentially |
| `just markdownlint` | `markdownlint` against repo markdown |
| `just validate-marketplace` | Asserts `.claude-plugin/marketplace.json` references real `skills/*` folders |

## Commit message format

```
<type>(<scope>): <short summary>

<body — wrap at 100 chars>

<footer — closes #N, refs #M, ADR-XXX>
```

`type` ∈ {`feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `revert`}.
`scope` ∈ {`skills/`, `.claude-plugin/`, `.codex-plugin/`, `docs/`, `pyproject`,
`justfile`}.

## Branch and PR

- Branch names: `<scope>/<issue-number>-<slug>` —
  e.g. `skills/12-add-verification`, `chore/7-bump-hephaestus`.
- PRs target `main`. Add a `Closes #<issue>` line in the body.
- Do **not** arm `--auto --rebase` here. Athena is cross-repo with Odysseus
  (`.gitmodules` SHA bumps require operator sign-off
  per [Odysseus/AGENTS.md](https://github.com/HomericIntelligence/Odysseus/blob/main/AGENTS.md)).

## Things this repo forbids

- Editing anything under `hephaestus/` (lives in the Hephaestus repo).
- Bumping the Hephaestus pin in `pyproject.toml` without coordination
  (cross-repo integration event).
- Hand-writing logs, metrics, or test results into the repo to satisfy a
  verification claim — this triggers [Odysseus ADR-014](
  https://github.com/HomericIntelligence/Odysseus/blob/main/docs/adr/014-runnable-evidence-for-metric-claims.md).
