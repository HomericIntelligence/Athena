# Autonomous task completion

Apply the [technical-English policy](../../skills/TECHNICAL_ENGLISH.md).

This policy describes aspirations for recovery and continuation in every Athena skill: keep
useful work moving, and stop only the affected action when a specific unresolved decision or
actual constraint prevents progress.

## Authority and continuation

Use the user's existing task authority. Candidate IDs can track work; they are a tracking tool, not
a reason to ask for more approval. A review-only request can stay read-only. When the task includes
implementation, continue from assessment toward the applicable repair, planning, and finalization
steps. Keep author and executor responsibilities distinct. A new user message is not needed solely
to invoke the next step.

Select an ambiguous target from the strongest explicit task, branch, repository, and
linked-artifact evidence. State the selection. Ask only when a material choice remains unresolved.
Infer a public API migration policy from consumers and release practice within the task's authority.
Document the compatibility decision. A material architecture change benefits from rationale in a
design or an architecture decision record (ADR).

Prefer forge-owned authority records. If that capability is unavailable, a conversation record with
the actual conversation log ID, decision, target, and limits serves the same purpose.
Inventing a log ID or inferring risk acceptance defeats that record. Publish the authority record on
GitHub when possible.

## Recovery

When a helper fails, investigate its cause. Attempt a scoped repair and issue handling before an
equivalent fallback. A fallback works best when it keeps the same identity, scope, and checks
visible. Record the actual fallback method; an invented helper receipt helps no one. Recovered
state helps most when it stays distinguishable from a new decision; preserve the original
records.

Before retrying an uncertain write, read back its exact target. If the write succeeded, use that
result. If it did not occur, revalidate and retry within a finite budget. If the outcome remains
unknown, withhold dependent writes, report the uncertainty, and avoid duplicates.

When source changes, preserve the change, refresh the affected binding, and repeat the affected
analysis or checks. Integrate compatible existing edits. Ask only about unresolved conflicts.
Evidence whose source and assumptions remain valid stays useful as it is.

After unsuccessful repairs, reassess the cause and approach. After several failed rounds, record
progress, remaining findings, and the next viable approach. Continue when the evidence supports
that approach. Request intervention when no viable path remains.

## Resources and coverage

Use finite operations with bounded reads, pagination, batches, and recorded progress. Continue until
the requested scope is covered. A per-operation limit is not a whole-task size limit. An
agent-selected threshold, including 8 MiB, is not repository policy. When the complete repository
does not fit in one read, picking retrieval back up in additional batches beats stopping early.
Respect actual host and provider limits.

If some source remains unavailable after recovery, deliver supported findings and identify the
exact coverage gap. An incompletely reviewed scope does not get presented as clear.
A sample does not establish complete coverage.

## Validation and delivery

Run repository-native validation under host permissions. Recording the revision and any uncommitted
content alongside the command, environment, exit status, and actual output keeps a run auditable. A
clean commit, a special container, or an additional isolation layer can help but is not a
prerequisite. Preserve user work. Delegate selected checks to bounded executors when available;
otherwise run them sequentially.

Test-driven development is the strong default for behavior changes. Record a concrete reason and an
alternative verification when test-first ordering is not useful or feasible. Good implementation
can stay even when test-first ordering was not practical. Keep tests honest; a test weakened to
hide a defect helps no one.

For a pre-existing failure, assign issue discovery to the lowest-cost capable subagent. Find an
existing GitHub issue or file one with the reproduction and evidence. If delegation is unavailable,
do this sequentially. Continue the task. If publication fails, provide the prepared issue and exact
command. Separate pre-existing failures from regressions; an unrun or failed check is reported as
such, not as passing.

When sandbox permissions cause failure, attempt supported permission escalation. If access remains
unavailable, complete local work and the available checks. Provide exact manual validation, push,
and PR-publication commands with the prepared artifact paths. If an independent review is
unavailable, finish preparation and report what is missing.

## Worktrees and cleanup

Create new worktrees and additional project clones under the primary project's ignored `.worktrees/`
directory. Verify or add its ignore rule. Feature branches are the usual path; `main` stays
available. Existing checkouts at other locations remain valid. Preserve an unexpected dependency
checkout; prepare the correctly identified repository separately. Record the source commit and local
review base.

An explicit cleanup request is a useful signal for removing verified merged branches and clean
worktrees with no unique work. Preserve ambiguous, uncommitted, or unintegrated work. Prefer
guarded cleanup tooling. A workflow that declares post-delivery cleanup can remove its own
invocation-created worktree after verified remote delivery, provided the worktree is clean and
fully integrated. Ordinary delivery is not a cleanup request by itself.
