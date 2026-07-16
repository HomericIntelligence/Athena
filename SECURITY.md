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
- **Dependency substitution:** Mnemosyne and Hephaestus owner overrides can redirect Athena to
  custom content and therefore act as explicit trust decisions. An automatically discovered fork
  may contain organization-specific changes, but is accepted only when the current repository is
  organization-owned, the authenticated viewer has write/maintain/admin permission there, and
  GitHub verifies the candidate's canonical parent. Repository identity, SHA, and trust basis are
  reported and the complete gate is repeated immediately before use. Existing checkout origins must
  match the resolved repository.
- **Instruction and execution trust:** Mnemosyne text enters agent context and Hephaestus automation
  may execute commands. Athena reports the exact repository, commit, and trust basis before use and
  fails closed when identity, authority, ancestry, or checked-out revision cannot be proved.
- **Marketplace redirection:** host manifests use the repository root and are validated before
  merge and release.
- **Supply chain:** GitHub Actions are commit-pinned and restricted by the repository allowlist to
  the reviewed action revisions used by the required and release workflows; dependency checkouts
  verify identity, and the release contains repository resources rather than executable package
  artifacts.
- **Secrets:** required CI scans full history; repository policies prohibit credentials and private
  data.

Security issues in a dependency's own code or corpus should be reported to that resolved
repository. Athena issues include unsafe resolution, invocation, permissions, packaging, or policy
within this repository.
