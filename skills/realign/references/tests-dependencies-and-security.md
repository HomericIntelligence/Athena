# Tests, dependencies, security, and evidence

Read the [shared review contract](../../../docs/review/common.md), the
[behavior-first testing contract](../../../docs/review/behavior-first-testing.md), and the
[language-routing contract](../../../docs/review/language-routing.md) before you use this catalog.
Apply the [ASD-STE100 technical-English policy](../../TECHNICAL_ENGLISH.md) to the assessment and
repair output.

Use each pattern as an investigation signal. Do not infer authorship from a pattern. Do not make a
finding until the required evidence shows an effect on behavior, architecture, security, or
maintenance. A scanner result, metric, test name, or passing command is not sufficient evidence.

## Test theater, weak oracles, and mock-only proof

- **Signal:** A test asserts mock calls, private call order, snapshots of internal layout, or fixed
  values without an observable product result. Expected values come from the implementation or the
  same speculative hypothesis as the change. A snapshot or golden file has no authoritative
  contract. The product path can be absent or wrong while the test stays green.
- **Required evidence:** Identify the product contract. Trace the test input through real product
  code to the assertion. Bind an independent oracle, property, metamorphic relation, canonical
  implementation, or authoritative example. Show the missing connection between the assertion and
  the contract. Inspect the substitute boundary, test runner, and applicable callers. Try a bounded
  falsification or negative control before you trust the oracle.
- **Impact:** A regression can pass the suite. A refactor can require test changes although product
  behavior does not change. A self-derived oracle can certify the same incorrect assumption as the
  implementation.
- **Legitimate counterexample:** A controlled substitute represents a real external boundary. The
  test exercises core product code and asserts the observable result or failure contract. An
  approved snapshot or golden file is itself the public compatibility contract.
- **Smallest safe correction:** Keep substitutes only at external boundaries. Assert the observable
  contract. Derive expected results independently from the implementation. Add the smallest
  falsifying, boundary, or property case that distinguishes the incorrect hypothesis. Remove
  duplicate implementation assertions only after the behavior test gives equivalent coverage.
- **Validation:** Run the focused test and confirm that it selects an applicable test. Exercise the
  product path and the applicable failure path. Confirm that a controlled wrong implementation or
  counterexample makes the test fail. Use repository-approved mutation testing only when it is
  already available and proportionate to the risk.
- **Routing owner:** Use `realign` for test-architecture repair. Use `systematic-debugging` when the
  test exposes an observed defect. Use `simplify` for proven duplicate or obsolete tests.
- **Applicable principles:** [P022](../../../docs/principles/README.md#p022),
  [P027](../../../docs/principles/README.md#p027),
  [P028](../../../docs/principles/README.md#p028),
  [P064](../../../docs/principles/README.md#p064), and
  [P067](../../../docs/principles/README.md#p067).
- **Sources:** [Athena behavior-first testing](../../../docs/review/behavior-first-testing.md),
  [Are Coding Agents Generating Over-Mocked Tests? An Empirical Study](https://andrehora.github.io/pub/2026-msr-agents-over-mocked-tests.pdf),
  [EvalPlus](https://arxiv.org/abs/2305.01210), and
  [OpenAI Codex issue 40639](https://github.com/openai/codex/issues/40639).

## Asynchronous false-green tests and empty selection

- **Signal:** A test starts asynchronous work but does not await or join it. An exception occurs
  after the runner reports success. A filtered command selects no tests. A test fixture hides
  cancellation, timeout, or cleanup behavior.
- **Required evidence:** Inspect the test signature, scheduler boundary, returned task or promise,
  runner configuration, and assertion path. Record the selected-test count. Trace asynchronous
  failures to the runner result.
- **Impact:** The suite can report success before the behavior finishes. Failure, cancellation, and
  cleanup regressions can be invisible.
- **Legitimate counterexample:** A framework-required event handler cannot return an awaitable value,
  and a separate observable completion contract captures its result and errors.
- **Smallest safe correction:** Await or join all work that is part of the contract. Replace ambient
  delays with explicit synchronization. Make failures reach the test runner. Make filtered commands
  prove that they selected the intended test.
- **Validation:** Run the focused test with a controlled failure, timeout, and cancellation when
  these paths apply. Confirm deterministic completion and a nonzero applicable-test count.
- **Routing owner:** Use `realign` for test-lifecycle repair. Use `systematic-debugging` for a
  reproduced product defect.
- **Applicable principles:** [P022](../../../docs/principles/README.md#p022),
  [P027](../../../docs/principles/README.md#p027),
  [P028](../../../docs/principles/README.md#p028),
  [P064](../../../docs/principles/README.md#p064), and
  [P065](../../../docs/principles/README.md#p065).
- **Sources:** [Athena behavior-first testing](../../../docs/review/behavior-first-testing.md),
  the [AISlop 0.16.0 rules reference](https://github.com/scanaislop/aislop/blob/v0.16.0/docs/rules.md),
  and [Unit Testing Asynchronous Code](https://learn.microsoft.com/en-us/archive/msdn-magazine/2014/november/async-programming-unit-testing-asynchronous-code).

## Weakened validation gates

- **Signal:** A change skips, deletes, disables, or marks an applicable test as an expected failure.
  It lowers a threshold, adds a silent continuation, excludes an applicable path, or suppresses a
  diagnostic without an approved exception.
- **Required evidence:** Bind the gate definition, repository policy, current result, change history,
  and affected requirement. Show that the change reduces applicable coverage or changes a failure
  into success. Distinguish a pre-existing failure from a new regression.
- **Impact:** Continuous integration (CI) can accept a defect or a policy violation. A passing badge
  can give false confidence.
- **Legitimate counterexample:** Evidence proves that a test or check is obsolete, inapplicable, or
  replaced with equal or stronger coverage. An authoritative process records a narrow exception with
  an owner and an end condition.
- **Smallest safe correction:** Correct the product or gate cause. Restore the applicable check. If
  the contract changed, replace the old check with a behavior test that traces to the new contract.
- **Validation:** Run the focused check and all required repository gates. Record the command,
  revision, environment, exit status, and unedited output.
- **Routing owner:** Use `realign` for validation-architecture repair. Use `simplify` only after
  evidence proves that a gate artifact is obsolete. Require qualified review when the gate protects
  security or availability.
- **Applicable principles:** [P063](../../../docs/principles/README.md#p063),
  [P064](../../../docs/principles/README.md#p064),
  [P065](../../../docs/principles/README.md#p065),
  [P067](../../../docs/principles/README.md#p067),
  [P068](../../../docs/principles/README.md#p068),
  [P069](../../../docs/principles/README.md#p069), and
  [P070](../../../docs/principles/README.md#p070).
- **Sources:** [GitHub guidance for review of AI-generated code](https://docs.github.com/en/copilot/tutorials/review-ai-generated-code).

## Fictional APIs, dependencies, and missed reuse

- **Signal:** Code imports an undeclared or unresolved package. It calls a symbol that the bound
  dependency version does not provide. It adds a package or wrapper although the repository,
  language, framework, or standard library already owns the capability.
- **Required evidence:** Inspect manifests, locks, generated sources, package resolution, the exact
  dependency version, authoritative API documentation, current repository mechanisms, and runtime
  consumers. Confirm that dynamic loading or generation does not supply the symbol.
- **Impact:** Builds or runtime paths can fail. A new package can add maintenance, license, security,
  and supply-chain work. Duplicate mechanisms can cause architecture drift.
- **Legitimate counterexample:** The import is an intentional optional peer, plug-in, generated
  surface, platform branch, or vendored capability with a documented loading and validation contract.
- **Smallest safe correction:** Use the existing narrow mechanism when it meets the requirement.
  Correct the API call to the bound version. Add a dependency only when a current requirement and its
  supply-chain evidence make that addition necessary.
- **Validation:** Resolve and build from the bound lockfile in an authorized isolated environment.
  Exercise the reachable behavior. Verify that no stale import, symbol, or wrapper remains.
- **Routing owner:** Use `simplify` for an unused dependency or a safely removable duplicate. Use `realign`
  for dependency-direction, ownership, or interface repair. Use `systematic-debugging` for a
  reproduced behavior defect.
- **Applicable principles:** [P012](../../../docs/principles/README.md#p012),
  [P015](../../../docs/principles/README.md#p015),
  [P057](../../../docs/principles/README.md#p057), and
  [P074](../../../docs/principles/README.md#p074).
- **Sources:** [GitHub guidance for review of AI-generated code](https://docs.github.com/en/copilot/tutorials/review-ai-generated-code)
  and [We Have a Package for You!](https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen).

## Dependency trust and provenance

- **Signal:** A change adds or updates a dependency, uses a mutable source reference, leaves a lock
  mismatch, trusts a package name as identity, enables an install-time script, or adds permissions
  and transitive dependencies without a stated need.
- **Required evidence:** Bind the package identity, source, version, lock entry, checksum or signature,
  provenance, license, maintainer status, advisories, lifecycle scripts, permissions, transitive
  graph, and the current requirement. Inspect repository dependency policy.
- **Impact:** The change can execute untrusted code, introduce a vulnerable or deceptive package,
  expand privileges, or create an unmaintained build input.
- **Legitimate counterexample:** Repository policy already approves the exact pinned artifact. The
  dependency is necessary, its provenance is verified, its authority is bounded, and no existing
  mechanism meets the requirement.
- **Smallest safe correction:** Remove or replace an unnecessary dependency. Otherwise, pin and lock
  the approved artifact. Keep provenance and integrity evidence. Disable unnecessary lifecycle
  behavior and permissions. Do not install a package under `realign` authority alone.
- **Validation:** Use repository-approved software composition analysis and lock verification. In an
  authorized isolated environment, reproduce installation and required behavior from the lock.
- **Routing owner:** Use `simplify` for proven removal. Use `realign` for dependency-boundary repair. Stop for
  explicit authority when the correction needs an installation, license decision, credential, or
  external write.
- **Applicable principles:** [P048](../../../docs/principles/README.md#p048),
  [P050](../../../docs/principles/README.md#p050),
  [P055](../../../docs/principles/README.md#p055),
  [P057](../../../docs/principles/README.md#p057),
  [P061](../../../docs/principles/README.md#p061), and
  [P062](../../../docs/principles/README.md#p062).
- **Sources:** [GitHub guidance for review of AI-generated code](https://docs.github.com/en/copilot/tutorials/review-ai-generated-code)
  and [We Have a Package for You!](https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen).

## Trust boundaries, authorization, and secrets

- **Signal:** Code removes or bypasses authorization. It accepts untrusted data without boundary
  validation. It fails open when security state is unknown. Untrusted input reaches an evaluation,
  command, query, markup, or deserialization sink. A credential or sensitive value appears in code,
  a fixture, a prompt, a log, or an artifact.
- **Required evidence:** Trace the untrusted source to the protected operation or sink. Bind the
  authorization policy, trust boundary, data classification, validation and encoding rules, failure
  state, and credential owner. Do not print or copy a suspected secret.
- **Impact:** The defect can disclose data, grant an unauthorized capability, execute injected input,
  or expose a credential.
- **Legitimate counterexample:** The value is a documented non-secret test token that cannot grant a
  capability. A typed and validated value reaches a context-safe API. An authoritative boundary
  performs complete mediation.
- **Smallest safe correction:** Restore authorization at the authoritative boundary. Parse, validate,
  constrain, and safely encode untrusted data. Use parameterized APIs. Remove a secret from source and
  history only through an authorized security procedure. Rotate or revoke an exposed credential.
- **Validation:** Add or run behavior tests for denied access, invalid input, failure state, and safe
  encoding. Run repository-approved secret and security checks. Do not put secret material in the
  validation receipt.
- **Routing owner:** Use `realign` with a qualified security reviewer. Treat a possible live secret or a
  material authorization bypass as a stop condition. Deleting a secret from one file is not complete
  remediation because it does not revoke the credential or remove history.
- **Applicable principles:** [P035](../../../docs/principles/README.md#p035),
  [P048](../../../docs/principles/README.md#p048),
  [P049](../../../docs/principles/README.md#p049),
  [P050](../../../docs/principles/README.md#p050),
  [P051](../../../docs/principles/README.md#p051),
  [P053](../../../docs/principles/README.md#p053),
  [P056](../../../docs/principles/README.md#p056), and
  [P069](../../../docs/principles/README.md#p069).
- **Sources:** [AISlop 0.16.0 security rules](https://github.com/scanaislop/aislop/blob/v0.16.0/docs/rules.md#security)
  and the [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html).

## Performance changes without evidence

- **Signal:** A change adds a cache, concurrency, batching, pooling, manual memory control, or a more
  complex algorithm without a measured constraint. A claim uses only a complexity warning, intuition,
  or a benchmark result that is not bound to the reviewed revision.
- **Required evidence:** Identify the product constraint and representative workload. Bind the
  baseline and candidate revisions, environment, benchmark command, samples, variance, resource
  limits, and correctness checks. Separate latency, throughput, memory, and cost claims.
- **Impact:** Speculative optimization can add state, races, invalidation defects, and maintenance
  work without a useful result.
- **Legitimate counterexample:** A current requirement or verified resource bound requires the design.
  Evidence shows the constraint, and the repository already uses the selected mechanism.
- **Smallest safe correction:** Remove speculative complexity when it has no current requirement.
  Otherwise, measure first and make the smallest change that satisfies the measured constraint.
- **Validation:** Reproduce the baseline and candidate measurements in the same controlled
  environment. Run behavior, failure, concurrency, and resource-limit tests that the change affects.
- **Routing owner:** Use `realign` for an evidenced structural correction. Use `simplify` to remove
  speculative machinery. Use `retain` when evidence does not support a change.
- **Applicable principles:** [P065](../../../docs/principles/README.md#p065),
  [P072](../../../docs/principles/README.md#p072),
  [P073](../../../docs/principles/README.md#p073), and
  [P080](../../../docs/principles/README.md#p080).
- **Sources:** [Athena evidence-integrity policy](../../../docs/policies/evidence-integrity.md) and
  [Brendan Gregg's performance-analysis methodology](https://www.brendangregg.com/methodology.html).

## Comments, documentation, and excessive churn

- **Signal:** A comment only narrates mechanics, refers to an agent or implementation phase, or
  repeats a symbol name. Documentation claims behavior that the product does not have. A change
  includes unrelated formatting, renames, compatibility residue, TODO stubs, or broad rewrites.
- **Required evidence:** Compare the prose with code, contracts, public behavior, history, generation
  policy, and the requested scope. Identify the maintenance or review effect. Do not use comment
  length or changed-line count alone.
- **Impact:** Misleading prose can hide an invariant or false behavior claim. Unrelated churn can
  conceal a defect, create conflicts, and make ownership history difficult to inspect.
- **Legitimate counterexample:** A comment records rationale, a non-obvious invariant, a security
  constraint, compatibility evidence, or a required generation notice. A mechanical rewrite is a
  separately authorized migration with reproducible validation.
- **Smallest safe correction:** Make code show its mechanics. Keep necessary rationale. Correct
  behavior claims. Remove obsolete prose and unrelated residue only after consumer and history
  evidence makes deletion safe.
- **Validation:** Run documentation, link, example, formatting, and behavior checks that the changed
  surface activates. Inspect the final diff for unrelated paths and stale identifiers.
- **Routing owner:** Use `simplify` for safe deletion, consolidation, or churn removal. Use `realign` only
  when prose or churn conceals an architecture, invariant, or contract defect. Otherwise, use
  `retain`.
- **Applicable principles:** [P010](../../../docs/principles/README.md#p010),
  [P014](../../../docs/principles/README.md#p014),
  [P066](../../../docs/principles/README.md#p066),
  [P070](../../../docs/principles/README.md#p070),
  [P086](../../../docs/principles/README.md#p086),
  [P087](../../../docs/principles/README.md#p087),
  [P088](../../../docs/principles/README.md#p088), and
  [P090](../../../docs/principles/README.md#p090).
- **Sources:** [AISlop 0.16.0 rules](https://github.com/scanaislop/aislop/blob/v0.16.0/docs/rules.md),
  [SlopCodeBench](https://arxiv.org/abs/2603.24755), and a
  [practitioner discussion](https://news.ycombinator.com/item?id=45535937).

## Catalog boundary

Do not create a finding because a repository contains mocks, comments, dependencies, asynchronous
code, or optimization. Do not remove a security check as simplification. Do not add a dependency to
repair an unsupported scanner diagnostic. Route an observed defect through the workflow that owns
behavior repair. Route a safe subtraction through `simplify`.
