# ADR 0001: Plugin-Distribution Scope Policy

**Status:** Accepted

> **Append-only.** Per [Odysseus/AGENTS.md](https://github.com/HomericIntelligence/Odysseus/blob/main/AGENTS.md)
> (principle 3) and Athena's own AGENTS procedural rules, accepted ADRs in
> this repo are immutable. Any change to the policy below is recorded in a
> **new superseding ADR** with the next sequential number, referencing this
> one. Do not amend or amend-commit this file; write a successor.

This ADR is the scope-policy for this repo. It is the **Athena-side
counterpart** to
[Hephaestus/docs/adr/0001-automation-library-boundary.md](https://github.com/HomericIntelligence/Hephaestus/blob/main/docs/adr/0001-automation-library-boundary.md)
and is kept one-directional.

---

## Context

Athena was carved out of Hephaestus in 2026 to separate the host-side plugin
distribution surface (`.claude-plugin/`, `.codex-plugin/`, `skills/`,
`assets/`, plugins dispatched to AI agents) from the Python library code that
those plugins compose (`hephaestus/`). Before the carve-out, repo roles were
ambiguous: skills lived alongside `hephaestus/automation/` files, and
contributors wasted review cycles deciding whether a `pip install -e .` would
ship skill metadata to a library consumer.

The carve-out is mechanical — files moved, `pyproject.toml` reorganised.
The hard part is keeping the boundary durable under ongoing contribution.
A `from athena import …` in library code, or a `from hephaestus.automation
import …` published under a `hephaestus.*` package in this repo, would
re-collapse the carve-out.

## Decision

Athena is a **plugin / skill distribution** repo. It owns the namespaces
that AI agents invoke:

- `.claude-plugin/` — Claude Code marketplace and plugin manifests.
- `.codex-plugin/` — Codex marketplace and plugin manifests.
- `.agents/` — agent-host skill bundles imported by Codex / Pi / etc.
- `plugins/` — third-party plugin contributions.
- `skills/` — first-party skill definitions (`SKILL.md` + assets).
- `assets/` — static assets referenced by skills.

Athena does **not** own:

- `hephaestus/*` — Python library code. Lives in the Hephaestus repo. Athena
  consumes it as a runtime dependency.
- Anything that would create a `hephaestus.*` Python package from this repo.

The dependency direction is **one-way**:

- `Athena → Hephaestus` — Athena may import from `hephaestus.automation`,
  but only from inside a skill body, only via the pinned `hephaestus>=3.0,<4`
  floor in `pyproject.toml`.
- `Hephaestus → Athena` is forbidden. Hephaestus's `test_import_surface.py`
  enforces this on the library side.

Bumping the Hephaestus pin in `pyproject.toml` is a **cross-repo
integration event** per
[Odysseus/AGENTS.md](https://github.com/HomericIntelligence/Odysseus/blob/main/AGENTS.md).
Bumping requires explicit operator sign-off; the Odysseus myrmidon pipeline
will surface the diff for review before merging.

## Consequences

**Positive:**

- Hephaestus library consumers never drag in skill metadata
  (`pip install -e .` of Hephaestus does not pull `.claude-plugin/`).
- Athena marketplace scanners can rely on a fixed set of top-level paths
  to find plugins.
- The carve-out is enforceable: Hephaestus-side `test_import_surface.py`
  fails the gate if anyone re-introduces `from athena` on the library side.

**Negative:**

- A skill that genuinely needs new utility code requires two PRs in two
  repos (Athena side + Hephaestus side) plus a `.gitmodules` SHA bump.
  Mitigation: skills should compose existing Hephaestus utilities; new
  library code is the exception, not the rule.
- A `pre-commit` hook (`athena_validate_marketplace`) is now load-bearing
  for review velocity — it must run locally before every push.

**Neutral:**

- Athena's `[project.optional-dependencies.automation]` mirrors Hephaestus's
  contract by pulling `hephaestus[automation]`. This is not a feature
  expansion; it is a faithful transfer of the existing surface.

## References

- [Hephaestus ADR-0001](https://github.com/HomericIntelligence/Hephaestus/blob/main/docs/adr/0001-automation-library-boundary.md) — library-side boundary contract.
- [Odysseus/AGENTS.md](https://github.com/HomericIntelligence/Odysseus/blob/main/AGENTS.md) — cross-repo coordination rules.
- [Odysseus ADR-014](https://github.com/HomericIntelligence/Odysseus/blob/main/docs/adr/014-runnable-evidence-for-metric-claims.md) —
  governs claims made inside skill outputs.
