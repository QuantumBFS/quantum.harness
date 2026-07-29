#!/usr/bin/env julia

using JSON

include(joinpath(@__DIR__, "src", "Issue86TrackB.jl"))
using .Issue86TrackB

function main(args)
    2 <= length(args) <= 3 ||
        error("usage: pending_cells.jl RUN_SPEC.json OUTPUT_DIR [RESOURCE_CLASS]")
    spec = JSON.parsefile(abspath(args[1]))
    output_directory = abspath(args[2])
    selected_class = length(args) == 3 ? args[3] : nothing
    for index in pending_cell_indices(
            spec, output_directory; resource_class = selected_class
        )
        println(index)
    end
    flush(stdout)
end

main(ARGS)
