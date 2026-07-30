# Challenge 15: finite-sphere projected-Pfaffian core

This package implements the auditable core calculation for the finite-size
lowest-`L=2` sector gap at Laughlin filling `ν=1/3`. It uses one
sector-conditioned projected-Pfaffian parameter tree for `L=0` and `L=2`.

## Environment

The supported interpreter is CPython 3.12. From this directory:

```bash
uv sync
uv run python -c \
  "import jax; print(jax.default_backend(), jax.config.x64_enabled)"
uv run pytest -q
```

`jax.config.x64_enabled` must be `True`. CPU execution is supported. A GPU run
requires a matching CUDA-enabled `jaxlib`; the runtime provenance in every
artifact records the backend and x64 state.

## Commands and restart

All subcommands accept `--config PATH` with a JSON object. Command-line values
override the corresponding JSON fields. The canonical JSON SHA256 is stored in
each artifact.

```bash
uv run python -m challenge15.cli oracle \
  --particles 6 \
  --output ../../../results/frustration-free/challenge-15/oracle-n6

uv run python -m challenge15.cli train \
  --particles 6 --ranks 1,2,4 --seeds 0,1,2,3,4 --steps 100 \
  --output ../../../results/frustration-free/challenge-15/n6

uv run python -m challenge15.cli train \
  --config n6.json --output ../../../results/frustration-free/challenge-15/n6 \
  --resume

uv run python -m challenge15.cli evaluate \
  --checkpoint ../../../results/frustration-free/challenge-15/n6/checkpoint.json \
  --oracle ../../../results/frustration-free/challenge-15/oracle-n6/result.json \
  --output ../../../results/frustration-free/challenge-15/n6

uv run python -m challenge15.cli verify \
  --artifact ../../../results/frustration-free/challenge-15/n6/evaluation.json

uv run python -m challenge15.cli report \
  --evaluation ../../../results/frustration-free/challenge-15/n6/evaluation.json \
  --output ../../../results/frustration-free/challenge-15/n6

uv run python -m challenge15.cli manifest \
  --n6 ../../../results/frustration-free/challenge-15/n6/evaluation.json \
  --n7 ../../../results/frustration-free/challenge-15/n7/evaluation.json \
  --n8 ../../../results/frustration-free/challenge-15/n8/evaluation.json \
  --output ../../../results/frustration-free/challenge-15/final
```

Training publishes a verified atomic checkpoint after each rank/seed. A resume
is rejected unless its complete canonical configuration hash matches. Each
checkpoint includes the shared parameters, Adam state, every PRNG split,
paired-batch hashes, optimizer diagnostics, source hashes, Git revision,
runtime versions, and input hashes. Unique sibling partials are file-fsynced,
verified, atomically replaced, and followed by parent-directory fsync.
Every load recomputes the training-configuration digest, record coverage,
serialized-state hashes, completed identities, and rank-parent lineage.
It also recomputes the execution fingerprint over all package sources,
`pyproject.toml`, `uv.lock`, Python, JAX, jaxlib, Flax, Optax, NumPy, SciPy,
SymPy, and h5py versions, x64, backend, platform, and schema policy. Stale code
or runtime artifacts fail closed.

## Physical and numerical conventions

- `2Q = 3(N-1)`, with north-chart holomorphic monopole spinors.
- Orbital order follows increasing `2m`; determinant order follows increasing
  integer bit patterns with ascending creation operators.
- Distances are physical sphere chords
  `r_ij = 2 sqrt(Q) l_B sin(gamma_ij/2)`.
- Energies are in `E_C = e²/(4π ε₀ ε l_B)`.
- The reported gap is `Δ₂ = E(L=2)-E(L=0)`, not necessarily the absolute
  lowest neutral excitation.
- The sparse M=0 low-energy scan separately reports the absolute excitation
  energy and its integer `L`; it resolves energy-degenerate subspaces with
  `L²` and fails closed on ambiguous classification.
- One parameter tree is optimized with `w₀E₀+w₂E₂` on paired sector batches.
  There are no private sector models.

For `N≤8`, exact coefficient-space evaluation reports energy, overlap, true
projected-Hamiltonian variance `Var(H_LLL)`, exact angular-momentum residuals,
quadrature changes, and projected carrier-span singular values. Coordinate VMC
reports a bare Coulomb potential estimator and its sampling variance. That
sampling variance is never labeled as `Var(H_LLL)`.

## Fail-closed gates

Ranks are nested as `1,2,4,...`. Two consecutive doublings must each satisfy

```text
|delta E_L| + 2 sigma_diff <= 1e-4 E_C
|delta Delta_2| + 2 sigma_diff <= 0.002 Delta_2
```

Exact rank analysis requires identical seed sets at every adjacent rank and
uses `sigma_diff=0` by contract. Stochastic analysis is separate: it requires
at least two identically paired seeds and computes uncertainty from paired
differences, retaining covariance. Missing pairs fail closed rather than
returning zero uncertainty. Increased noise makes the left-hand side larger
and can never relax a gate. Where exact overlaps exist, their change must be at
most `1e-3`. These tolerances, two required doublings, and the minimum four of
five seed gate are immutable. Any missing `(rank, seed)`, failed numerical
gate, or unavailable gate leaves the system explicitly pending.

Smoke optimization uses generated coordinate batches, not an accept/reject
sampler. Its acceptance-rate fields are therefore JSON `null`; step energies,
norms, and gradient norms are explicitly labeled as pre-update diagnostics.

The production target-sector solver uses a basis-invariant thin `D×r`
canonicalization with lexicographic row pivots and only `r×r` gauge matrices;
it never forms a `D×D` projector. Its immutable symmetry gates are a Gram
defect at most `1e-12`, an `L²` target residual at most `1e-11`, and a
reconstructed generator/ladder intertwining residual at most `1e-11`. All
three diagnostics, pivots, and the linear-storage bound are persisted and
recomputed when an oracle cache is restored.

Production proceeds in order `N=6`, then `N=7`, then `N=8`; a later size is not
accepted without a hash- and provenance-bound accepted artifact for the prior
size. The final manifest remains pending unless all three semantic evaluations
validate. Full determinant-space dimensions
are 8,008, 50,388, and 319,770 respectively. Exact construction, sector
diagonalization, repeated projected-carrier expansion, and doubled quadrature
dominate memory and wall time. Carrier rank, determinant block size, and
quadrature order must be reported with peak RSS and elapsed time.

**N=6-8 production acceptance is pending.** Passing every immutable numerical,
statistical, provenance, and cross-size gate would establish the finite-size
lowest-L=2 sector gap. It is not a chiral-graviton claim; that requires the
separate metric-response acceptance plan.

## Audited production controllers

The sole operator entry point is `challenge15 production-orchestrate-size`.
Low-level Slurm, transfer, deployment, and scientific commands are internal
create-only state-machine contracts.

- Qdeshell uses `dzagnormal`, account `giggleliu`, QOS
  `user_jiangweiqi`, and one A800 80 GB GPU per five-way seed array task.
  The approved result root is
  `/work/share/giggleliu/jiangweiqi/results/challenge15`.
- LASG02 uses `ihicnormal`, account `chenkun2025`, QOS
  `user_student090`, 24 CPUs, and 80000 MiB. The approved result root is
  `/public/home/student090/results/challenge15`.
- WUZH02 remains inactive. `discover_wuzh02.py` fails closed unless complete,
  explicitly labelled scheduler, capacity, Python 3.12, project-root, and
  result-root evidence is supplied.
- `xh5-jiangweiqi` is only a documented fallback (account `giggleliu`, QOS
  `user_jiangweiqi`; available GPU families include 3090, 3080, and V100).
  No production controller role or exact partition profile is approved by the
  immutable design, so the orchestrator does not submit there.

Remote `sbatch --test-only`, final deployment receipts, runtime attestations,
and scientific jobs are deferred until the final clean source freeze.
