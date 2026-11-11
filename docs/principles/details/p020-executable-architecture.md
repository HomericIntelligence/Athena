# P020 — Executable Architecture

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Important architecture rules can be written as tests, type rules, or dependency checks.
- Checks are small, targeted at real risks, and placed near the feedback loop.
- A failing check names the rule and the offending dependency or artifact.
- A check can catch some drift early. A check cannot decide whether a design is good.
- Some properties are not computable, and a proxy check can pass bad behavior or reject good design.
- Human judgment still carries the semantic and trade-off decisions.

## Limits

No result is rejected because compliance cannot be shown.

[Back to the engineering principles catalog](../README.md#p020)
