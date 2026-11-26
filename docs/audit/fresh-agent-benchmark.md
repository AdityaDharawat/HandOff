# Fresh-agent benchmark

Create six independent synthetic repositories with
`python scripts/audit_workloads.py fixtures .verification-audit-agents`.
The control has README and source. Treatment also has the two generated
handover reports. Each trial starts without conversation history. The shared
prompt asks for current state, three next actions, one bounded edit to
`app.py`, preserved tests, and local validation if available. Agents were
restricted to their assigned fixture and were asked to preserve Git state.

| Scenario | Ground truth | Control | Treatment |
|---|---|---|---|
| Queue | Append worked; dequeue needed FIFO and empty handling | Correct diagnosis and minimal patch | Correct diagnosis and minimal patch; cited placeholder evidence |
| Slug | Lowercasing worked; stale TODO; empty fallback missing despite README | Correct diagnosis and fallback | Correct diagnosis and fallback; cited evidence and removed stale TODO |
| Port | Configured port worked; absent configuration raised instead of defaulting | Correct diagnosis and one-line fix | Correct diagnosis and one-line fix |

Regenerate pristine inputs in a second directory. Run
`python -m pytest -q -p no:cacheprovider PATH/TO/ARM/app.py --tb=no` separately
for each input and result. The parent ran this against all six original arms
and all six resulting arms. Each original failed its one test. Each continuation
passed it. Each agent changed one file and preserved its test. No unsupported
completion claims were observed in the agents' responses. The treatment slug
trial made one additional, relevant comment deletion.

Both arms succeeded on three of three tasks. This small trial does not
establish an improvement in task selection or correctness. Time to
understanding was not instrumented. Most child shell checks were blocked by
the sandbox startup error, and parent-run tests provided a consistent score.
The synthetic workloads isolate the core behaviors. They do not model a full
multi-module integration, misleading Git history, or dirty Git state. The
separate Git-backed integration test covers misleading commit evidence.
