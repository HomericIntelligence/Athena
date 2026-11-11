# P019 — Explicit Contracts

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Where two parties could assume different things, the assumption is written down.
- Contracts cover inputs, outputs, units, ranges, ownership, mutability, side effects, and failures.
- Contracts live in types, schemas, assertions, tests, or protocol definitions when practical.
- Mutable data and resources have a clear owner and lifetime.
- External contracts are versioned, and semantic changes are treated as compatibility decisions.
- Small internal helpers with one caller need little or no prose contract.

## Limits

No result is rejected because compliance cannot be shown.

[Back to the engineering principles catalog](../README.md#p019)
