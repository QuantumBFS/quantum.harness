"""Settings required to run one reproducible Floquet spin-boson calculation."""
Base.@kwdef struct RunConfig
    mode::Symbol = :quick
    dt_target::Float64 = π / 60
    frequencies::Vector{Float64} = [2.5, 10.0]
    steps::Int = 120
    compression_tolerance::Float64 = 1e-7
    run_exact::Bool = false
    cache_dir::String = "output/cache"
    rebuild_cache::Bool = false
    temperature::Float64 = 0.0
    auto_nc::Bool = true
    n_c::Int = 100_000
    truncation::Symbol = :rel
    cap_rank::Int = 100_000
    max_rank::Int = 100_000
    low_rank_svd::Bool = false
    svd_filtering_tolerance::Float64 = 0.0
end

"""Configuration for the six single-spin Fig. 3 frequency-resolved points."""
Base.@kwdef struct Fig3Config
    mode::Symbol = :quick
    dt_target::Float64 = π / 60
    longitudinal_frequencies::Vector{Float64} = [10.0, 5.0, 2.5]
    transversal_frequencies::Vector{Float64} = [2.0, 1.5, 1.0]
    correlation_lag_steps::Int = 256
    tail_count::Int = 32
    tail_norm_tolerance::Float64 = 1e-4
    tail_mean_tolerance::Float64 = 1e-5
    tail_slope_tolerance::Float64 = 1e-5
    c0_tolerance::Float64 = 1e-8
    omega_max::Float64 = 20.0
    nmax::Int = 20
    weight_tolerance::Float64 = 0.0
    eigensolver_tolerance::Float64 = 1e-10
    eigensolver_max_iterations::Int = 1000
end

"""Construct a Floquet grid whose last point closes the drive period exactly."""
function period_grid(ωd::Real, dt_target::Real)
    isfinite(ωd) && ωd > 0 || throw(ArgumentError("drive frequency must be finite and positive"))
    isfinite(dt_target) && dt_target > 0 || throw(ArgumentError("target step must be finite and positive"))

    T = 2π / Float64(ωd)
    M = max(1, round(Int, T / Float64(dt_target)))
    dt = T / M
    return (; T, M, dt, tolerance=16eps(T))
end
