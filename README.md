# Athena

[![Required checks](https://github.com/HomericIntelligence/Athena/actions/workflows/_required.yml/badge.svg?branch=main)](https://github.com/HomericIntelligence/Athena/actions/workflows/_required.yml)
[![Release](https://github.com/HomericIntelligence/Athena/actions/workflows/release.yml/badge.svg)](https://github.com/HomericIntelligence/Athena/actions/workflows/release.yml)
[![Latest release](https://img.shields.io/github/v/release/HomericIntelligence/Athena)](https://github.com/HomericIntelligence/Athena/releases)
[![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-blue.svg)](LICENSE)

Portable, architecture-first repository-review, development, and orchestration skills for
**Claude Code**, **Codex**, and **Pi**. They give every harness the same trusted, evidence-based
workflow without requiring a host-specific runtime.

Athena is distributed only as an AI-harness plugin. It does not publish a Python wheel, source
distribution, or runtime library.

## Required repositories

Athena has two hard dependencies:

| Purpose | Default | Owner override | Checkout |
| --- | --- | --- | --- |
| Knowledge | `HomericIntelligence/Mnemosyne` | `HOMERIC_INTELLIGENCE_MNEMOSYNE_OWNER` | `$HOME/.agent_brain/knowledge` |
| Automation | `HomericIntelligence/Hephaestus` | `HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER` | `$HOME/.agent_brain/automation` |

Athena resolves a trusted, current dependency checkout under the
[`dependency-resolution` contract](docs/dependency-resolution.md); invalid overrides, trust or
authentication failures, checkout mismatches, and update failures are fatal. The knowledge backend
is mandatory. For a verified, non-duplicate lesson with direct write authority, `learn` uses an
isolated worktree and pull request; otherwise it reports without mutation.

Script-backed skills require Git and Python 3.13 on the host. Dependency resolution and the
GitHub pull-request helper route additionally require authenticated GitHub CLI (`gh`) access. GitHub
issue and repository routes require the authenticated GitHub capability selected by their own skill.
GitLab issue, merge-request, and epic routes instead require an authenticated GitLab capability
supplied by the host; they must not fall back to GitHub CLI. Skills that do not select a forge route
do not require a forge client. Athena ships scripts as plugin resources; it does not install a Python
package or third-party runtime library.

## Install

Install the section for your harness, then restart it so the skill catalog reloads.

### Claude Code

```bash
claude plugin marketplace add https://github.com/HomericIntelligence/Athena
claude plugin install athena@Athena
```

Invoke `/athena:repo-review`. Update or remove:

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

Invoke `$repo-review` or ask Codex to use Athena's repo-review skill. Update or remove:

```bash
codex plugin marketplace upgrade athena
codex plugin remove athena@athena
codex plugin marketplace remove athena
```

### Pi

Athena requires Pi `0.83.0`. The first Athena release with the native Pi
manifest will be `v0.4.0`; until that signed tag exists, install an immutable
commit. Do not use `v0.3.0`: it predates native Pi packaging.

```bash
pi install git:github.com/HomericIntelligence/Athena@<immutable-commit-or-supported-tag>
```

Pi discovers Athena's canonical `skills/` corpus as `/skill:<name>` commands;
for example, invoke `/skill:repo-review`. Update only Athena's configured
source; it reconciles the configured immutable ref rather than advancing it.
To change versions, install the new immutable ref explicitly; remove the
configured source when it is no longer needed:

```bash
pi install git:github.com/HomericIntelligence/Athena@<next-immutable-ref>
pi update git:github.com/HomericIntelligence/Athena@<configured-ref>
pi remove git:github.com/HomericIntelligence/Athena@<configured-ref>
```

Athena does not bundle third-party Pi packages. Review their source before
installing them. `pi-subagents` is optional because Athena falls back to
sequential work when delegation is unavailable; it is required by deployments
that need the `Agent`/delegation capability. `pi-web-access` is required only
for workflows that need explicitly scoped web evidence.

```bash
pi install npm:pi-subagents@0.37.2
pi install npm:pi-web-access@0.15.0
```

Mnemosyne and Hephaestus remain Athena's repository dependencies under the
contract above. They are not copied into, installed by, or represented as Pi
packages.

## Release archives

Claude Code and Codex install Athena from the Git-backed marketplace sources above. Each GitHub
release also provides a checksummed portable archive for offline distribution and provenance; it is
not a Python package and does not replace marketplace installation. The archive contains only
harness-consumed skills, host metadata, the native Pi package manifest, runtime documentation,
assets, and notices. It excludes tests, repository scripts, development lockfiles, task-runner
files, CI configuration, and generated development output.

## Skills

- Architecture-first review: `change-review`, `repo-review`, and `pr-review`.
- Issue planning and review: `plan-issue` and `issue-review`.
- Engineering: `brainstorm`, `systematic-debugging`, and `test-driven-development`.
- Coordination: `myrmidon-swarm`, `git-worktrees`, and `tidy`.
- Knowledge and enablement: `advise` and `learn`.

All harnesses consume the same top-level [`skills/`](skills/) directory. Missing delegation runs
sequentially with the current agent.

## Develop

Prerequisites are Git, uv, Just, and Python 3.13 for repository validation only.

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
