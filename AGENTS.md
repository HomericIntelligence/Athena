# AGENTS.md — Athena

> **AI agents:** Companion to \`Hephaestus/AGENTS.md\`. Athena is a
> *plugin/skill distribution* repo, not a library. It ships Claude Code,
> Codex, and Pi host-side plugins and skills. The **Python library code**
> that these skills interact with lives in \`Hephaestus\`.

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
