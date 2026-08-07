# Sealed holdout temporal-isolation protocol

Status: frozen execution design; not implemented or queried.
Query budget: `0 / 1` aggregate holdout queries consumed.

## Threat model

SCNet does not permit the unprivileged mount, PID, or user namespaces needed to
make a private directory unreadable to another process running as the same
account. The validated v1 seccomp filter denies network syscalls, but it is not
a path-based filesystem sandbox. Therefore no private label, oracle output, or
precomputed expected artifact may exist on a candidate-readable filesystem
while any candidate process can still execute.

The holdout uses temporal isolation instead: expected outputs do not exist
until candidate execution is irreversibly over. This protocol does not weaken
the frozen holdout family, statistical tests, or one-query budget.

## Preconditions

The aggregate holdout allocation may start only after a public preflight
manifest identifies and verifies all of the following:

1. the accepted candidate commit and source-tree SHA-256;
2. the locked environment and public instance-database hashes;
3. completed discovery, confirmation, cost-sensitivity, and independent-seed
   artifacts with their manifest hashes;
4. a complete draft report and science-gate checklist;
5. the v2 sandbox contract and all five negative controls, including
   `background-escape`;
6. an absent holdout-spend record and a declared budget of exactly one query.

The preflight contains no holdout seed, exact parameter tuple, coordinate
relabeling, request hash, label, or oracle output.

## One aggregate query

Before the first private request is exposed to the candidate, the trusted
orchestrator creates the holdout-spend record with exclusive-create semantics,
flushes the file and its parent directory, and records the Slurm allocation,
candidate identity, protocol version, and public family-bounds hash. Failure
after that point consumes the only query and cannot be retried as a new
holdout.

The spend record remains open and locked by the orchestrator throughout the
allocation. Deletion, replacement, mutation, or loss of its directory entry is
a terminal holdout failure, not permission to rerun.

## Candidate phase

The candidate phase runs as a dedicated Slurm job step. For each member of the
sealed family, the trusted orchestrator generates only the current request and
passes that request plus an empty output directory to the candidate. Requests
use unseen domain-separated seeds and coordinate relabelings but the same
frozen public schema and parameter bounds.

During this entire phase:

- no expected result, logical label, oracle output, or private validation
  report exists;
- proxy variables are removed and the v2 inherited seccomp filter is active;
- `setsid` and `setpgid` are denied, so descendants remain in the candidate
  process group;
- the runner inventories the process group after every candidate exit,
  terminates all surviving members, and rejects the query if any background
  member was detected;
- the candidate source hash and holdout-spend record are checked after every
  invocation;
- only requests and unvalidated candidate outputs persist for the later
  trusted phase.

All candidate invocations must finish before any expected artifact is
generated. A timeout, crash, sandbox violation, missing shot, background
process, or malformed output ends the aggregate query as a failure.

## Step boundary

After the final candidate invocation, the orchestrator closes the candidate
step and requires Slurm to report that step complete. It then proves that no
live process remains in any recorded candidate process group and that the
candidate step cgroup has no remaining process. If either proof is unavailable
or nonempty, the holdout fails before private validation begins.

## Private validation phase

Only after the step boundary passes may a separate trusted Slurm step derive
the oracle/reference outputs from the sealed requests. It performs exact shot
accounting, replay, schema, causal, resource, label-isolation, and score guards.
Detailed labels and per-instance diagnostics remain private. The public result
contains only the aggregate pass/fail result, guard summaries, provenance
hashes that cannot serve as pre-query lookup keys, and the spend-record hash.

Any failed guard is final and is reported without inspecting and tuning against
private details. Success does not authorize another query.

## Evidence required before acceptance

This protocol is not accepted merely because the code exists. The final
holdout allocation must preserve:

- the preflight manifest and its checksum;
- the exclusive holdout-spend record and checksum;
- candidate process-group cleanup evidence for every invocation;
- Slurm candidate-step and cgroup-empty evidence;
- private validation manifest and checksum;
- the aggregate public result and checksum;
- an audit showing exactly one holdout allocation and no prior private labels.
