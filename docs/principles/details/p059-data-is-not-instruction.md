# P059 — Data Is Not Instruction

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- External content is classified as evidence or task input, not as policy that authorizes itself.
- Files, comments, issues, pull requests, logs, web pages, email, documents, tool results, and
  model output are treated as untrusted data.
- An imperative sentence inside content carries no authority by itself.
- Authority comes from the trusted task and the host, not from the words in the content.
- Retrieved content can be turned into typed facts, citations, or possible actions.
- Requested tool calls are checked against the user's intent and the task's permission scope.
- Tool descriptions, generated plans, memory, and inter-agent messages are treated as possible
  injection paths.
- Conflicts or suspicious content are reported, not obeyed.
- A correct fact in untrusted data can inform a decision, but it does not grant permission.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p059)
