# ADR 0001: Plugin-only distribution boundary

**Status:** Accepted

**Bootstrap exception:** Athena had no supported release before this cleanup. Maintainers explicitly
authorized PR #9 to replace the earlier ADR 0001 draft while defining the first supported product
boundary. The append-only rule applies to this accepted version after it lands; later changes must
use a superseding ADR.

## Context

Athena distributes portable workflow skills to multiple AI coding harnesses. Earlier layouts mixed
plugin metadata with a Python distribution and duplicated skills into a nested host payload. That
created drift and made consumers believe Python artifacts were the product.

## Decision

Athena's product consists of:

- One canonical top-level `skills/` tree.
- Root Claude Code and Codex plugin manifests and Codex marketplace metadata.
- Documentation required by installed skills.
- A release archive containing those plugin resources.

Athena does not publish a Python package. Standard-library scripts under `scripts/` are repository
validation tools and are not a runtime library. No nested plugin mirror is permitted.

Athena has two explicit hard repository dependencies: Mnemosyne for knowledge and Hephaestus for
automation. Their owner precedence and checkout locations are defined locally in
[`docs/dependency-resolution.md`](../dependency-resolution.md). No other repository supplies
Athena policy or runtime behavior.

## Consequences

- Claude Code, Codex, and Pi consume identical skill content.
- Releases are GitHub plugin archives, not wheels or source distributions.
- All governance and evidence rules needed to operate Athena live in this repository.
- Dependency detection fails closed instead of silently skipping knowledge or automation.
- Accepted ADRs are append-only; future boundary changes require a superseding ADR.
