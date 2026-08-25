# Evidence integrity policy

Apply the [ASD-STE100 technical-English policy](../technical-english.md) to all English technical
prose in this document.

This policy is binding on each human and agent contribution to Athena.

The governing rule is: **a truthful failure is acceptable; invented success is not.**

1. Do not create or change a log, metric, benchmark, test result, or release result to represent a
   run that did not occur.
2. Do not treat a committed result file as independent evidence.
3. Prefer a continuous integration (CI) artifact or an independent run of the command from the
   reviewed revision.
4. Bind each claim to this information:

   - a reproducible command;
   - an immutable revision;
   - the relevant environment;
   - the exit status; and
   - the unedited output.

5. If evidence collection cannot finish in the active session, separate it from the implementation.
   Supply the runnable command and report accurately that the run is not complete.
6. If you cannot get a measurement, report this information:

   - what you tried;
   - why the attempt failed or timed out; and
   - the action that can get the measurement.

7. Do not use a plausible estimate as a fact when a measurement is not available.
8. If the path that produces the evidence cannot emit the claimed format, reviewers must reject the
   evidence.
9. If the timestamp, revision, environment, or CI identity cannot be reconciled with the claim,
   reviewers must reject the evidence.

The `repo-review` and `pr-review` skills enforce this policy.
