# Evidence integrity policy

Apply the [ASD-STE100 technical-English policy](../../skills/TECHNICAL_ENGLISH.md) to all English technical
prose in this document.

This policy is binding on each human and agent contribution to Athena.

The governing rule has two parts: **A truthful failure is acceptable. Invented success is not
acceptable.**

1. Do not create or change a log, metric, benchmark, test result, or release result to represent a
   run that did not occur.
2. Do not treat a committed result file as independent evidence.
3. Prefer a continuous integration (CI) artifact or an independent run of the command from the
   reviewed revision.
4. Bind each claim to this information:

   - a reproducible command;
   - an immutable revision and the recorded content identity of any uncommitted changes;
   - the relevant environment;
   - the exit status; and
   - the unedited output.

5. If evidence collection cannot finish in the active session, separate it from the implementation.
6. If evidence collection cannot finish in the active session, supply the runnable command.
7. If evidence collection cannot finish in the active session, report accurately that the run is
   not complete.
8. If you cannot get a measurement, report this information:

   - what you tried;
   - why the attempt failed or timed out; and
   - the action that can get the measurement.

9. Do not use a plausible estimate as a fact when a measurement is not available.
10. If the path that produces the evidence cannot emit the claimed format, reviewers must reject the
   evidence.
11. If the timestamp, revision, environment, or CI identity cannot be reconciled with the claim,
   reviewers must reject the evidence.
12. For feature work, bind evidence to the recorded worktree start commit and the exact candidate
    content. Use that commit as the initial review base. Do not replace it only because the remote
    target branch changes.
13. Remote target-branch movement does not invalidate evidence for unchanged candidate content. Do
    not require a rebase because the branch is behind. Treat the current target state as separate
    integration and merge-readiness evidence.
14. If a permitted rebase or conflict resolution changes candidate content, bind the changed
    content and repeat the affected review and validation.

The `repo-review` and `pr-review` skills enforce this policy.
