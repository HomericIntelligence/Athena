# P056 — Secrets Stay Out of Code and Context

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Credentials, private keys, tokens, and production secrets never appear in source code,
  fixtures, prompts, logs, generated artifacts, or agent context.
- Sensitive customer data (PII) never appears in source code or unprotected context.
- Secrets are kept in a managed secret facility, not in repository or configuration files without
  protection.
- Short-lived, task-specific identities are preferred over static shared credentials.
- Secret values stay out of command arguments, exceptions, telemetry, diffs, and test output.
- Sensitive fields are redacted before context goes to models, tools, sub-agents, or external
  services.
- References, scoped identities, and derived values are used instead of raw secret values.
- If a secret is exposed or may be exposed, the secret is revoked and replaced. Deleting the
  visible copy is not sufficient.
- Scanning source and artifacts is a secondary control. It is never permission to embed secrets.

## Limits

The protection of credentials, private keys, and PII is a hard requirement, not an advisory goal.
No output may carry credentials, private keys, or PII in code, logs, prompts, or artifacts.
No other compliance claim is required.

[Back to the principles catalog](../README.md#p056)
