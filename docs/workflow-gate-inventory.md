# Workflow gate decisions

This inventory records the user-approved workflow changes. Its consumer is the implementation and
review of Athena's autonomous task workflow. The inspected base is
`3ba737517e2234729bcc7eb45b6ec0e3531efdf0`. Source locations below identify the owning workflow;
shared rules belong to the [autonomous workflow policy](policies/autonomous-workflows.md).

## Complete skill inventory

| Skill and source | Previous gate | Agreed behavior | Enforcement or evidence |
| --- | --- | --- | --- |
| [advise](../skills/advise/SKILL.md) | Missing or stale dependency; broad local Git configuration rejection | Use available local guidance with limits. Preserve a wrong dependency and prepare the correct one separately when needed. | `resolve_knowledge_checkout.py`; local revision and refresh result |
| [brainstorm](../skills/brainstorm/SKILL.md) | Design checkpoint can be read as renewed implementation approval | Use the existing task authority and continue after resolving material intent. | Workflow instructions |
| [change-review](../skills/change-review/SKILL.md) | Inventory limits or source drift stop the entire review | Read bounded source batches, refresh affected evidence, and deliver supported findings with gaps. | `resolve_scope.py`; per-batch source receipts |
| [finalize-plan](../skills/finalize-plan/SKILL.md) | Foreign comment ownership and uncertain cleanup stop materialization | Verify source and authority, update the authorized issue body, preserve ineligible comments, and reconcile uncertain outcomes. | `issue_exchange.py`; body readback and deletion allowlist |
| [git-worktrees](../skills/git-worktrees/SKILL.md) | Unignored location or any baseline failure requires a user decision | Prepare ignored primary-project `.worktrees/`; delegate baseline issue handling and continue. | `prepare_worktree.py`; safe path/base and ignore checks |
| [issue-review](../skills/issue-review/SKILL.md) | Separate invocations, strict round limit, malformed state | Invoke the next authorized role, reassess at five, recover only verifiable state. | `issue_exchange.py`, `review_exchange.py` |
| [learn](../skills/learn/SKILL.md) | Freshness, multiple PRs, history completeness, main-file size, sensitive old content | Prepare locally, stack related PRs, use Git history, treat size as editorial, and preserve only safe reusable guidance. | Dependency resolver; Mnemosyne migration and validator |
| [myrmidon-swarm](../skills/myrmidon-swarm/SKILL.md) | Repeated approval, source drift, overlap, cleanup prompts | Use task authority, refresh affected evidence, integrate compatible edits, preserve unique work. | Coordinator assignments and integration evidence |
| [plan-issue](../skills/plan-issue/SKILL.md) | Publication ends task until explicit reviewer invocation | Continue to the next role with distinct evidence and recorded task authority. | `issue_exchange.py` |
| [pr-review](../skills/pr-review/SKILL.md) | Separate author invocation, caps, unknown-write stop, forge-only decisions | Continue roles; process bounded batches; reconcile writes; document conversation fallback with real log provenance. | Review reducer, collector, delivery helper |
| [realign](../skills/realign/SKILL.md) | Per-ID approval, green-baseline-only repair, immutable overlay stops | Use scoped task authority, preserve validation status, and refresh affected evidence. | `resolve_assessment.py`; candidate/source receipts |
| [repo-review](../skills/repo-review/SKILL.md) | All-or-nothing coverage and special validation boundary | Perform native delegated validation and deliver supported findings with accurate gaps. | Shared review contract and tracker evidence |
| [review-exchange](../skills/review-exchange/SKILL.md) | Five rounds, 100 findings, 1 MiB task limit, strict transition stops | Reassess with a viable path; process complete sequences of bounded batches; retain state integrity. | `review_exchange.py`; complete batch receipt |
| [simplify](../skills/simplify/SKILL.md) | Full-source byte limit, missing deprecation policy, repeated handoff authority | Review incrementally, infer supported migration policy from usage, and hand off under existing task authority. | Shared scope and recovery contracts |
| [systematic-debugging](../skills/systematic-debugging/SKILL.md) | Mandatory user discussion after three failed repairs | Reassess evidence and continue while a viable corrective path exists. | Investigation and repair evidence |
| [test-driven-development](../skills/test-driven-development/SKILL.md) | Absolute RED ordering, permission for exceptions, deletion of implementation | Strong test-first default with reasoned exceptions and proportionate verification; preserve useful work. | Behavior-first tests and validation receipts |
| [tidy](../skills/tidy/SKILL.md) | Fresh dependency and repeated destructive-action prompts | Honor explicit cleanup authority, recover dependency access, preserve unique work, and report actual cleanup results. | `run_tidy.py`; cleanup preconditions and exit status |

## Shared decisions

- Keep the architecture gate. A material deviation still requires supported rationale.
- Keep actual forge merge requirements. Local preparation or a published PR does not assert merge
  readiness.
- Prefer forge authority. When it is unavailable, use an explicit conversation decision with the
  actual log ID, message ID, digest, and fallback reason. Document it on the forge when possible.
- On sandbox restrictions, use supported host escalation. If access remains unavailable, complete
  local work and provide exact manual commands. Do not bypass host decisions.
- Use the cheapest capable executor to find or file a pre-existing-failure issue. Issue publication
  must not become another gate. Preserve a prepared issue when the forge is unavailable.
- Preserve compatible user edits. Ask about a concrete conflict, not overlap alone.
- Recover helper failures before using equivalent commands. Do not fabricate helper output.
- Report supported partial findings. Do not call incomplete coverage clear.
- Keep path containment, source identity, verified digests, protected content, and unique-work
  preservation. Resource continuation does not waive those checks.

## Resource regression

The motivating review contained 1,345 tracked files and 31.55 MB. Its stated 8 MiB limit did not
come from the inspected shared contract. An agent-selected byte threshold must not terminate a
review of an otherwise readable repository. Per-operation limits control buffering and response
size. Task-wide progress continues through bounded batches and complete source receipts.

## Mnemosyne migration

The separate Mnemosyne change uses pre-cleanup commit
`e98a4da5d67f0766bc6b4bfaed1ab399fca90e9f`, the head of existing advisory-guidance PR #3420.
The migration is stacked after that PR to preserve its changes and remove its additional histories.
It records every removed companion and its destination,
preserves useful current guidance, and links older content to immutable Git history. Notes remain
unless independently obsolete. Obsolete instructions and protected material are not republished.

## Acceptance evidence

Use behavior tests for source batching, review continuation, source identity, candidate authority,
worktree placement, dependency recovery, and migration. Use Markdown and link checks for workflow
prose. Do not add text-string tests that merely pin policy wording. Review source and prose together
so no old description or shared reference reinstates a removed gate.
