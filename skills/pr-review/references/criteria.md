# Pull and merge request review criteria

Use the shared review contract, language routing, and behavior-first testing
first. This file owns only evidence unique to a pull or merge request.

Use Athena's [ASD-STE100 writing policy](../../TECHNICAL_ENGLISH.md) for all technical prose
and review output.

## Engineering principle routes

- Apply [P010 Scope Fidelity](../../../docs/principles/README.md#p010),
  [P011 Minimal Coherent Change](../../../docs/principles/README.md#p011),
  [P014 Preserve Unrequested Behavior](../../../docs/principles/README.md#p014),
  [P063 Requirement-to-Code Traceability](../../../docs/principles/README.md#p063), and
  [P064 Requirement-to-Test Traceability](../../../docs/principles/README.md#p064) to scope and
  traceability. Bind changed paths and behaviors to one coherent issue outcome. Do not accept silent
  contract drift or unverified acceptance criteria.
- Apply [P008 Understand Before Subtracting](../../../docs/principles/README.md#p008),
  [P012 Evidence Before Modification](../../../docs/principles/README.md#p012),
  [P066 Preserve Existing Work](../../../docs/principles/README.md#p066),
  [P071 Consistency Over Personal Preference](../../../docs/principles/README.md#p071),
  [P072 Technical Evidence Over Preference](../../../docs/principles/README.md#p072), and
  [P074 Prefer Existing Mechanisms](../../../docs/principles/README.md#p074) when you inspect prior
  work. Use history and current-base behavior to decide if work is necessary, duplicate,
  superseded, or safe to remove. Do not use title similarity or reviewer preference for this
  decision.
- Apply [P021 Evolutionary and Reversible Design](../../../docs/principles/README.md#p021),
  [P057 Supply-Chain Integrity](../../../docs/principles/README.md#p057),
  [P065 Verify Before Claiming Completion](../../../docs/principles/README.md#p065),
  [P068 No Validation Bypass](../../../docs/principles/README.md#p068),
  [P070 Code Health Must Not Regress](../../../docs/principles/README.md#p070), and
  [P089 Delete Obsolete Configuration and Dependencies](../../../docs/principles/README.md#p089)
  when you assess integration and repository condition. Review compatibility, dependencies, gates,
  cleanup, and release evidence as one safe handoff.

## Requirements and prior work

- Verify these items against the actual change:
  - standalone issue-closure syntax;
  - each acceptance criterion;
  - the definition of done;
  - the title; and
  - the body.
- Search these locations for already-landed, superseded, duplicate, or zombie
  work:
  - issue comments;
  - current-base source;
  - default-branch commits; and
  - all-state pull or merge requests on the configured forge.
- Map each changed path to the stated scope.
- Identify silent additions or reductions.
- Identify each required acceptance criterion that has no changed behavior or
  verification.
- Compare proposed follow-ups with the backlog.
- If work is genuinely outside the scope, recommend a linked follow-up.
- Do not create the follow-up without separate authority.

## Integration and hygiene

- Check these items:
  - commit signatures;
  - Developer Certificate of Origin (DCO) attestations;
  - commit convention;
  - hook bypasses;
  - lockfiles;
  - vendored and generated artifacts;
  - dependency changes;
  - single-purpose scope;
  - release handoff; and
  - applicable compatibility.
- Distinguish base failures from review-introduced failures. Do not call a pull
  or merge request merge-ready from incomplete, stale, skipped, or mismatched
  evidence.
