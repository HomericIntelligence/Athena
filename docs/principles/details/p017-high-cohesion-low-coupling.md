# P017 — High Cohesion, Low Coupling

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Elements that change for the same reason live together.
- Each invariant stays with the state it protects.
- Components connect through the smallest stable contract that works.
- Shared mutable global data is avoided in favor of explicit dependencies.
- Wide interfaces and dependency cycles get a second look.
- Event buses and shared databases can hide coupling, so they are used with care.
- Cohesion can go too far; a huge component serving every cause is not cohesive.

## Limits

No result is rejected because compliance cannot be shown.

[Back to the engineering principles catalog](../README.md#p017)
