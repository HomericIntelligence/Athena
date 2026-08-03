# Language and toolchain routing

**Why:** Architecture-first review still needs language-specific evidence. Routing prevents a generic
checklist from substituting for the conventions, failure modes, and tools of the code actually changed.

Repository guidance, selected formatter, linter, type checker, compiler, test runner, and framework
policy override these defaults. When the repository has no local rule, use current primary language or
framework documentation; if it is unavailable, use repository evidence and report the documentation
coverage gap. An unknown executable language is a coverage gap, never a generic-checklist pass.

## Select a profile

After the shared architecture gate and surface classification, use every applicable deep or routed
profile below. Do not route an intentionally excluded language through an invented generic overlay;
apply the shared architecture, surface, security, and behavior review instead.

## Deep profiles

### Python

Review public type and data contracts, exception boundaries, resource lifetime, async or concurrency,
import and packaging effects, and test isolation. Prefer repository-selected formatters, linters, type
checkers, and test tools. Runtime validation protects untyped boundaries; mocks stay at genuine external
boundaries. When local rules do not define a stricter public-type contract, use the current
[Python typing documentation](https://docs.python.org/3/library/typing.html).

### C++

Review interfaces and ABI impact, ownership and lifetime, RAII, error conventions, constness, value and
reference semantics, concurrency and data races, exception safety, and measured performance claims. Use
configured warnings, formatters, static analysis, sanitizers, and test targets. A C++ test is evidence
only when wired into a real build target. Default to the
[C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines) when local guidance
does not supersede them.

### Go

Review package and API design, `context.Context` propagation and cancellation, goroutine lifetime,
error wrapping and handling, zero-value behavior, data-race risks, and public documentation. Use
`gofmt`, configured static analysis, race testing, and package tests where applicable. A filtered
`go test -run` command is evidence only after its match set is proven non-empty. Default to
[Go Code Review Comments](https://go.dev/wiki/CodeReviewComments) when local guidance does not supersede
them.

### Mojo

Review ownership, lifetime, argument conventions, resource destructors, error contracts, and `fn` versus
`def` semantics. For accelerator code, inspect CPU/GPU boundaries, data movement, launch assumptions,
and performance evidence. For Python interoperability, review both sides of the boundary and runtime
type and ownership contracts. Use repository tooling and current official Modular guidance, especially
[modular/skills](https://github.com/modular/skills): `mojo-syntax`, `mojo-gpu-fundamentals`, and
`mojo-python-interop`. Use native Mojo testing when available.

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

The following are intentional N/A for a dedicated language profile, not unknown-language coverage gaps:
Cython, PowerShell, SQL/PLpgSQL/PLSQL, HCL, Nix, Starlark, Jsonnet, CSS, SCSS, MDX, Liquid, XSLT,
Jupyter Notebook, TeX, BibTeX (including BibTeX Style), Roff, ANTLR, Tree-sitter Query, Rocq
(including Rocq Prover), Red, and POV-Ray SDL. Apply shared architecture, surface, security, and
behavior review when their artifact requires it; do not invent a generic or dedicated overlay without a
demonstrated product need.
