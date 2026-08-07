import TOML

const REQUIRED_CONVERGENCE_AXES = (
    "dt",
    "compression",
    "eigensolver",
    "tau_max",
    "delta_omega",
    "omega_max",
    "nmax",
)

function _validate_convergence_axis(name::AbstractString, record)
    record isa AbstractDict ||
        throw(ArgumentError("convergence axis $(name) lacks a measured record"))
    settings = get(record, "settings", Any[])
    settings isa AbstractVector && length(settings) >= 2 ||
        throw(ArgumentError("convergence axis $(name) needs at least two settings"))
    all(value -> value isa Real && isfinite(value), settings) ||
        throw(ArgumentError("convergence axis $(name) settings must be finite"))
    quantity = get(record, "quantity", "")
    quantity isa AbstractString && !isempty(quantity) ||
        throw(ArgumentError("convergence axis $(name) lacks a primary quantity"))
    difference = get(record, "difference", NaN)
    tolerance = get(record, "tolerance", NaN)
    difference isa Real && isfinite(difference) && difference >= 0 ||
        throw(ArgumentError("convergence axis $(name) difference is invalid"))
    tolerance isa Real && isfinite(tolerance) && tolerance >= 0 ||
        throw(ArgumentError("convergence axis $(name) tolerance is invalid"))
    get(record, "passed", false) === true && difference <= tolerance ||
        throw(ArgumentError("convergence axis $(name) did not pass"))
    return record
end

"""Fail closed when a production run lacks complete, equally strict evidence.

Quick and validation modes may proceed without evidence, but this function
never changes a requested tolerance.
"""
function require_convergence_evidence(mode::Symbol, path::AbstractString,
                                      required_thresholds::AbstractDict)
    mode == :production || return nothing
    isfile(path) ||
        throw(ArgumentError("production mode requires convergence evidence at $(path)"))
    evidence = TOML.parsefile(path)
    get(evidence, "complete", false) === true ||
        throw(ArgumentError("convergence evidence is not marked complete"))

    axes = get(evidence, "axes", Dict{String, Any}())
    missing_axes = [axis for axis in REQUIRED_CONVERGENCE_AXES
                    if !haskey(axes, axis)]
    isempty(missing_axes) ||
        throw(ArgumentError("convergence evidence is missing axes: $(join(missing_axes, ", "))"))
    for axis in REQUIRED_CONVERGENCE_AXES
        _validate_convergence_axis(axis, axes[axis])
    end

    recorded_thresholds = get(evidence, "thresholds", Dict{String, Any}())
    results = get(evidence, "results", Dict{String, Any}())
    for (name, requested) in required_thresholds
        haskey(recorded_thresholds, name) ||
            throw(ArgumentError("convergence evidence lacks threshold $(name)"))
        haskey(results, name) ||
            throw(ArgumentError("convergence evidence lacks result $(name)"))
        recorded = Float64(recorded_thresholds[name])
        measured = Float64(results[name])
        recorded <= Float64(requested) ||
            throw(ArgumentError("recorded $(name) threshold $(recorded) is looser than requested $(requested)"))
        measured <= Float64(requested) ||
            throw(ArgumentError("measured $(name)=$(measured) exceeds requested $(requested)"))
    end
    return evidence
end

"""Route measured work locally only below both declared hard limits."""
function choose_compute_route(wall_seconds::Real, resident_bytes::Integer)
    isfinite(wall_seconds) && wall_seconds >= 0 ||
        throw(ArgumentError("wall estimate must be finite and nonnegative"))
    resident_bytes >= 0 ||
        throw(ArgumentError("memory estimate must be nonnegative"))
    return wall_seconds < 600 && resident_bytes < 16 * 2^30 ?
           :local : :remote
end

"""Conservative pre-run estimate used to route local versus cluster work."""
function estimate_resources(; bond_dimension::Integer, period_steps::Integer,
                            correlation_lag_steps::Integer,
                            frequency_points::Integer,
                            liouville_dimension::Integer=4,
                            effective_matvec_rate::Real=5e8)
    all(>(0), (bond_dimension, period_steps, correlation_lag_steps,
               frequency_points, liouville_dimension)) ||
        throw(ArgumentError("resource dimensions must be positive"))
    effective_matvec_rate > 0 ||
        throw(ArgumentError("effective_matvec_rate must be positive"))

    augmented_dimension = Base.checked_mul(Int(liouville_dimension), Int(bond_dimension))
    dense_floquet_bytes = Base.checked_mul(
        Base.checked_mul(augmented_dimension, augmented_dimension),
        sizeof(ComplexF64),
    )
    phase_state_bytes = Base.checked_mul(
        Base.checked_mul(augmented_dimension, Int(period_steps) + 1),
        sizeof(ComplexF64),
    )
    work_units = Float64(augmented_dimension)^2 * period_steps *
                 correlation_lag_steps * frequency_points
    estimated_wall_seconds = work_units / Float64(effective_matvec_rate)
    estimated_peak_bytes = dense_floquet_bytes + 4phase_state_bytes
    execution = choose_compute_route(estimated_wall_seconds, estimated_peak_bytes)
    return (; augmented_dimension, dense_floquet_bytes, phase_state_bytes,
            estimated_peak_bytes, estimated_wall_seconds, execution)
end
