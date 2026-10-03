# Task Plan: GitHub issue #16

## Goal

Produce a concrete implementation plan for the time-gated CVE-2026-15308 recheck, grounded in Athena's current files, policies, and runnable commands.

## Phases

- [x] Read repository and planning instructions.
- [x] Locate the active exception, lock/environment definition, scanner, workflows, and tests.
- [x] Determine the exact post-2026-08-04 evidence and remediation flow.
- [x] Draft every required plan section with file-level changes and acceptance checks.

## Key Questions

- Which files encode the Python pin, lock state, exception, Grype database metadata, and reports?
- Which repository commands reproduce Conda-platform resolution and vulnerability scanning?
- Does issue #16 require code/tests, or only lockfile and exception changes once prerequisites pass?

## Decisions

- Treat 2026-08-04 UTC as a hard execution gate.
- Preserve the issue's official-Python and three-platform Conda-forge checks as upstream evidence.
- Do not recreate deleted Pixi configuration: current `main` is UV-based and its tests explicitly prohibit Pixi in the package workflow.
- Pin the replacement interpreter with `.python-version` (`3.13.15`), which UV documents as the project pin honored by `uv sync`; `uv.lock` does not encode the interpreter itself.
- Remove the exception only after the Linux `.venv` inventory built from the pin passes the current Grype scan with no CVE-2026-15308 match.
- Record raw package/build/platform and Grype database metadata in the PR/issue record, not in a hand-authored committed evidence file.
- If any upstream, Conda, UV-managed-Python, or Grype prerequisite fails, make no remediation-file changes and request an explicit security decision before 2026-08-14.

## Errors Encountered

| Error | Attempt | Resolution |
| --- | --- | --- |
| Zsh expanded an unquoted `jq` program passed through nested `sh -c` | 1 | Query JSON directly without nested shell quoting. |
| `pixi search --json` rejects `--limit` | 1 | Re-run JSON search without `--limit`; JSON mode already returns the complete structured result needed for filtering. |
| Local `pixi search` cannot write its Rattler cache under `~/Library/Caches` in this planning sandbox | 1–2 | Do not treat this pre-gate planning run as package evidence; author the future command for an authorized implementation environment and record the operational failure if it recurs there. |

---

# Task Plan: GitHub issue #15

## Goal

Produce a concrete implementation plan for removing Athena's CVE-2026-15308 exception after updating the locked supported Python environment to a compatible fixed package or confirming corrected vulnerability metadata.

## Phases

- [x] Read the issue, repository contract, and planning-skill instructions.
- [x] Inspect the active exception, environment locks, scanner workflow, policies, and tests.
- [x] Establish exact file changes and runnable acceptance evidence.
- [x] Deliver the complete implementation plan in the required section structure.

## Key Questions

- Where is Python 3.13.14 locked, and is the issue's Pixi reference still accurate at the current head?
- Which command refreshes the supported lock and which files change?
- Which live scan and aggregate gate commands reproduce CI with current Grype metadata?
- Are code or test changes needed beyond the lock/exception update?

## Errors Encountered

| Error | Attempt | Resolution |
| --- | --- | --- |
| None | — | — |
