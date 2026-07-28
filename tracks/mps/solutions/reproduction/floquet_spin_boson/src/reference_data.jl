using DelimitedFiles

"""Load an author curve only when its samples exactly match the requested grid.

One-column Zenodo files inherit `expected_times`; two-column fixtures and future
exports carry their own time column and are checked pointwise.
"""
function load_reference_curve(path::AbstractString, expected_times::AbstractVector{<:Real};
                              atol::Real=1e-12)
    isfile(path) || throw(ArgumentError("reference CSV does not exist: $path"))
    raw = readdlm(path, ',', Float64)
    data = raw isa AbstractVector ? reshape(raw, :, 1) : raw
    size(data, 2) in (1, 2) || throw(ArgumentError("reference CSV must have one value column or time,value columns"))
    size(data, 1) == length(expected_times) ||
        throw(ArgumentError("reference length $(size(data, 1)) does not match expected grid length $(length(expected_times))"))

    times = Float64.(expected_times)
    values = if size(data, 2) == 1
        vec(Float64.(data[:, 1]))
    else
        source_times = vec(Float64.(data[:, 1]))
        all(isapprox.(source_times, times; atol=atol, rtol=0)) ||
            throw(ArgumentError("reference time grid does not match expected grid"))
        vec(Float64.(data[:, 2]))
    end
    return (; times, values)
end

"""The exact frequency grid declared by the authors' Zenodo Fig. 3 script."""
fig3_reference_grid() = collect(0.005:0.005:15.0)

"""Load a headerless Fig. 3 current vector on the exact 3000-point author grid."""
function load_fig3_reference(path::AbstractString)
    grid = fig3_reference_grid()
    loaded = load_reference_curve(path, grid)
    all(isfinite, loaded.values) ||
        throw(ArgumentError("Fig. 3 reference contains non-finite current values"))
    return (; omega=loaded.times, current=loaded.values)
end

function _fig3_frequency_label(omega_d::Real)
    return isinteger(omega_d) ? string(round(Int, omega_d)) : string(Float64(omega_d))
end

"""Resolve the exact author filename for one of the six Fig. 3 points."""
function fig3_reference_path(reference_dir::AbstractString,
                             drive::Symbol, omega_d::Real)
    drive in (:longitudinal, :transversal) ||
        throw(ArgumentError("Fig. 3 reference drive is invalid"))
    label = _fig3_frequency_label(omega_d)
    filename =
        "heat_current_$(drive)_Ω_1_ϵ_d_1_ω_d_$(label)_α_0.05_ω_c_2.5_bond_dim_235_dt_0.052.csv"
    return joinpath(reference_dir, filename)
end

"""The exact 191-point drive-frequency grid declared by the Fig. 5 script."""
fig5_reference_grid() = collect(0.5:0.05:10.0)

"""Load one headerless Fig. 5 total-current curve on the author grid."""
function load_fig5_reference(path::AbstractString)
    grid = fig5_reference_grid()
    loaded = load_reference_curve(path, grid)
    all(isfinite, loaded.values) ||
        throw(ArgumentError("Fig. 5 reference contains non-finite values"))
    return (; frequencies=loaded.times, current=loaded.values)
end

"""Resolve the exact author filename for one Fig. 5 drive direction."""
function fig5_reference_path(reference_dir::AbstractString, drive::Symbol)
    drive in (:longitudinal, :transversal) ||
        throw(ArgumentError("Fig. 5 reference drive is invalid"))
    return joinpath(
        reference_dir,
        "total_heat_current_$(drive)_Ω_1_ϵ_d_1_α_0.05_ω_c_2.5_bond_dim_235_dt_0.052.csv")
end
