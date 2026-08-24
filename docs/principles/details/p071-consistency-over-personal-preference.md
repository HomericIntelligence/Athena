# P071 — Consistency Over Personal Preference

## Definition

Follow established repository conventions, style guides, patterns, terminology, and architectural
direction when multiple technically sound choices exist. Do not rewrite working code merely because
another valid style is more familiar or personally appealing.

**Aliases:** local consistency; convention over individual taste.

## Provenance

**Classification:** practitioner heuristic.

Consistency has long been emphasized by language and project style guides, without a single verified
origin. This formulation treats it as a tie-breaker for equivalent choices, not as authority to
preserve defects.

## Decision rule

When competing approaches satisfy the same requirements and evidence does not materially favor one,
choose the repository's established approach. When credible technical evidence distinguishes them,
[P072 Technical Evidence](p072-technical-evidence-over-preference.md) takes precedence.

## How to apply

- Read repository instructions, nearby code, public contracts, and active architecture decisions.
- Use existing terminology, layout, error conventions, test style, and extension mechanisms.
- Separate broad modernization or formatting from a feature change unless it is necessary.
- Propose convention changes explicitly and apply them coherently once accepted.
- Record the technical reason when departing from a convention so the exception is not accidental.

## Boundaries and tensions

Consistency is subordinate to correctness, security, accessibility, explicit requirements, and
measured evidence. Do not reproduce a known vulnerability or invalid pattern merely because it is
common nearby. A repository may also be intentionally migrating between conventions; follow the
documented direction rather than whichever style has more instances. Consistency concerns reader
expectations, not aesthetic uniformity at any cost.

## Examples

**Positive:** Two serialization approaches are equally correct, so a new endpoint uses the existing
repository serializer and error envelope.

**Misuse:** A contributor rewrites an entire module into a preferred naming and formatting style
while implementing one small behavior change.

**Athena/agent workflow:** A skill author follows Athena's existing host-neutral vocabulary and
section conventions instead of introducing vendor-specific terminology that expresses the same
capability.

## Related principles

- [P006 Principle of Least Astonishment](p006-principle-of-least-astonishment.md)
- [P014 Preserve Unrequested Behavior](p014-preserve-unrequested-behavior.md)
- [P015 Architecture Conformance](p015-architecture-conformance.md)
- [P070 Code Health Must Not Regress](p070-code-health-must-not-regress.md)
- [P072 Technical Evidence Over Preference](p072-technical-evidence-over-preference.md)

## References

### Origin/history

- [PEP 8: A Foolish Consistency Is the Hobgoblin of Little Minds](https://peps.python.org/pep-0008/#a-foolish-consistency-is-the-hobgoblin-of-little-minds)
  is a long-standing language guide that values project consistency while explicitly recognizing
  justified exceptions; it is not claimed as the origin of the broader heuristic.

### Current guidance

- [Google Go Style Guide: Local consistency](https://google.github.io/styleguide/go/guide.html#local-consistency)
  treats nearby convention as a tie-breaker but rejects consistency that spreads a defect or
  violates a stronger rule.
- [Google Engineering Practices: The standard of code review](https://google.github.io/eng-practices/review/reviewer/standard.html)
  places style guides above personal taste and technical facts above both.

### Further reading

- [Google JavaScript Style Guide: Reformatting existing code](https://google.github.io/styleguide/jsguide.html#policies-reformatting-existing-code)
  explains the trade-off among consistency, code churn, and change focus.

[Back to the engineering principles catalog](../README.md#p071)
