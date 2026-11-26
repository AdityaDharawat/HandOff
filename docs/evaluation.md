# Evaluation

Use fixtures for working and incomplete applications, missing setup information,
misleading Git claims, failing recorded tests, and stale snapshots. Compare each
generated finding with an independently reviewed fixture manifest. Count supported
claims, unsupported claims, broken references, secret canary occurrences, detected
changes, and byte differences outside the managed blocks. Measure scan duration
with file counts, byte totals, operating system, and interpreter recorded.

For the fresh-agent benchmark, give separate sessions the same repository and
task with equal time and tools. Provide HANDOFF_AGENT.md only to the treatment
session. Compare first useful action, correctness, scope control, validation,
and time to a working patch. Repeat across fixtures and record both results.

An initial read-only pilot used two separate agent sessions and the sample
project's two source files. The treatment also received the generated
`HANDOFF_AGENT.md` finding and evidence excerpt. Both recognized the reset
placeholder and avoided claiming tests ran. The control proposed a regression
test for addition. The treatment prioritized establishing the reset contract
and proposed conditional implementation and validation steps. Neither edited
files or executed checks. This single case shows a difference in task choice.
A repeated benchmark with full reports and executed patches remains pending.
