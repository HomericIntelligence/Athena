# P089 — Delete Obsolete Configuration and Dependencies

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- The author traces the obsolete capability through manifests, lockfiles, images, deploy files, and environment variables.
- The author examines optional, build-time, dependency-chain, and platform consumers.
- The author removes obsolete flags, defaults, dashboards, alerts, and runbook steps with the capability.
- The author changes the canonical source, then makes the derived artifacts again.
- The author checks clean installation, packaging, and startup after the removal.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p089)
