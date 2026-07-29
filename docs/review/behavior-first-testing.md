# Behavior-first testing

Athena treats tests as evidence for product behavior, not evidence that a
particular sentence, implementation layout, or tool invocation still exists.
This contract applies to planning, implementation, change review, PR review,
and repository review.

## What a good test proves

A good test proves an observable product contract: a result, state transition,
public error contract, security property, resource bound, performance bound, or
executable artifact behavior. It is deterministic, isolated, independent of
test order and ambient machine state, and fails when the claimed regression is
reintroduced.

| Situation | Good test | Bad test |
| --- | --- | --- |
| API behavior | A request produces the documented result and rejects invalid or boundary input. | A private helper is called in a particular order. |
| Bug fix | A regression reproduces through a public or architectural boundary and fails without the fix. | A test only checks that the issue number or a TODO appears. |
| State change | The durable state and externally visible transition are correct across success and failure. | A snapshot freezes an internal object layout with no outcome assertion. |
| Documentation | Markdown, links, and executable examples validate syntax, navigation, or real output. | A test pins wording, headings, paragraph counts, or documentation counts. |
| Integration | Controlled substitutes exercise a real external boundary and error behavior. | A live service, wall-clock sleep, or ambient credential decides the result. |

## Flakiness and false confidence

Flag tests that depend on wall-clock delays, unseeded randomness, test order,
live network services, current machine paths, unspecified scheduling, or shared
mutable state unless the product contract requires the condition and the test
controls it.

Use mocks at genuine external boundaries. A test that only asserts the mock
arrangement is not behavior coverage. Prefer controlled time, seeded data,
temporary paths, fake transports, and explicit synchronization primitives.

Name-filtered test commands can succeed while selecting zero tests. Treat
`pytest -k`, `ctest -R`, `go test -run`, and equivalent filters as unproven
until the selected registered test set is demonstrably non-empty. For CMake,
also prove that the test source is wired into a real target. A green command
that ran no relevant test is a coverage failure.

## Planning and review rules

- Map each changed acceptance criterion to an observable verification step.
- Add a regression test for every bug fix unless a concrete, documented reason
  makes that impossible.
- Verify error, boundary, and relevant concurrency paths proportionately to the
  product risk.
- Do not weaken, skip, xfail, delete, or mock around a test solely to make a
  change green.
- Do not claim a benchmark, model metric, or runtime measurement succeeded
  without reproducible execution evidence bound to the reviewed revision.

Documentation-only changes use existing Markdown, link, and executable-example
checks. They do not justify a prose-string test harness.
