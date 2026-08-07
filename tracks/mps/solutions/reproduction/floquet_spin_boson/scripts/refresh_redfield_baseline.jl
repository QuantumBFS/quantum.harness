#!/usr/bin/env julia

using TOML

const ROOT = normpath(joinpath(@__DIR__, ".."))
include(joinpath(ROOT, "src", "FloquetSpinBoson.jl"))
using .FloquetSpinBoson

function refresh_config(path)
    raw = TOML.parsefile(path)
    return RunConfig(mode=Symbol(raw["mode"]), dt_target=raw["dt_target"],
                     frequencies=Float64.(raw["frequencies"]), steps=raw["steps"],
                     compression_tolerance=raw["compression_tolerance"], run_exact=false)
end

function redfield_paths(reference_dir, frequencies)
    paths = Dict{Float64,String}()
    for ωd in frequencies
        label = ωd == round(ωd) ? string(round(Int, ωd)) : string(ωd)
        paths[ωd] = joinpath(reference_dir,
            "dynamics_Redfield_Magnus_Ω_1_ϵ_d_1_ω_d_$(label)_α_0.05_ω_c_2.5_bond_dim_235_dt_0.052.csv")
    end
    return paths
end

length(ARGS) == 3 || error("usage: refresh_redfield_baseline.jl <fig2 config> <reference_dir> <output_dir>")
config = refresh_config(ARGS[1])
error_path = joinpath(ARGS[3], "baseline", "fig2_errors.json")
existing_exact = parse_exact_baseline(read(error_path, String))
results = run_fig2(config, redfield_paths(ARGS[2], config.frequencies))
redfield = Dict(ωd => (; max_error=r.max_error, rmse=r.rmse, samples=length(r.times))
                for (ωd, r) in results)
Set(keys(existing_exact)) == Set(keys(redfield)) ||
    error("refusing Redfield refresh: exact and Redfield frequency sets differ")
write(error_path, render_refreshed_errors(existing_exact, redfield, config))
println("refreshed driven Redfield metrics in ", error_path)
