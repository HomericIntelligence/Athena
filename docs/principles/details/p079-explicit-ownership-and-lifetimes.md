# P079 — Explicit Ownership and Lifetimes

## Definition

**Explicit Ownership and Lifetimes** requires every resource and unit of work to have a clear owner,
a defined valid lifetime, and deterministic transfer, cleanup, or termination semantics. Resources
include memory, files, locks, transactions, connections, callbacks, processes, tasks, and temporary
artifacts.

**Aliases:** none in common use; RAII and ownership types are related implementation families.

## Provenance

**Classification:** established principle.

The general rule has no single origin. It is embodied by structured programming, C++ Resource
Acquisition Is Initialization (RAII), ownership types, scope-bound cleanup, and structured
concurrency. These mechanisms differ, but all make responsibility and lifetime visible.

## Decision rule

Before acquiring a resource or starting work, identify who owns it, when ownership transfers, which
events end its lifetime, and how cleanup occurs on success, failure, timeout, and cancellation.

## How to apply

- Prefer scope-bound resource handles, context managers, or equivalent cleanup constructs.
- Make ownership transfer visible in types, names, or interface contracts.
- Tie child tasks to a parent scope unless a durable owner explicitly adopts them.
- Define shutdown order and wait behavior for concurrent work.
- Track temporary artifacts and partial state until their final disposition is known.
- Test exceptional exits as well as the normal release path.

## Boundaries and tensions

Garbage collection does not close files, release locks, cancel requests, or settle transactions.
Shared ownership and long-lived background work can be valid, but their final owner and shutdown
protocol must still be explicit. Lifetimes need not always be lexical; leases and durable workflows
can express them when scope-bound cleanup is insufficient.

## Examples

**Positive:** A transaction object owns its lock and connection, commits or rolls back exactly once,
and releases both on every exit path.

**Misuse:** A helper launches a detached task that continues using a request-scoped credential after
the request ends, with no cancellation or supervisor.

**Athena/agent workflow:** A coordinator records each subagent, its deadline, expected output, and
terminal disposition, then collects or cancels every child before reporting completion.

## Related principles

- [P039 Bounded Waiting](p039-bounded-waiting.md)
- [P046 Resumability](p046-resumability.md)
- [P080 Make Concurrency Deliberate](p080-make-concurrency-deliberate.md)
- [P082 Design for Cancellation](p082-design-for-cancellation.md)
- [P083 Irreversible Actions Last](p083-irreversible-actions-last.md)

## References

### Origin/history

- [Bjarne Stroustrup's C++ glossary](https://stroustrup.com/glossary.html) records RAII as a
  technique that binds resource management to object construction and destruction.

### Current guidance

- [The Rust Programming Language: What Is Ownership?](https://doc.rust-lang.org/stable/book/ch04-01-what-is-ownership.html)
  demonstrates compiler-enforced ownership and scope rules.
- [Go: Contexts and structs](https://go.dev/blog/context-and-structs) explains why making a
  request's lifetime visible at each call avoids confused cancellation and deadlines.

### Further reading

- [Standard C++ FAQ: Exceptions and RAII](https://isocpp.org/wiki/faq/exceptions/1000) explains
  deterministic cleanup across success and exception paths.

[Back to the engineering principles catalog](../README.md#p079)
