# ADR 0005: Pull-request publication before validation finishes

**Status:** Accepted

**Supersedes:** Only the pre-publication local test requirement in
[ADR 0004](0004-ci-owned-full-test-suite.md).

## Context

A local execution limit can prevent publication and delay hosted validation. Publication makes
candidate source available for review. It does not prove that the change is complete or safe to
merge. Issue [#286](https://github.com/HomericIntelligence/Athena/issues/286) requires this distinction.

## Decision

Permit pull-request publication before validation finishes. Report pending, failed, and unavailable
checks accurately. Use approved local or hosted runners for focused tests. Preserve behavior-first
test ordering, execution isolation, source identity, and evidence integrity.

Before completion or merge, require successful applicable validation, including focused selection
of each new or changed test. Keep required CI and independent review gates. Source-review verdicts
remain independent of CI status. Keep the pytest ownership decision from ADR 0004.

## Consequences

Source review and hosted validation can proceed while local execution is unavailable. A published
pull request does not establish completion or merge readiness. No execution permission, production
authority, or ruleset change follows from publication.
