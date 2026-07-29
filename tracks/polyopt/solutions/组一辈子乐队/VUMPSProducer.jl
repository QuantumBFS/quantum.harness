module VUMPSProducer

using Random
using MPSKit
using MPSKitModels
using TensorKit

Base.@kwdef struct VUMPSSettings
    D::Int
    internal_D::Int = D
    maxiter::Int = 200
    tol::Float64 = 1e-10
    seed::Int = 1234
    verbosity::Int = 0
    unitcell::Int = 1
    delta::Float64 = 1.0
    symmetry::Symbol = :none
end

function _balanced_u1_space(D::Int, offset::Rational{Int})
    D > 0 || throw(ArgumentError("D must be positive"))
    denominator(offset) in (1, 2) ||
        throw(ArgumentError("U(1) bond offset must be integer or half-integer"))
    multiplicities = Dict{Rational{Int},Int}()
    if denominator(offset) == 1
        # Integer bonds can contain q=0.  For even D, duplicate q=0 rather
        # than retaining an unpaired outer charge.
        multiplicities[0//1] = iseven(D) ? 2 : 1
        remaining = D - multiplicities[0//1]
        shell = 1
        while remaining > 0
            multiplicities[-shell//1] = 1
            multiplicities[shell//1] = 1
            remaining -= 2
            shell += 1
        end
    else
        iseven(D) || throw(ArgumentError(
            "a charge-conjugation-balanced half-integer U(1) bond requires even D"))
        shell = 1
        while 2shell <= D
            charge = (2shell - 1) // 2
            multiplicities[-charge] = 1
            multiplicities[charge] = 1
            shell += 1
        end
    end
    sum(values(multiplicities)) == D || error("internal U(1) multiplicity error")
    U1Space((charge => multiplicity for (charge, multiplicity) in
        sort(collect(multiplicities)))...)
end

function u1_bond_spaces(D::Int, internal_D::Int=D)
    internal = _balanced_u1_space(internal_D, 1//2)
    coarse = _balanced_u1_space(D, 0//1)
    return (; internal, coarse)
end

function _validate_settings(settings::VUMPSSettings)
    settings.D > 0 || throw(ArgumentError("D must be positive"))
    settings.internal_D > 0 || throw(ArgumentError("internal_D must be positive"))
    settings.maxiter > 0 || throw(ArgumentError("maxiter must be positive"))
    isfinite(settings.tol) && settings.tol > 0 ||
        throw(ArgumentError("tol must be finite and positive"))
    isfinite(settings.delta) || throw(ArgumentError("delta must be finite"))
    settings.unitcell in (1, 2) || throw(ArgumentError("unitcell must be one or two"))
    settings.symmetry in (:none, :u1) ||
        throw(ArgumentError("symmetry must be :none or :u1"))
    if settings.symmetry == :u1
        settings.unitcell == 2 ||
            throw(ArgumentError("spin-1/2 U(1) VUMPS requires a two-site unit cell"))
        iseven(settings.internal_D) || throw(ArgumentError(
            "spin-1/2 U(1) VUMPS requires even internal_D for paired half-integer charges"))
    end
    nothing
end

function _vumps_problem(settings::VUMPSSettings)
    _validate_settings(settings)
    if settings.symmetry == :u1
        settings.unitcell == 2 || throw(ArgumentError("spin-1/2 U(1) VUMPS requires a two-site unit cell"))
        H = heisenberg_XXZ(U1Irrep, InfiniteChain(2); J=1.0, Delta=settings.delta, spin=1//2)
        physical = [physicalspace(H, site) for site in 1:2]
        # Alternating half-integer/integer bonds resolve the one-site spin-1/2 charge offset.
        virtual = u1_bond_spaces(settings.D, settings.internal_D)
        return H, InfiniteMPS(rand, Float64, physical,
            [virtual.internal, virtual.coarse])
    end
    H1 = heisenberg_XXZ(; J=1.0, Delta=settings.delta, spin=1//2)
    H = settings.unitcell == 1 ? H1 : repeat(H1, 2)
    InfiniteMPS(fill(ComplexSpace(2), settings.unitcell),
        fill(ComplexSpace(settings.D), settings.unitcell)) |> initial -> (H, initial)
end

function run_vumps(settings::VUMPSSettings)
    _validate_settings(settings)
    Random.seed!(settings.seed)
    H, initial = _vumps_problem(settings)
    algorithm = VUMPS(; maxiter=settings.maxiter, tol=settings.tol, verbosity=settings.verbosity)
    state, environments, delta = find_groundstate(initial, H, algorithm)
    total_energy = real(expectation_value(state, H, environments))
    energy_per_site = total_energy / settings.unitcell
    residual_clean = isfinite(energy_per_site) && delta <= max(10settings.tol, 1e-8)
    quality_clean = settings.D == 1 || energy_per_site < -0.25
    clean = residual_clean && quality_clean
    status = !residual_clean ? "not_converged" : (!quality_clean ? "stationary_product_plateau" : "converged")
    record = Dict(
        "D" => settings.D, "internal_D" => settings.internal_D,
        "maxiter" => settings.maxiter, "tolerance" => settings.tol,
        "seed" => settings.seed, "verbosity" => settings.verbosity,
        "unit_cell_length" => settings.unitcell, "energy_per_site" => energy_per_site,
        "delta" => settings.delta, "symmetry" => String(settings.symmetry),
        "algorithm_error" => delta, "clean_convergence" => clean,
        "iteration_status" => status,
        "mps_scalar_type" => string(eltype(state.AL[1])),
        "real_mps" => eltype(state.AL[1]) <: Real,
    )
    return (; state, environments, record)
end

function run_u1_vumps(; D::Int, internal_D::Int=D, delta::Real=1.0,
        maxiter::Int=200, tol::Real=1e-10, seed::Int=1234, verbosity::Int=0)
    run_vumps(VUMPSSettings(; D, internal_D, maxiter, tol=Float64(tol), seed,
        verbosity, unitcell=2, delta=Float64(delta), symmetry=:u1))
end

function run_vumps_with_fallback(settings::VUMPSSettings)
    primary = run_vumps(settings)
    primary.record["clean_convergence"] && return primary
    settings.unitcell == 1 || return primary
    fallback = run_vumps(VUMPSSettings(; D=settings.D, internal_D=settings.internal_D,
        maxiter=settings.maxiter, tol=settings.tol, seed=settings.seed,
        verbosity=settings.verbosity, unitcell=2,
        delta=settings.delta, symmetry=settings.symmetry))
    fallback.record["fallback_from_one_site"] = true
    return fallback
end

export VUMPSSettings, u1_bond_spaces, run_vumps, run_u1_vumps, run_vumps_with_fallback
end
