#!/usr/bin/env julia

using JSON
using LinearAlgebra

include(joinpath(@__DIR__, "src", "Issue86TrackB.jl"))
using .Issue86TrackB

function main(args)
    length(args) == 3 ||
        error("usage: run_cell.jl RUN_SPEC.json CELL_INDEX OUTPUT_DIR")
    spec = JSON.parsefile(abspath(args[1]))
    index = parse(Int, args[2])
    output_directory = abspath(args[3])
    BLAS.set_num_threads(parse(Int, get(ENV, "OPENBLAS_NUM_THREADS", "1")))
    execute_cell(spec, index, output_directory)
end

main(ARGS)
