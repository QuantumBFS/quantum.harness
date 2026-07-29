# AITP 2.0 migration handoff

Date: 2026-07-29

## Protocol boundary

AITP v5 is retired and its local Codex plugin has been uninstalled. The
authoritative AITP 2.0 repository states that S0 has not started and that no
installable 2.0 CLI or runtime exists. This file is therefore a
migration-ready handoff, not an AITP canonical record.

Do not import this handoff through a v5 MCP server or legacy v5 CLI. When the
AITP 2.0 runtime becomes available, convert each durable item below into the
smallest appropriate typed record and pin the cited Git and run artifacts.

## Project identity

- Challenge: Quantum Harness issue 15, antisymmetric SO(3)-equivariant neural
  quantum state for the `nu=1/3` chiral-graviton neutral gap.
- Fork: `https://github.com/bhjia-phys/quantum.harness-collab`.
- Development branch: `codex/route-d-plus`.
- Route D+ base commit:
  `80cc1d094dd919c43192d39d8498ba4cdebaa2f2`.
- Local compute policy: do not execute project code, tests, JAX, VMC, or ED on
  the WSL2 development host.

## Durable decisions

1. Benchmark Phase 1 fixes `N=6`, `2Q=15`, fully polarized fermions in the
   lowest Landau level on the Haldane sphere.
2. The energy convention is pair-only chord Coulomb in
   `e^2/(epsilon*l_B)`; the common fixed-`N,2Q` background cancels in
   `Delta_2=E(L=2)-E(L=0)`.
3. Production numerics require Python 3.11, JAX x64, `float64` and
   `complex128`, and a visible GPU. CPU fallback is not accepted.
4. The shared variational family must represent the `L=0` tower and all five
   `L=2` components. Phase 2 cannot begin before the Phase 1 manifest passes.
5. Nontrivial execution is restricted to the `hpccube-xh5` Slurm cluster.

## Environment observations

- The local WSL2 host has Git and authenticated GitHub access but lacks
  `python3.11`, `nvidia-smi`, and `nvcc`.
- The selected cluster login is reachable through the private SSH alias
  `hpccube-xh5`; key contents are deliberately excluded from this record.
- The Slurm account is `giggleliu`, QOS is `user_jiabohan5`, and the default
  Phase 1 partition is `xhhgnormal` with one RTX 3080.
- Remote project root:
  `/work/home/jiabohan5/quantum.harness-collab`.
- The remote login environment has no default Python 3 interpreter. A
  project-scoped Python 3.11 environment is required.
- The cluster has glibc 2.17. The compatible binary environment is pinned to
  JAX/JAXLIB/CUDA plugin 0.4.38, NumPy 2.0.2, `ml_dtypes` 0.5.1, and Optax
  0.2.4; the visible CUDA dependency set provides cuDNN 9.5.

## Evidence to attach after Phase 1

- clean validation commit SHA;
- Slurm job ID and exact submit request;
- `environment-manifest.json`;
- `requirements-lock.txt` and its SHA-256 digest;
- scheduler stdout/stderr;
- any failed environment attempt, preserved separately from physics evidence.

## Environment attempts

- A pre-submit request for 4 CPU and 16 GiB was rejected because it exceeded
  the partition's memory-per-CPU policy. No Slurm job was created; the ratified
  Phase 1 request is 4 CPU and 12 GiB.
- Slurm job `23000293` ran for two seconds on `e08r01` and failed before any
  dependency or project execution. Slurm spooled the batch script, so deriving
  the repository from `BASH_SOURCE[0]` produced `fatal: Not a git repository`.
  The entrypoint now requires an explicit absolute `ROUTE_D_PLUS_REPO_ROOT`.
- Slurm job `23001017` ran for 3 minutes 35 seconds on `e01r03`. The compute
  node could not resolve the package index host, so `pip` could not upgrade
  itself. The job was cancelled after the final retry to release the GPU. This
  establishes that environment installation must run on the internet-enabled
  login node and the compute allocation must only validate the locked venv.
- The first login-node dependency resolution did not produce a lock. An
  unconstrained `jax[cuda12]` backtracked to JAX 0.7.0 because newer wheels
  require a newer glibc; that stack then required cuDNN 9.8, which is absent,
  and attempted an `ml_dtypes` source build whose isolated NumPy dependency
  could not be satisfied. A binary-only dry-run identified the pinned 0.4.38
  stack before the next install attempt.
