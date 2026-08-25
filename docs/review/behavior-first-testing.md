# Behavior-first testing

**Why:** Tests must prove core product behavior. They must fail if that behavior regresses. Do not
make tests preserve wording, implementation layout, or incidental timing. This contract applies to
planning, implementation, change review, pull request review, and repository review.

Use the [ASD-STE100 technical-English policy](../../skills/TECHNICAL_ENGLISH.md) for all technical prose and review
output.

This contract applies the catalog's testing rules:
[P022](../principles/README.md#p022), [P023](../principles/README.md#p023),
[P024](../principles/README.md#p024), [P025](../principles/README.md#p025),
[P026](../principles/README.md#p026), [P027](../principles/README.md#p027),
[P028](../principles/README.md#p028), and [P091](../principles/README.md#p091).
Apply only the rules that are relevant to the reviewed behavior and risk. Apply P091 to a behavior
change that uses test-driven development (TDD). Apply the other rules independently when they are
relevant.

## What a good test proves

A good test proves one observable product contract. The contract can specify:

- a result;
- a state transition;
- a public error contract;
- a security property;
- a resource or performance limit; or
- executable artifact behavior.

Make each test deterministic and isolated. Make sure that its result does not depend on test order
or ambient machine state. The test must fail if the regression occurs again.

| Situation | Good test | Bad test |
| --- | --- | --- |
| API behavior | A request produces the documented result and rejects invalid or boundary input. | A private helper runs in a particular order. |
| Bug fix | A regression crosses a public or architectural boundary and fails without the fix. | Only an issue number or TODO appears. |
| State change | Durable state and externally visible transitions are correct on success and failure. | A snapshot freezes internal layout without an outcome assertion. |
| Documentation | Markdown, links, and executable examples validate syntax, navigation, or real output. | A test pins wording, headings, paragraph counts, or documentation counts. |
| Integration | Controlled substitutes exercise a real external boundary and error behavior. | A live service, wall-clock sleep, or ambient credential decides the result. |

## Avoid flakiness and false confidence

If the product contract does not require and control a condition, flag a test that depends on any of
these conditions:

- wall-clock delays;
- unseeded randomness;
- test order;
- live network services;
- current machine paths;
- unspecified scheduling; or
- shared mutable state.

Use mocks only at genuine external boundaries. Do not count a test that only verifies its mock
arrangement as behavior coverage. Use controlled time, seeded data, temporary paths, fake
transports, and explicit synchronization.

A name-filtered command can pass when it selects no tests. Before you accept `pytest -k`, `ctest -R`,
`go test -run`, or an equivalent filter as evidence, verify that it selects at least one registered
test. For CMake, also verify that a real build target includes the test source. Treat a successful
command that runs no relevant test as a coverage failure.

## Planning and review rules

- Map each changed acceptance criterion to observable verification.
- If no concrete documented constraint prevents a regression test, add one for every bug fix.
- Verify error, boundary, and relevant concurrency paths proportionately to product risk.
- Do not weaken, skip, xfail, delete, or mock around a test solely to make a change green.
- Do not claim a benchmark, model metric, or runtime measurement succeeded without reproducible
  execution evidence bound to the reviewed revision.

Documentation-only changes use existing Markdown, link, and executable-example checks. They do not
justify a prose-string test harness.
