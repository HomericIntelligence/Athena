---
name: verification
description: Audit a metric, CI result, or benchmark claim under Athena's local evidence-integrity policy; truthful failure is acceptable and invented success is not.
allowed-tools: [Read, Bash, Glob, Grep, Agent]
---

# When to use

Invoke this skill whenever the user posts an assertion that names a specific
measured value: a metric, a CI gate result, a benchmark number, a training
loss, or a "this ran successfully" claim. The skill does not automatically reproduce an expensive
or side-effecting run. It does query current read-only evidence and may re-execute safe, bounded
verification commands. Its job is to determine whether the claim is backed by **runnable evidence** per
[`docs/policies/evidence-integrity.md`](../../docs/policies/evidence-integrity.md).

# Inputs the skill expects

The user must supply, or the skill must collect:

1. **The claim.** A sentence like "the build passed in 4m12s" or "epoch 1
   loss = 0.4123". Quoted verbatim.
2. **The evidence pointer.** A path, a URL, or a CI run id. If absent, the
   skill will ask before proceeding.

# Verified workflow

1. **Classify the claim type.**
   - **CI gate result** (e.g., "all checks pass"): the evidence is the
     `gh pr checks` JSON, not a PR body line.
   - **Measured metric / benchmark**: the evidence is a CI-produced artifact
     or an independently-reproduced log; a file committed into a PR does NOT
     count.
   - **Training/optimization result**: the accepted evidence is a CI-produced artifact or a
     detached-execution run record bound to the reviewed revision.
   - **Operational status** (e.g., "the daemon is running"):
     `systemctl status` or `podman ps` output.

2. **Locate the evidence.** Use read-only file inspection for workspace evidence. Run read-only
   commands such as `gh pr checks`, `systemctl status`, or `podman ps` directly when the host grants
   Bash. Quote user-provided identifiers, reject values beginning with `-`, and prefer structured
   output. Delegate an independent or long-running check when the host grants subagents. If neither
   execution nor delegation is available, return `CONDITIONAL` or `NO-GO` with the exact command the
   caller must run; never present an unexecuted command as evidence. Any command with side effects,
   credentials beyond read access, or material cost requires explicit user authority.

3. **Apply the evidence audit table.**

   | Claim type | Accepted evidence | Default verdict |
   |------------|-------------------|-----------------|
   | CI gate result | `gh pr checks <pr> --json name,state` showing the named gate in SUCCESS state | Run `gh pr checks`; report gate state verbatim |
   | Measured metric in PR body | (a) CI-produced artifact URL, OR (b) re-executed run output | NO-GO unless either is present |
   | Committed `epoch*.log` file in PR | n/a | **NEVER** independent evidence |
   | Training result on slow path | detached-execution run record | NO-GO unless a follow-up evidence-collection task has landed |

4. **Report.** Use the Output contract below. **Do not soften the verdict.**
   A NO-GO with a clear "here is what would change it" answer is the right
   outcome for a fabricated claim.

# Failed attempts

- Do NOT call `repo-review` for claim verification; it audits repositories, not individual claims.
- Do NOT accept a "✓" emoji in a comment as evidence.
- Do NOT re-read the same PR body line to "find" the evidence the user already pasted. Query the
  current gate state or run the safe verification command; reproduce an expensive run only with the
  required authority and resource budget.
- Do NOT claim "looks good" because the PR is from a trusted author.
  Under Athena's evidence policy, evidentiary channel matters, not source reputation.

# Output contract

Return a markdown table:

```markdown
## Verification verdict for <one-line claim>

| Field | Value |
|-------|-------|
| Claim | <verbatim claim text> |
| Class | CI gate / measured metric / training result / operational |
| Evidence cited | <path, URL, or PR #N> |
| Evidence channel | CI-produced artifact / re-executed run / committed file (NOT EVIDENCE) / none |
| Verdict | GO / CONDITIONAL / NO-GO |
| Action | <one-line "what would change the verdict"> |
| Policy reference | `docs/policies/evidence-integrity.md` |
```

Then a short paragraph (≤ 4 lines) explaining the verdict.

# References

- [`docs/policies/evidence-integrity.md`](../../docs/policies/evidence-integrity.md) — governing
  policy.
- Skill catalog: see the canonical [`skills/`](../) directory and the root
  [`README.md`](../../README.md).
