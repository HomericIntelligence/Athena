# Evidence integrity policy

This policy is binding on every human and agent contribution to Athena.

The governing rule is: **a truthful failure is acceptable; invented success is not.**

1. Never hand-author or edit a log, metric, benchmark, test result, or release result to represent a
   run that did not happen.
2. A committed result file has no independent evidentiary weight. Prefer CI artifacts or a command
   independently re-executed from the reviewed revision.
3. Bind every claim to a reproducible command, immutable revision, relevant environment, exit
   status, and unedited output.
4. Separate long-running evidence collection from implementation when it cannot finish within the
   active session. Deliver the runnable command and report non-completion truthfully.
5. When a measurement cannot be obtained, report what was attempted, why it failed or timed out,
   and what would obtain it. Never fill the gap with a plausible estimate presented as fact.
6. Reviewers must reject evidence whose producing path cannot emit the claimed format or whose
   timestamp, revision, environment, or CI identity cannot be reconciled.

Athena's `verification`, `repo-review`, and `pr-review` skills enforce this policy.
