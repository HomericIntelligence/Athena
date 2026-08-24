# P029 — Generalize Error Policy; Preserve Specific Cause

## Definition

Use a small, stable error taxonomy at architectural boundaries while retaining the original cause,
stack, and safe structured context for diagnosis. Handling policy should be general enough for
callers to rely on without erasing the specific event that failed.

**Aliases:** error translation with cause preservation; layered error taxonomy.

## Provenance

**Classification:** Athena synthesis with established foundations.

Exception chaining, causal errors, and protocol-level problem taxonomies are established
separately. No historical source is known to define this exact combined rule.

## Decision rule

Translate low-level failures only when crossing a meaningful boundary, map them to a stable caller
policy, and attach the original cause plus non-sensitive diagnostic context.

## How to apply

- Define a bounded set of errors callers can act on, such as invalid, unavailable, or conflict.
- Translate vendor and transport failures at the boundary that owns the public contract.
- Preserve causal links and structured fields for operators and debugging.
- Keep retryability, status, and user messaging separate from incidental exception text.
- Redact secrets and internals from externally visible details without discarding internal evidence.

## Boundaries and tensions

A single "operation failed" result is too general when callers need different actions. Exposing
every dependency exception is too specific and couples consumers to internals. Cause preservation
does not authorize leaking stacks, paths, queries, credentials, or personal data. Stable taxonomies
must evolve deliberately rather than grow a type for every occurrence.

## Examples

### Positive application

A storage timeout becomes a public `temporarily-unavailable` problem with a correlation ID and
retry policy, while the internal error record retains the driver exception and operation context.

### Misuse or counterexample

A handler converts every exception to a success response containing `null`, erasing both the
failure policy and the cause. Another handler sends the full database stack to the client.

### Athena or agent workflow

A dependency helper returns one documented unavailable status to its skill, but its diagnostic
record identifies the attempted checkout, command, exit status, and causal error without secrets.

## Related principles

- [P019 — Explicit Contracts](p019-explicit-contracts.md)
- [P028 — Test Failure Paths, Not Just Success Paths](p028-test-failure-paths.md)
- [P030 — Handle Errors at the Nearest Responsible Boundary](p030-nearest-responsible-error-boundary.md)

## References

### Origin and history

- [PEP 3134, "Exception Chaining and Embedded Tracebacks" (2005)](https://peps.python.org/pep-3134/)
  records explicit causal links and context when one exception is raised while handling another.

### Current guidance

- [RFC 9457, "Problem Details for HTTP APIs" (2023)](https://www.rfc-editor.org/rfc/rfc9457.html)
  defines stable problem types and occurrence-specific details while warning against exposing
  implementation internals.
- [Python documentation, "Exception context"](https://docs.python.org/3/library/exceptions.html#exception-context)
  documents current implicit and explicit exception chaining semantics.

### Further reading

- [OWASP, "Error Handling Cheat Sheet"](https://cheatsheetseries.owasp.org/cheatsheets/Error_Handling_Cheat_Sheet.html)
  distinguishes safe external errors from detailed internal diagnostics needed for investigation.

[Back to the engineering principles catalog](../README.md#p029)
