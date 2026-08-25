# Athena documentation

Athena ships one portable skill corpus. Readers must be able to find its architecture, dependency,
technical-English, and governance contracts. Do not copy these contracts for each coding harness.

## Architecture

- [`adr/0001-plugin-distro-scope-policy.md`](adr/0001-plugin-distro-scope-policy.md): the accepted
  plugin-only distribution boundary.
- [`host-compatibility.md`](host-compatibility.md): coding-harness capability mapping.
- [`dependency-resolution.md`](dependency-resolution.md): mandatory Mnemosyne and Hephaestus owner
  and checkout resolution.

## Policies

- [`technical-english.md`](technical-english.md): the required ASD-STE100 technical-English policy
  for Athena instructions and output prose.
- [`policies/development.md`](policies/development.md): Git, pull-request, safety, and human-review
  rules.
- [`policies/evidence-integrity.md`](policies/evidence-integrity.md): runnable evidence and truthful
  failure requirements.
- [`policies/required-checks.md`](policies/required-checks.md): merge-gate and release contexts.
- [`supply-chain-security.md`](supply-chain-security.md): software bill of materials scope, software
  composition analysis gate, and exceptions.

## Engineering principles

- [`principles/README.md`](principles/README.md): the stable P001-P091 catalog and links to the
  evidence-backed definition, application guidance, examples, tensions, and sources for each
  principle.

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
