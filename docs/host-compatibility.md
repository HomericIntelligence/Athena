# Coding-harness compatibility

Apply the [ASD-STE100 technical-English policy](technical-english.md) to all English technical prose
in this document.

Athena uses one canonical skill corpus in all coding harnesses. Harnesses have different invocation
and delegation application programming interfaces (APIs). Thus, skill instructions use this
capability map.

| Capability | Required behavior |
| --- | --- |
| Invoke a skill | Use the native skill-invocation mechanism of the harness. |
| Delegate work | Use native subagent or task capabilities when they are available. |
| No delegation support | Run independent work sequentially with the current agent. |
| Model selection | If the selected model is available, use it. Otherwise, use the default model. Do not require a named model tier. |
| Repository contract | Read the `AGENTS.md` guidance of the repository. |
| Technical English | Apply the [ASD-STE100 technical-English policy](technical-english.md) to English technical prose. |

Canonical skill bodies use the instruction `invoke the <name> skill`. The harness supplies the
applicable syntax. Skills use these neutral terms:

- coordinator;
- specialist;
- executor;
- skill invocation; and
- subagent.

Each delegated workflow must have a sequential fallback. If the harness does not have a referenced
skill, include an inline fallback. Do not assume that the skill is installed.

Athena maintains installation, verification, update, and removal commands in the root
[`README.md`](../README.md).
