# Autonomous task completion

Apply the [technical-English policy](../../skills/TECHNICAL_ENGLISH.md).

Recover and continue useful work. Stop only the affected action when a specific unresolved decision
or actual constraint prevents progress. This policy applies to every Athena skill. Preserve the
[architecture gate](../review/common.md#architecture-gate), accurate evidence, existing work, and
actual forge merge requirements.

## Authority and continuation

Use the user's existing task authority. Candidate IDs track work; they do not require repeated
approval. A review-only request remains read-only. When the task includes implementation, continue
from assessment to the applicable repair, planning, review, and finalization workflow. Keep author,
reviewer, and executor responsibilities distinct. Complete each verified transition before the next.
Do not require a new user message solely to invoke the next skill.

Select an ambiguous target from the strongest explicit task, branch, repository, and linked-artifact
evidence. State the selection. Ask only when a material choice remains unresolved. Infer a public
API migration policy from consumers and release practice within the task's authority. Document the
compatibility decision. A material architecture change still needs rationale in a design or ADR.

Prefer forge-owned authority records. If that capability is unavailable, use explicit conversation
authority for the same action and scope. Record the actual conversation log ID, decision, target,
and limits. Do not invent a log ID or infer risk acceptance. Publish the authority record on GitHub
when possible. A conversation record does not replace a forge-required merge approval.

## Recovery

When a helper fails, investigate its cause. Attempt a scoped repair and issue handling before an
equivalent fallback. A fallback must preserve the necessary identity, scope, and evidence checks.
Record the actual fallback method; never fabricate a helper receipt. Recover malformed review state
from verifiable records. Preserve the original records and distinguish recovered state from a new
review or authority decision.

Before retrying an uncertain write, read back its exact target. If the write succeeded, use that
receipt. If it did not occur, revalidate and retry within a finite budget. If the outcome remains
unknown, withhold only dependent writes and report the uncertainty. Do not publish duplicates.

When source changes, preserve the change, refresh the affected binding, and repeat affected analysis
or checks. Integrate compatible existing edits. Ask only about unresolved conflicts. Keep unchanged
evidence when its source and assumptions remain valid.

After unsuccessful repairs, reassess the cause and approach. At five review rounds, record progress,
remaining findings, and the next viable approach. Continue when evidence supports that approach.
Request intervention when no viable path remains. A round count alone is not a task blocker.

## Resources and coverage

Use finite operations with bounded reads, pagination, batches, and recorded progress. Continue until
the requested scope is covered. A per-operation limit is not a whole-task size limit. An
agent-selected threshold, including 8 MiB, is not repository policy. Do not stop because the complete
repository does not fit in one read. Continue finding lists, exchange records, and retrieval pages
in additional batches. Respect actual host and provider limits.

If some source remains unavailable after recovery, deliver supported findings and identify the exact
coverage gap. Do not report an incompletely reviewed scope as clear. Do not claim complete coverage
from a sample. Withhold only decisions that require the missing evidence.

## Validation and delivery

Run repository-native validation under host permissions. Bind receipts to the revision and recorded
uncommitted content. A clean commit, special container, or additional isolation layer is not a
prerequisite. Record commands, environment, exit status, and actual output. Preserve user work.
Delegate selected checks to bounded executors when available; otherwise run them sequentially.

TDD is the strong default for behavior changes. Record a concrete reason and alternative verification
when test-first ordering is not useful or feasible. Never delete good implementation solely to
recreate test-first ordering. Do not weaken a test to hide a defect.

For a pre-existing failure, assign issue discovery to the lowest-cost capable subagent. Find an
existing GitHub issue or file one with the reproduction and evidence. If delegation is unavailable,
do this sequentially. Continue the task. If publication fails, provide the prepared issue and exact
command. Separate pre-existing failures from regressions; do not claim an unrun or failed check passed.

When sandbox permissions cause failure, attempt supported permission escalation. If access remains
unavailable, complete local work and available checks. Provide exact manual validation, push, and
PR-publication commands with the prepared artifact paths. If required independent review is
unavailable, finish preparation and withhold only the action that requires that review. Preserve all
actual forge-required checks and merge conditions.

## Worktrees and cleanup

Create new worktrees and additional project clones under the primary project's ignored `.worktrees/`
directory. Verify or add its ignore rule. Use feature branches, not `main`. Existing checkouts at
other locations remain valid. Preserve an unexpected dependency checkout; prepare the correctly
identified repository separately. Record the source commit and local review base.

An explicit cleanup request authorizes removal of verified merged branches and clean worktrees with
no unique work. Preserve ambiguous, uncommitted, or unintegrated work. Prefer the guarded cleanup
workflow. Do not treat ordinary delivery as a cleanup request.
