module VUMPSProducer

using Random
using MPSKit
using MPSKitModels
using TensorKit

Base.@kwdef struct VUMPSSettings
    D::Int
    maxiter::Int = 200
    tol::Float64 = 1e-10
    seed::Int = 1234
    verbosity::Int = 0
    unitcell::Int = 1
end

function run_vumps(settings::VUMPSSettings)
    Random.seed!(settings.seed)
    settings.unitcell in (1, 2) || throw(ArgumentError("unitcell must be one or two"))
    H1 = heisenberg_XXX(; J=1.0, spin=1//2)
    H = settings.unitcell == 1 ? H1 : repeat(H1, 2)
    physical = fill(ComplexSpace(2), settings.unitcell)
    virtual = fill(ComplexSpace(settings.D), settings.unitcell)
    initial = InfiniteMPS(physical, virtual)
    algorithm = VUMPS(; maxiter=settings.maxiter, tol=settings.tol, verbosity=settings.verbosity)
    state, environments, delta = find_groundstate(initial, H, algorithm)
    total_energy = real(expectation_value(state, H, environments))
    energy_per_site = total_energy / settings.unitcell
    residual_clean = isfinite(energy_per_site) && delta <= max(10settings.tol, 1e-8)
    quality_clean = settings.D == 1 || energy_per_site < -0.25
    clean = residual_clean && quality_clean
    status = !residual_clean ? "not_converged" : (!quality_clean ? "stationary_product_plateau" : "converged")
    record = Dict(
        "D" => settings.D, "maxiter" => settings.maxiter, "tolerance" => settings.tol,
        "seed" => settings.seed, "verbosity" => settings.verbosity,
        "unit_cell_length" => settings.unitcell, "energy_per_site" => energy_per_site,
        "algorithm_error" => delta, "clean_convergence" => clean,
        "iteration_status" => status,
    )
    return (; state, environments, record)
end

function run_vumps_with_fallback(settings::VUMPSSettings)
    primary = run_vumps(settings)
    primary.record["clean_convergence"] && return primary
    settings.unitcell == 1 || return primary
    fallback = run_vumps(VUMPSSettings(; D=settings.D, maxiter=settings.maxiter,
        tol=settings.tol, seed=settings.seed, verbosity=settings.verbosity, unitcell=2))
    fallback.record["fallback_from_one_site"] = true
    return fallback
end

export VUMPSSettings, run_vumps, run_vumps_with_fallback
end
