# G2 measured resource report

Status: measured locally for χ=64 and χ=128 and on the `manageb` Slurm
`batch` partition for 20 seeds each at χ=192 and χ=512. SCNet was not used.

## Local machine and graph

- local CPU: Intel Core Ultra 5 125H, 18 logical CPUs;
- local memory: 11 GiB total, about 9 GiB available during inspection;
- no usable GPU was visible in the current environment;
- OLE graph: 49 vertices, 54 unique edges, with 39 degree-2 and 10 degree-3
  vertices.

For a fully saturated ComplexF64 tensor-network state, the site-tensor storage
alone is

```text
16 bytes × Σ_v (2 χ^degree(v)).
```

This excludes BP messages, copied caches, contraction intermediates, SVD
workspace, Julia runtime, and checkpoints.

| χ | saturated site tensors | recommended memory tier for a probe |
|---:|---:|---:|
| 64 | 0.08 GiB | 8–16 GiB |
| 128 | 0.64 GiB | 16–32 GiB |
| 192 | 2.15 GiB | 32 GiB; 64 GiB if the first probe approaches the limit |
| 256 | 5.08 GiB | 64 GiB |
| 384 | 17.05 GiB | 128 GiB |
| 512 | 40.30 GiB | 256 GiB preferred; 128 GiB only after a measured probe |

Actual bonds may remain below χ, so these are not predictions of observed RSS.
They are useful upper-envelope checks. Conversely, allocating only the
site-tensor number is unsafe because simple-update SVD and BP create additional
large objects.

## Measured local probes

The measurements below use one Julia thread, nine BLAS threads, ComplexF64,
`cutoff=1e-12`, and a fresh Julia process for every cell. Thus they include
roughly 24–28 s of first-call compilation in layer 2.

| χ | δ | wall time | peak RSS | OLE sample | max truncation error |
|---:|---:|---:|---:|---:|---:|
| 64 | 0.15 | 101.0 s | 1.66 GiB | 0.8340207 | 2.73e-3 |
| 64 | 0 | 89.4 s | 1.11 GiB | 1.0000000 | 8.92e-29 |
| 128 | 0.15 | 129.9 s | 2.12 GiB | 0.8264242 | 5.29e-4 |

All BP solves reported convergence. The largest recorded BP residual was
5.04e-10, below the configured tolerance 1e-8. The δ=0 circuit returned
exactly one and never needed a bond above 32, providing a strong protocol
sanity check. The χ=64 and χ=128 OLE values are single-seed diagnostics, not
the final 20-seed baseline.

Per-layer norm defects are unavailable: TNQS local tensor normalization
discards the global scale required for that diagnostic. The χ=64, δ=0.15
probe predates that guard, so its stored `norm_defect` field must be ignored;
its OLE, timing, RSS, truncation, and BP fields remain valid. Later records
mark the diagnostic unavailable explicitly.

## Measured Slurm production runs

The production cells used one Julia thread, 16 BLAS threads, ComplexF64,
`cutoff=1e-12`, and the `batch` partition. Each cell was a fresh Julia
process. The table covers the same 20 deterministic seeds at both χ values.

| χ | mean wall | max wall | mean RSS | max RSS | max truncation | max BP residual |
|---:|---:|---:|---:|---:|---:|---:|
| 192 | 120.2 s | 129.3 s | 2.27 GiB | 2.37 GiB | 2.50e-4 | 4.40e-11 |
| 512 | 134.2 s | 162.0 s | 3.07 GiB | 3.34 GiB | 9.99e-13 | 2.84e-16 |

No BP layer failed to converge. The actual high-χ memory is far below the
fully saturated site-tensor envelope because most graph bonds do not remain
at χ simultaneously.

The 40 completed χ=192/512 cells consumed 1.41 aggregate task-hours, or
22.61 allocated CPU-hours at 16 CPUs per cell. Because Slurm shared the nodes,
this should not be reported as 1.41 exclusive node-hours.

For future runs of this exact graph and implementation, 16 GiB per cell is
already more than 4.7 times the observed maximum RSS. Use 32 GiB when changing
depth, gate set, or TNQS version until a new probe confirms the memory.

## Scheduling note

On 2026-07-28, `sbatch --test-only` on this Slurm 23.11.4 installation
incorrectly predicted a 2026-08-06 start even for a 1-CPU job pinned to an
idle node. A real `srun --immediate=30 --mpi=none` smoke allocation started
immediately, as did jobs 410808, 410810, and array 410814. Therefore the
test-only timestamp was not used as queue evidence.

The run used a temporary, non-activated profile for
`zyli@172.16.42.215`; no `skills/using-slurm/profiles/active.toml` was created.
