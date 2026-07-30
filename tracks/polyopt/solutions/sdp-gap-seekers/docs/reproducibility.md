# Reproducibility

How to reproduce the harvested results. Two levels: a solver-free structural
validation (laptop, no licence) and the full build+solve on SCNet (Mosek
required). Every harvested run is self-documenting — its `evidence/<run>/`
bundle records the exact commit, tree, source-file SHA-256s, solver status,
dimensions, runtime, and RSS, so a reproduction is a diff against that record,
not a guess.

## Pinned software stack

| Component | Version |
|---|---|
| Julia | 1.11.5 |
| JuMP | 1.31.1 |
| MathOptInterface | 1.51.2 |
| Mosek | 11.2.0 (licence required for solves) |
| MosekTools.jl | 0.15.10 |
| NCTSSoS.jl | (pinned in `julia-env/Project.toml`) |
| QMBCertify.jl | (pinned in `julia-env/Project.toml`) |
| SpectralGap.jl | path dep at `../.external/SpectralGap` + `spectralgap_a1171c9.patch` |
| Clarabel, DynamicPolynomials, StarAlgebras | (pinned in `julia-env/Project.toml`) |

The SDP environment is `julia-env/Project.toml` **under this team directory**
(the repo-root shared `julia-env/` is left at upstream). The working
`Manifest.toml` is gitignored. A clean checkout needs the `SpectralGap.jl` path
dependency reconstructed + patched first — pinned commit `a1171c9` of
`github.com/wangjie212/SpectralGap` plus the committed
`spectralgap_a1171c9.patch`:

```bash
cd tracks/polyopt/solutions/sdp-gap-seekers
# 1. obtain SpectralGap.jl at the pinned commit and apply the patch
git clone https://github.com/wangjie212/SpectralGap .external/SpectralGap
cd .external/SpectralGap && git checkout a1171c9 && git apply ../../spectralgap_a1171c9.patch && cd -
# 2. activate the team env, develop SpectralGap from that path, instantiate
julia --project=julia-env -e 'using Pkg; Pkg.develop(path=abspath(".external/SpectralGap")); Pkg.instantiate()'
```

## SCNet resources

| Cluster | Partition | Typical node | Use |
|---|---|---|---|
| scnet1 (xh5) | `xhacnormalb` | 32–128 core / ~500 GiB | Square Rung B D4 solves (~87 GiB, 32 threads); SS solves (~1.2 GiB, 16 threads) |
| scnet2 (Kunshan) | `kshcnormal` | 32 cpu / ~123 GiB | second pool; Rung C sizing gate; future Rung C spin solves |

The runners reference `$HOME` only — no account name or absolute home path is
hardcoded — so the same sbatch files work under any account with the standard
install layout: Julia at `$HOME/julia-1.11.5`, Mosek at
`$HOME/mosek/mosek/11.2/...`, and the
`LD_LIBRARY_PATH=$HOME/julia-1.11.5/lib/julia` fix (Mosek's libtbb needs
`CXXABI_1.3.8` from Julia's bundled libstdc++).

## Runner environment-variable contract

The Square runner `scripts/square_conic_solve.sbatch` is parameterized; nothing
hardcodes an absolute account path except via `$HOME` (portable across accounts
with the same install layout). Required env at submit time:

| Variable | Meaning | Example |
|---|---|---|
| `CONIC_BASIS` | basis family (allowlist: `bare_weight_one` / `bare_operator` / `one_symbol_lift`) | `bare_operator` |
| `CONIC_G` | g = J2/J1 (rational) | `1//2` |
| `CONIC_GAMMA` | γ threshold (rational) | `0//1` |
| `CONIC_POS_DIM` | expected positive dimension | `352` |
| `CONIC_GAP_DIM` | expected gap dimension | `4` |
| `CONIC_LABEL` | run-label slug | `rungb-d4q-g0p5-gamma0` |
| `CONIC_BUILD_SCRIPT` | builder (default `build_square_conic_mof.jl`; D4 uses `build_square_d4_conic_mof.jl`) | `build_square_d4_conic_mof.jl` |
| `CONIC_TIME_LIMIT` | Mosek time limit, seconds (default 480) | `2400` |

The SS runners (`scripts/shastry_sutherland_full_spin_isotypic_*_xh5.sbatch`)
have their own parameterized inputs; see the file headers.

## Route 1 — solver-free structural validation (no SCNet, no Mosek)

Validates the exact reductions + assembly without solving. Runs on a laptop
(exact-arithmetic structural checks only).

```bash
cd tracks/polyopt/solutions/sdp-gap-seekers
julia --project=julia-env test/runtests.jl
julia --project=julia-env test/run_exact_symmetry_reduction_truth.jl
julia --project=julia-env scripts/check_d4_coefficient_gates.jl
```

Pass criterion: all assertions pass (Hamiltonian invariance, basis closure,
per-coefficient covariance, moment-inventory closure, exact cross-block zeros,
row-basis ranks, cone congruence, `W=3M` isotypic relation). These are the same
gates every harvested solve passed before Mosek was attached.

## Route 2 — full build + solve (SCNet + Mosek)

### Square J1-J2 Rung A (γ-scan, 28/4)

```bash
for g in 0 1//4 2; do
  CONIC_BASIS=bare_weight_one CONIC_G=1//2 CONIC_GAMMA=$g \
  CONIC_POS_DIM=28 CONIC_GAP_DIM=4 CONIC_LABEL="runga-g0p5-gamma${g}" \
  sbatch scripts/square_conic_solve.sbatch
done
```
Expected: each `OPTIMAL` + feasible in <2 s, <1 GiB.

### Square J1-J2 Rung B, D4-quotiented (γ-scan, 352/4)

```bash
for g in 0 1//4 2//5 2; do
  CONIC_BASIS=bare_operator CONIC_G=1//2 CONIC_GAMMA=$g \
  CONIC_POS_DIM=352 CONIC_GAP_DIM=4 CONIC_TIME_LIMIT=2400 \
  CONIC_BUILD_SCRIPT=build_square_d4_conic_mof.jl \
  CONIC_LABEL="rungb-d4q-g0p5-gamma${g}" \
  sbatch --cpus-per-task=32 --mem-per-cpu=3800M scripts/square_conic_solve.sbatch
done
```
Expected: each `OPTIMAL` + feasible in ~25–28 min, ~87 GiB peak RSS, 32 threads.

### Shastry-Sutherland L=1/d=2, full-spin isotypic (γ-scan)

```bash
sbatch scripts/shastry_sutherland_full_spin_isotypic_solve_xh5.sbatch   # see file for γ env
```
Expected: each `OPTIMAL` + feasible in ~7 s, ~1.2 GiB, 16 threads.

## Verifying a reproduced run

Each run writes `results/<run-id>/` (gitignored) containing `result.toml`,
`input-runmeta.toml`, `input-build-SHA256SUMS`, `harness-commit.txt`,
`git-status.txt`, `environment.txt`, `solver-exit-code.txt`, `sacct-provisional.txt`,
`SHA256SUMS`, and (for the D4 build) `quotient-manifest.txt` +
`reduced_model_sha256`. To confirm a reproduction:

1. `git-status.txt` shows no tracked source modifications at build time
   (untracked scratch is tolerated and recorded).
2. `harness-commit.txt` matches the cited commit.
3. `SHA256SUMS` verifies and `input-build-SHA256SUMS` matches the builder output.
4. `result.toml` shows `termination = "OPTIMAL"`, `primal/dual = "FEASIBLE_POINT"`,
   and the expected dimensions.
5. The reduced-model hash (`reduced_model_sha256`) matches the cited value for
   that (basis, γ) — this is the semantic fingerprint of the reduction.

The curated copies checked into `evidence/<run>/` are the canonical records to
diff against.

## Known portability notes

- The runners invoke `$HOME/julia-1.11.5` and `$HOME/mosek/...`. This is
  portable across accounts that share the install layout, but Sihan's
  integration guidance asks for full env-var parameterization
  (`JULIA_BIN`, `JULIA_PROJECT`, `MOSEK_BIN_DIR`, `MOSEK_LICENSE`) with no
  `$HOME` assumption. That parameterization is a finalization step on the
  integration branch (deferred while the route-C experiment was using the repo).
- scnet1's `AssocGrpJobsLimit` (account `giggleliu`, 80/200-job cap) is
  intermittent; scnet2 is the queue-free fallback at lower per-node memory.
- The repo's Slurm helper assumed Python 3.11 `tomllib`; the experiment branch
  added a `tomli` fallback for Python 3.10 (unrelated to the science).
