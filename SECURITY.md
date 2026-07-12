# Security policy

Athena is a plugin and skill distribution repository. It ships
host-side surfaces (`.claude-plugin/`, `.codex-plugin/`, `skills/`,
`assets/`) for AI agents and depends on
[Hephaestus](https://github.com/HomericIntelligence/Hephaestus) for the
underlying Python utilities. Most security issues surface there; this page
covers what is in scope here.

## Supported versions

Athena does not yet tag runtime releases. Security fixes land on `main` and
are pulled into ecosystems via the marketplace fetch on session start. If
you depend on a pinned SHA, treat the latest commit on `main` as supported
until a tag-based release policy is published in `CHANGELOG.md`.

## Reporting a vulnerability

Email **research@villmow.us** with:

- A reproducer (commit hash, agent invocation, expected vs observed behavior).
- The skill, market-place entry, or asset involved.
- Whether you have disclosed the issue publicly.

You should receive an acknowledgement within 5 business days. We aim to
publish a fix or a clear mitigation within 30 days for severity ≥ medium.
For skills shipped from this repo, fixes ship via a marketplace refresh; no
client action is required.

## Threat model

Athena is a **distribution** repo. Its attack surface is:

- **Skills (SKILL.md bodies).** A malicious skill could instruct an agent to
  execute untrusted commands. Defenses: per-skill `allowed-tools` frontmatter;
  Hephaestus-side `allowedTools` propagation to the invoker; project-level
  deny rules in `.claude/settings.json`; CI agents run inside the
  `achaean-claude` ephemeral container per
  [Odysseus/AGENTS.md](https://github.com/HomericIntelligence/Odysseus/blob/main/AGENTS.md).
- **Marketplace manifests.** A malicious entry could redirect a skill source.
  Defenses: git-source pinning to a known SHA; marketplace.json validated
  against `skills/*` folder paths by `just validate-marketplace`.
- **Cross-repo coupling.** A wrong bump to the Hephaestus pin in
  `pyproject.toml` could pull in unreviewed code. Defenses: pin-floor in
  `[project.dependencies]`; cross-repo integration review per
  [Odysseus/AGENTS.md](https://github.com/HomericIntelligence/Odysseus/blob/main/AGENTS.md#escalation--human-review-required).

## Out of scope

Vulnerabilities in [Hephaestus](https://github.com/HomericIntelligence/Hephaestus)
library code should be reported in the Hephaestus repo. Issues that originate
in upstream dependencies are tracked via `just audit` (pip-audit) and surfaced
through [Renovate](https://github.com/renovatebot/renovate) PRs.
