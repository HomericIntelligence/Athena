# Athena documentation

Athena is a self-contained AI-harness plugin distribution. These documents define its local
architecture, dependency contracts, and governance.

## Architecture

- [`adr/0001-plugin-distro-scope-policy.md`](adr/0001-plugin-distro-scope-policy.md): the accepted
  plugin-only distribution boundary.
- [`host-compatibility.md`](host-compatibility.md): Claude Code, Codex, and Pi capability mapping.
- [`dependency-resolution.md`](dependency-resolution.md): mandatory Mnemosyne and Hephaestus owner
  and checkout resolution.

## Policies

- [`policies/development.md`](policies/development.md): Git, PR, safety, and human-review rules.
- [`policies/evidence-integrity.md`](policies/evidence-integrity.md): runnable evidence and truthful
  failure requirements.
- [`policies/required-checks.md`](policies/required-checks.md): merge-gate and release contexts.

The root [`AGENTS.md`](../AGENTS.md) is the authoritative repository-agent contract. Installation
and lifecycle commands are maintained in [`README.md`](../README.md).
