# Athena

[![Required checks](https://github.com/HomericIntelligence/Athena/actions/workflows/_required.yml/badge.svg?branch=main)](https://github.com/HomericIntelligence/Athena/actions/workflows/_required.yml)
[![Release](https://github.com/HomericIntelligence/Athena/actions/workflows/release.yml/badge.svg)](https://github.com/HomericIntelligence/Athena/actions/workflows/release.yml)
[![Latest release](https://img.shields.io/github/v/release/HomericIntelligence/Athena)](https://github.com/HomericIntelligence/Athena/releases)
[![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-blue.svg)](LICENSE)

Portable repository-review, development, and agent-orchestration skills for **Claude Code**,
**Codex**, and **Pi**.

Athena is distributed only as an AI-harness plugin. It does not publish a Python wheel, source
distribution, or runtime library.

## Required repositories

Athena has two hard dependencies:

| Purpose | Default | Owner override | Checkout |
| --- | --- | --- | --- |
| Knowledge | `HomericIntelligence/Mnemosyne` | `HOMERIC_INTELLIGENCE_MNEMOSYNE_OWNER` | `$HOME/.agent_brain/knowledge` |
| Automation | `HomericIntelligence/Hephaestus` | `HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER` | `$HOME/.agent_brain/automation` |

Without an explicit override, Athena prefers a same-named repository in the current repository's
GitHub owner only when GitHub verifies it is a fork of the corresponding default. Otherwise it uses
the default. An invalid override, authentication failure, checkout mismatch, or update failure is
fatal. See [`docs/dependency-resolution.md`](docs/dependency-resolution.md).

The knowledge backend is mandatory. `learn` always uses an isolated worktree and creates a pull
request; it never writes directly to the knowledge repository's default branch.

Script-backed skills require Git, GitHub CLI, and Python 3.10 or newer on the host. Athena ships the
scripts as plugin resources; it does not install a Python package or third-party runtime library.

## Install

Install the section for your harness, then restart it so the skill catalog reloads.

### Claude Code

```bash
claude plugin marketplace add https://github.com/HomericIntelligence/Athena
claude plugin install athena@Athena
```

Invoke `/athena:verification`. Update or remove:

```bash
claude plugin marketplace update Athena
claude plugin uninstall athena@Athena
```

### Codex

```bash
codex plugin marketplace add https://github.com/HomericIntelligence/Athena --ref main
codex plugin add athena@athena
codex plugin list --marketplace athena
```

Invoke `$verification` or ask Codex to use Athena's verification skill. Update or remove:

```bash
codex plugin marketplace upgrade athena
codex plugin remove athena@athena
codex plugin marketplace remove athena
```

### Pi

```bash
pi install https://github.com/HomericIntelligence/Athena
```

Invoke `/skill:verification`. Update or remove:

```bash
pi update https://github.com/HomericIntelligence/Athena
pi remove https://github.com/HomericIntelligence/Athena
```

## Skills

- Strict repository and PR evaluation: `repo-review` and `pr-review`.
- Engineering: `brainstorm`, `systematic-debugging`, `test-driven-development`, `verification`,
  `code-review`, and `finish-branch`.
- Coordination: `myrmidon-swarm`, `git-worktrees`, `worktree-cleanup`, and `tidy`.
- Knowledge and enablement: `advise`, `learn`, `skill-advisor`, `python-repo-modernization`,
  `github-actions-python-cicd`, and `create-reusable-utilities`.

All harnesses consume the same top-level [`skills/`](skills/) directory. Missing delegation runs
sequentially with the current agent.

## Develop

Prerequisites are Git, Pixi, Just, and Python 3.10+ for repository validation only.

```bash
git clone https://github.com/HomericIntelligence/Athena
cd Athena
just bootstrap
just all
```

`just all` validates skills and manifests, runs executable unit tests, enforces at least 80% branch
coverage for every repository and skill-local executable script, runs Ruff and strict mypy over the
same tooling, lints public documentation and workflows, and builds a deterministic plugin archive
with a SHA-256 checksum. It never builds Python distribution artifacts.

## Layout

```text
skills/                  canonical skills and their tested local helpers
.claude-plugin/          Claude Code marketplace and plugin metadata
.codex-plugin/           Codex plugin metadata
.agents/plugins/         Codex marketplace metadata
scripts/                 typed validation, CI-policy, and archive tooling
tests/unit/              executable-script behavior tests
docs/                    local policies and dependency contracts
.github/                 ownership and required/release workflows
```

## License

BSD-3-Clause. See [`LICENSE`](LICENSE), [`NOTICE`](NOTICE), and
[`skills/THIRD_PARTY_LICENSES.md`](skills/THIRD_PARTY_LICENSES.md).
