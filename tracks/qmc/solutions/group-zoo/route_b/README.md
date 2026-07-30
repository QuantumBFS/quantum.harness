# Challenge #148 Route B

This directory contains the independent continuous-time Huang worm route for
the triangular/honeycomb transverse-field Ising critical-point ratio. The
sampler uses the rotated but spectrally equivalent Hamiltonian

```text
H = -J sum_<ij> sigma_x(i) sigma_x(j) - h sum_i sigma_z(i),  J = 1.
```

Route B has its own Julia environment and must not import Route A's geometry,
worldline state, update kernel, random streams, checkpoints, or observables.

## Storage boundaries

- Local tracked worktree: `/home/zcq/work/challenge-148-route-b-lab`
- Local untracked evidence: `/home/zcq/work/challenge-148-route-b-evidence`
- SCNet root: `/work/home/zhangchenqi/challenge148/route-b/`
- Future final deliverable: `tracks/qmc/solutions/group-zoo/route-b/`

Route B must not write into the Route A worktree, Route A evidence, Route A
SCNet campaigns, or `/home/zcq/work/challenge-148-final`.

## Current authorization

Implementation and non-production validation are authorized. Target-lattice
production, Suwa optimization, SCNet submission, final ratio fitting, and a
scientific verdict remain gated by the approved design and later plans.

Run the isolated test suite with:

```bash
julia --project=route_b route_b/test/runtests.jl
```
