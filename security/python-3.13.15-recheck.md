# Python 3.13.15 recheck

This file records the candidate release used in the recheck.

| Item | Evidence |
| --- | --- |
| Python release | Python 3.13.15. The Python release page lists 2026-08-05 as the release date. |
| linux-64 package | `linux-64/python-3.13.15-hf47f18c_101_cp313.conda` |
| osx-arm64 package | `osx-arm64/python-3.13.15-hb59dee6_101_cp313.conda` |
| osx-64 package | `osx-64/python-3.13.15-h9dec186_101_cp313.conda` |
| Grype database | v6.1.9, built 2026-08-18T06:15:38Z |
| Result | The current Grype database still matches CVE-2026-15308 for CPython 3.13.15. This remains a blocking result. Issue #15 still needs an explicit security decision. |
| Decision | Keep issue #15 open and keep the exception in place until a recorded security decision changes the outcome. Do not close #16 from this recheck. |
| Decision evidence | The active exception in `security/vulnerability-exceptions.yaml` still records CVE-2026-15308 for `python` 3.13.14 with owner `@mvillmow`, issue #15, approval `2026-08-16`, and expiry `2026-09-15`. |

Sources:

- [Python 3.13.15 release page](https://www.python.org/downloads/release/python-31315/)
- [conda-forge python package index](https://anaconda.org/conda-forge/python/files?type=conda&version=3.13.15)
- [Grype DB issue 1102](https://github.com/anchore/grype-db/issues/1102)
- [Active exception record](security/vulnerability-exceptions.yaml)
