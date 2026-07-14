# Host compatibility

Athena uses one canonical skill corpus across Claude Code, Codex, and Pi. Hosts expose different
invocation and delegation APIs, so skill instructions follow this mapping.

| Capability | Claude Code | Codex | Pi |
| --- | --- | --- | --- |
| Invoke a skill | `/athena:<name>` | `$<name>` or natural language | `/skill:<name>` |
| Delegate work | Native subagent/task tool | Codex subagents when available | Extension when installed |
| No delegation support | Run sequentially | Run sequentially | Run sequentially |
| Model selection | Use an available model | Use an available model | Use the selected/default model |
| Repository contract | `AGENTS.md` | `AGENTS.md` | `AGENTS.md` |

Skills use the neutral terms coordinator, specialist, executor, skill invocation, and subagent.
Every delegated workflow retains a sequential fallback.

Installation, verification, update, and removal commands are maintained in the root
[`README.md`](../README.md).
