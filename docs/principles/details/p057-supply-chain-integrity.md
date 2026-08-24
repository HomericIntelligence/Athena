# P057 — Supply-Chain Integrity

## Definition and aliases

Supply-Chain Integrity preserves justified trust in the source, dependencies, tools, build inputs,
processes, and artifacts used to deliver software. Consumers should be able to identify what entered
the build, where it came from, how it was transformed, and whether it changed unexpectedly.

**Aliases:** software supply-chain security, build integrity, artifact provenance.

## Provenance

**Classification:** established principle.

Thompson's compiler-backdoor lecture is an early primary demonstration that source review alone
cannot establish trust in delivered software. Modern frameworks add provenance, protected builds,
dependency controls, and attestations.

## Decision rule

Every new build input or dependency must have a necessary purpose, an accountable source, a bounded
version policy, and a way to verify identity and integrity appropriate to its risk. Protect the path
from reviewed source to distributed artifact, not only the final repository state.

## How to apply

- Prefer existing or standard-library capability before adding a third-party component.
- Obtain inputs from trusted sources; review ownership, maintenance, license, and security posture.
- Preserve lockfiles and verify digests, signatures, provenance, and attestations where supported.
- Isolate and authenticate build systems, minimize their credentials, and keep builds reproducible.
- Record component and artifact provenance and scan for known risks without treating scans as proof.
- Define update, vulnerability-response, removal, and compromise-recovery paths before adoption.

## Boundaries and tensions

Pinning prevents surprise changes but can preserve known vulnerabilities; integrity and freshness are
separate questions. A signed artifact proves control of a signing identity, not that the software is
benign or correct. An inventory without an operational consumer does not reduce risk. Match controls
to impact, and avoid adding supply-chain tools whose own cost and trust dependencies exceed their value.

## Examples

### Positive

A project reviews a required dependency, commits its lockfile, verifies registry provenance in CI,
builds in an isolated environment, and binds the release artifact to an attested source revision.

### Misuse

A build downloads an unversioned installer at runtime, executes it with release credentials, and signs
the resulting artifact. The signature authenticates the compromised output rather than its inputs.

### Athena and agent workflows

An agent verifies that a plugin dependency comes from the canonical repository and expected revision.
Retrieved skill text remains untrusted data unless the host explicitly designates it as instruction.

## Related principles

- [P053 — Validate at Trust Boundaries](./p053-validate-at-trust-boundaries.md)
- [P055 — Minimize Attack Surface](./p055-minimize-attack-surface.md)
- [P056 — Secrets Stay Out of Code and Context](./p056-secrets-stay-out-of-code-and-context.md)
- [P059 — Data Is Not Instruction](./p059-data-is-not-instruction.md)

## References

### Origin and history

- [Ken Thompson, *Reflections on Trusting Trust*](https://doi.org/10.1145/358198.358210) demonstrates
  how a compromised compiler can subvert output without malicious source being visible.

### Current guidance

- [NIST SP 800-218, SSDF Version 1.1](https://doi.org/10.6028/NIST.SP.800-218) includes practices for
  protecting software components and addressing third-party software risk.
- [SLSA Specification 1.2](https://slsa.dev/spec/v1.2/) defines current source and build integrity
  levels and standardized provenance attestations.

### Further reading

- [NIST SP 800-161 Revision 1](https://doi.org/10.6028/NIST.SP.800-161r1-upd1) addresses cybersecurity
  supply-chain risk management across systems and organizations.

[Back to the principles catalog](../README.md#p057)
