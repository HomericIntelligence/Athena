# Athena

[![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)
[![Type-checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy.readthedocs.io/)

Reusable **Claude Code**, **Codex**, and **Pi** plugins and skills for the
HomericIntelligence ecosystem.

Athena is a **plugin and skill distribution** repository. It ships the
host-side surfaces that AI agents invoke (`.claude-plugin/`, `.codex-plugin/`,
`.agents/`, `skills/`, `assets/`). The Python library code that skill bodies
compose lives in [`Hephaestus`](https://github.com/HomericIntelligence/Hephaestus);
skills import from it as `from hephaestus.automation import …`.

## What this repo is not

Athena is **not** a library. Do not add Python modules under a `hephaestus.*`
package from this repo. The dependency direction is one-way: **Athena → Hephaestus**.
Hephaestus must never import from Athena. The boundary is enforced on the
library side by Hephaestus's `test_import_surface.py`.

## Install

The Athena marketplace is registered in `~/.claude/settings.json` under
`extraKnownMarketplaces` as a git source pointing at this repository. On a
new Claude Code session start, Claude Code clones the marketplace to
`~/.claude/plugins/marketplaces/Athena`. Project-level
`enabledPlugins: { athena@Athena: true }` resolves to the locally-cloned
marketplace.

If you are wiring Athena into another project for the first time:

```bash
# Once, at user scope
claude plugin marketplace add https://github.com/HomericIntelligence/Athena
claude plugin install athena@Athena

# Per-project, in <repo>/.claude/settings.json
{ "enabledPlugins": { "athena@Athena": true } }
```

## Skill catalog

Skills live under [`skills/`](skills/) and are advertised in
[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json).

| Skill | Description |
|-------|-------------|
| [`verification`](skills/verification/SKILL.md) | Audit a metric, CI result, or benchmark claim and report whether it is backed by runnable evidence per [Odysseus ADR-014](https://github.com/HomericIntelligence/Odysseus/blob/main/docs/adr/014-runnable-evidence-for-metric-claims.md). |

## Project layout

```
.
├── .claude-plugin/        # Claude Code marketplace + plugin manifests
├── .codex-plugin/         # Codex marketplace + plugin manifests
├── .claude/
│   └── settings.json      # Project-level plugin enablement + deny rules
├── skills/                # Skills (one folder per skill, with SKILL.md)
├── docs/
│   └── adr/               # Architecture decision records (this repo)
├── scripts/               # Validation/lint/test helpers (added in follow-ups)
├── tests/                 # Skill-catalog + manifest tests (added in follow-ups)
├── pyproject.toml         # Package metadata; depends on Hephaestus
├── pixi.toml              # Reproducible task environment
├── justfile               # `just <recipe>` entry points
└── AGENTS.md              # AI-agent behavioural contract (Athena-specific)
```

## Development

```bash
# Install dev tooling
pixi install

# Run the quality gate (CI-equivalent)
just check

# Or step by step
just lint        # ruff
just format-check
just typecheck   # mypy
just test        # pytest
just audit       # pip-audit
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add a skill. New skills must:

1. Live under `skills/<name>/SKILL.md` with the standard Claude Code frontmatter
   (`description`, `allowed-tools`).
2. Be added to [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json)
   under `plugins`.
3. Reference Hephaestus utility code via
   `from hephaestus.automation import …` if orchestration code is needed —
   `hephaestus/` must remain untouched in this repo (see
   [ADR 0001](docs/adr/0001-plugin-distro-scope-policy.md)).

## License

BSD-3-Clause. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
