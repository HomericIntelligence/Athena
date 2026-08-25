# Language and toolchain routing

**Why:** An architecture-first review also needs language-specific evidence. Use language routing so
that a generic checklist does not replace the conventions, failure modes, and tools of the changed
code.

Use the [ASD-STE100 writing policy](../../skills/TECHNICAL_ENGLISH.md) for all technical prose and review
output.

Follow repository guidance and repository-selected tools first. These instructions override the
defaults in this document. If the repository has no local rule, use the current primary language or
framework documentation. If that documentation is not available, use repository evidence. Report the
documentation coverage gap. If the executable language is unknown, report a coverage gap. Do not
report a generic-checklist pass.

## Select a profile

After the shared architecture gate and surface classification, apply every relevant deep or routed
profile. If a language is intentionally excluded, do not create a generic language overlay. Apply the
shared architecture, surface, security, and behavior review.

## Deep profiles

### Python

Review these items:

- public type and data contracts;
- exception boundaries;
- resource lifetime;
- asynchronous operations or concurrency;
- import and packaging effects; and
- test isolation.

Use repository-selected formatters, linters, type checkers, and test tools. Use runtime validation at
untyped boundaries. Use mocks only at genuine external boundaries. If local rules do not define a
stricter public-type contract, use the current
[Python typing documentation](https://docs.python.org/3/library/typing.html).

### C++

Review these items:

- interfaces and application binary interface (ABI) effects;
- ownership and lifetime;
- resource acquisition is initialization (RAII);
- error conventions;
- constness;
- value and reference semantics;
- concurrency and data races;
- exception safety; and
- measured performance claims.

Use configured warnings, formatters, static analysis, sanitizers, and test targets. Accept a C++ test
as evidence only when a real build target includes it. If local guidance does not supersede them, use
the [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines).

### Go

Review these items:

- package and application programming interface (API) design;
- `context.Context` propagation and cancellation;
- goroutine lifetime;
- error wrapping and error handling;
- zero-value behavior;
- data-race risks; and
- public documentation.

Use `gofmt`, configured static analysis, race tests, and package tests when they apply. Accept a
filtered `go test -run` command as evidence only after you verify that it selects at least one test.
If local guidance does not supersede it, use
[Go Code Review Comments](https://go.dev/wiki/CodeReviewComments).

### Mojo

Review these items:

- ownership;
- lifetime;
- argument conventions;
- resource destructors;
- error contracts; and
- `fn` and `def` semantics.

For accelerator code, inspect central processing unit (CPU) and graphics processing unit (GPU)
boundaries. Also inspect data movement, launch assumptions, and performance evidence. For Python
interoperability, review both sides of the boundary. Review the runtime type and ownership contracts.
Use repository tooling and current official Modular guidance. Give special attention to
[modular/skills](https://github.com/modular/skills): `mojo-syntax`, `mojo-gpu-fundamentals`, and
`mojo-python-interop`. Use native Mojo tests when they are available.

## Routed profiles

| Surface | Review focus |
| --- | --- |
| C, CUDA (`Cuda` in GitHub Linguist), HIP | Ownership, bounds, undefined behavior, host/device boundary, synchronization, portability, compiler and sanitizer evidence, and measured performance claims. |
| Batchfile | Quoting and delayed expansion, `%ERRORLEVEL%` propagation, `%` escaping, path-with-space handling, filesystem-destructive command scope, `cmd.exe` portability, and change-discard boundaries. |
| COBOL | Record and copybook contracts, fixed or free source format, numeric precision and rounding, file/status handling, batch and transaction boundaries, compiler dialect, and mainframe job or deployment wiring. |
| MLIR | Dialect interfaces and verifier invariants, SSA/value ownership, operation and attribute semantics, conversion legality, pass-pipeline ordering, generated artifacts, and end-to-end compiler-test coverage. |
| Procfile | Process type ownership, executable command and argument boundaries, configuration and secrets, port binding, signal handling and graceful shutdown, worker/web concurrency, and platform deployment evidence. |
| RenderScript | Allocation and kernel data contracts, host/device synchronization, bounds and numeric behavior, lifecycle and resource release, API deprecation or compatibility constraints, and device-level functional evidence. |
| Rust | Ownership and borrowing, `Result` and error propagation, unsafe boundaries, trait/API contracts, concurrency, feature flags, and configured `cargo` checks. |
| TypeScript, JavaScript | Runtime validation at untyped boundaries, strictness and nullability, promise/error paths, browser/server boundaries, dependency and bundling effects, and configured tests/lint. |
| Java, C#, Swift | Public API and nullability contracts, ownership or resource lifetime, concurrency, error semantics, framework lifecycle, package/build configuration, and configured analyzers. |
| Ruby, Lua, Julia, R, Scheme | Dynamic boundary validation, error and resource behavior, numerical or reproducibility assumptions where relevant, package/runtime isolation, and repository test tooling. |
| Shell | Quoting, word splitting, globbing, exit-status propagation, temporary-file safety, command injection, filesystem-destructive scope, portability, and change-discard boundaries. |
| CMake, Makefile, Just | Target graph, dependency ordering, reproducibility, quoted paths, generated artifacts, and whether validation commands invoke the intended target. |
| Dockerfile | Pinned bases, least privilege, build context, secrets, layers, entrypoint behavior, exposed ports, and reproducible build/run evidence. |
| Jinja, Go Template, templ, HTML | Escaping and injection boundaries, template data contracts, rendering or accessibility behavior where applicable, generated-output ownership, and executable example or render checks. |
| Vim Script | Script-local versus global state, quoting and escaping, mappings and autocommands, command injection, option restoration, editor-version compatibility, and repeatable headless editor tests when available. |

## Intentionally excluded dedicated profiles

Treat these languages as intentionally not applicable (N/A) for a dedicated language profile. Do not
treat them as unknown-language coverage gaps:

- Cython;
- PowerShell;
- SQL, PLpgSQL, and PLSQL;
- HCL;
- Nix;
- Starlark;
- Jsonnet;
- CSS;
- SCSS;
- MDX;
- Liquid;
- XSLT;
- Jupyter Notebook;
- TeX;
- BibTeX, including BibTeX Style;
- Roff;
- ANTLR;
- Tree-sitter Query;
- Rocq, including Rocq Prover;
- Red; and
- POV-Ray SDL.

Apply the shared architecture, surface, security, and behavior review when the artifact requires it.
Do not create a generic or dedicated overlay without a demonstrated product need.
