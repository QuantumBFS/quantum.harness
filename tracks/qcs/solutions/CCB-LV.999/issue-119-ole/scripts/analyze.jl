using TOML

include(joinpath(@__DIR__, "..", "src", "ErrorBudget.jl"))
using .ErrorBudget

function main()
    length(ARGS) >= 3 || throw(
        ArgumentError(
            "usage: julia --project=. scripts/analyze.jl OUTPUT.toml REFERENCE RESULT.toml...",
        ),
    )
    output_path = abspath(ARGS[1])
    reference = parse(Float64, ARGS[2])
    result_paths = abspath.(ARGS[3:end])
    samples = Float64[]
    seed_ids = Int[]
    for path in result_paths
        document = TOML.parsefile(path)
        get(document["run"], "status", "") == "complete" ||
            throw(ArgumentError("run is not complete: $path"))
        push!(samples, document["result"]["sample_value"])
        push!(seed_ids, document["result"]["seed_id"])
    end
    length(unique(seed_ids)) == length(seed_ids) ||
        throw(ArgumentError("duplicate seed ids in analysis inputs"))

    acceptance = baseline_acceptance(samples, reference)
    output = Dict(
        "result_paths" => result_paths,
        "seed_ids" => seed_ids,
        "samples" => samples,
        "summary" => Dict(
            string(key) => value
            for (key, value) in pairs(acceptance)
        ),
    )
    mkpath(dirname(output_path))
    open(output_path, "w") do io
        TOML.print(io, output; sorted = true)
    end
    println(
        "mean=$(acceptance.mean) se=$(acceptance.standard_error) " *
        "difference=$(acceptance.difference) tolerance=$(acceptance.tolerance) " *
        "accepted=$(acceptance.accepted)",
    )
    println("summary=$output_path")
    flush(stdout)
    return nothing
end

main()
