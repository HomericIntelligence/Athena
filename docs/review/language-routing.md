# Language and toolchain routing

Athena review skills use this routing contract after they establish the
repository architecture and identify the changed surfaces. Repository guidance,
formatter, linter, type checker, compiler, test runner, and framework policy
take precedence over these defaults. Reviewers use current primary language or
framework documentation when a repository has no local rule. If that material
is unavailable to the host, use available repository evidence and report the
documentation coverage gap rather than silently assuming a generic practice.

An unmapped executable language is a coverage gap. Do not silently treat it as
adequately reviewed by a generic checklist.

## Deep profiles

### Python

Review public type and data contracts, exception boundaries, resource lifetime,
async or concurrency behavior, import and packaging effects, and test isolation.
Prefer repository-selected formatters, linters, type checkers, and test tools.
Check that runtime validation protects untyped boundaries and that mocks remain
at genuine external boundaries.

Use the current [Python typing documentation](https://docs.python.org/3/library/typing.html)
as the baseline when the repository does not define a stricter public-type
contract.

### C++

Review explicit interfaces and ABI impact, ownership and lifetime, RAII,
error-handling conventions, constness, value and reference semantics,
concurrency and data races, exception safety, and measured performance claims.
Use configured compiler warnings, formatters, static analysis, sanitizers, and
test targets when they exist. A C++ test must be wired into a real build target
before it is accepted as evidence.

Use the [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines)
as the default language reference when repository guidance does not supersede
them.

### Go

Review package and API design, `context.Context` propagation and cancellation,
goroutine lifetime, error wrapping and handling, zero-value behavior, data-race
risks, and public documentation. Use `gofmt`, configured static analysis, race
testing, and package tests where applicable. A name-filtered `go test -run`
command is evidence only after its match set is proven non-empty.

Use [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments) as the
default idiom reference when repository guidance does not supersede it.

### Mojo

Review ownership, lifetime, argument conventions, resource destructors, error
contracts, and `fn` versus `def` semantics. For accelerator code, also inspect
CPU/GPU boundaries, data movement, launch assumptions, and evidence for any
performance claim. For Python interoperability, review both sides of the
boundary and the runtime type and ownership contract.

Use the repository's Mojo tooling and current official Modular guidance. In
particular, consult [modular/skills](https://github.com/modular/skills):
`mojo-syntax` for modern syntax, `mojo-gpu-fundamentals` for accelerator code,
and `mojo-python-interop` for Python/Mojo boundaries. Use Mojo's native testing
facilities when available.

## Routed profiles

| Surface | Review focus |
| --- | --- |
| C, CUDA (`Cuda` in GitHub Linguist), HIP | Ownership, bounds, undefined behavior, host/device boundary, synchronization, portability, compiler and sanitizer evidence, and measured performance claims. |
| Batchfile | Quoting and delayed expansion, `%ERRORLEVEL%` propagation, `%` escaping, path-with-space handling, destructive command scope, `cmd.exe` portability, and explicit external-write authority. |
| COBOL | Record and copybook contracts, fixed or free source format, numeric precision and rounding, file/status handling, batch and transaction boundaries, compiler dialect, and mainframe job or deployment wiring. |
| MLIR | Dialect interfaces and verifier invariants, SSA/value ownership, operation and attribute semantics, conversion legality, pass-pipeline ordering, generated artifacts, and end-to-end compiler-test coverage. |
| Procfile | Process type ownership, executable command and argument boundaries, configuration and secrets, port binding, signal handling and graceful shutdown, worker/web concurrency, and platform deployment evidence. |
| RenderScript | Allocation and kernel data contracts, host/device synchronization, bounds and numeric behavior, lifecycle and resource release, API deprecation or compatibility constraints, and device-level functional evidence. |
| Rust | Ownership and borrowing, `Result` and error propagation, unsafe boundaries, trait/API contracts, concurrency, feature flags, and configured `cargo` checks. |
| TypeScript, JavaScript | Runtime validation at untyped boundaries, strictness and nullability, promise/error paths, browser/server boundaries, dependency and bundling effects, and configured tests/lint. |
| Java, C#, Swift | Public API and nullability contracts, ownership or resource lifetime, concurrency, error semantics, framework lifecycle, package/build configuration, and configured analyzers. |
| Ruby, Lua, Julia, R, Scheme | Dynamic boundary validation, error and resource behavior, numerical or reproducibility assumptions where relevant, package/runtime isolation, and repository test tooling. |
| Shell | Quoting, word splitting, globbing, exit-status propagation, temporary-file safety, command injection, destructive scope, portability, and explicit external-write authority. |
| CMake, Makefile, Just | Target graph, dependency ordering, reproducibility, quoted paths, generated artifacts, and whether validation commands invoke the intended target. |
| Dockerfile | Pinned bases, least privilege, build context, secrets, layers, entrypoint behavior, exposed ports, and reproducible build/run evidence. |
| Jinja, Go Template, templ, HTML | Escaping and injection boundaries, template data contracts, rendering or accessibility behavior where applicable, generated-output ownership, and executable example or render checks. |
| Vim Script | Script-local versus global state, quoting and escaping, mappings and autocommands, command injection, option restoration, editor-version compatibility, and repeatable headless editor tests when available. |

The following are intentionally outside Athena's dedicated routing matrix:
Cython, PowerShell, SQL/PLpgSQL/PLSQL, HCL, Nix, Starlark, Jsonnet, CSS, SCSS,
MDX, Liquid, XSLT, Jupyter Notebook, TeX, BibTeX (including BibTeX Style),
Roff, ANTLR, Tree-sitter Query, Rocq (including Rocq Prover), Red, and POV-Ray
SDL. Review their surrounding product behavior when a changed artifact requires
it, but do not add a dedicated language profile without a demonstrated product
need.
