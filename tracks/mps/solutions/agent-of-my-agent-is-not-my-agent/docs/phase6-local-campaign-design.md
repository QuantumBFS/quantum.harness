# Phase 6 local campaign design

## Scope

Run a serial, resumable sigma=1.75 pilot on local hardware without Slurm:

- sizes `L=32,64`;
- Gamma values `1.555,1.560,1.565`;
- even sector at every point for full `C(r)` and `R_xi`;
- odd sector only at `Gamma=1.560` for the gap;
- direct `chi=128`;
- exact-zero channel pruning (`chi_MPO=44`);
- atomic HDF5 MPS checkpoints and JSON manifests.

The completed `L=32, Gamma=1.560` even/odd pilot is reused after strict
settings, fit-hash, code-hash, and checkpoint validation.

## Execution

A local campaign ledger enumerates individual sector cells and records
`pending`, `running`, `success`, or `failed`. Cells run serially and publish
their manifest only after successful checkpoint publication. Restarting the
campaign skips compatible successful cells and retains failed/missing cells.

The campaign contains eight sector cells:

- six even cells: two sizes times three Gamma values;
- two odd cells: two sizes at `Gamma=1.560`.

Two L=32 cells already exist, leaving six new cells.

## Analysis

Collect raw `S(0)`, `S(k_min)`, `xi`, `R_xi`, energies, variances, discarded
weights, sweeps, wall time, reached chi, fit/MPO metadata, and code hash.
Compare the L=32 and L=64 `R_xi` curves. Use the locked neighboring-point
linear interpolation only when the sampled difference changes sign.

The gap is reported independently at each size. No final `Gamma_c` or `z`
claim is made from two sizes.

## L=128 feasibility

Estimate runtime and peak memory from measured L=32 and L=64 cells. Report
ground-only and even+odd costs separately. Do not launch L=128 automatically.

## Local-only guarantee

The campaign has no SSH, Slurm, sbatch, rsync, or cluster-profile call. The
previously created active SCNet profile link is removed from the active
workflow. Cluster profile source files remain untouched.
