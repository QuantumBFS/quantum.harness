#!/usr/bin/env julia

using TOML

include(joinpath(@__DIR__, "src", "Issue86TrackB.jl"))
using .Issue86TrackB

function main(args)
    length(args) == 2 || error("usage: julia run.jl CONFIG.toml OUTPUT_DIR")
    config_path = abspath(args[1])
    output_directory = abspath(args[2])
    config = TOML.parsefile(config_path)
    rows = run_jobs(config, output_directory)
    println("completed $(length(rows)) job(s); results: $output_directory")
    flush(stdout)
end

main(ARGS)
