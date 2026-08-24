# P066 — Preserve Existing Work

## Definition

Do not revert, overwrite, reformat, regenerate, delete, or clean up unrelated work to simplify the
current change. Identify pre-existing modifications, keep task-owned edits distinct, and stop or
isolate the work when both cannot be preserved safely.

**Aliases:** worktree preservation; noninterference with existing changes.

## Provenance

**Classification:** Athena synthesis.

No singular historical origin is established. The rule adapts version-control safety, narrow-change
practice, and collaborative ownership into an explicit contract for agents sharing a workspace with
users and other agents.

## Decision rule

Before changing or cleaning a path, determine whether it contains work outside the current task. If
the intended edit cannot preserve that work, do not discard or overwrite it without explicit
authority; use safe isolation or request direction.

## How to apply

- Inspect working-tree, index, branch, and worktree state before editing or cleanup.
- Attribute changes by comparing the initial state, task scope, and current diff.
- Edit only intentional paths and stage explicit pathsets.
- Use an isolated branch or linked worktree when concurrent changes would overlap unsafely.
- Report conflicts or ambiguous ownership instead of resolving them by deletion.

## Boundaries and tensions

Preservation does not make existing changes immutable. The user may ask to modify, replace, or remove
them, and a scoped task may require careful edits to an already modified file. Generated output may
also need coherent regeneration when it is a real product artifact. The rule forbids silent loss or
unrelated churn, not authorized collaboration. A clean repository is not more valuable than its
uncommitted work.

## Examples

**Positive:** An agent sees unrelated edits in the primary checkout and performs feature work in a
new linked worktree, staging only the feature's paths.

**Misuse:** A formatter rewrites the entire repository, or a reset removes unknown modifications,
solely to make the requested patch easier to review.

**Athena/agent workflow:** A delegated writer detects that another agent is editing the same skill,
avoids the file, and reports the overlap to the coordinator rather than replacing the other patch.

## Related principles

- [P010 Scope Fidelity](p010-scope-fidelity.md)
- [P011 Minimal Coherent Change](p011-minimal-coherent-change.md)
- [P021 Evolutionary and Reversible Design](p021-evolutionary-and-reversible-design.md)
- [P083 Irreversible Actions Last](p083-irreversible-actions-last.md)

## References

### Origin/history

- [Git worktree documentation](https://git-scm.com/docs/git-worktree) describes linked worktrees and
  gives an example of isolating an urgent change without disturbing in-progress work; it is not
  claimed as the origin of this broader principle.

### Current guidance

- [Git status documentation](https://git-scm.com/docs/git-status) defines how to inspect staged,
  unstaged, and untracked working-tree state before acting on it.
- [Google Engineering Practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
  recommends separating unrelated refactoring and keeping a change conceptually focused.

### Further reading

- [Git restore documentation](https://git-scm.com/docs/git-restore) makes explicit that restoration
  can replace working-tree content or remove paths, underscoring why targets must be resolved first.

[Back to the engineering principles catalog](../README.md#p066)
