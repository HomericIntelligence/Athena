# Architecture and structure catalog

Use this catalog after the
[shared architecture gate](../../../docs/review/common.md#architecture-gate). Use the
[language-routing contract](../../../docs/review/language-routing.md) for language-specific evidence.
This catalog supplies candidate patterns. It does not replace repository architecture or a design
decision.

Do not infer code authorship from a pattern. A metric, style feature, or generated diagnostic is a
signal only. Confirm each candidate with repository contracts, callers, tests, history, and
reachable behavior. If evidence does not support a change, use the `retain` disposition.

## Architecture boundary or dependency-direction drift

- **Signal:** A component imports an implementation detail from another layer. An entry point owns
  domain policy. A low-level component controls a high-level decision. A new path bypasses an
  established port, adapter, service, or module boundary.
- **Required evidence:** Identify the repository rule, architecture decision record (ADR), module
  graph, public interface, or stable convention that defines the boundary. Trace the relevant
  callers and data flow. Show the dependency direction that the candidate violates. A directory
  name or import count is not sufficient evidence.
- **Impact:** State the observed effect on change isolation, replacement, testing, security, or
  behavior. Do not claim a future cycle or failure without evidence.
- **Legitimate counterexample:** Retain the code when an accepted ADR changes the architecture, an
  adapter must cross the boundary, or the repository shows that the apparent layers are not
  architectural boundaries.
- **Smallest safe correction:** Route the dependency through the established interface. Move the
  decision to its documented owner. Add a new boundary only when a current requirement or accepted
  design requires it.
- **Validation:** Run applicable architecture checks. Test the observable behavior at the corrected
  boundary. Inspect all known consumers and dependency paths again.
- **Routing owner:** Use `realign` for a structural correction. If the complete correction is safe
  deletion or reuse, route it to `simplify`. If the evidence shows a current behavior defect, use
  `systematic-debugging` before repair.
- **Applicable principles:** [P012](../../../docs/principles/README.md#p012),
  [P014](../../../docs/principles/README.md#p014),
  [P015](../../../docs/principles/README.md#p015),
  [P019](../../../docs/principles/README.md#p019),
  [P020](../../../docs/principles/README.md#p020), and
  [P072](../../../docs/principles/README.md#p072).
- **Sources:** [Athena shared architecture gate](../../../docs/review/common.md#architecture-gate),
  [GitHub guidance for review of generated code](https://docs.github.com/en/copilot/tutorials/review-ai-generated-code),
  and [a practitioner report about imported architecture and conventions](https://github.com/openai/codex/issues/13823).

## Misplaced responsibility or mixed policy and mechanism

- **Signal:** One function or component selects policy, performs transport or storage work, formats
  results, and controls retries or authorization. A mechanism has repository-specific decisions that
  belong to a caller or policy owner. A policy is repeated in multiple mechanisms.
- **Required evidence:** Identify each cause for change and its authoritative owner. Trace the
  inputs, side effects, and consumers. Show that the responsibilities change independently or that
  repeated policy has different values. Function size or the number of branches is not sufficient
  evidence.
- **Impact:** State the observed coupling, duplicate authority, inconsistent outcome, or blocked
  substitution. Bind the impact to a consumer or maintenance action.
- **Legitimate counterexample:** Retain a cohesive operation when the steps implement one atomic
  policy, when separation would expose an unstable representation, or when a framework defines the
  lifecycle owner.
- **Smallest safe correction:** Put each policy decision in its existing owner. Give a mechanism the
  minimum input that it needs. Keep one transaction or lifecycle boundary when correctness requires
  it. Do not add a new service only to make a function shorter.
- **Validation:** Use behavior tests for each public outcome. Test policy selection separately from
  mechanism failure only when those are observable contracts. Confirm that authorization,
  transaction, and lifecycle boundaries did not move by accident.
- **Routing owner:** Use `realign`. Route a redundant wrapper or duplicate policy that needs only
  deletion to `simplify`.
- **Applicable principles:** [P011](../../../docs/principles/README.md#p011),
  [P012](../../../docs/principles/README.md#p012),
  [P015](../../../docs/principles/README.md#p015),
  [P016](../../../docs/principles/README.md#p016),
  [P019](../../../docs/principles/README.md#p019),
  [P021](../../../docs/principles/README.md#p021),
  [P070](../../../docs/principles/README.md#p070), and
  [P077](../../../docs/principles/README.md#p077).
- **Sources:** [Athena architecture and simplicity profile](../../../docs/review/common.md#architecture-and-simplicity)
  and [SlopCodeBench](https://arxiv.org/abs/2603.24755).

## Duplicate invariant or mutable-state ownership

- **Signal:** Two components can write the same logical fact. A cache, index, configuration value,
  status flag, or derived field becomes an independent authority. Callers must select which copy is
  current. Repair code repeatedly synchronizes representations.
- **Required evidence:** List all writers and readers. Identify the invariant, the intended source of
  truth, update order, failure behavior, and reconciliation rule. Reproduce a divergent state or
  show a reachable path that permits one. Similar field names are not sufficient evidence.
- **Impact:** State the incorrect decision, stale result, race, recovery problem, or maintenance
  burden that the duplicate authority causes.
- **Legitimate counterexample:** Retain an immutable snapshot, derived cache, read replica, or event
  projection when its owner, freshness rule, invalidation, and reconciliation behavior are explicit
  and tested.
- **Smallest safe correction:** Select the established state owner. Derive other representations
  from it. If a migration is necessary, use a reversible sequence with explicit dual-read or
  dual-write termination criteria. Do not remove recovery data that has a documented purpose.
- **Validation:** Test the invariant across success, failure, restart, and concurrent update paths
  that apply. Verify migration and rollback behavior. Reinspect every writer after the correction.
- **Routing owner:** Use `realign` for ownership or migration changes. Use `simplify` only when
  evidence proves that a duplicate representation and all its consumers can be removed safely.
- **Applicable principles:** [P012](../../../docs/principles/README.md#p012),
  [P014](../../../docs/principles/README.md#p014),
  [P015](../../../docs/principles/README.md#p015),
  [P019](../../../docs/principles/README.md#p019),
  [P021](../../../docs/principles/README.md#p021),
  [P072](../../../docs/principles/README.md#p072), and
  [P078](../../../docs/principles/README.md#p078).
- **Sources:** [Athena architecture and simplicity profile](../../../docs/review/common.md#architecture-and-simplicity),
  [Athena behavior-first testing contract](../../../docs/review/behavior-first-testing.md), and
  [Microsoft CQRS pattern guidance](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs).

## Public-contract or representation leak

- **Signal:** A public interface exposes database records, framework request objects, transport
  errors, internal flags, or mutable collections. A caller must know an implementation detail to use
  the interface. A refactor changes public shape without a stated requirement.
- **Required evidence:** Bind the public contract and its consumers. Identify the implementation
  detail that crosses the boundary. Show how the leak restricts replacement or changes observable
  behavior. Do not treat every concrete type as a leak.
- **Impact:** State the compatibility, coupling, security, or maintenance effect for an identified
  consumer.
- **Legitimate counterexample:** Retain a concrete or framework type when it is the documented public
  contract, when conversion would remove necessary semantics, or when an accepted design changes the
  contract.
- **Smallest safe correction:** Restore the established data or error contract at the boundary. Use
  an existing domain type or adapter. If a public migration is required, compatibility,
  deprecation, rollout, and rollback evidence is necessary, but it does not replace separate
  authority for the public API migration. Stop until both are present.
- **Validation:** Run public contract tests and consumer checks. Verify serialization, error,
  compatibility, and boundary-value behavior that applies.
- **Routing owner:** Use `realign`. A public interface removal is not a `simplify` repair unless the
  report proves that it has no consumers and the repository permits removal.
- **Applicable principles:** [P010](../../../docs/principles/README.md#p010),
  [P012](../../../docs/principles/README.md#p012),
  [P014](../../../docs/principles/README.md#p014),
  [P015](../../../docs/principles/README.md#p015),
  [P018](../../../docs/principles/README.md#p018),
  [P019](../../../docs/principles/README.md#p019), and
  [P021](../../../docs/principles/README.md#p021).
- **Sources:** [Athena shared review contract](../../../docs/review/common.md),
  [GitHub guidance for review of generated code](https://docs.github.com/en/copilot/tutorials/review-ai-generated-code),
  and [a practitioner report about public-interface drift](https://news.ycombinator.com/item?id=48322956).

## Speculative or pass-through abstraction

- **Signal:** A factory, manager, provider, adapter, interface, or wrapper has one implementation and
  no current extension requirement. Its methods only pass arguments and results through. It adds a
  name or configuration path but owns no policy, invariant, translation, lifecycle, or test seam.
- **Required evidence:** Inspect all implementations, consumers, history, and current requirements.
  Identify what the abstraction owns. Compare the direct alternative with the current design. A
  one-implementation interface or short wrapper is not sufficient evidence by itself.
- **Impact:** State the additional concept, navigation cost, configuration, test substitution, or
  maintenance action that has no demonstrated purpose.
- **Legitimate counterexample:** Retain an abstraction that owns authorization, tracing, stability,
  cross-process translation, resource lifetime, a framework contract, or a documented extension
  seam. Retain duplication when a shared abstraction would join different concepts.
- **Smallest safe correction:** Reuse the direct existing capability. Remove the pass-through layer
  only after its consumers and hidden contracts are known. If the abstraction is in the correct
  place but has too much responsibility, correct its boundary instead of deleting it.
- **Validation:** Run behavior tests through the public boundary. Verify dependency wiring,
  observability, authorization, compatibility, and resource cleanup that the layer previously owned.
- **Routing owner:** Use `simplify` when safe deletion or consolidation is the complete correction.
  Use `realign` when responsibility or a boundary must move.
- **Applicable principles:** [P002](../../../docs/principles/README.md#p002),
  [P010](../../../docs/principles/README.md#p010),
  [P011](../../../docs/principles/README.md#p011),
  [P012](../../../docs/principles/README.md#p012),
  [P013](../../../docs/principles/README.md#p013),
  [P015](../../../docs/principles/README.md#p015),
  [P019](../../../docs/principles/README.md#p019),
  [P072](../../../docs/principles/README.md#p072), and
  [P074](../../../docs/principles/README.md#p074).
- **Sources:** [Athena simplification coverage](../../../docs/review/common.md#simplification-coverage),
  [AISlop rule catalog](https://github.com/scanaislop/aislop/blob/v0.16.0/docs/rules.md), and
  [a practitioner discussion of unnecessary generated abstractions](https://news.ycombinator.com/item?id=48322956).

## Missed reuse or copied authority

- **Signal:** New code repeats an existing parser, validator, formatter, query, schema, business rule,
  or test helper. The copies can change the same decision independently. A new dependency duplicates
  a narrow repository capability.
- **Required evidence:** Compare semantics, failure behavior, lifecycle, consumers, and expected
  evolution. Identify the canonical capability or rule. Show that reuse preserves the applicable
  contract. Text similarity or a duplication percentage is not sufficient evidence.
- **Impact:** State the observed or reachable inconsistent behavior, duplicate maintenance, larger
  dependency surface, or test burden.
- **Legitimate counterexample:** Retain duplication when the cases have different policy owners,
  trust boundaries, release cycles, failure domains, or expected changes. Retain a direct copy when
  an abstraction would be premature.
- **Smallest safe correction:** Use the existing narrow capability. Consolidate only the stable
  shared concept at its authoritative owner. Do not create a generic utility that hides domain
  semantics.
- **Validation:** Run the consumer behavior and failure-path tests for all consolidated cases. Check
  that the selected owner does not gain an invalid dependency.
- **Routing owner:** Use `simplify` for direct reuse or safe consolidation. Use `realign` when the
  correction changes ownership, dependency direction, or a public contract.
- **Applicable principles:** [P003](../../../docs/principles/README.md#p003),
  [P011](../../../docs/principles/README.md#p011),
  [P012](../../../docs/principles/README.md#p012),
  [P013](../../../docs/principles/README.md#p013),
  [P014](../../../docs/principles/README.md#p014),
  [P015](../../../docs/principles/README.md#p015),
  [P019](../../../docs/principles/README.md#p019),
  [P070](../../../docs/principles/README.md#p070), and
  [P074](../../../docs/principles/README.md#p074).
- **Sources:** [More Code, Less Reuse](https://arxiv.org/abs/2601.21276),
  [Athena simplification coverage](../../../docs/review/common.md#simplification-coverage), and
  [a practitioner discussion of duplicate generated helpers](https://news.ycombinator.com/item?id=48322956).

## Weak type or invalid domain-state representation

- **Signal:** Core logic uses unchecked strings, maps, sentinel values, unrelated Boolean flags,
  broad nullable values, unsafe casts, or type suppression for a defined domain concept. Invalid
  combinations can pass the construction boundary. Validation is repeated after the boundary.
- **Required evidence:** Identify the domain contract and construction boundary. Show a reachable
  invalid state, a suppressed type error, or repeated checks that protect the same invariant. A
  dynamic type or cast at an external boundary is not sufficient evidence.
- **Impact:** State the incorrect branch, invalid transition, lost diagnostic, or maintenance burden
  that the representation permits.
- **Legitimate counterexample:** Retain dynamic data at an untyped interoperability boundary when
  the code parses and validates it before core use. Retain a cast that the language or framework
  requires when evidence proves its precondition.
- **Smallest safe correction:** Use an existing domain type, schema, constructor, or state model at
  the authoritative boundary. Parse and validate once. Keep public compatibility unless the approved
  candidate includes a migration contract.
- **Validation:** Add or run boundary-value and invalid-state tests. Use the repository-selected type
  checker or compiler. Verify serialization and public error behavior.
- **Routing owner:** Use `realign`. Use `simplify` for duplicate validation only after the
  authoritative validation boundary is proved.
- **Applicable principles:** [P012](../../../docs/principles/README.md#p012),
  [P014](../../../docs/principles/README.md#p014),
  [P015](../../../docs/principles/README.md#p015),
  [P019](../../../docs/principles/README.md#p019),
  [P020](../../../docs/principles/README.md#p020),
  [P070](../../../docs/principles/README.md#p070),
  [P075](../../../docs/principles/README.md#p075), and
  [P076](../../../docs/principles/README.md#p076).
- **Sources:** [Athena language-routing contract](../../../docs/review/language-routing.md),
  [AISlop rule catalog](https://github.com/scanaislop/aislop/blob/v0.16.0/docs/rules.md), and
  [GitHub guidance for review of generated code](https://docs.github.com/en/copilot/tutorials/review-ai-generated-code).

## Hidden dependency or nonlocal control

- **Signal:** Core behavior reads process-wide state, environment variables, a service locator, a
  mutable singleton, or an implicit callback chain. A reader cannot identify important dependencies,
  side effects, or transitions from the component interface.
- **Required evidence:** Trace the hidden read or write to an observable decision. Identify the
  lifecycle and owner. Show that repository conventions provide a clearer boundary. A framework
  global or module constant is not sufficient evidence.
- **Impact:** State the observed test isolation, concurrency, configuration, reproducibility, or
  change-isolation problem.
- **Legitimate counterexample:** Retain framework-managed context, immutable process configuration,
  or language-standard state when its lifecycle is explicit and repository conventions require it.
- **Smallest safe correction:** Pass the necessary stable dependency or value through the existing
  boundary. Put configuration parsing at its owner. Do not introduce a container or injection
  framework when a parameter is sufficient.
- **Validation:** Test behavior with controlled dependencies. Verify initialization, shutdown,
  concurrency, and configuration-error paths that apply.
- **Routing owner:** Use `realign`. Route an unused global, callback, or configuration path to
  `simplify` when safe removal is the complete correction.
- **Applicable principles:** [P010](../../../docs/principles/README.md#p010),
  [P011](../../../docs/principles/README.md#p011),
  [P012](../../../docs/principles/README.md#p012),
  [P015](../../../docs/principles/README.md#p015),
  [P019](../../../docs/principles/README.md#p019),
  [P072](../../../docs/principles/README.md#p072),
  [P079](../../../docs/principles/README.md#p079),
  [P084](../../../docs/principles/README.md#p084), and
  [P085](../../../docs/principles/README.md#p085).
- **Sources:** [Athena architecture and simplicity profile](../../../docs/review/common.md#architecture-and-simplicity),
  [Athena behavior-first testing contract](../../../docs/review/behavior-first-testing.md),
  and [Service Locator is an Anti-Pattern](https://blog.ploeh.dk/2010/02/03/ServiceLocatorisanAnti-Pattern/).
