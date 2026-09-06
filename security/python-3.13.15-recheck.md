# Python 3.13.15 recheck

This file records the candidate release used in the recheck, the security
decision record for issue #15, and the open status of #16.

| Item | Evidence |
| --- | --- |
| Python release | Python 3.13.15. The Python release page lists 2026-08-05 as the release date. |
| linux-64 package | `linux-64/python-3.13.15-hf47f18c_101_cp313.conda` |
| osx-arm64 package | `osx-arm64/python-3.13.15-hb59dee6_101_cp313.conda` |
| osx-64 package | `osx-64/python-3.13.15-h9dec186_101_cp313.conda` |
| Grype database | v6.1.9, built 2026-08-18T06:15:38Z |
| Result | The current Grype database still matches CVE-2026-15308 for CPython 3.13.15. This remains a blocking result. |
| Security decision | The active exception is the security decision for CVE-2026-15308. `@mvillmow` owns the exception. It applies to `python` 3.13.14 and expires on `2026-09-15`. |
| Decision evidence | The exception record links the decision to issue #15 and gives the approval date as `2026-08-16`. |
| Issue status | Grype still blocks the candidate package. Therefore, #16 stays open. This PR does not close #16. |

Sources:

- [Python 3.13.15 release page](https://www.python.org/downloads/release/python-31315/)
- [conda-forge python package index](https://anaconda.org/conda-forge/python/files?type=conda&version=3.13.15)
- [Grype DB issue 1102](https://github.com/anchore/grype-db/issues/1102)
- [Active exception record](vulnerability-exceptions.yaml)
