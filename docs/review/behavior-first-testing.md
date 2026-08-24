# Behavior-first testing

**Why:** Tests should prove core product behavior and fail when that behavior regresses, not freeze
wording, implementation layout, or incidental timing. This contract applies to planning,
implementation, change review, PR review, and repository review.

This contract applies the catalog's testing rules:
[P022](../principles/README.md#p022), [P023](../principles/README.md#p023),
[P024](../principles/README.md#p024), [P025](../principles/README.md#p025),
[P026](../principles/README.md#p026), [P027](../principles/README.md#p027),
[P028](../principles/README.md#p028), and [P091](../principles/README.md#p091).
Activate only those relevant to the behavior and risk under review; P091 governs behavior-changing
TDD, while the other entries remain independently applicable verification rules.

## What a good test proves

A good test proves an observable product contract: a result, state transition, public error contract,
security property, resource or performance bound, or executable artifact behavior. It is deterministic,
isolated, independent of test order and ambient machine state, and fails when the claimed regression
returns.

| Situation | Good test | Bad test |
| --- | --- | --- |
| API behavior | A request produces the documented result and rejects invalid or boundary input. | A private helper runs in a particular order. |
| Bug fix | A regression crosses a public or architectural boundary and fails without the fix. | Only an issue number or TODO appears. |
| State change | Durable state and externally visible transitions are correct on success and failure. | A snapshot freezes internal layout without an outcome assertion. |
| Documentation | Markdown, links, and executable examples validate syntax, navigation, or real output. | A test pins wording, headings, paragraph counts, or documentation counts. |
| Integration | Controlled substitutes exercise a real external boundary and error behavior. | A live service, wall-clock sleep, or ambient credential decides the result. |

## Avoid flakiness and false confidence

Flag tests that depend on wall-clock delays, unseeded randomness, test order, live network services,
current machine paths, unspecified scheduling, or shared mutable state unless the product contract
requires and controls that condition. Use mocks at genuine external boundaries; a test that only
asserts its mock arrangement is not behavior coverage. Prefer controlled time, seeded data, temporary
paths, fake transports, and explicit synchronization.

Name-filtered commands can pass while selecting zero tests. Treat `pytest -k`, `ctest -R`,
`go test -run`, and equivalent filters as unproven until the selected registered set is demonstrably
non-empty. For CMake, also prove the test source is wired into a real target. A green command that ran
no relevant test is a coverage failure.

## Planning and review rules

- Map each changed acceptance criterion to observable verification.
- Add a regression test for every bug fix unless a concrete documented reason makes it impossible.
- Verify error, boundary, and relevant concurrency paths proportionately to product risk.
- Do not weaken, skip, xfail, delete, or mock around a test solely to make a change green.
- Do not claim a benchmark, model metric, or runtime measurement succeeded without reproducible
  execution evidence bound to the reviewed revision.

Documentation-only changes use existing Markdown, link, and executable-example checks. They do not
justify a prose-string test harness.
