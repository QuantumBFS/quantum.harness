# Phase 6 sigma=1.75 production preparation

## Planner inventory

- Locked Gamma values: 24 (`1.540...1.580`, nested fine grid included).
- Planned base cells: 96 = 4 sizes x 24 Gamma values.
- L=32 qualification cells: 24.
- L=64,128,256 production cells: 72.
- Targeted chi refinement and odd-sector gap cells are additional and are
  generated only after crossing brackets are known.

## Measured timing probe

The completed `L=32`, `Gamma=1.560`, `chi=128`, `K=24` cell used:

- wall time: 235.48 seconds;
- peak resident memory: 954528 KiB (0.91 GiB);
- energy variance: `1.4906618162058294e-9`;
- discarded weight: `8.20702739217239e-11`.

Its manifest contains energy, variance, discarded weight, achieved chi,
complete `C(r)`, `S(0)`, `S(k_min)`, `k_min`, `xi`, `R_xi`, and per-sweep
statistics. Its correlation CSV has 32 data rows.

## Resource estimate

Using the measured cell and the leading linear-in-L cost/memory scaling at
fixed chi:

| Size | Estimated wall per base cell | Estimated peak memory |
|---|---:|---:|
| 64 | 7.85 min | 1.82 GiB |
| 128 | 15.70 min | 3.64 GiB |
| 256 | 31.40 min | 7.28 GiB |

The 72 production base cells represent about 22 node-hours if serialized.
Array wall time depends on the ratified concurrency and live queue. Higher-chi
refinements scale approximately as `chi^3` in compute and `chi^2` in MPS
memory and therefore require separate resource requests.

## Blocking preparation requirements

1. Complete the remaining 23 L=32 base cells remotely; the measured serial
   local estimate is 1.57 hours, above the harness local-compute limit.
2. Complete/checkpoint the per-sigma K=32 validation fit; the all-at-once
   local fit command exceeded ten minutes and was stopped.
3. Select and activate a valid Slurm profile, probe its live partitions, and
   ratify the partition before submission.
4. Authorize a shipping strategy for the dirty solution worktree. No implicit
   commit, push, or rsync is permitted.
5. Qualify the remote TeNPy environment before array submission.

No Slurm job has been submitted.

## Optimization benchmark update

The exact-zero gate passed dense-MPO, spectrum, and correlation validation
through `L=12`. The three zero coefficients in the locked K=24 fit are now
eligible for exact pruning, reducing the bulk MPO dimension from 50 to 44.
No approximate MPO compression is used.

At `L=32`, `Gamma=1.560`, the staged `32 -> 64 -> 128` calculation gave:

| Sector | Direct chi=128 phase | Staged total | Final staged energy |
|---|---:|---:|---:|
| even | 193.26 s | 285.93 s | -56.98348639337348 |
| odd | 200.63 s | 271.14 s | -56.83038718330993 |

The staged calculation reproduces the direct gap and `R_xi`, but its two
preconditioning stages make the pair about 41% slower overall. It is therefore
not selected for the base Gamma scan. It remains available for targeted chi
refinement, where each stage now produces a provenance-safe HDF5 checkpoint.

The final warm/pruned chi=128 stages took 178.06 s (even) and 184.51 s (odd),
about 8% below the corresponding direct unpruned phases. Because this combines
warm initialization and exact pruning, it is not an isolated pruning
benchmark. The conservative production estimate remains 22 serialized
node-hours for the 72 base cells. A structural projection using the MPO
dimension ratio `44/50` is 19.3 node-hours, but this is explicitly not a
measured runtime commitment.

The L=16 staged pair took 154.85 s. A complete two-sector forward/reverse
continuation audit would exceed the remaining local budget and is recorded as
deferred, as allowed by the approved cost gate. Continuation correctness is
locally qualified against cold DMRG and ED only for `L<=12`.
