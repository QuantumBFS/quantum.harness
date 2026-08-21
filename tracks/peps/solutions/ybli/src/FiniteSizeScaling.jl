"""
Finite-size scaling analysis (workflow section 6).

Extracts the effective central charge c_eff and scaling dimensions
from the free-energy data at multiple system sizes L.

Central-charge fits (workflow 6.2):
  Model A:  Phi_L = a*L - pi*alpha*c_eff / (6*L)
  Model B:  Phi_L = a*L - pi*alpha*c_eff / (6*L) + b/L^3
  Model C:  Phi_L = a*L - pi*alpha*c_eff / (6*L) + b/L^3 + d/L^5

Bulk-free pair estimator:
  c_eff(L, L') = -(6 / (pi*alpha)) * (f_L - f_L') / (L^{-2} - L'^{-2})

Scaling dimensions (workflow 6.3):
  x_i(L) = L / (2*pi*alpha) * (Phi_i - Phi_0)

Error budget (workflow 6.4):
  - Block/replica bootstrap for statistical uncertainty
  - L_min stability envelope for finite-size model uncertainty
  - Separate systematic tables for chi, burn-in, alpha uncertainties
"""

using Statistics
using LinearAlgebra

# ----------------------------------------------------------------------
# Central-charge fits
# ----------------------------------------------------------------------

"""
    fit_central_charge(Ls, Phis, alpha; model, L_min)

Fit the free-energy per row Phi_L to extract c_eff.

  Model A (2 params):  Phi_L = a*L - pi*alpha*c / (6*L)
  Model B (3 params):  Phi_L = a*L - pi*alpha*c / (6*L) + b/L^3
  Model C (4 params):  Phi_L = a*L - pi*alpha*c / (6*L) + b/L^3 + d/L^5

Returns (c_eff, a, params..., fit_quality) where fit_quality contains
residuals, R^2, and the number of data points used.
"""
function fit_central_charge(Ls::AbstractVector{<:Integer},
                              Phis::AbstractVector{<:Real},
                              alpha::Real=1.0;
                              model::Symbol=:B,
                              L_min::Integer=minimum(Ls))
    # Filter by L_min
    mask = Ls .>= L_min
    Lf = Float64.(Ls[mask])
    Pf = Float64.(Phis[mask])
    n = length(Lf)

    if model == :A
        # 2 parameters: a, c
        # Phi = a*L - (pi*alpha/6) * c / L
        # Design matrix: [L, -pi*alpha/(6*L)]
        X = [Lf -(pi*alpha/6) ./ Lf]
        nparams = 2
    elseif model == :B
        # 3 parameters: a, c, b
        # Phi = a*L - (pi*alpha/6)*c/L + b/L^3
        X = [Lf -(pi*alpha/6) ./ Lf 1.0 ./ Lf.^3]
        nparams = 3
    elseif model == :C
        # 4 parameters: a, c, b, d
        X = [Lf -(pi*alpha/6) ./ Lf 1.0 ./ Lf.^3 1.0 ./ Lf.^5]
        nparams = 4
    else
        error("Unknown model: $model. Use :A, :B, or :C")
    end

    if n < nparams
        @warn "Not enough data points: $n < $nparams for model $model"
        return NaN, NaN, fill(NaN, nparams), (r2=NaN, rmse=NaN, n=n)
    end

    # Least-squares solve
    params = X \ Pf
    residuals = Pf - X * params
    ss_res = sum(residuals.^2)
    ss_tot = sum((Pf .- mean(Pf)).^2)
    r2 = ss_tot > 0 ? 1 - ss_res / ss_tot : NaN
    rmse = sqrt(ss_res / n)

    a = params[1]
    c_eff = params[2]

    fit_quality = (r2=r2, rmse=rmse, n=n, residuals=residuals)

    return c_eff, a, params, fit_quality
end

# ----------------------------------------------------------------------
# Pair estimator (bulk-free)
# ----------------------------------------------------------------------

"""
    effective_c_eff(L1, L2, f1, f2, alpha)

Bulk-free pair estimator using free-energy density f = Phi / (alpha * L):

  c_eff(L, L') = -(6 / (pi*alpha)) * (f_L - f_L') / (L^{-2} - L'^{-2})

This eliminates the bulk free energy a*L, leaving only the Casimir term.
Useful for checking stability without fitting a specific correction model.
"""
function effective_c_eff(L1::Integer, L2::Integer, f1::Real, f2::Real,
                           alpha::Real=1.0)
    if L1 == L2
        return NaN
    end
    return -(6 / (pi * alpha)) * (f1 - f2) / (L1^(-2) - L2^(-2))
end

"""
    pair_estimator_table(Ls, fs, alpha)

Compute all pairwise c_eff(L, L') estimators.
Returns a vector of (L1, L2, c_eff) tuples.
"""
function pair_estimator_table(Ls::AbstractVector{<:Integer},
                                fs::AbstractVector{<:Real},
                                alpha::Real=1.0)
    results = Tuple{Int,Int,Float64}[]
    n = length(Ls)
    for i in 1:n, j in (i+1):n
        c = effective_c_eff(Ls[i], Ls[j], fs[i], fs[j], alpha)
        push!(results, (Ls[i], Ls[j], c))
    end
    return results
end

# ----------------------------------------------------------------------
# Stability envelope
# ----------------------------------------------------------------------

"""
    stability_envelope(Ls, Phis, alpha; models, L_min_range)

Vary L_min and correction model to assess the stability of c_eff.
Returns a table of (L_min, model, c_eff, rmse) tuples.

The stability envelope is the spread of c_eff values across all
combinations of L_min and correction model.  This is the systematic
uncertainty from finite-size corrections.
"""
function stability_envelope(Ls::AbstractVector{<:Integer},
                              Phis::AbstractVector{<:Real},
                              alpha::Real=1.0;
                              models::Vector{Symbol}=[:A, :B, :C],
                              L_min_range=nothing)
    if L_min_range === nothing
        L_min_range = collect(minimum(Ls):2:maximum(Ls)-2)
    end

    results = Tuple{Int,Symbol,Float64,Float64}[]
    for L_min in L_min_range
        for model in models
            c, a, params, fq = fit_central_charge(Ls, Phis, alpha;
                                                    model=model, L_min=L_min)
            if !isnan(c)
                push!(results, (L_min, model, c, fq.rmse))
            end
        end
    end
    return results
end

# ----------------------------------------------------------------------
# Bootstrap
# ----------------------------------------------------------------------

"""
    bootstrap_c_eff(Ls, Phis_replicas, alpha; n_bootstrap, model, L_min, rng)

Block bootstrap with per-replica resampling.

Phis_replicas is a Vector{Vector{Float64}} where each inner vector
contains independent estimates of Phi_L from one replica.

The bootstrap resamples replicas (not individual measurements) to
account for between-replica variance, then fits c_eff for each
bootstrap replicate.
"""
function bootstrap_c_eff(Ls::AbstractVector{<:Integer},
                           Phis_replicas::AbstractVector{<:AbstractVector{<:Real}},
                           alpha::Real=1.0;
                           n_bootstrap::Int=1000,
                           model::Symbol=:B,
                           L_min::Integer=minimum(Ls),
                           rng::AbstractRNG=Random.default_rng())
    nL = length(Ls)

    # Mean Phi for each L across replicas
    Phis_mean = [mean(reps) for reps in Phis_replicas]

    c_eff_samples = Float64[]

    for _ in 1:n_bootstrap
        # Resample replicas for each L independently
        Phis_boot = Float64[]
        for iL in 1:nL
            reps = Phis_replicas[iL]
            nr = length(reps)
            # Bootstrap: resample with replacement and take mean
            idx = rand(rng, 1:nr, nr)
            push!(Phis_boot, mean(reps[idx]))
        end

        c, _, _, _ = fit_central_charge(Ls, Phis_boot, alpha;
                                          model=model, L_min=L_min)
        if !isnan(c)
            push!(c_eff_samples, c)
        end
    end

    if isempty(c_eff_samples)
        return (mean=NaN, std=NaN, median=NaN, ci_lo=NaN, ci_hi=NaN, samples=c_eff_samples)
    end

    return (
        mean = mean(c_eff_samples),
        std = std(c_eff_samples),
        median = median(c_eff_samples),
        ci_lo = quantile(c_eff_samples, 0.025),
        ci_hi = quantile(c_eff_samples, 0.975),
        samples = c_eff_samples
    )
end

# ----------------------------------------------------------------------
# Scaling dimensions
# ----------------------------------------------------------------------

"""
    fit_scaling_dimension(gaps, Ls, alpha; model, L_min)

Extrapolate scaling dimensions from Lyapunov gaps at multiple L.

  x_i(L) = L / (2*pi*alpha) * (gamma_0 - gamma_i)

The gap (gamma_0 - gamma_i) is computed at each L, giving x_i(L).
Fit x_i(L) = x_i + a/L^2 + ... to extrapolate to the thermodynamic limit.

Arguments:
  - gaps: Vector{Float64}, the Lyapunov gap (gamma_0 - gamma_i) at each L
  - Ls:   Vector{Int}, system sizes
  - alpha: anisotropy factor
"""
function fit_scaling_dimension(gaps::AbstractVector{<:Real},
                                 Ls::AbstractVector{<:Integer},
                                 alpha::Real=1.0;
                                 model::Symbol=:linear,
                                 L_min::Integer=minimum(Ls))
    mask = Ls .>= L_min
    Lf = Float64.(Ls[mask])
    gf = Float64.(gaps[mask])

    # Compute x_i(L) = L / (2*pi*alpha) * gap
    xL = Lf ./ (2 * pi * alpha) .* gf

    n = length(Lf)

    if model == :linear
        # x(L) = x + a/L^2
        if n < 2
            return (x=NaN, correction=NaN, n=n)
        end
        X = [ones(n) 1.0 ./ Lf.^2]
        params = X \ xL
        return (x=params[1], correction=params[2], n=n)
    elseif model == :quadratic
        # x(L) = x + a/L^2 + b/L^4
        if n < 3
            return (x=NaN, a=NaN, b=NaN, n=n)
        end
        X = [ones(n) 1.0 ./ Lf.^2 1.0 ./ Lf.^4]
        params = X \ xL
        return (x=params[1], a=params[2], b=params[3], n=n)
    else
        error("Unknown model: $model")
    end
end

# ----------------------------------------------------------------------
# Free-energy density helper
# ----------------------------------------------------------------------

"""
    free_energy_density(Phi_L, L, alpha)

Convert free-energy per row to free-energy density:
  f_L = Phi_L / (alpha * L)
"""
function free_energy_density(Phi_L::Real, L::Integer, alpha::Real=1.0)
    return Phi_L / (alpha * L)
end

"""
    free_energy_densities(Phis, Ls, alpha)

Vectorized version of free_energy_density.
"""
function free_energy_densities(Phis::AbstractVector{<:Real},
                                 Ls::AbstractVector{<:Integer},
                                 alpha::Real=1.0)
    return [free_energy_density(Phi, L, alpha) for (Phi, L) in zip(Phis, Ls)]
end

# ----------------------------------------------------------------------
# Summary report
# ----------------------------------------------------------------------

"""
    summarize_fit(Ls, Phis, Phis_replicas, alpha; model, L_min, n_bootstrap)

Run the complete finite-size analysis and print a summary report.
Returns a NamedTuple with all results.
"""
function summarize_fit(Ls::AbstractVector{<:Integer},
                         Phis::AbstractVector{<:Real},
                         Phis_replicas::AbstractVector{<:AbstractVector{<:Real}},
                         alpha::Real=1.0;
                         model::Symbol=:B,
                         L_min::Integer=minimum(Ls),
                         n_bootstrap::Int=1000,
                         rng::AbstractRNG=Random.default_rng())
    # Point estimate
    c_eff, a, params, fq = fit_central_charge(Ls, Phis, alpha;
                                                model=model, L_min=L_min)

    # Bootstrap
    boot = bootstrap_c_eff(Ls, Phis_replicas, alpha;
                            n_bootstrap=n_bootstrap, model=model,
                            L_min=L_min, rng=rng)

    # Stability envelope
    stab = stability_envelope(Ls, Phis, alpha)

    # Pair estimators
    fs = free_energy_densities(Phis, Ls, alpha)
    pairs = pair_estimator_table(Ls, fs, alpha)

    # Systematic uncertainty from stability
    c_effs = [s[3] for s in stab if !isnan(s[3])]
    sys_unc = isempty(c_effs) ? NaN : (maximum(c_effs) - minimum(c_effs)) / 2

    println("=" ^ 60)
    println("Finite-Size Scaling Summary")
    println("=" ^ 60)
    println("  Model            : $model (L_min=$L_min)")
    println("  c_eff (point)    : $(round(c_eff, digits=6))")
    println("  c_eff (bootstrap): $(round(boot.mean, digits=6)) +/- $(round(boot.std, digits=6))")
    println("  95% CI           : [$(round(boot.ci_lo, digits=6)), $(round(boot.ci_hi, digits=6))]")
    println("  Systematic unc.  : $(round(sys_unc, digits=6))")
    println("  R^2              : $(round(fq.r2, digits=6))")
    println("  RMSE             : $(round(fq.rmse, digits=6))")
    println("  N data points    : $(fq.n)")
    println("-" ^ 60)
    println("  Pair estimators:")
    for (L1, L2, c) in pairs
        println("    c_eff($L1, $L2) = $(round(c, digits=6))")
    end
    println("-" ^ 60)
    println("  Stability envelope:")
    for (Lm, mdl, c, rmse) in stab
        println("    L_min=$Lm, model=$mdl: c_eff=$(round(c, digits=6)), rmse=$(round(rmse, digits=6))")
    end
    println("=" ^ 60)

    return (
        c_eff_point = c_eff,
        c_eff_bootstrap = boot,
        systematic_uncertainty = sys_unc,
        fit_quality = fq,
        stability = stab,
        pair_estimators = pairs,
    )
end