---
name: verification
description: Audit a metric, CI result, or benchmark claim and report whether it is backed by runnable evidence per Odysseus ADR-014 (truthful failure acceptable, invented success is not). Use when a user posts a measurement assertion and asks whether to trust it.
allowed-tools: [Read, Glob, Grep]
---

# When to use

Invoke this skill whenever the user posts an assertion that names a specific
measured value: a metric, a CI gate result, a benchmark number, a training
loss, or a "this ran successfully" claim. The skill's job is **not** to
re-execute the run — that is a slow, out-of-band step. The skill's job is to
determine whether the claim is backed by **runnable evidence** per
[Odysseus ADR-014](https://github.com/HomericIntelligence/Odysseus/blob/main/docs/adr/014-runnable-evidence-for-metric-claims.md).

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
   - **Training/optimization result**: per ADR-014, the only accepted
     evidence is a CI-produced artifact or a detached-execution run record.
   - **Operational status** (e.g., "the daemon is running"):
     `systemctl status` or `podman ps` output.

2. **Locate the evidence.** Use `Read` / `Glob` / `Grep` to inspect the cited
   pointer in the workspace. For any external command (e.g. `gh pr checks`,
   `systemctl status`, a benchmark re-run), INVOKE THE COMMAND VIA ANOTHER
   SKILL OR AGENT WAVE — do not run it from inside this skill's invocation,
   because this skill's `allowed-tools` does not include `Bash`. Capture the
   verbatim output the caller returns.

3. **Apply the ADR-014 audit table.**

   | Claim type | Accepted evidence | Default verdict |
   |------------|-------------------|-----------------|
   | CI gate result | `gh pr checks <pr> --json name,state` showing the named gate in SUCCESS state | Run `gh pr checks`; report gate state verbatim |
   | Measured metric in PR body | (a) CI-produced artifact URL, OR (b) re-executed run output | NO-GO unless either is present |
   | Committed `epoch*.log` file in PR | n/a | **NEVER** evidence (per ADR-014 §1) |
   | Training result on slow path | detached-execution run record | NO-GO unless a follow-up evidence-collection task has landed |

4. **Report.** Use the Output contract below. **Do not soften the verdict.**
   A NO-GO with a clear "here is what would change it" answer is the right
   outcome for a fabricated claim.

# Failed attempts

- Do NOT call `/repo-analyze*` skills — those audit code structure, not claims.
- Do NOT accept a "✓" emoji in a comment as evidence.
- Do NOT re-read the same PR body line to "find" the evidence the user
  already pasted — re-running the gate is the whole point.
- Do NOT claim "looks good" because the PR is from a trusted author.
  Per ADR-014, evidentiary channel matters, not source reputation.

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
| ADR reference | ADR-014 |
```

Then a short paragraph (≤ 4 lines) explaining the verdict.

# References

- [Odysseus ADR-014](https://github.com/HomericIntelligence/Odysseus/blob/main/docs/adr/014-runnable-evidence-for-metric-claims.md) — governing policy.
- Hephaestus `hephaestus.audit.filter` — programmatic filter for the same
  audit, callable without invoking a skill.
- Skill catalog: see
  [`.claude-plugin/marketplace.json`](../../.claude-plugin/marketplace.json)
  for the latest published skills.
