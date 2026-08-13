# Coding-harness compatibility

Athena uses one canonical skill corpus across coding harnesses. Harnesses expose different
invocation and delegation APIs, so skill instructions follow this capability mapping.

| Capability | Required behavior |
| --- | --- |
| Invoke a skill | Use the harness's native skill-invocation mechanism. |
| Delegate work | Use native subagent or task capabilities when available. |
| No delegation support | Run independent work sequentially with the current agent. |
| Model selection | Use an available selected or default model; do not require a named model tier. |
| Repository contract | Read the repository's `AGENTS.md` guidance. |

Canonical skill bodies say `invoke the <name> skill`; the harness supplies the concrete syntax.
Skills use the neutral terms coordinator, specialist, executor, skill invocation, and subagent.
Every delegated workflow retains a sequential fallback. A reference to a skill that the harness has
not installed must include an inline fallback rather than silently assuming it exists.

Installation, verification, update, and removal commands are maintained in the root
[`README.md`](../README.md).
