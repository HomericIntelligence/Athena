# Security policy

Athena distributes instruction-bearing AI-harness plugins. The latest tagged release and `main`
receive security fixes.

## Reporting

Privately email **[research@villmow.us](mailto:research@villmow.us)** with the affected revision,
skill or manifest, reproduction, expected behavior, observed behavior, and disclosure status. We
aim to acknowledge reports within five business days.

## Threat model

- **Skill instructions:** malicious or overly broad instructions can cause unsafe tool use.
  Frontmatter declares capabilities; skill bodies define human gates and fail-closed behavior.
- **Dependency substitution:** Mnemosyne and Hephaestus owner overrides could redirect Athena to an
  unintended repository. Athena accepts an explicit owner or a same-owner repository only when
  GitHub verifies the latter is a fork of the canonical upstream. Existing checkout origins must
  match the resolved repository.
- **Marketplace redirection:** host manifests use the repository root and are validated before
  merge and release.
- **Supply chain:** GitHub Actions are commit-pinned, dependency checkouts verify identity, and the
  release contains repository resources rather than executable package artifacts.
- **Secrets:** required CI scans full history; repository policies prohibit credentials and private
  data.

Security issues in a dependency's own code or corpus should be reported to that resolved
repository. Athena issues include unsafe resolution, invocation, permissions, packaging, or policy
within this repository.
