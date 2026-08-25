# Athena release notes

Apply the [ASD-STE100 technical-English policy](../skills/TECHNICAL_ENGLISH.md) to all English
technical prose in the release notes.

Install Athena through its Git-backed skill or plugin source. Installation and invocation commands
depend on the coding harness. The root [`README.md`](../README.md) gives the general instructions.

Each release includes a checksummed portable plugin archive. Use it for offline distribution and
provenance.

The archive contains only these items:

- skills that coding harnesses use;
- host manifests and marketplace metadata;
- runtime documentation;
- assets; and
- legal notices.

The archive excludes these items:

- tests;
- repository scripts;
- development manifests and lockfiles;
- task-runner files;
- continuous integration (CI) configuration;
- caches; and
- generated development output.

The archive is not a Python package. It does not replace a Git-backed marketplace installation.
