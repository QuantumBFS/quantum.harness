# YueYuan Hardware-Readiness Design

## Goal

Make attempt 004 meaningful for later real-hardware tests by adding a
batch-oriented hardware boundary that does not depend on the simulator's exact
fidelity interface.

## Context

The current attempt is a strong software sim-to-real benchmark. Its closed-loop
optimizers call a strict `QueryOnlyDevice`, but the control flow is still local:
each optimizer evaluates one pulse candidate and immediately receives one scalar
infidelity estimate. Real cloud or lab hardware is usually job-oriented. Pulses
or circuits are submitted in batches, results return later as counts or
probabilities, and every submitted candidate and shot must be accounted for.

To make the work more publishable and hardware-ready, attempt 004 should prove
that the optimizer-facing objective can be separated from the physical
submission boundary.

## Design

Add a new `hardware_adapter.py` module with three responsibilities:

1. Define backend-neutral dataclasses for candidates, submitted jobs, returned
   results, and scalar evaluations.
2. Provide a dry-run batch backend powered by the existing `QueryOnlyDevice`,
   but expose only job IDs, count dictionaries, probabilities, query counts, and
   shot counts.
3. Write and read hardware-style batch artifacts: a manifest JSON file, a
   candidate CSV, a JSONL payload file for pulse parameters, and a JSONL result
   file that can be replaced by real hardware output later.

Add `run_hardware_dry_run.py` to exercise the boundary. The script should build a
small one-qubit Hessian candidate batch, export the batch bundle, run it through
the dry-run backend, ingest the returned counts, and write a summary with the
best candidate and resource accounting.

The hardware-readiness layer must not:

- include credentials, usernames, hostnames, SSH commands, or private keys;
- claim to submit to real hardware;
- change the existing full-sweep or adaptive-sweep scientific results;
- use exact true-device fidelity for optimizer decisions.

## Expected Artifacts

For a dry run under `tracks/qcs/results/YueYuan/attempt-004/hardware_dry_run/`,
the script should write:

- `batch_manifest.json`;
- `candidates.csv`;
- `pulse_payloads.jsonl`;
- `hardware_results.jsonl`;
- `hardware_summary.json`.

Generated artifacts remain ignored by git.

## Validation

Add tests that verify:

- batch dry-run submission consumes exactly one query and `shots` shots per
  candidate;
- scalar objectives are reconstructed from returned counts or probabilities;
- exported batch files contain candidate IDs, pulse dimensions, shots, and
  parameter payloads;
- the hardware dry-run script emits manifest, result, and summary files;
- exported files do not contain private access markers.

Run the existing attempt-004 and broader attempt test suites after the change.
