# Athena docs

This directory holds canonical Athena documentation. Athena is a
plugin/skill distribution repo; the docs here describe the boundary, the
boundary's enforcement, and operational notes.

## ADRs

- [ADR 0001 — Plugin-distribution scope policy](adr/0001-plugin-distro-scope-policy.md).
  The authoritative scope contract for this repo. Athena owns
  `.claude-plugin/`, `.codex-plugin/`, `.agents/`, `plugins/`, `skills/`,
  `assets/`. Library code lives in Hephaestus — never re-introduce
  `hephaestus.*` packages here.

## Runbooks

None yet. Runbook-style docs apply to operational systems, and Athena is
metadata-driven (skills + manifests). If we add operational surfaces
later (e.g. a marketplace validation daemon), runbooks will go here.

## Plugin installation

The plugin manifest sits at
[`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json).
The marketplace is registered at user scope in `~/.claude/settings.json`
under `extraKnownMarketplaces.Athena` (git source pointing at this repo).

Project-level enablement lives in
[`.claude/settings.json`](../.claude/settings.json) with the
strict-permission deny list that mirrors Hephaestus's posture.

## Cross-repo references

- [Hephaestus docs](https://github.com/HomericIntelligence/Hephaestus/tree/main/docs)
  — library-side ADRs and runbooks.
- [ProjectMnemosyne](https://github.com/HomericIntelligence/ProjectMnemosyne)
  — the cross-cutting skill marketplace catalog.
- [Odysseus](https://github.com/HomericIntelligence/Odysseus) — the
  meta-repo that coordinates submodule pins.
