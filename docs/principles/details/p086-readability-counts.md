# P086 — Readability Counts

## Definition

**Readability Counts** means optimizing code for the people who must review, debug, operate, and
change it. Clear names, straightforward control flow, focused units, and understandable data shapes
are correctness and maintenance features, not cosmetic polish.

**Aliases:** code readability; readable-code principle.

## Provenance

**Classification:** practitioner heuristic.

The exact aphorism appears in Tim Peters's Zen of Python, recorded as PEP 20. The broader priority
is older and language-independent; programming practice has long recognized that software is read
and maintained repeatedly after it is written.

## Decision rule

Among correct designs, choose the one that lets the intended maintainer recover purpose, control
flow, data meaning, and failure behavior with the least avoidable mental simulation.

## How to apply

- Use domain names that communicate role and units.
- Keep functions and modules focused on coherent behavior.
- Prefer linear control flow and named intermediate results over clever compression.
- Make invariants and exceptional branches easy to locate.
- Follow established formatting and language idioms.
- Review code in its surrounding context, not only as an isolated diff.

## Boundaries and tensions

Readability depends partly on audience and ecosystem conventions. Replacing a standard idiom with
verbose ceremony can make code less readable. Do not flatten useful abstractions or duplicate
knowledge merely to keep everything in one file. Performance, security, and interoperability may
require intrinsic complexity; isolate it, test it, and explain the non-obvious constraints.

## Examples

**Positive:** A compound eligibility check is expressed through named predicates that match the
domain rules and expose which rule failed.

**Misuse:** A dense expression saves four lines but mixes conversion, validation, mutation, and
fallback behavior in one statement.

**Athena/agent workflow:** An agent produces a focused diff and evidence summary whose intent a
reviewer can verify without reconstructing the entire session transcript.

## Related principles

- [P001 KISS](p001-kiss.md)
- [P006 Principle of Least Astonishment](p006-principle-of-least-astonishment.md)
- [P071 Consistency Over Personal Preference](p071-consistency-over-personal-preference.md)
- [P084 Prefer Local Reasoning](p084-prefer-local-reasoning.md)
- [P087 Comments Explain Why, Code Explains What](p087-comments-explain-why-code-explains-what.md)

## References

### Origin/history

- [PEP 20 — The Zen of Python](https://peps.python.org/pep-0020/) is the primary published source
  for the exact wording *Readability counts*.

### Current guidance

- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  evaluates naming, complexity, comments, context, and whether a reader can understand the code
  quickly.

### Further reading

- [Software Engineering at Google: Style Guides and Rules](https://abseil.io/resources/swe-book/html/ch08.html)
  explains why scalable code standards optimize for readers and consistency over individual
  preference.

[Back to the engineering principles catalog](../README.md#p086)
