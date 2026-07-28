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
