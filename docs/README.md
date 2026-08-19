# Athena documentation

**Why:** Athena ships one portable skill corpus, so its architecture, dependency, and governance
contracts must be easy to find without duplicating them for each coding harness.

## Architecture

- [`adr/0001-plugin-distro-scope-policy.md`](adr/0001-plugin-distro-scope-policy.md): the accepted
  plugin-only distribution boundary.
- [`host-compatibility.md`](host-compatibility.md): coding-harness capability mapping.
- [`dependency-resolution.md`](dependency-resolution.md): mandatory Mnemosyne and Hephaestus owner
  and checkout resolution.

## Policies

- [`policies/development.md`](policies/development.md): Git, PR, safety, and human-review rules.
- [`policies/evidence-integrity.md`](policies/evidence-integrity.md): runnable evidence and truthful
  failure requirements.
- [`policies/required-checks.md`](policies/required-checks.md): merge-gate and release contexts.
- [`supply-chain-security.md`](supply-chain-security.md): SBOM scope, SCA gate, and exceptions.

## Review framework

- [`review/README.md`](review/README.md): why the review system exists, its high-level flow, and
  the right contract to read for each review scope.
- [`review/common.md`](review/common.md): architecture-first shared contract, findings, and
  delivery boundaries.
- [`review/language-routing.md`](review/language-routing.md): language and toolchain profiles.
- [`review/behavior-first-testing.md`](review/behavior-first-testing.md): functional-test quality
  and false-confidence rules.
- [`review/repository-scorecard.md`](review/repository-scorecard.md): repository-review inventory
  and scoring sections.
- [`review/issue-planning.md`](review/issue-planning.md): canonical issue-plan, issue-review, and
  finalized-planning-epoch artifacts.
- [`review/design-docs.md`](review/design-docs.md): concise, why-first structure for new design
  documents.

The root [`AGENTS.md`](../AGENTS.md) is the authoritative repository-agent contract. Installation
and lifecycle commands are maintained in [`README.md`](../README.md).
