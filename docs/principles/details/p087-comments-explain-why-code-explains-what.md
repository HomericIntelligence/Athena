# P087 — Comments Explain Why, Code Explains What

## Definition

**Comments Explain Why, Code Explains What** means preferring code that communicates its ordinary
mechanics directly and using comments for rationale, constraints, invariants, provenance,
surprising tradeoffs, or context the code cannot express. Public API documentation separately
explains purpose, usage, behavior, parameters, results, and failures.

**Aliases:** why-comments; rationale comments.

## Provenance

**Classification:** practitioner heuristic.

No verified single origin exists for the phrase. It is a widely repeated code-review heuristic,
and Google's published review guidance states the same default while documenting important
exceptions.

## Decision rule

First ask whether names, structure, or types can make the code clear. Add a comment when important
information would otherwise be lost, or when a public contract requires documentation that the
implementation cannot supply.

## How to apply

- Explain the reason for a workaround, invariant, limit, or compatibility path.
- Link a specification, issue, or measurement when it is the source of a surprising decision.
- Document public APIs according to their language and repository contract.
- Keep comments adjacent to the behavior they constrain.
- Update or remove comments in the same change that invalidates them.
- Replace stale TODOs with owned, actionable work or delete them.

## Boundaries and tensions

Complex algorithms, regular expressions, protocols, and performance-sensitive code may need
comments that explain *what* the steps mean because clearer executable notation is unavailable.
API documentation must describe externally observable behavior even when implementation code is
clear. Comments are not an excuse for tangled control flow, and they must not expose secrets or
repeat facts likely to drift.

## Examples

**Positive:** A compatibility branch cites the legacy format and explains why removal must wait for
a named migration milestone.

**Misuse:** A comment says "increment retry count" immediately above an obvious increment while the
actual retry limit remains unexplained.

**Athena/agent workflow:** A repository helper documents why it uses a one-off audit instead of a
retained prose validator, preserving the policy rationale for future maintainers.

## Related principles

- [P018 Information Hiding](p018-information-hiding.md)
- [P019 Explicit Contracts](p019-explicit-contracts.md)
- [P047 Observability Is Part of Correctness](p047-observability-is-part-of-correctness.md)
- [P084 Prefer Local Reasoning](p084-prefer-local-reasoning.md)
- [P086 Readability Counts](p086-readability-counts.md)

## References

### Origin/history

- No primary source establishing one coinage was found; treat the phrase as a practitioner
  heuristic rather than a quotation attributable to a single author.

### Current guidance

- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  says comments usually explain why, while naming complex algorithms and regular expressions as
  exceptions that can benefit from explanation of what they do.
- [Google API reference code comments](https://developers.google.com/style/api-reference-comments)
  requires public API documentation to cover purpose, use, parameters, results, and exceptions.

### Further reading

- [Google Documentation Best Practices](https://google.github.io/styleguide/docguide/best_practices.html)
  distinguishes inline comments, API documentation, READMEs, and longer conceptual documents by
  audience and purpose.

[Back to the engineering principles catalog](../README.md#p087)
