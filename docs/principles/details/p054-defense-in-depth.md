# P054 — Defense in Depth

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Important threats get more than one control at different layers.
- Layers can include identity, application, data, runtime, and network controls.
- Layers fail in different ways. Shared credentials, configuration, and libraries are avoided.
- Detection and recovery are used, not only prevention.
- Controls at different layers address different failure modes of the same threat.
- Each control has a clear owner and maintenance path.
- The minimum useful layer set is preferred over a large control checklist.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p054)
