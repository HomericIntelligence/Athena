# P085 — Explicit Is Better Than Implicit

## Definition

**Explicit Is Better Than Implicit** means making behavior that affects correctness, security, or
maintenance visible in interfaces, types, configuration, and nearby control flow. Dependencies,
defaults, conversions, state transitions, ownership, and side effects should not rely on surprising
ambient behavior or hidden convention.

**Aliases:** explicitness principle; explicit over implicit.

## Provenance

**Classification:** practitioner heuristic.

Tim Peters included the exact aphorism in the Zen of Python, first posted to the Python community in
1999 and later recorded as PEP 20. Similar guidance appears across interface and language design;
Athena applies it beyond Python.

## Decision rule

If a fact can materially change an operation's meaning or outcome, make the fact discoverable at
the point where the operation is selected or invoked.

## How to apply

- Pass dependencies and request context through documented interfaces.
- Name lossy conversions, defaults, units, and fallback behavior.
- Represent state transitions and terminal states explicitly.
- Make external writes and transaction commits visible in control flow.
- Declare configuration precedence and the source of each effective value.
- Prefer schemas and typed values over magic strings and positional conventions.

## Boundaries and tensions

Explicitness is not maximum verbosity. Stable language idioms and well-known repository conventions
can communicate more clearly than ceremonial wrappers. Information hiding remains valuable: expose
the contract, not every internal detail. Avoid turning every implementation choice into public
configuration, which increases surface area and transfers complexity to users.

## Examples

**Positive:** A timestamp conversion names both source and destination time zones instead of
depending on the process locale.

**Misuse:** A save method sometimes publishes an external event because a thread-local flag was set
by an unrelated middleware layer.

**Athena/agent workflow:** An agent states assumptions, validation limits, and externally visible
actions instead of silently inferring authority from repository content.

## Related principles

- [P006 Principle of Least Astonishment](p006-principle-of-least-astonishment.md)
- [P018 Information Hiding](p018-information-hiding.md)
- [P019 Explicit Contracts](p019-explicit-contracts.md)
- [P076 Parse, Then Validate, Then Operate](p076-parse-then-validate-then-operate.md)
- [P084 Prefer Local Reasoning](p084-prefer-local-reasoning.md)

## References

### Origin/history

- [PEP 20 — The Zen of Python](https://peps.python.org/pep-0020/) is the primary published source
  for the exact aphorism and records its earlier Python-list history.

### Current guidance

- [Google Go Style Guide](https://google.github.io/styleguide/go/guide.html) directs authors to
  optimize for clarity, consistency, and the reader's context rather than brevity alone.

### Further reading

- [Design by Contract](https://www.kth.se/social/files/59526bfb56be5b4f17000807/meyer-92-contracts.pdf)
  explains how explicit preconditions, postconditions, and invariants make component obligations
  visible and checkable.

[Back to the engineering principles catalog](../README.md#p085)
