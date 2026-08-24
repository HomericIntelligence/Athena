# P084 — Prefer Local Reasoning

## Definition

**Prefer Local Reasoning** means structuring a component so its behavior can be understood from its
contract, implementation, and nearby collaborators without reconstructing distant hidden state,
ambient configuration, implicit control flow, or unrelated subsystems.

**Aliases:** local reasoning; locality of reasoning.

## Provenance

**Classification:** established principle.

The exact phrase has no single verified origin. It draws from modularity, information hiding,
structured programming, and the Law of Demeter, all of which reduce the amount of nonlocal
knowledge required to understand or change software.

## Decision rule

If correctness depends on a distant fact, make that dependency explicit or move the governing
invariant closer to the code that enforces it. A maintainer should not need whole-system knowledge
for a local change whose contract is local.

## How to apply

- Keep invariants and the state they govern in the same module.
- Pass important dependencies explicitly through narrow interfaces.
- Limit global state, hidden callbacks, reflection, and action at a distance.
- Keep state transitions visible and close to their triggering operations.
- Use types and contracts to summarize facts established elsewhere.
- Provide a clear entry point before exposing lower-level implementation detail.

## Boundaries and tensions

Local reasoning does not justify duplicating global policy or authoritative data. A component can
refer to a canonical source through an explicit interface. Cross-cutting concerns such as
authorization, tracing, and transactions may span components, but their interception and effects
should be visible in the architecture. Some distributed invariants are inherently nonlocal; model
and document them rather than pretending otherwise.

## Examples

**Positive:** A pricing function receives a typed pricing policy and order rather than consulting
mutable globals, environment variables, and an implicit request-local cache.

**Misuse:** Assigning a property triggers an undocumented observer in another package that mutates
persistent state.

**Athena/agent workflow:** An agent grounds its decision in the task, repository instructions, and
nearby implementation rather than relying on undocumented memory about another checkout.

## Related principles

- [P005 Modularity](p005-modularity.md)
- [P018 Information Hiding](p018-information-hiding.md)
- [P019 Explicit Contracts](p019-explicit-contracts.md)
- [P078 Single Source of Truth](p078-single-source-of-truth.md)
- [P085 Explicit Is Better Than Implicit](p085-explicit-is-better-than-implicit.md)

## References

### Origin/history

- [Object-Oriented Programming: An Objective Sense of Style](https://doi.org/10.1145/62084.62113)
  is the 1988 primary Law of Demeter paper connecting limited collaborator knowledge to lower
  coupling and easier correctness reasoning.
- [On the Criteria To Be Used in Decomposing Systems into Modules](https://doi.org/10.1145/361598.361623)
  gives the foundational information-hiding argument for comprehensible module boundaries.

### Current guidance

- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  treats code that cannot be understood quickly by readers as excessive complexity.

### Further reading

- [Google Go Style Guide](https://google.github.io/styleguide/go/guide.html) centers clarity and
  reader context when choosing among otherwise correct implementations.

[Back to the engineering principles catalog](../README.md#p084)
