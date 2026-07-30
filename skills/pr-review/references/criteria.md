# Pull/merge-request-specific review criteria

Use these criteria after the shared review contract, language routing, and
behavior-first testing guidance. They own pull/merge-request-specific evidence only; they do
not replace or duplicate the architecture, language, principles, or test rules.

## Requirements and prior work

- Verify standalone issue-closure syntax, every acceptance criterion,
  definition of done, title, and body against the actual change.
- Search issue comments, current-base source, default-branch commits, and
  all-state pull/merge requests on the configured forge for already-landed,
  superseded, duplicate, or zombie work.
- Map every changed path to stated scope. Identify silent additions, reductions,
  or required acceptance criteria that have no changed behavior or verification.
- Reconcile proposed follow-ups against the backlog. Recommend a linked
  follow-up for genuinely out-of-scope work, but do not create one without
  separate authority.

## Pull/merge-request identity and diff lenses

- Bind evidence to the reviewed immutable base and head identities. Never
  substitute branch names for verified source revisions.
- Inspect both author-intent and current-base lenses. Verify behind count,
  conflicts, landed work, revert/deletion risk, and current-head checks when
  the selected profile permits that evidence.
- Read every changed file in full context, linked issue, cited ADR, public
  contract, affected test, and applicable generation source. Retry failed or
  sampled dimensions before calculating a score.

## Integration and hygiene

- Check commit signatures, DCO, commit convention, hook bypasses, lockfiles,
  vendored/generated artifacts, dependency changes, single-purpose scope,
  release handoff, and applicable compatibility.
- Distinguish pre-existing failures from pull/merge-request-introduced failures
  using the base revision where needed. Do not call a pull/merge request
  merge-ready from incomplete, stale, skipped, or mismatched evidence.
- Keep findings on the pull/merge request. Use inline comments or discussions
  only for actionable changed lines; put cross-cutting findings in the one
  batched review summary. Never post a clean review or alter labels, workflow
  state, or merge state.
