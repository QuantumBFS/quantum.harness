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

"""Construct a Floquet grid whose last point closes the drive period exactly."""
function period_grid(ωd::Real, dt_target::Real)
    isfinite(ωd) && ωd > 0 || throw(ArgumentError("drive frequency must be finite and positive"))
    isfinite(dt_target) && dt_target > 0 || throw(ArgumentError("target step must be finite and positive"))

    T = 2π / Float64(ωd)
    M = max(1, round(Int, T / Float64(dt_target)))
    dt = T / M
    return (; T, M, dt, tolerance=16eps(T))
end
