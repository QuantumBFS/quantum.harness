# Criticality in open quantum matter

## Team

| | |
|---|---|
| **Team name** | ybli |
| **Members** | ybli |

## Challenge

| Row | |
|---|---|
| **Challenge** | Reproduce effective central charges at the Nishimori and weak self-dual critical points in open quantum matter, with a finite-size Lyapunov-spectrum analysis. |
| **Catalog issue** | Addresses #122 -- released by Guo-Yi Zhu, Hong Kong University of Science and Technology (Guangzhou). |
| **Track** | `peps`, chosen by the team because the issue explicitly includes tensor-network contraction. |

## Results

See [RESULTS.md](RESULTS.md) for the full report with tables and analysis.

### Clean Ising (validation, c = 1/2)

- c_eff = 0.500 (Model C fit, error < 0.02%)
- Delta_1 = 0.124 (exact: 1/8 = 0.125)
- Delta_2 = 0.996 (exact: 1.0)

### Nishimori RBIM (p = 0.8899)

- c_eff = 0.49 +/- 0.04 (Model A, bootstrap)
- c_eff(6,10) = 0.466 (pair estimator, matches literature 0.464(4))
- Delta_1 = 0.055 +/- 0.001 (nearly marginal operator)
- Delta_2 = 1.632 +/- 0.005
- System sizes L = 4..12, 3150 total disorder samples

### Weak self-dual point (c_eff ~ 0.447)

- Toric code PEPS Born-weight sampling implemented
- Exact Born sampler validated at L=4
- MCMC sampler for larger L is functional
- Full scaling analysis pending: see RESULTS.md section 3

## Method

The effective central charge c_eff is extracted from the finite-size scaling
of the Born-weighted free energy:

    Phi_L = -(1/Ly) * log Z_m

where Z_m is the Born weight of configuration m. For each configuration,
the leading Lyapunov exponent of the transfer-matrix product determines the
free-energy density. The Lyapunov approach avoids boundary contamination
from open boundary conditions.

### Architecture

```
src/
  OpenCriticality.jl      -- module entry point, exports
  Conventions.jl          -- ModelConvention, free_energy_per_row
  Models.jl               -- ClassicalIsing, NishimoriRBIM, MeasuredToricCode
  Contraction.jl          -- dense_logZ, boundary_mps_logZ (log-space)
  Lyapunov.jl             -- leading_lyapunov, lyapunov_spectrum (Householder QR)
  Samplers.jl             -- DirectSampler, MetropolisSampler
  FiniteSizeScaling.jl    -- fit_central_charge, bootstrap_c_eff, pair estimators
test/
  runtests.jl             -- 12 test sets, 49 tests (all pass)
scripts/
  benchmark_ising.jl      -- clean Ising c_eff extraction
  nishimori_cluster.jl    -- cluster Lyapunov spectrum for Nishimori RBIM
  nishimori_dense_run2.jl -- independent second run (different seeds)
  nishimori_mps_only.jl   -- boundary MPS free energy for L=14,16
  self_dual_born.jl       -- measured toric code Born-weight sampling
  slurm_array.jl          -- Slurm array job template
  results/                -- CSV data from cluster runs
```

## Reproduction

### Prerequisites

- Julia 1.10+ (tested on 1.12.6)
- No external packages required (stdlib only: LinearAlgebra, Statistics, Random, Printf)
- Optional: Slurm cluster for large-L runs

### Run tests

```bash
julia -e 'include("tracks/peps/solutions/ybli/test/runtests.jl")'
```

### Clean Ising benchmark

```bash
julia tracks/peps/solutions/ybli/scripts/benchmark_ising.jl
```

Expected output: c_eff = 0.500 (Model C), matching exact c = 1/2.

### Nishimori RBIM scaling

The raw data (3150 samples, L=4..12) is included in `scripts/results/`.
To re-run the finite-size scaling analysis:

```bash
julia -e '
include("tracks/peps/solutions/ybli/src/OpenCriticality.jl")
using .OpenCriticality
using Printf, Statistics, LinearAlgebra

Ls = [4, 6, 8, 10, 12]
results_dir = "tracks/peps/solutions/ybli/scripts/results"
mean_neg_g0 = Float64[]
for L in Ls
    neg_g0s = Float64[]
    for suffix in ["", "_run2"]
        f = "$results_dir/nishimori_dense_L$(L)$(suffix).csv"
        isfile(f) || continue
        for line in readlines(f)[2:end]
            push!(neg_g0s, -parse(Float64, split(line, ",")[2]))
        end
    end
    push!(mean_neg_g0, mean(neg_g0s))
end
c = fit_central_charge(Ls, mean_neg_g0, 1.0; model=:A)[1]
println("c_eff = ", c)
'
```

To generate fresh data on a cluster:

```bash
# Submit Slurm job
sbatch slurm_array_template.sh
# Or run locally for small L
julia tracks/peps/solutions/ybli/scripts/nishimori_cluster.jl
```

### Weak self-dual point

```bash
# L=4 (exact Born sampling)
julia tracks/peps/solutions/ybli/scripts/self_dual_born.jl "4"

# L=4,6 (L=6 uses MCMC)
julia tracks/peps/solutions/ybli/scripts/self_dual_born.jl "4,6"
```

## Key technical decisions

- **Transfer matrix**: symmetric form T = sqrt(Dh) * Tv * sqrt(Dh)
- **Lyapunov extraction**: Householder QR with R_{ii} > 0 convention,
  reorthogonalization when ||Q'Q - I|| > 1e-10
- **Free energy from gamma_0**: Phi_L = -gamma_0 avoids boundary
  contamination for disordered models
- **Finite-size fit**: Model A (2-param) is most stable for L=4-12;
  higher-order corrections require larger L
- **Log-space normalization**: prevents overflow for large Ly

## References

- [Issue #122](https://github.com/QuantumBFS/quantum.harness/issues/122)
- [arXiv:2502.14034](https://arxiv.org/abs/2502.14034)
- [cond-mat/0106023](https://arxiv.org/abs/cond-mat/0106023)
- [cond-mat/0010143](https://arxiv.org/abs/cond-mat/0010143)
- [arXiv:2606.12132](https://arxiv.org/abs/2606.12132)