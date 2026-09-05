# Security policy

Apply the [ASD-STE100 technical-English policy](skills/TECHNICAL_ENGLISH.md) to all English technical
prose in this document.

Athena distributes plugins that contain instructions for artificial intelligence (AI) harnesses.
Athena supplies security fixes for the latest tagged release and `main`.

## Reporting

Send security reports privately to
**[research@villmow.us](mailto:research@villmow.us)**. Include this information:

- the affected revision;
- the affected skill or manifest;
- the reproduction steps;
- the expected behavior;
- the observed behavior; and
- the disclosure status.

We aim to acknowledge reports no later than five business days after receipt.

## Threat model

- **Skill instructions:** Malicious or overly broad instructions can cause unsafe tool use.
  Frontmatter declares capabilities. Skill bodies define human gates and fail-closed behavior.
- **Dependency substitution:** Owner overrides for Mnemosyne and Hephaestus can direct Athena to
  custom content. Thus, each override is an explicit trust decision. An automatically discovered
  fork can contain organization-specific changes. Athena accepts that fork only when all these
  conditions are true:

  - The current repository has an organization owner.
  - The authenticated viewer has `WRITE`, `MAINTAIN`, or `ADMIN` permission on that repository.
  - GitHub verifies that the candidate has the canonical repository as its parent.

  Athena reports the repository identity, commit SHA, and trust basis. Athena repeats the complete
  gate immediately before use. The `origin` of an existing checkout must identify the resolved
  repository.
- **Instruction and execution trust:** Text from Mnemosyne enters the agent context. Automation from
  Hephaestus can execute commands. Before use, Athena reports the exact repository, commit, and trust
  basis. Athena stops when it cannot prove the identity, authority, ancestry, or checkout revision.
- **Marketplace redirection:** Host manifests use the repository root. Athena validates the manifests
  before merge and release.
- **Supply chain:** GitHub Actions use commit pins. The repository allowlist permits only the reviewed
  action revisions in the required and release workflows. Dependency checkouts verify their identity.
  A release contains repository resources and not executable package artifacts.
- **Untrusted fork code in CI:** On pull requests, the required `package` job deliberately installs
  the plugin from the pull request head fork with `pi install git:github.com/<fork>@<head>
  --no-approve` and checks its source skill inventory through Pi RPC. It then installs the built
  archive and checks the archive skill inventory through a separate Pi RPC probe. Athena accepts this
  supply-chain risk because the job must inspect both inventories to verify the distributed artifact.
  The job has only `contents: read` permission. Its checkout does not persist credentials, Git
  prompts are disabled, the Pi runtime uses locked dependencies, no token is exported to the step,
  and RPC probes run offline. This step must never gain secrets, write-scoped tokens, elevated
  workflow permissions, or network egress beyond the install-time fetch. Any capability change
  requires an explicit review of this risk acceptance.
- **Secrets:** Required continuous integration (CI) scans the complete Git history. Repository
  policies prohibit credentials and private data.

Report a security issue in dependency code or its corpus to the resolved dependency repository.
Athena security issues include unsafe resolution, invocation, permissions, packaging, or policy in
this repository.
