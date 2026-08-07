#!/usr/bin/env julia

using TOML

const ROOT = normpath(joinpath(@__DIR__, ".."))
include(joinpath(ROOT, "src", "FloquetSpinBoson.jl"))
using .FloquetSpinBoson

function config_from_toml(path)
    raw = TOML.parsefile(path)
    return RunConfig(mode=Symbol(raw["mode"]), dt_target=raw["dt_target"],
                     frequencies=Float64.(raw["frequencies"]), steps=raw["steps"],
                     compression_tolerance=raw["compression_tolerance"],
                     run_exact=raw["run_exact"])
end

function reference_paths(reference_dir, frequencies, run_exact)
    paths = Dict{Float64,Any}()
    for ωd in frequencies
        label = ωd == round(ωd) ? string(round(Int, ωd)) : string(ωd)
        redfield = joinpath(reference_dir,
            "dynamics_Redfield_Magnus_Ω_1_ϵ_d_1_ω_d_$(label)_α_0.05_ω_c_2.5_bond_dim_235_dt_0.052.csv")
        exact = joinpath(reference_dir,
            "dynamics_exact_Ω_1_ϵ_d_1_ω_d_$(label)_α_0.05_ω_c_2.5_bond_dim_235_dt_0.052.csv")
        paths[ωd] = run_exact ? (; exact, redfield) : redfield
    end
    return paths
end

function write_baseline(output_dir, results, mode)
    mkpath(joinpath(output_dir, "baseline"))
    performance = joinpath(output_dir, "baseline", "performance.json")
    errors = joinpath(output_dir, "baseline", "fig2_errors.json")
    open(performance, "w") do io
        exact = all(hasproperty(r, :exact) for r in values(results))
        if exact
            if_seconds = sum(r.exact.if_build_seconds for r in values(results))
            propagation_seconds = sum(r.exact.propagation_seconds for r in values(results))
            bond_dimensions = [r.exact.bond_dimension for r in values(results)]
            print(io, "{\"mode\":\"", mode, "\",\"if_build_seconds\":", if_seconds,
                  ",\"propagation_seconds\":", propagation_seconds,
                  ",\"peak_memory_bytes\":null,\"allocations_bytes\":null,\"bond_dimensions\":[",
                  join(bond_dimensions, ","), "]}")
        else
            print(io, "{\"mode\":\"", mode,
                  "\",\"if_build_seconds\":null,\"propagation\":\"Redfield-Magnus only\",",
                  "\"peak_memory_bytes\":null,\"allocations_bytes\":null,\"bond_dimension\":null}")
        end
    end
    open(errors, "w") do io
        print(io, "{")
        for (index, ωd) in enumerate(sort(collect(keys(results))))
            index > 1 && print(io, ",")
            r = results[ωd]
            exact = hasproperty(r, :exact) ? r.exact : nothing
            print(io, "\"", ωd, "\":{\"max_error\":", r.max_error,
                  ",\"rmse\":", r.rmse, ",\"samples\":", length(r.times),
                  isnothing(exact) ? "" : ",\"redfield_max_error\":$(r.redfield.max_error)", "}")
        end
        print(io, "}")
    end
end

length(ARGS) == 3 || error("usage: reproduce_fig2.jl <quick|fig2 config> <reference_dir> <output_dir>")
config = config_from_toml(ARGS[1])
results = run_fig2(config, reference_paths(ARGS[2], config.frequencies, config.run_exact))
write_baseline(ARGS[3], results, config.mode)
config.run_exact && write_fig2_curves(ARGS[3], results)
println("strict Fig. 2 Redfield baseline written to ", joinpath(ARGS[3], "baseline"))
