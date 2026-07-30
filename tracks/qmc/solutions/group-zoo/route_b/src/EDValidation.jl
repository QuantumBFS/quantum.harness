struct EDReport
    status::Symbol
    production_eligible::Bool
    failures::Vector{String}
    comparisons::Dict{String,Float64}
end

function compare_ed(qmc::AbstractDict, reference::AbstractDict)
    required = ("energy", "mx", "bond", "worm_return")
    missing_fields = String[]
    for name in required
        haskey(qmc, name) || push!(missing_fields, name)
        haskey(qmc, name * "_stderr") || push!(missing_fields, name * "_stderr")
        haskey(qmc, name * "_ess") || push!(missing_fields, name * "_ess")
    end
    isempty(missing_fields) || return EDReport(:insufficient_samples, false, missing_fields, Dict())
    low_ess = [name * "_ess" for name in required if qmc[name * "_ess"] < 20]
    isempty(low_ess) || return EDReport(:insufficient_samples, false, low_ess, Dict())

    failures = String[]
    differences = Dict{String,Float64}()
    for name in required
        difference = abs(Float64(qmc[name]) - Float64(reference[name]))
        differences[name] = difference
        floor = name == "worm_return" ? 1e-2 : 5e-3
        tolerance = max(4 * Float64(qmc[name * "_stderr"]), floor)
        difference <= tolerance || push!(failures, name)
    end
    status = isempty(failures) ? :pass : :fail
    return EDReport(status, isempty(failures), failures, differences)
end
