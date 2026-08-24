# Pull/merge-request-specific review criteria

Use the shared review contract, language routing, and behavior-first testing
first. This file owns only evidence unique to a pull or merge request.

## Engineering principle routes

- Apply [P010 Scope Fidelity](../../../docs/principles/README.md#p010),
  [P011 Minimal Coherent Change](../../../docs/principles/README.md#p011),
  [P014 Preserve Unrequested Behavior](../../../docs/principles/README.md#p014),
  [P063 Requirement-to-Code Traceability](../../../docs/principles/README.md#p063), and
  [P064 Requirement-to-Test Traceability](../../../docs/principles/README.md#p064) to bind changed
  paths and behaviors to one coherent issue outcome without accepting silent contract drift or
  unverified acceptance criteria.
- Apply [P008 Understand Before Subtracting](../../../docs/principles/README.md#p008),
  [P012 Evidence Before Modification](../../../docs/principles/README.md#p012),
  [P066 Preserve Existing Work](../../../docs/principles/README.md#p066),
  [P071 Consistency Over Personal Preference](../../../docs/principles/README.md#p071),
  [P072 Technical Evidence Over Preference](../../../docs/principles/README.md#p072), and
  [P074 Prefer Existing Mechanisms](../../../docs/principles/README.md#p074) when checking prior
  work, so history and current-base behavior—not title similarity or reviewer taste—decide whether
  work is needed, duplicate, superseded, or safely removable.
- Apply [P021 Evolutionary and Reversible Design](../../../docs/principles/README.md#p021),
  [P057 Supply-Chain Integrity](../../../docs/principles/README.md#p057),
  [P065 Verify Before Claiming Completion](../../../docs/principles/README.md#p065),
  [P068 No Validation Bypass](../../../docs/principles/README.md#p068),
  [P070 Code Health Must Not Regress](../../../docs/principles/README.md#p070), and
  [P089 Delete Obsolete Configuration and Dependencies](../../../docs/principles/README.md#p089)
  when assessing integration and hygiene, so compatibility, dependencies, gates, cleanup, and
  release evidence are reviewed as one safe handoff.

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
