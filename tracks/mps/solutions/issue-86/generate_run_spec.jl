#!/usr/bin/env julia

using JSON
using TOML

include(joinpath(@__DIR__, "src", "Issue86TrackB.jl"))
using .Issue86TrackB

function write_json_atomic(path, payload)
    mkpath(dirname(path))
    temporary = path * ".tmp-" * string(getpid())
    open(temporary, "w") do io
        JSON.print(io, payload, 2)
        println(io)
    end
    mv(temporary, path; force = true)
end

function main(args)
    length(args) == 4 ||
        error("usage: generate_run_spec.jl CONFIG.toml RUN_SPEC.json RUN_ID STAGE")
    config_path, spec_path, run_id, stage = abspath(args[1]), abspath(args[2]), args[3], args[4]
    spec = build_run_spec(TOML.parsefile(config_path); run_id, stage)
    write_json_atomic(spec_path, spec)
    println("wrote $(length(spec["cells"])) cells to $spec_path")
    flush(stdout)
end

main(ARGS)
