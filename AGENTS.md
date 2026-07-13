# AGENTS.md — Athena

> **AI agents:** Companion to \`Hephaestus/AGENTS.md\`. Athena is a
> *plugin/skill distribution* repo, not a library. It ships Claude Code,
> Codex, and Pi host-side plugins and skills. The **Python library code**
> that these skills interact with lives in \`Hephaestus\`.

## Design Philosophy

Athena's design philosophy is inherited from [Hephaestus], the
repository Athena was carved out of under [ADR-016], and from the
[seven development principles] applied across the HomericIntelligence
ecosystem.

### Repository role and rhythm

Athena is a **plugin/skill distribution repository**, not a Python
library. ADR-016 separates it from Hephaestus so the plugin surface moves
at a fast release cadence (a new skill may land and ship this week) while
Hephaestus keeps its slow, semver-stable cadence. The split is enforced by
tooling: the Hephaestus library MUST NOT import from Athena, and Athena's
`pyproject.toml` declares `hephaestus` (plus the `[automation]` extra) as
the only library dependency. A contributor to Athena writes **skill
descriptions** that agent hosts (Claude Code, Codex, Pi) discover and
execute via a plugin install contract; the artifact shipped from this
repo is the plugin manifest plus the contents of `.claude-plugin/`,
`.codex-plugin/`, `.agents/`, `plugins/`, `skills/`, and `assets/`.

### Core principles

The seven HomericIntelligence principles apply to this surface as
follows.

- **KISS** — A skill body should solve one user intent with the smallest
  defensible scaffold. Reject novel abstractions whose only justification
  is "we might need them later."
- **YAGNI** — A skill ships only when at least one agent host can drive
  it today. Don't add a `.codex-plugin/` capability before a Codex
  integration is wired and tested.
- **TDD** — A skill's behaviour contract is encoded in a fixture before
  its prose is finalised. The same fixtures double as documentation for
  future maintainers and as the regression net for host-version drift.
- **DRY** — Shared skill scaffolding lives in a single plugin-utility
  snippet, not duplicated host-by-host. Skill bodies differ in intent,
  not in boilerplate.
- **SOLID** — Each skill's input handling, tool orchestration, and
  output formatting belongs to one operational concern. Cross-skill
  reuse goes through declared dependencies in `pyproject.toml`, never
  through cross-plugin imports.
- **Modularity** — Athena's plugin manifests and Hephaestus's library
  subpackages are **separately versioned**, with Athena explicitly
  depending on Hephaestus's stable API and never the reverse. This module
  boundary is the file system itself, per ADR-016.
- **POLA** — Plugin manifest field names, host-side install paths, and
  skill invocation names match the agent host's vocabulary, not our
  internal one. The roadmap marketplace entry is `athena@Athena` per
  ADR-016 (contingent on packaging Athena as a Claude Code plugin);
  deviations must carry a written reason.

### Boundaries with Hephaestus

Per ADR-016 the dependency direction is one-way and is structural in the
meta-repo: `Athena → Hephaestus`. Any code that implies the inverse (a
Hephaestus library submodule path that resolves through `athena`) is
rejected at Hephaestus's static-analysis gate, not at Athena's. The
meta-repo's `AGENTS.md` mirrors this rule and treats cross-submodule
integration pin bumps as a human-driven event that requires explicit
operator approval.

### Naming convention

Per [ADR-015] every identifier in this repo uses the bare myth-name
(`Athena`), never `ProjectAthena`. This applies to PyPI distribution
names, marketplace entries, plugin path strings, and the `description:`
field of each skill manifest.

[Hephaestus]: https://github.com/HomericIntelligence/Hephaestus
[ADR-016]: https://github.com/HomericIntelligence/Odysseus/blob/main/docs/adr/016-split-hephaestus.md
[seven development principles]: https://github.com/HomericIntelligence/Odysseus/blob/main/shared/Hephaestus/skills/_repo_analyze_common/principles.md
[ADR-015]: https://github.com/HomericIntelligence/Odysseus/blob/main/docs/adr/015-drop-project-prefix.md

## Dependency direction

- **Athena → Hephaestus (one-way).** Athena's \`pyproject.toml\` declares
  \`hephaestus\` (and the \`[automation]\` extra) as a dependency.
- **Hephaestus NEVER imports from Athena.** Library-side
  \`test_import_surface.py\` enforces this. Do not add any
  \`from athena\` / \`import athena\` statement under \`hephaestus/\`.

## Boundaries

- Anything under \`.claude-plugin/\`, \`.codex-plugin/\`, \`.agents/\`,
  \`plugins/\`, \`skills/\`, \`assets/\` — owned by Athena.
- Anything under \`hephaestus/*\` — owned by Hephaestus (NOT Athena).
  Skills that need orchestrator functionality do
  \`from hephaestus.automation import …\` from inside the skill body.

## Permitted tools

Bash, Read, Write, Edit, Glob, Grep (same as Hephaestus myrmidons).

## Prohibited actions

- Edit anything under \`hephaestus/\` — that lives in the Hephaestus repo.
- Add a Python package under \`hephaestus.*\` from this repo.
- Bump the Hephaestus pin in \`pyproject.toml\` without coordination
  (cross-repo integration event per Odysseus/AGENTS.md).
