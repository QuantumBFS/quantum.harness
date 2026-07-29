#!/usr/bin/env julia

using Dates
using JSON

include(joinpath(@__DIR__, "src", "Issue86TrackB.jl"))
using .Issue86TrackB

function main(args)
    length(args) == 2 ||
        error("usage: collect.jl RUN_SPEC.json OUTPUT_DIR")
    spec_path, output_directory = abspath(args[1]), abspath(args[2])
    spec = JSON.parsefile(spec_path)
    mkpath(output_directory)
    rows = collect_cell_results(spec, output_directory)
    payload = Dict(
        "metadata" => merge(
            Dict{String, Any}(spec["metadata"]),
            Dict(
                "completed_cells" => length(rows),
                "collected_utc" => string(Dates.now(Dates.UTC)),
            ),
        ),
        "rows" => rows,
    )
    Issue86TrackB._write_json_atomic(joinpath(output_directory, "raw.json"), payload)
    csv_path = joinpath(output_directory, "raw.csv")
    temporary_csv = csv_path * ".tmp-" * string(getpid())
    Issue86TrackB._write_csv(temporary_csv, rows)
    mv(temporary_csv, csv_path; force = true)
    println("collected $(length(rows))/$(length(spec["cells"])) successful cells")
    flush(stdout)
end

main(ARGS)
