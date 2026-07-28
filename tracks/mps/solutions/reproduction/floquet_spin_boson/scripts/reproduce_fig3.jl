#!/usr/bin/env julia

using TOML

include(joinpath(@__DIR__, "cache_uniform_if.jl"))

function fig3_config_from_toml(path::AbstractString)
    raw = TOML.parsefile(path)
    defaults = Fig3Config()
    return Fig3Config(
        mode=Symbol(get(raw, "mode", string(defaults.mode))),
        dt_target=Float64(get(raw, "dt_target", defaults.dt_target)),
        longitudinal_frequencies=Float64.(get(
            raw, "longitudinal_frequencies",
            defaults.longitudinal_frequencies)),
        transversal_frequencies=Float64.(get(
            raw, "transversal_frequencies",
            defaults.transversal_frequencies)),
        correlation_lag_steps=Int(get(
            raw, "correlation_lag_steps",
            defaults.correlation_lag_steps)),
        tail_count=Int(get(raw, "tail_count", defaults.tail_count)),
        tail_norm_tolerance=Float64(get(
            raw, "tail_norm_tolerance", defaults.tail_norm_tolerance)),
        tail_mean_tolerance=Float64(get(
            raw, "tail_mean_tolerance", defaults.tail_mean_tolerance)),
        tail_slope_tolerance=Float64(get(
            raw, "tail_slope_tolerance", defaults.tail_slope_tolerance)),
        c0_tolerance=Float64(get(
            raw, "c0_tolerance", defaults.c0_tolerance)),
        omega_max=Float64(get(raw, "omega_max", defaults.omega_max)),
        nmax=Int(get(raw, "nmax", defaults.nmax)),
        weight_tolerance=Float64(get(
            raw, "weight_tolerance", defaults.weight_tolerance)),
        eigensolver_tolerance=Float64(get(
            raw, "eigensolver_tolerance",
            defaults.eigensolver_tolerance)),
        eigensolver_max_iterations=Int(get(
            raw, "eigensolver_max_iterations",
            defaults.eigensolver_max_iterations)))
end

function _fig3_cli_options(args)
    resume = "--resume" in args
    rebuild = "--rebuild-cache" in args
    parallel = :phases
    reference_dir = nothing
    positional = String[]
    index = 1
    while index <= length(args)
        argument = args[index]
        if argument in ("--resume", "--rebuild-cache")
            index += 1
        elseif argument == "--parallel"
            index < length(args) ||
                error("--parallel requires phases or none")
            parallel = Symbol(args[index + 1])
            index += 2
        elseif argument == "--reference-dir"
            index < length(args) ||
                error("--reference-dir requires the extracted Zenodo fig_3 directory")
            reference_dir = args[index + 1]
            index += 2
        elseif startswith(argument, "--")
            error("unknown Fig. 3 option: " * argument)
        else
            push!(positional, argument)
            index += 1
        end
    end
    length(positional) == 2 ||
        error("usage: reproduce_fig3.jl [--parallel phases|none] [--resume] [--rebuild-cache] [--reference-dir DIR] <config.toml> <output_dir>")
    return (; config_path=positional[1], output_dir=positional[2],
            resume, rebuild, parallel, reference_dir)
end

function fig3_cli_main(args=ARGS;
                       pt_builder::Function=default_uniform_pt_builder)
    options = _fig3_cli_options(args)
    fig3 = fig3_config_from_toml(options.config_path)
    run_config = cache_config_from_toml(options.config_path)
    run_config.temperature == 0.0 ||
        error("Fig. 3 currently implements only the paper's zero-temperature bath")
    fig3.mode !== :quick && isnothing(options.reference_dir) &&
        error("validation/production Fig. 3 runs require --reference-dir")
    adapter_provider = function (model, exact_dt)
        return build_or_load_uniform_if(
            run_config, run_config.cache_dir, pt_builder;
            model, exact_dt,
            rebuild=(run_config.rebuild_cache || options.rebuild))
    end
    reference_provider = isnothing(options.reference_dir) ? nothing :
        ((drive, omega_d) -> load_fig3_reference(
            fig3_reference_path(options.reference_dir, drive, omega_d)))
    return run_fig3(
        fig3, options.output_dir;
        adapter_provider,
        resume=options.resume,
        parallel_mode=options.parallel,
        reference_provider)
end

if abspath(PROGRAM_FILE) == @__FILE__
    fig3_cli_main()
end
