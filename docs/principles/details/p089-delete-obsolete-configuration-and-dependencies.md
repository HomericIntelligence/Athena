# P089 — Delete Obsolete Configuration and Dependencies

## Definition

**Delete Obsolete Configuration and Dependencies** means completing a removal across its entire
supporting surface. When a feature, compatibility path, or subsystem is retired, remove the flags,
packages, lockfile entries, deployment settings, tests, documentation, metrics, and scaffolding that
have no remaining purpose, after verifying that they have no consumers.

**Aliases:** none in common use.

## Provenance

**Classification:** Athena synthesis.

No single source establishes this exact rule. It combines dependency hygiene, configuration
management, attack-surface reduction, and the operational lesson that partial removals leave
misleading or vulnerable artifacts behind.

## Decision rule

A removal is complete only when every supporting artifact either has another demonstrated current
consumer or is deleted through its canonical management mechanism.

## How to apply

- Trace the removed capability through manifests, lockfiles, images, deploy files, and environment
  variables.
- Inspect optional, transitive, dynamically loaded, build-time, and platform-specific consumers.
- Remove obsolete feature flags, defaults, secrets, dashboards, alerts, and runbook steps.
- Update the canonical dependency or configuration source, then regenerate derived artifacts.
- Test clean installation, packaging, startup, supported platforms, and deployment paths.
- Review the final dependency and configuration diff for unintended upgrades or drift.

## Boundaries and tensions

Configuration and packages may serve external, downstream, migration, or rarely exercised platform
consumers invisible to a local search. Honor compatibility and deprecation contracts. Do not turn a
focused cleanup into an unrelated dependency upgrade. Preserve lockfile integrity and supply-chain
evidence, and never remove a safety control merely because its normal path is quiet.

## Examples

**Positive:** Removing an obsolete exporter also removes its package, lockfile closure, feature
flag, credentials, container layer, metrics, tests, and operator documentation.

**Misuse:** Production code stops reading a flag, but deployment templates still advertise it and
the unused parser dependency remains in every release image.

**Athena/agent workflow:** When removing a skill helper, an agent verifies and updates its package
inclusion, references, tests, and shipped documentation rather than deleting only the script.

## Related principles

- [P008 Understand Before Subtracting](p008-understand-before-subtracting.md)
- [P014 Preserve Unrequested Behavior](p014-preserve-unrequested-behavior.md)
- [P055 Minimize Attack Surface](p055-minimize-attack-surface.md)
- [P057 Supply-Chain Integrity](p057-supply-chain-integrity.md)
- [P078 Single Source of Truth](p078-single-source-of-truth.md)
- [P088 Delete Dead Code](p088-delete-dead-code.md)

## References

### Origin/history

- No primary source for the combined rule is established; Athena treats it as a lifecycle and
  supply-chain synthesis rather than attributing it to one author.

### Current guidance

- [OpenSSF: Simplifying Software Component Updates](https://best.openssf.org/Simplifying-Software-Component-Updates)
  explains dependency cost, minimizing unneeded components, lockfiles, and automated verification.
- [NIST SP 800-218, Secure Software Development Framework 1.1](https://csrc.nist.gov/pubs/sp/800/218/final)
  defines current practices for protecting and maintaining software components and build inputs.

### Further reading

- [CISA: Secure by Design and Default](https://www.cisa.gov/sites/default/files/2023-06/principles_approaches_for_security-by-design-default_508c.pdf)
  recommends prioritizing protective mechanisms over unnecessary features that enlarge attack
  surface.
- [Google SRE: Regaining Simplicity](https://sre.google/workbook/simplicity/) discusses removing
  unused dependencies, configuration, and operational complexity as staffed engineering work.

[Back to the engineering principles catalog](../README.md#p089)
