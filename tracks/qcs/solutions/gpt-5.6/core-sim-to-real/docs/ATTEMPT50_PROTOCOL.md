# Attempt 50 protocol — final audit, reproduction, and submission package

Date frozen: 2026-07-29

Formal scientific result: Attempt 49, commit `c073ad0`

## Purpose

Attempt 50 does not select a new method, tune a gate, open a new truth set, or
upgrade a failed claim. It turns the immutable Attempt-49 result into a compact,
reviewable, and reproducible Challenge-113 package.

## Frozen scientific decision

The final scientific decision is the Attempt-49 `PASS`, unchanged:

- synthetic two-qubit CNOT only;
- 24 fresh truth cells, with four finite-shot replicates nested per cell;
- three frozen methods;
- post-hoc oracle-scored success at infidelity `<= 1e-3`;
- deterministic full-cap query and shot cost;
- six preregistered statistical, resource, and safety gates.

Attempt 50 must preserve both positive and negative results. In particular, it
must not relabel full-cap cost as observed online queries-to-target, claim that
the tested cross-dimension law passed, or turn the synthetic neutral-atom
adapter into cesium or hardware evidence.

## Deliverables

1. `code/attempt50_result_audit.py`
   independently reconstructs the run grid, seeds, truth-cell bootstrap,
   paired differences, cost formulas, safety interval, gates, source seals,
   and generated-artifact hashes without importing the simulator.
2. `run_challenge.py --mwe`
   runs one public development truth through the frozen `k=15`, completed
   `k=40`, and raw `k=40` paths. It retains every finite-shot query row and
   makes no statistical claim.
3. `run_challenge.py --full`
   replays all 288 public Attempt-49 runs into a new output directory. It is a
   reproducibility replay, not a second independent fresh confirmation.
4. `final/run.json`, `final/report.json`, and `final/report.html`
   provide the organizer-compatible compact result and offline report.
5. `code/attempt51_queries_to_target.py` derives the explicit
   queries-to-target versus dimension deliverable from sealed Attempts 44 and
   49 without opening a new truth or making a scientific query.
6. README, status, handoff, reproducibility, reflection, and final-report
   documents all use the same claim boundary.

## Runtime contract

- Set `JAX_PLATFORMS=cpu` and `JAX_ENABLE_X64=True` before importing JAX.
- Resolve all repository paths from `Path(__file__)`.
- Do not depend on a personal virtual-environment path.
- Use UTF-8 JSON, reject NaN/Infinity, and write JSON atomically.
- Never overwrite a non-empty run directory.
- Return exit code zero only if every mode-specific integrity check passes.
- Running the pipeline requires no network after dependencies are installed.
- Generated run directories live under ignored `run_outputs/` by default.

## MWE auditability rule

The formal Attempt-49 artifact compacted each detailed query ledger to:

- row count;
- total shots;
- per-purpose counts and shots; and
- canonical full-ledger hash.

That is sufficient to audit aggregate cost but not to reconstruct the stored
row hash from the compact artifact alone. The MWE therefore retains every
query row, including rejected and validation queries. Expected row counts are
`66`, `166`, and `166`.

## Full replay rule

The full mode uses exactly the now-public Attempt-49 truth identities, paired
measurement seeds, methods, caps, and scoring logic. Its summary must match
the archived Attempt-49 summary exactly. The output must explicitly say that
the truths are public and that the replay is not independent confirmation.

No replay may overwrite:

- `QL1F-attempt49-fresh-confirmation.json`;
- `ATTEMPT49_REPORT.md`; or
- either Attempt-49 figure.

## Final acceptance gates

Attempt 50 passes only if:

1. the independent result audit passes all checks;
2. `--mwe` completes with three full ledgers and a readable plot;
3. `--full` completes 288/288 runs and exactly reproduces the archived
   summary;
4. `run.json` has at least one non-empty figure result;
5. the post-hoc queries-to-target derivation passes all checks and preserves
   the failed online-certificate boundary;
6. `report.json` contains Challenge, Approach, Results, and Highlight;
7. `report.html` is valid UTF-8, self-contained, and embeds both result PNGs;
8. a clean-clone MWE leaves the Git tree clean; and
9. no protected notebook or teammate directory is staged.

## Known semantic correction

For drift-only Attempt-49 rows, the metadata field
`control_map_minus_identity_spectral_norm` describes a sampled candidate map
that was not applied. The actual applied control-map perturbation is zero.
This naming issue does not enter the simulator, success labels, bootstrap, or
gates. The immutable result is not edited; the correction is recorded in the
Attempt-50 audit and final report.
