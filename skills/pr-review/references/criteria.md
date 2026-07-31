# Pull/merge-request-specific review criteria

Use the shared review contract, language routing, and behavior-first testing
first. This file owns only evidence unique to a pull or merge request.

## Requirements and prior work

- Verify standalone issue-closure syntax, every acceptance criterion,
  definition of done, title, and body against the actual change.
- Search issue comments, current-base source, default-branch commits, and
  all-state pull/merge requests on the configured forge for already-landed,
  superseded, duplicate, or zombie work.
- Map every changed path to stated scope. Identify silent additions, reductions,
  or required acceptance criteria with no changed behavior or verification.
- Reconcile proposed follow-ups against the backlog. Recommend a linked
  follow-up for genuinely out-of-scope work, but create none without separate
  authority.

## Integration and hygiene

- Check commit signatures, DCO, commit convention, hook bypasses, lockfiles,
  vendored/generated artifacts, dependency changes, single-purpose scope,
  release handoff, and applicable compatibility.
- Distinguish base failures from review-introduced failures. Do not call a pull
  or merge request merge-ready from incomplete, stale, skipped, or mismatched
  evidence.
