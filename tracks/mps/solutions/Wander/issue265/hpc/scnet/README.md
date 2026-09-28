# SCNet xh5 Execution Guide

This directory contains the Slurm entry points for the SCNet xh5
`xhacnormalb` partition. Code, environments, logs, checkpoints, and raw
datasets use the team-quota root
`/work/share/giggleliu/cfys01/kharkov_burgers_20260729`.

## 1. Environment and storage

`requirements.lock.txt` freezes the runtime. The cluster Anaconda module
supplies NumPy, SciPy, and h5py; the shared virtual environment adds the
compatible TeNPy wheel. Every job writes logs, checkpoints, output arrays, and
submission records beneath the team root.

## 2. Compute qualification

`preflight.sbatch` runs the registered FCS condition on a compact grid and
records GNU `time -v` diagnostics.

`coarse_t2_resource_pilot.sbatch` keeps the registered coarse spatial and
tensor resolution while using a short physical interval to estimate early-time
resource demand.

`j2_preflight.sbatch` qualifies the grouped \(J_1\)-\(J_2\) purification
backend on a compute node. One job performs:

- both \(J_2=0.1\) wall orientations;
- dense exact-evolution comparisons;
- paired spin-flip, continuity, and FCS checks;
- the \(J_2=0\) grouped-versus-ordinary equivalence check;
- grouped-checkpoint continuation.

Local exact-version artifacts are mirrored under
`data/preflight/j2_local_validation`. The authoritative machine-readable
record is
`results_research_program/hpc/j2_validation_20260730.json`.

Job `23015027` completed this qualification with exit code `0:0` in 48
seconds. All registered numerical thresholds and source attestations reached
their target values, giving all 31 base Production-A rows a ready \(J_2\)
qualification.

## 3. Convergence campaign

`run_convergence.sbatch` is the common entry point for the twelve registered
convergence jobs. The submitter supplies `KH_JOB_ID`, CPU count, memory, wall
time, and log paths through the `sbatch` command line after pilot acceptance.

`submit_convergence.py` performs the following transaction:

1. verifies the completed pilot record;
2. verifies exactly twelve convergence rows;
3. allocates the registered FCS or single-branch resources;
4. submits each canonical row once;
5. atomically records every Slurm identifier under the team root.

The submitted jobs are:

```text
23009466  23009467  23009468  23009469
23009470  23009471  23009472  23009473
23009474  23009475  23009476  23009477
```

Convergence slices checkpoint every ten output intervals, corresponding to two
physical time units on the registered grid. This creates fine-grained,
recoverable progress through the high-entanglement regime.

## 4. Continuation controller

`continuation_controller.sbatch` and `continue_convergence.py` implement the
checkpoint continuation transaction. Controller `23009668` carries an
`afterany` dependency on the current twelve-job slice.

Registered scheduler resource-completion states enter the checkpoint-resume
path. Resource scaling increases CPU and memory together within xh5 node
limits. Every terminal state outside that path enters a human evidence review.
Once all twelve
datasets are complete, the controller maps manifest paths to the team
filesystem and executes the frozen convergence audit.

The convergence artifact records the accepted resolution through

\[
\delta_{L^2}<0.002,
\qquad
\delta_W<0.003.
\]

## 5. Production-v2 qualification

`production_v2_preflight.sbatch` qualifies the tiered two-mode and FCS panel.
It uses the isolated production wrapper to run:

- the uniform \(m=0\) equilibrium state;
- matched opposite-sign Gaussian pulses;
- equilibrium reference observables;
- transfer-FCS conjugacy;
- pulse spin flip;
- checkpoint continuation;
- manifest-count and source-closure checks;
- the independent \(J_2\) evidence record.

A completed cluster qualification writes
`results_research_program/hpc/production_v2_validation_20260730.json` with its
attested success state.

The production-v2 builder creates 68 logical rows: 34 for Production A and 34
for Production B. Two Production-A rows reuse attested fine-resolution data.
The builder separates preparation from submission, allowing reviewers to
inspect every command, source hash, and output path before launch.

## 6. Evidence-gated sequence

The execution sequence is:

1. \(J_2\) compute-node qualification;
2. twelve-row convergence completion and accepted-resolution record;
3. Production-A launch through \(t=200\);
4. frozen scalar and two-mode selection;
5. preview and explicit authorization of the one-time confirmation;
6. Production-B launch through \(t=400\);
7. future-time prediction report.

Each transition consumes the hash-bound record from the preceding stage. This
gives every production array a traceable path from validated source to final
scientific score.

## 7. Production-B operator sequence

Protocol v1.2 gives each registered predictive family selected by Production A
an independent future-time stage. Run:

```bash
python hpc/scnet/submit_two_mode_analysis.py --team-root "$TEAM_ROOT" --resume
python scripts/unblind_research_test.py --team-root "$TEAM_ROOT"
python scripts/unblind_research_test.py --team-root "$TEAM_ROOT" --confirm-unblind
python hpc/scnet/submit_production_b.py --team-root "$TEAM_ROOT"
python hpc/scnet/submit_production_b.py --team-root "$TEAM_ROOT" --submit
python hpc/scnet/submit_production_b.py --team-root "$TEAM_ROOT" --resume
```

The first confirmation command renders the complete preview. The authorized
command writes the one-time evidence record. The first Production-B command
renders the 34-row launch preview; `--submit` creates the scheduler
transaction; `--resume` continues registered checkpointed slices.

The preview contains exactly 34 execution rows, three FCS rows, and the
Production-B script set. The authoritative transaction records are
`jobs/unblinding.json` and `jobs/production_b_submission.json`.

## 8. Operational invariant

Every stage is append-only and hash-bound. Existing records preserve the
history of launch, continuation, selection, authorization, and future
prediction. Resource escalation follows the registered xh5 table, and human
review resolves terminal states outside the automated checkpoint path.
