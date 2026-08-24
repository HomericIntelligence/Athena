# P056 — Secrets Stay Out of Code and Context

## Definition and aliases

Credentials, private keys, tokens, production secrets, and sensitive customer data must not be placed
in source code, fixtures, prompts, logs, generated artifacts, or agent memory unless the task
explicitly requires that data and an appropriate protected channel is used. Exposure is itself a
security event even when the secret was not visibly abused.

**Aliases:** secret hygiene, credential isolation, context minimization.

## Provenance

**Classification:** established security practice with an Athena extension to agent context. Secret
isolation and credential management have diffuse histories; no single origin is asserted for this
combined code, telemetry, artifact, and AI-context rule.

## Decision rule

If a component or person can complete the task using a reference, scoped identity, derived value, or
redacted record, do not expose the underlying secret. Where secret use is necessary, reveal the
minimum value to the minimum principal for the minimum time and prevent secondary copies.

## How to apply

- Store secrets in a managed secret facility, not repository or ordinary configuration files.
- Prefer short-lived, task-scoped identity and just-in-time retrieval over static shared credentials.
- Keep secret values out of command arguments, prompts, exceptions, telemetry, diffs, and test output.
- Redact sensitive fields before passing context to models, tools, sub-agents, or external services.
- Scan source and artifacts, but treat scanning as a backstop rather than permission to embed secrets.
- Revoke or rotate a secret promptly after suspected exposure; deleting the visible copy is insufficient.

## Boundaries and tensions

Environment variables are transport, not a complete secret-management system, and can leak through
process inspection or debugging. Encoding and encryption with a committed key do not make a secret
safe. Some authorized operations require access to sensitive values; use protected tool boundaries
that perform the operation without returning the value whenever possible. Diagnostic usefulness does
not justify secret-bearing logs.

## Examples

### Positive

A deployment runner obtains a short-lived credential from the platform identity service, uses it
inside the deployment boundary, masks output, and lets the credential expire after the run.

### Misuse

A test embeds a production-like access token in a fixture because the repository is private, then the
same fixture is copied into a prompt and CI artifact.

### Athena and agent workflows

An agent asks a credential-aware tool to perform an authorized operation without reading the token.
Before delegating, it strips unrelated file content, identifiers, and tool output from the child context.

## Related principles

- [P047 — Observability Is Part of Correctness](./p047-observability-is-part-of-correctness.md)
- [P050 — Least Privilege](./p050-least-privilege.md)
- [P053 — Validate at Trust Boundaries](./p053-validate-at-trust-boundaries.md)
- [P058 — Bounded Agent Authority](./p058-bounded-agent-authority.md)

## References

### Origin and history

- No single historical source is claimed. This principle combines long-standing credential-management
  practice with newer risks from telemetry, build artifacts, model context, and persistent memory.

### Current guidance

- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
  covers centralized storage, short lifetimes, rotation, auditing, source exposure, and log redaction.
- [NIST SP 800-218, SSDF Version 1.1](https://doi.org/10.6028/NIST.SP.800-218) requires protection of
  software, credentials, and development environments throughout the secure-development lifecycle.

### Further reading

- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
  applies data classification, redaction, memory isolation, and non-sensitive logging to agent systems.

[Back to the principles catalog](../README.md#p056)
