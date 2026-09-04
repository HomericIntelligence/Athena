# ADR 0002: Public agent-contract workflow

**Status:** Proposed

## Context

Athena owns the canonical development-principles catalog. Homeric Intelligence repositories need
one executable contract that checks their root `AGENTS.md` and `CLAUDE.md` files against that
catalog. Copied validators and copied catalogs can drift.

The accepted [plugin-distribution boundary](0001-plugin-distro-scope-policy.md) does not define a
public cross-repository governance interface.

## Decision

Athena will publish a reusable GitHub Actions workflow as a versioned governance interface.

- `docs/principles/README.md` remains the only catalog authority.
- A standard-library parser renders one ordered `P001` through `P091` block.
- Each caller checks out its own revision. The called Athena revision supplies the action, parser,
  renderer, and catalog.
- The workflow accepts no input and no secret. It has read-only repository permission.
- The action does not install a package, fetch a network resource, execute caller code, use a cache,
  or transfer an artifact.
- Root `CLAUDE.md` contains exactly `@AGENTS.md` followed by one line feed.
- The marked block starts with
  `<!-- BEGIN ATHENA DEVELOPMENT PRINCIPLES: agent-contract-v1.0.0 -->` and ends with
  `<!-- END ATHENA DEVELOPMENT PRINCIPLES -->`. No blank line occurs between a marker and a row.
- Contract detail links use the immutable `agent-contract-v1.0.0` tag.
- [Issue #163](https://github.com/HomericIntelligence/Athena/issues/163) owns tag protection and
  release. Consumers must wait until that work protects and publishes the contract tag.

Athena calls the reusable workflow locally from each required and publishing workflow. The caller
job is `agent-contract`. The called job is `validate-agent-contract`.

## Consequences

- A consumer pins one public workflow version and receives the same catalog and validator.
- A catalog change requires a new agent-contract version and a coordinated consumer update.
- The marked block is generated data. Authors must not edit its rows manually.
- This governance interface does not change the plugin-only release boundary in ADR 0001.
- The `$/` self-repository syntax limits this first interface to GitHub.com.
