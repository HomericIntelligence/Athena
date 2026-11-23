# Agent authority and host permissions

Status: canonical. Version 1.0.0.
Applies to every agent and skill in the HomericIntelligence workspace.

## Authority

A development request authorizes ordinary work needed to deliver the change:

- create a worktree and task branch;
- fetch from origin;
- stage intentional paths and create a signed commit;
- push the task branch;
- rebase the agent’s own task branch when required content blocks work,
  or when the forge reports a conflict;
- update the agent’s own PR branch with an exact lease;
- merge an ordinary PR through the forge after required checks pass for
  the current head and review permits;
- remove a merged branch and its worktree when cleanup is authorized.

A release, deployment, publication, tag, or protected-branch change needs
authority from the task or the owning release page. A destructive action or
discarded change needs action-bound authority.

Analysis, review, or planning requests remain read-only.

Host rules and repository rules may be stricter. Follow the stricter rule.

## Host permissions

Host configuration owns exact permission flags, tool names, and matching rules.
A skill states the intended outcome and the stop condition. It does not copy host
mechanics or grant authority.

Try an authorized command once. If a host rule blocks it, do not retry it in
another form. Use a documented host escalation path when one exists. Otherwise,
report the exact command and the block.

Do not bypass a denial with another tool, an admin flag, a hook skip, a different
ref, or a replacement PR. A replacement PR is valid only when the task authorizes
a new review identity and the old PR points forward.

## Security invariants

Keep these fatal:

- authentication and authorization;
- filesystem permissions and credential modes;
- path confinement;
- secret handling;
- exact identity where the operation requires it.

Traceability metadata, checksums, seals, and acceptance records may warn when
policy permits. They do not relax a security check.

## Change control

This file is the single source of truth. Update it before you update a linking
document. Do not restate it in another repository or skill.