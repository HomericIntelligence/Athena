# Athena release notes

Install Athena through its Git-backed marketplace source: Claude Code uses the repository marketplace
and Codex uses the repository marketplace with an explicit ref. The harness-specific commands are
maintained in the root [`README.md`](../README.md).

Each release includes a checksummed portable plugin archive for offline distribution and provenance.
It contains only harness-consumed skills, host manifests and marketplace metadata, runtime
documentation, assets, and legal notices. It excludes tests, repository scripts, development
manifests and lockfiles, task-runner files, CI configuration, caches, and generated development
output. The archive is not a Python package and does not replace Git-backed marketplace
installation.
