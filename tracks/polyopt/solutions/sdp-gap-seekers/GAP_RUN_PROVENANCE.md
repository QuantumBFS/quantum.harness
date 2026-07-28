# Gap-cert run provenance — frozen for independent reproduction

> Frozen record of the turnkey `SpectralGap.jl` gap-certification runs, per the
> 2026-07-28 coordination ask (independent SCNet dual-run to verify the
> feasible/infeasible → gap-upper-bound direction). Anyone pulling
> `challenge/polyopt-sdp-gap` + the SpectralGap pin below can reproduce these
> numbers bit-for-bit.
>
> ⚠️ **Status: numerical result, not a strict certificate.** The `flag =
# (status==OPTIMAL ? 1 : 0)` convention (SpectralGap.jl upstream) collapses all
# non-OPTIMAL statuses into flag=0. Per `square-j1j2-gap-sdp-spec.md` §8 this is
# adequate for bound-localization but a residual/witness audit is required
# before claiming a formally certified bound. Flag values below are labelled
# "numerical" accordingly.

## 1. SpectralGap.jl source pin (frozen)

| field | value |
|---|---|
| upstream repo | https://github.com/wangjie212/SpectralGap.git |
| commit | `a1171c906ff2cc2901e58c2426397a2f68c32bb7` ("use the new formulation and add extra constraints") |
| mounted at | `.external/SpectralGap/` (local path dep, gitignored; resolved via `julia-env/Project.toml` UUID `2cd8220c-fa98-40a0-8d32-c3094c958e9c`) |
| `src/SpectralGap.jl` SHA-256 | `ec0a8b4e723e0accaee33826bd6f2bb4eef82debaf3a9f9a9e51cc749fb7648f` |
| `src/basicfunction.jl` SHA-256 | `2095cf7401355f37e9d17915b3ab29d44712d8e40f750eb8449f8c294229b03a` |
| `src/sdp.jl` SHA-256 | `dbdb31d13f4eb484a9f80f6190d8ac31e8030580246228ca5dca3a1bc86e9208` |
| `src/strengthening.jl` SHA-256 | `de56b12b17049f81f689d4caef193b9dfd3bf50061fc78b1bf1547a748f7c57b` |

## 2. Hamiltonian conventions (normalization)

Both use the `ncpoly` encoding: site `i` → `3i-2 = X_i`, `3i-1 = Y_i`, `3i = Z_i`.

- **1D TFIM**: `H = -Σ_{i=1}^{N-1} Z_i Z_{i+1} + g Σ_{i=1}^{N} X_i`, with
  `supp = [[3i,3(i+1)] for bonds; [3i-2] for fields]`, `coe = [-1,…; g,…]`.
- **Kagome Heisenberg**: `H = Σ_{triangles} Σ_{pairs∈tri} S_i·S_j` where
  `S_i·S_j = ¼(XX+YY+ZZ)`. Per triangle: 9 terms (3 pairs × 3 Pauli components),
  coefficient `0.25`. `supp` built from `triples`; `coe = 0.25·ones(9·|triples|)`.

## 3. Exact commands (reproducible)

Scripts committed on `challenge/polyopt-sdp-gap`:
- `tracks/polyopt/solutions/sdp-gap-seekers/scripts/gap_tfim_validate.sh`
- `tracks/polyopt/solutions/sdp-gap-seekers/scripts/gap_kagome.sh`

Both are SLURM scripts for SCNet (`xhacnormalb`). Required env:
```
PATH=$HOME/julia-1.11.5/bin:$PATH
MOSEKBINDIR=$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin
LD_LIBRARY_PATH=$HOME/julia-1.11.5/lib/julia:$LD_LIBRARY_PATH
```
Then: `sbatch gap_tfim_validate.sh` / `sbatch gap_kagome.sh` from `~/quantum.harness`.

The Julia entry points (inside the heredoc):
```julia
# TFIM
H = ncpoly([[3*[i;i+1] for i=1:N-1]; [[3i-2] for i=1:N]], [-ones(N-1); g*ones(N)])
flag = certify_Ising_gap(N, H, gamma, d, QUIET=true)          # lso=6 default

# Kagome
H = ncpoly(<9 terms per triangle>, 0.25*ones(9*length(triples)))
flag = certify_Heisenberg_kagome_gap(N, H, triples, edges, triples0, edges0,
                                     gamma, d, lso=5, QUIET=true)
```

## 4. Run config + solver

| | TFIM | Kagome |
|---|---|---|
| N | 9 | 13 |
| d (relaxation order) | 2 | 3 (d=2 structurally invalid — empty bulk basis) |
| symmetry | sign-symmetric (default) | sign-symmetric (default) |
| lso (localizing support order) | 6 (default) | 5 |
| γ-scan | 0.15…0.34 | 1.0…1.6 |
| solver | Mosek 11.2.2 | Mosek 11.2.2 |
| tolerances | Mosek defaults (no custom `mosek_setting`) | Mosek defaults |
| SCNet job | 22970362 | 22970838 |

## 5. Results — γ-scan transitions (numerical)

**TFIM (Gate 5, validated):**
| γ | 0.15 | 0.20 | 0.22 | 0.24 | 0.25 | 0.26 | 0.27 | 0.28 | 0.30 | 0.34 |
|---|---|---|---|---|---|---|---|---|---|---|
| flag | 1 | 1 | 1 | 1 | **1** | **0** | 0 | 0 | 0 | 0 |

Transition γ* ∈ (0.25, 0.26] → **Δ_TFIM ≤ 0.26** (reference 0.258 ✓).

**Kagome Heisenberg, N=13, d=3 (#88 frustrated target):**
| γ | 1.0 | 1.2 | 1.26 | 1.28 | 1.29 | 1.30 |
|---|---|---|---|---|---|---|
| flag | 1 | 1 | **1** | **0** | 0 | 0 |

Transition γ* ∈ (1.26, 1.28] → **Δ_kagome ≤ 1.28** (reference ~1.28 ✓).

Raw per-γ logs: `gap_tfim.results`, `gap_kagome.results` (on SCNet; append as
the scan continues to N=27 d=3 + N=13 d=4).

## 6. Direction reminder (for the dual-run check)

Feasibility is monotone decreasing in γ (per SPEC §1 / arXiv:2606.03836):
- `flag=1` (OPTIMAL) → γ feasible → Δ could be ≥ γ (not excluded).
- `flag=0` (non-OPTIMAL) → γ infeasible → Δ < γ (excludes gap ≥ γ).
- largest feasible γ* → certified **upper** bound: Δ ≤ γ*.

The kagome scan obeys this (feasible at low γ, infeasible above the transition,
no reversals) — the direction check Sihan's side will independently confirm.
