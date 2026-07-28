#!/usr/bin/env julia

using TOML
import UniformTEMPO

const ROOT = normpath(joinpath(@__DIR__, ".."))
if !isdefined(Main, :FloquetSpinBoson)
    include(joinpath(ROOT, "src", "FloquetSpinBoson.jl"))
end
using .FloquetSpinBoson

function cache_config_from_toml(path)
    raw = TOML.parsefile(path)
    defaults = RunConfig()
    return RunConfig(
        mode=Symbol(get(raw, "mode", string(defaults.mode))),
        dt_target=Float64(get(raw, "dt_target", defaults.dt_target)),
        frequencies=Float64.(get(raw, "frequencies", defaults.frequencies)),
        steps=Int(get(raw, "steps", defaults.steps)),
        compression_tolerance=Float64(get(raw, "compression_tolerance", defaults.compression_tolerance)),
        run_exact=Bool(get(raw, "run_exact", defaults.run_exact)),
        cache_dir=String(get(raw, "cache_dir", defaults.cache_dir)),
        rebuild_cache=Bool(get(raw, "rebuild_cache", defaults.rebuild_cache)),
        temperature=Float64(get(raw, "temperature", defaults.temperature)),
        auto_nc=Bool(get(raw, "auto_nc", defaults.auto_nc)),
        n_c=Int(get(raw, "n_c", defaults.n_c)),
        truncation=Symbol(get(raw, "truncation", string(defaults.truncation))),
        cap_rank=Int(get(raw, "cap_rank", defaults.cap_rank)),
        max_rank=Int(get(raw, "max_rank", defaults.max_rank)),
        low_rank_svd=Bool(get(raw, "low_rank_svd", defaults.low_rank_svd)),
        svd_filtering_tolerance=Float64(get(raw, "svd_filtering_tolerance",
                                           defaults.svd_filtering_tolerance)),
    )
end

function default_uniform_pt_builder(model, exact_dt, compression_tolerance, settings;
                                    unitempo::Function=UniformTEMPO.uniTEMPO)
    pt = unitempo(model.coupling_operator, exact_dt,
                  t -> bath_correlation(model, t),
                  compression_tolerance;
                  auto_nc=settings.auto_nc, n_c=settings.n_c,
                  truncation=settings.truncation, cap_rank=settings.cap_rank,
                  max_rank=settings.max_rank, low_rank_svd=settings.low_rank_svd,
                  svd_filtering_tol=settings.svd_filtering_tolerance)
    convergence_metadata = Dict{String,Any}(
        "builder_identity" => "UniformTEMPO.uniTEMPO",
        "status" => "completed",
        "achieved_chi" => UniformTEMPO.bond_dim(pt),
        "build_settings" => Dict(
            "auto_nc" => settings.auto_nc,
            "n_c" => settings.n_c,
            "truncation" => String(settings.truncation),
            "cap_rank" => settings.cap_rank,
            "max_rank" => settings.max_rank,
            "low_rank_svd" => settings.low_rank_svd,
            "svd_filtering_tolerance" => settings.svd_filtering_tolerance,
        ),
    )
    return pt, convergence_metadata
end

"""
Run the cache-backed UniformTEMPO construction.

Usage: cache_uniform_if.jl [--rebuild-cache] <config.toml> [cache_dir]
"""
function cache_cli_main(args=ARGS; pt_builder::Function=default_uniform_pt_builder)
    rebuild_override = "--rebuild-cache" in args
    positional = filter(arg -> arg != "--rebuild-cache", args)
    length(positional) in (1, 2) ||
        error("usage: cache_uniform_if.jl [--rebuild-cache] <config.toml> [cache_dir]")
    config = cache_config_from_toml(positional[1])
    config.temperature == 0.0 ||
        error("the current zero-temperature bath builder rejects nonzero temperature")
    cache_dir = length(positional) == 2 ? positional[2] : config.cache_dir
    adapter = build_or_load_uniform_if(config, cache_dir, pt_builder;
                                       rebuild=(config.rebuild_cache || rebuild_override))
    println("uniform IF cache ready: χ=", size(adapter.q, 1), " dir=", cache_dir)
    return adapter
end

if abspath(PROGRAM_FILE) == @__FILE__
    cache_cli_main()
end
