# Evidence integrity policy

Apply the [ASD-STE100 technical-English policy](../../skills/TECHNICAL_ENGLISH.md) to all English
technical prose in this document.

This document describes integrity aspirations for evidence in Athena contributions, from humans
and agents alike.

The governing rule has two parts: **A truthful failure is acceptable. Invented success is not
acceptable.**

1. Aim to create or change a log, metric, benchmark, test result, or release result only for a
   run that occurred.
2. A committed result file is a starting point, not independent evidence.
3. Prefer a continuous integration (CI) artifact or an independent run of the command from the
   final revision when the command is cheap enough to reproduce.
4. A claim binds best to this information:

   - a reproducible command;
   - an immutable revision and the recorded content identity of any uncommitted changes;
   - the relevant environment;
   - the exit status; and
   - the unedited output.

5. If evidence collection cannot finish in the active session, separate it from the
   implementation.
6. If evidence collection cannot finish in the active session, supply the runnable command.
7. If evidence collection cannot finish in the active session, report accurately that the run is
   not complete.
8. If you cannot get a measurement, report this information:

   - what you tried;
   - why the attempt failed or timed out; and
   - the action that can get the measurement.

9. Prefer a measurement over an estimate; a plausible estimate, when one is all you have, is
   presented as an estimate, not as a measurement.
10. Evidence the producing process cannot emit in the claimed format, or evidence whose timestamp,
    revision, environment, or CI identity cannot be reconciled with the claim, is worth treating
    with plain skepticism and a closer look.
11. For feature work, binding evidence to the recorded worktree start commit and the exact
    candidate content keeps an initial review base stable.
12. Remote target-branch movement does not invalidate evidence for unchanged candidate content.
    A rebase because the branch is behind is rarely the right fix.
13. If a permitted rebase or conflict resolution changes candidate content, bind the changed
    content and repeat the affected checks and validation.
