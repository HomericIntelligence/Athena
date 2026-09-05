# Control flow and error catalog

Use this catalog with the
[errors and reliability profile](../../../docs/review/common.md#errors-and-reliability) and the
[language-routing contract](../../../docs/review/language-routing.md). Apply the error model of the
target language. Exceptions, error values, result types, status values, and cancellation signals can
carry the same policy concerns.

Handle a failure at the nearest responsible boundary. This is the nearest boundary that has enough
policy context to complete recovery, cleanup, compensation, bounded retry, redaction, translation,
termination, or another specified outcome. It is not always the local function. It is not always the
outermost boundary. If a layer cannot complete the outcome, preserve the cause and propagate the
failure.

Do not infer a defect from branch count, nesting depth, exception count, or a generated diagnostic.
Confirm a reachable behavior or architecture effect. Use retain when the evidence does not support
a change.

## Branch or guard structure that hides a state model

- **Signal:** Nested conditions, repeated predicates, Boolean flags, early exits, and switch branches
  encode combinations of the same domain state. Different branches perform the same transition or
  use incompatible transition rules.
- **Required evidence:** Enumerate the reachable states and transitions. Identify repeated decisions,
  unreachable paths, or inconsistent outcomes. Bind them to a contract, caller, or test. A complexity
  score or nesting threshold is not sufficient evidence.
- **Impact:** State the incorrect transition, hidden invariant, duplicate policy, or maintenance
  action that the flow causes.
- **Legitimate counterexample:** Retain explicit branches when they are the clearest form of a small
  decision. Retain a decision table or state machine when the domain has necessary states and the
  repository makes their transitions explicit.
- **Smallest safe correction:** Name the state or predicate one time at its owner. Use an existing
  state type, decision table, or guard form when it makes the transitions explicit. Do not add a
  framework only to reduce nesting.
- **Validation:** Test each applicable transition, boundary value, and invalid state. Confirm that the
  refactor starts from a green behavior baseline.
- **Routing owner:** Use realign for state or policy restructuring. Use simplify when branch
  deletion is the complete evidence-backed correction. Use systematic-debugging first when a
  branch has a current behavior defect.
- **Applicable principles:** [P012](../../../docs/principles/README.md#p012),
  [P014](../../../docs/principles/README.md#p014),
  [P019](../../../docs/principles/README.md#p019),
  [P020](../../../docs/principles/README.md#p020),
  [P070](../../../docs/principles/README.md#p070),
  [P072](../../../docs/principles/README.md#p072), and
  [P075](../../../docs/principles/README.md#p075).
- **Sources:** [Athena behavior-first testing contract](../../../docs/review/behavior-first-testing.md),
  [AISlop rule catalog](https://github.com/scanaislop/aislop/blob/v0.16.0/docs/rules.md), and
  [a practitioner discussion of generated nesting and broad catches](https://news.ycombinator.com/item?id=45535937).

## Duplicate validation or validation at the wrong boundary

- **Signal:** Core functions repeatedly check a representation that an earlier trusted boundary
  already validated. Parsing, normalization, validation, and operation occur in many layers. An
  external or trust boundary has no validation, while downstream code adds defensive guards.
- **Required evidence:** Identify the trust and construction boundaries. Trace the value from its
  untrusted form to its trusted form. Show the duplicated invariant or the path that can bypass
  validation. Similar checks are not sufficient evidence when they enforce different contracts.
- **Impact:** State the inconsistent rejection, missing protection, branch growth, type erosion, or
  duplicate maintenance that the placement causes.
- **Legitimate counterexample:** Retain independent checks for different trust boundaries. Retain a
  check near a destructive operation when state can change after initial validation. Retain defense
  in depth when the controls do not share one failure cause.
- **Smallest safe correction:** Parse and validate at each applicable trust boundary. Pass a trusted
  representation to core logic. Remove downstream checks only after all bypass paths and time-of-use
  changes are excluded.
- **Validation:** Test malformed, boundary, and valid inputs at the public boundary. Test direct
  internal entry points when they are supported contracts. Run the repository-selected type and
  schema checks.
- **Routing owner:** Use realign to move or strengthen a validation boundary. Use simplify for
  duplicate checks only after evidence proves that the authoritative boundary is complete.
- **Applicable principles:** [P011](../../../docs/principles/README.md#p011),
  [P012](../../../docs/principles/README.md#p012),
  [P014](../../../docs/principles/README.md#p014),
  [P015](../../../docs/principles/README.md#p015),
  [P019](../../../docs/principles/README.md#p019),
  [P072](../../../docs/principles/README.md#p072),
  [P053](../../../docs/principles/README.md#p053),
  [P054](../../../docs/principles/README.md#p054), and
  [P076](../../../docs/principles/README.md#p076).
- **Sources:** [Athena architecture and simplicity profile](../../../docs/review/common.md#architecture-and-simplicity),
  [GitHub guidance for review of generated code](https://docs.github.com/en/copilot/tutorials/review-ai-generated-code),
  and [AISlop rule catalog](https://github.com/scanaislop/aislop/blob/v0.16.0/docs/rules.md).

## Hidden default or semantic fallback

- **Signal:** A catch, error branch, null-coalescing path, or feature fallback returns an empty,
  cached, permissive, or default result without a public contract for that result. The caller cannot
  distinguish success from degraded operation.
- **Required evidence:** Trace the reachable failure to the fallback and its consumers. Identify the
  stated result contract, security state, freshness rule, and observability requirement. A default
  value is not sufficient evidence when it is part of the documented contract.
- **Impact:** State the incorrect success signal, stale result, denied diagnostic, weakened security,
  or state divergence that the fallback causes.
- **Legitimate counterexample:** Retain a documented graceful-degradation mode when it keeps correct
  and secure operation. Retain a fail-safe outer boundary when its contract requires continued
  service, records sufficient evidence, and puts state in a safe condition.
- **Smallest safe correction:** Make the degraded outcome explicit or propagate the failure to the
  nearest responsible boundary. Remove a fallback only when all consumers can handle the corrected
  contract.
- **Validation:** Test dependency failure, stale data, invalid input, and degraded operation that
  apply. Verify the public status, error, state, and structured diagnostic.
- **Routing owner:** Use realign for fallback-policy or boundary repair. Use simplify only when
  the fallback is dead or redundant and safe deletion is complete.
- **Applicable principles:** [P014](../../../docs/principles/README.md#p014),
  [P019](../../../docs/principles/README.md#p019),
  [P029](../../../docs/principles/README.md#p029),
  [P030](../../../docs/principles/README.md#p030),
  [P031](../../../docs/principles/README.md#p031),
  [P032](../../../docs/principles/README.md#p032),
  [P033](../../../docs/principles/README.md#p033),
  [P034](../../../docs/principles/README.md#p034), and
  [P036](../../../docs/principles/README.md#p036).
- **Sources:** [Athena errors and reliability profile](../../../docs/review/common.md#errors-and-reliability),
  [AISlop rule catalog](https://github.com/scanaislop/aislop/blob/v0.16.0/docs/rules.md), and
  [a reproduced exception-handling regression report](https://github.com/anthropics/claude-code/issues/40355).

## Error handling without policy ownership

- **Signal:** A local function catches or converts all failures but cannot recover, retry, compensate,
  redact, translate a public contract, or stop correctly. An outer boundary handles unrelated
  failures with one outcome. Intermediate layers repeatedly change the error form.
- **Required evidence:** Map the initial cause through each boundary. For every handler, identify its
  policy decision and ability to complete that decision. Show the consumer contract and state after
  failure. Catch width alone is not sufficient evidence.
- **Impact:** State the lost cause, incorrect response, duplicate handling, unsafe continuation, or
  policy coupling that the boundary causes.
- **Legitimate counterexample:** Retain local handling when it completes a specified recovery or
  cleanup policy. Retain an outer safety boundary when it must isolate one request, task, or event and
  it records the failure before safe continuation.
- **Smallest safe correction:** Keep handling at the nearest boundary that owns the outcome. If the
  current layer has no outcome to select, preserve type, cause, and useful context, and propagate one
  time. Do not move all handling to the outermost boundary as a universal rule.
- **Validation:** Test each public error outcome, recovery path, cleanup path, and failure state.
  Verify language-specific cause chaining or error wrapping. Confirm that one policy owner handles
  each failure.
- **Routing owner:** Use realign for error-boundary repair. Use systematic-debugging before repair
  when evidence shows an active failure. Route a redundant catch that can be deleted without another
  structural change to simplify.
- **Applicable principles:** [P012](../../../docs/principles/README.md#p012),
  [P019](../../../docs/principles/README.md#p019),
  [P029](../../../docs/principles/README.md#p029),
  [P030](../../../docs/principles/README.md#p030),
  [P031](../../../docs/principles/README.md#p031),
  [P032](../../../docs/principles/README.md#p032).
- **Sources:** [Athena errors and reliability profile](../../../docs/review/common.md#errors-and-reliability),
  [Exception Handling Bugs in Python](https://doi.org/10.1016/j.infsof.2026.108264), and
  [a practitioner discussion of blanket catches](https://news.ycombinator.com/item?id=45535937).

## Duplicate handling or lost causal information

- **Signal:** Code catches, logs, and throws the same failure without a policy decision. It converts
  all causes to one string, Boolean, null value, or generic status. Several layers emit the same
  failure as separate incidents. A replacement error omits the initial cause.
- **Required evidence:** Trace error identity, cause, context, and diagnostics from source to the
  responsible boundary. Identify the information that a caller or operator needs. Similar log
  messages alone are not sufficient evidence.
- **Impact:** State the incorrect classification, duplicate alert, lost diagnosis, false success, or
  public-contract error that results.
- **Legitimate counterexample:** Retain a local span event, metric, or context addition when it has a
  distinct observability purpose and keeps correlation. Retain public translation that intentionally
  redacts sensitive detail while the internal cause remains available to the authorized operator.
- **Smallest safe correction:** Select one policy owner for handling. Preserve the language-specific
  causal chain when context or a public error type is added. Emit one operator incident with stable
  correlation. Do not expose secrets to preserve diagnostics.
- **Validation:** Test error classification and public translation. Inspect the cause chain and
  structured diagnostics. Confirm that failure telemetry is neither absent nor duplicated.
- **Routing owner:** Use realign for error-contract or observability ownership changes. Use
  simplify when removal of an unchanged catch or duplicate log is the complete safe correction.
- **Applicable principles:** [P014](../../../docs/principles/README.md#p014),
  [P019](../../../docs/principles/README.md#p019),
  [P029](../../../docs/principles/README.md#p029),
  [P030](../../../docs/principles/README.md#p030),
  [P031](../../../docs/principles/README.md#p031),
  [P032](../../../docs/principles/README.md#p032), and
  [P047](../../../docs/principles/README.md#p047).
- **Sources:** [Athena language-routing contract](../../../docs/review/language-routing.md),
  [AISlop rule catalog](https://github.com/scanaislop/aislop/blob/v0.16.0/docs/rules.md), and
  [a reproduced exception-handling regression report](https://github.com/anthropics/claude-code/issues/40355).

## Unsafe or duplicate retry policy

- **Signal:** A loop retries all failures, has no finite budget, or repeats a non-idempotent effect.
  Several layers retry the same operation. Timeouts cause retries that continue after the caller has
  stopped. A circuit breaker or backoff is added without dependency-failure evidence.
- **Required evidence:** Identify the retry owner, transient-failure classification, total deadline,
  attempt budget, idempotency or reconciliation mechanism, and retries in lower or higher layers.
  Show the duplicate effect or availability requirement. The presence or absence of retry code alone
  is not sufficient evidence.
- **Impact:** State the duplicate side effect, request amplification, delayed failure, capacity loss,
  or unmet availability contract.
- **Legitimate counterexample:** Retain a repository or client-library retry when it has the complete
  policy, obeys the caller deadline, and makes repeated effects safe. Do not require retry for a
  permanent failure or an operation that cannot repeat safely.
- **Smallest safe correction:** Give one responsible boundary the retry policy. Make the operation
  idempotent or reconcilable before retry. Classify transient failures and use a finite budget within
  the caller deadline. Add backoff or a circuit breaker only when operation evidence requires it.
- **Validation:** Use controlled failure injection. Test the maximum attempt count, permanent
  failure, deadline, cancellation, repeated side effects, and success after a transient failure.
- **Routing owner:** Use realign. Use systematic-debugging first for a reproduced retry defect.
  Use simplify when an extra retry layer can be removed with no other contract change.
- **Applicable principles:** [P012](../../../docs/principles/README.md#p012),
  [P014](../../../docs/principles/README.md#p014),
  [P019](../../../docs/principles/README.md#p019),
  [P029](../../../docs/principles/README.md#p029),
  [P030](../../../docs/principles/README.md#p030),
  [P037](../../../docs/principles/README.md#p037),
  [P038](../../../docs/principles/README.md#p038), and
  [P070](../../../docs/principles/README.md#p070).
- **Sources:** [Athena errors and reliability profile](../../../docs/review/common.md#errors-and-reliability)
  and [AWS guidance for timeouts and retries](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/).

## Missing or broken timeout and cancellation propagation

- **Signal:** An external operation, lock, queue wait, or child task has no applicable bound. Code
  catches or replaces cancellation. A child operation outlives its owner. A timeout is reported as
  success or as an unrelated failure.
- **Required evidence:** Identify the lifecycle owner, caller deadline, cancellation source, cleanup
  duties, and result contract. Show a reachable unbounded wait, orphaned operation, or lost
  cancellation. A function without a timeout parameter is not sufficient evidence.
- **Impact:** State the resource leak, capacity loss, stale write, delayed shutdown, or incorrect
  caller outcome.
- **Legitimate counterexample:** Retain a process-lifetime task, local bounded computation, or
  framework-managed deadline when its owner and termination contract are explicit. Retain a cleanup
  operation after cancellation when it has its own safe bound.
- **Smallest safe correction:** Propagate the existing cancellation or deadline through the supported
  interface. Give child work the owner lifecycle. On cancellation, stop new work and release owned
  resources. Preserve the cancellation outcome.
- **Validation:** Use controlled time and explicit synchronization. Test cancellation before start,
  during work, and during cleanup. Test deadline expiry and shutdown. Do not use a wall-clock sleep
  as the only proof.
- **Routing owner:** Use realign. Use systematic-debugging first when the repository has a
  reproduced hang or orphaned task. Use simplify only for a proven unused timeout wrapper.
- **Applicable principles:** [P012](../../../docs/principles/README.md#p012),
  [P014](../../../docs/principles/README.md#p014),
  [P019](../../../docs/principles/README.md#p019),
  [P029](../../../docs/principles/README.md#p029),
  [P030](../../../docs/principles/README.md#p030),
  [P039](../../../docs/principles/README.md#p039),
  [P070](../../../docs/principles/README.md#p070), and
  [P082](../../../docs/principles/README.md#p082).
- **Sources:** [Athena behavior-first testing contract](../../../docs/review/behavior-first-testing.md),
  [Athena language-routing contract](../../../docs/review/language-routing.md), and
  [AWS guidance for timeouts and retries](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/).

## Partial state change without atomicity or compensation

- **Signal:** One logical operation writes multiple state owners and can stop between writes. A catch
  continues after partial progress without a state contract. Compensation is best-effort but has no
  durable progress, idempotency, or reconciliation rule.
- **Required evidence:** Identify the invariant, commit boundaries, irreversible step, each failure
  point, and state after interruption. Show that one transaction is possible or that the distributed
  workflow needs compensation. Multiple writes are not sufficient evidence when partial progress is
  the documented state.
- **Impact:** State the lost update, duplicate effect, unrecoverable state, incorrect resume, or
  operator action that can result.
- **Legitimate counterexample:** Retain an eventually consistent or resumable workflow when progress,
  reconciliation, idempotency, and operator recovery are explicit and tested. Retain independent
  writes when they do not share an invariant.
- **Smallest safe correction:** Use one existing transaction when all changes share its boundary. If
  one transaction is not possible, record durable progress and define idempotent compensation or
  roll-forward. Put the irreversible action after applicable validation and reversible work.
- **Validation:** Inject a failure at each material step. Test retry, compensation, resume, duplicate
  delivery, and rollback or roll-forward. Verify the invariant after each outcome.
- **Routing owner:** Use realign. Use systematic-debugging first for reproduced data loss or state
  corruption. A dead rollback path can use simplify only after the replacement recovery contract is
  proved.
- **Applicable principles:** [P011](../../../docs/principles/README.md#p011),
  [P012](../../../docs/principles/README.md#p012),
  [P014](../../../docs/principles/README.md#p014),
  [P019](../../../docs/principles/README.md#p019),
  [P021](../../../docs/principles/README.md#p021),
  [P044](../../../docs/principles/README.md#p044),
  [P045](../../../docs/principles/README.md#p045),
  [P046](../../../docs/principles/README.md#p046),
  [P070](../../../docs/principles/README.md#p070), and
  [P083](../../../docs/principles/README.md#p083).
- **Sources:** [Athena errors and reliability profile](../../../docs/review/common.md#errors-and-reliability)
  and [Microsoft compensating-transaction guidance](https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction).

## Unclear resource or task lifetime

- **Signal:** A file, connection, lock, transaction, subscription, temporary file, child process, or
  asynchronous task has no clear owner. Cleanup occurs only on success. Cleanup failure replaces the
  initial failure without an explicit policy. A detached task has no result consumer.
- **Required evidence:** Trace acquisition, ownership transfer, use, release, and all failure exits.
  Identify the repository or language lifetime convention. Show a reachable leak, deadlock, orphan,
  lost failure, or invalid cleanup order. Manual cleanup alone is not sufficient evidence.
- **Impact:** State the resource exhaustion, blocked progress, data loss, duplicate work, or lost
  diagnostic that can result.
- **Legitimate counterexample:** Retain a process-lifetime pool, framework-owned resource, or detached
  operation when its owner, shutdown, failure, and capacity contracts are explicit. Retain explicit
  cleanup when the language does not supply a safer construct.
- **Smallest safe correction:** Give the resource one owner. Use the repository's existing scoped
  lifetime mechanism. Release resources on every applicable exit. Preserve the initial cause when
  cleanup also fails, according to the public error policy.
- **Validation:** Test success, operation failure, cleanup failure, cancellation, and repeated use.
  Use repository tools that can detect leaks, races, or unreleased locks when the execution boundary
  permits them.
- **Routing owner:** Use realign. Use systematic-debugging first for a reproduced leak, race, or
  deadlock. Use simplify when an unused resource layer can be removed safely.
- **Applicable principles:** [P012](../../../docs/principles/README.md#p012),
  [P014](../../../docs/principles/README.md#p014),
  [P019](../../../docs/principles/README.md#p019),
  [P029](../../../docs/principles/README.md#p029),
  [P030](../../../docs/principles/README.md#p030),
  [P032](../../../docs/principles/README.md#p032), and
  [P079](../../../docs/principles/README.md#p079).
- **Sources:** [Athena language-routing contract](../../../docs/review/language-routing.md),
  [Athena errors and reliability profile](../../../docs/review/common.md#errors-and-reliability), and
  [Exception Handling Bugs in Python](https://doi.org/10.1016/j.infsof.2026.108264).

## Detached or uncoordinated concurrent work

- **Signal:** Code starts parallel work without a measured need, shared-state contract, result owner,
  sibling-failure policy, cancellation rule, or capacity bound. One task failure is ignored while
  other tasks continue to change state.
- **Required evidence:** Identify the concurrency requirement, task owner, shared state,
  synchronization, maximum work, failure aggregation, and cancellation path. Show a reachable race,
  orphan, duplicate effect, or resource growth. Parallel syntax alone is not sufficient evidence.
- **Impact:** State the incorrect result, state race, failure loss, shutdown delay, or capacity
  problem.
- **Legitimate counterexample:** Retain repository-standard structured concurrency or a supervised
  background task when ownership, failure, cancellation, and resource limits are explicit. Retain
  concurrency when reproducible measurements show its need.
- **Smallest safe correction:** Use the existing lifecycle owner and structured concurrency
  mechanism. Collect every result. Define sibling behavior after failure. Propagate cancellation and
  cap concurrent work. Remove concurrency only when behavior and measured requirements permit it.
- **Validation:** Use deterministic synchronization and race detection when available. Test one and
  multiple failures, cancellation, shutdown, capacity, and ordering-independent outcomes.
- **Routing owner:** Use realign. Use systematic-debugging first for a reproduced race or lost
  result. Use simplify when unnecessary concurrency can be removed with no behavior change.
- **Applicable principles:** [P012](../../../docs/principles/README.md#p012),
  [P014](../../../docs/principles/README.md#p014),
  [P019](../../../docs/principles/README.md#p019),
  [P020](../../../docs/principles/README.md#p020),
  [P070](../../../docs/principles/README.md#p070),
  [P072](../../../docs/principles/README.md#p072),
  [P080](../../../docs/principles/README.md#p080), and
  [P082](../../../docs/principles/README.md#p082).
- **Sources:** [Athena errors and reliability profile](../../../docs/review/common.md#errors-and-reliability),
  [Athena behavior-first testing contract](../../../docs/review/behavior-first-testing.md),
  [Athena language-routing contract](../../../docs/review/language-routing.md), and
  [Notes on structured concurrency](https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/).
