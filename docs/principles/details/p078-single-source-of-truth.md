# P078 — Single Source of Truth

## Definition

**Single Source of Truth** (SSOT) means that each authoritative mutable fact or policy has one
declared owner and write path. Other representations are derived views, caches, replicas, or
exports whose lineage and synchronization rules are explicit.

**Aliases:** SSOT; authoritative source; canonical owner.

## Provenance

**Classification:** practitioner heuristic.

The phrase is widespread across data management, configuration management, and software design,
but no reliable single origin has been established. It is related to database normalization and
DRY, while focusing specifically on authority and divergence rather than all duplication.

## Decision rule

For every fact that can change, be able to answer which representation wins, who may update it, and
how every other representation becomes consistent with it.

## How to apply

- Assign an authoritative owner and supported write interface for each domain fact.
- Generate or project secondary representations when practical.
- Mark caches and replicas as non-authoritative and define freshness expectations.
- Record lineage, version, and reconciliation behavior across asynchronous boundaries.
- Migrate authority explicitly; avoid periods where two writers can silently disagree.
- Detect drift when independent copies are unavoidable.

## Boundaries and tensions

SSOT does not mean one database, one service, or one global owner for an entire system. Different
bounded contexts may author different facts, and distributed replicas may be necessary for
availability. Derived copies are acceptable when their authority and consistency model are clear.
Centralization that creates a bottleneck or false consensus is not an improvement.

## Examples

**Positive:** One schema owns an API shape; generated clients and documentation identify their
schema version and are never edited independently.

**Misuse:** A timeout default appears separately in code, deployment configuration, and a runbook,
with no precedence rule when the values diverge.

**Athena/agent workflow:** The principles catalog owns IDs and decision rules; detail pages explain
them, and skills link to the catalog instead of maintaining competing definitions.

## Related principles

- [P018 Information Hiding](p018-information-hiding.md)
- [P020 Executable Architecture](p020-executable-architecture.md)
- [P077 Separate Policy from Mechanism](p077-separate-policy-from-mechanism.md)
- [P084 Prefer Local Reasoning](p084-prefer-local-reasoning.md)
- [P089 Delete Obsolete Configuration and Dependencies](p089-delete-obsolete-configuration-and-dependencies.md)

## References

### Origin/history

- No primary source establishing a single coinage was found. The term should be treated as a
  practitioner label rather than attributed to one author.
- [On the Criteria To Be Used in Decomposing Systems into Modules](https://doi.org/10.1145/361598.361623)
  supplies the related historical foundation of assigning design decisions to authoritative module
  boundaries.

### Current guidance

- [Microsoft Azure Architecture Center: Data considerations for microservices](https://learn.microsoft.com/en-us/azure/architecture/microservices/design/data-considerations)
  recommends one authoritative service where strong consistency is required while permitting
  explicitly non-authoritative eventual copies.

### Further reading

- [NASA: A PPE Use Case on Configuration Management Approach for MBSE](https://ntrs.nasa.gov/citations/20230000079)
  describes managing a model as the controlled source for derived engineering artifacts.
- [USENIX SREcon: There Is No Single Source of Truth](https://www.usenix.org/conference/srecon24emea/presentation/burke)
  provides a useful counterpoint about ambiguity and domain-specific authority in real systems.

[Back to the engineering principles catalog](../README.md#p078)
