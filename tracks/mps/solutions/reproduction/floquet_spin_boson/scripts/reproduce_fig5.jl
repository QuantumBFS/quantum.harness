#!/usr/bin/env julia

using TOML
using SHA

include(joinpath(@__DIR__, "cache_uniform_if.jl"))

function _fig5_frequency_grid(raw, defaults)
    value = get(raw, "frequencies", defaults.frequencies)
    if value isa AbstractVector
        return Float64.(value)
    elseif value isa AbstractDict
        all(key -> haskey(value, key), ("start", "step", "stop")) ||
            error("Fig. 5 frequency range requires start, step, and stop")
        start = Float64(value["start"])
        step = Float64(value["step"])
        stop = Float64(value["stop"])
        step > 0 || error("Fig. 5 frequency step must be positive")
        return collect(start:step:stop)
    end
    error("Fig. 5 frequencies must be an array or range table")
end

function fig5_config_from_toml(path::AbstractString)
    raw = TOML.parsefile(path)
    defaults = Fig5Config()
    return Fig5Config(
        mode=Symbol(get(raw, "mode", string(defaults.mode))),
        dt_target=Float64(get(raw, "dt_target", defaults.dt_target)),
        frequencies=_fig5_frequency_grid(raw, defaults),
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
            defaults.eigensolver_max_iterations)),
        energy_balance_tolerance=Float64(get(
            raw, "energy_balance_tolerance",
            defaults.energy_balance_tolerance)),
        energy_balance_floor=Float64(get(
            raw, "energy_balance_floor", defaults.energy_balance_floor)))
end

function _fig5_cli_options(args)
    resume = "--resume" in args
    rebuild = "--rebuild-cache" in args
    parallel = :frequencies
    reference_dir = nothing
    convergence_evidence = nothing
    positional = String[]
    index = 1
    while index <= length(args)
        argument = args[index]
        if argument in ("--resume", "--rebuild-cache")
            index += 1
        elseif argument == "--parallel"
            index < length(args) ||
                error("--parallel requires frequencies, phases, or none")
            parallel = Symbol(args[index + 1])
            parallel in (:frequencies, :phases, :none) ||
                error("--parallel requires frequencies, phases, or none")
            index += 2
        elseif argument == "--reference-dir"
            index < length(args) ||
                error("--reference-dir requires the extracted Zenodo fig_5 directory")
            reference_dir = args[index + 1]
            index += 2
        elseif argument == "--convergence-evidence"
            index < length(args) ||
                error("--convergence-evidence requires a TOML file")
            convergence_evidence = args[index + 1]
            index += 2
        elseif startswith(argument, "--")
            error("unknown Fig. 5 option: " * argument)
        else
            push!(positional, argument)
            index += 1
        end
    end
    length(positional) == 2 ||
        error("usage: reproduce_fig5.jl [--parallel frequencies|phases|none] [--resume] [--rebuild-cache] [--reference-dir DIR] [--convergence-evidence FILE] <config.toml> <output_dir>")
    return (; config_path=positional[1], output_dir=positional[2],
            resume, rebuild, parallel, reference_dir, convergence_evidence)
end

function fig5_cli_main(args=ARGS;
                       pt_builder::Function=default_uniform_pt_builder)
    options = _fig5_cli_options(args)
    fig5 = fig5_config_from_toml(options.config_path)
    run_config = cache_config_from_toml(options.config_path)
    run_config.temperature == 0.0 ||
        error("Fig. 5 currently implements only the paper's zero-temperature bath")
    fig5.mode !== :quick && isnothing(options.reference_dir) &&
        error("validation/production Fig. 5 runs require --reference-dir")
    required = Dict(
        "eigensolver" => fig5.eigensolver_tolerance,
        "tail_norm" => fig5.tail_norm_tolerance,
        "energy_balance" => fig5.energy_balance_tolerance,
    )
    require_convergence_evidence(
        fig5.mode,
        isnothing(options.convergence_evidence) ? "" : options.convergence_evidence,
        required,
    )
    adapter_provider = function (model, exact_dt)
        return build_or_load_uniform_if(
            run_config, run_config.cache_dir, pt_builder;
            model, exact_dt,
            rebuild=(run_config.rebuild_cache || options.rebuild))
    end
    reference_paths = isnothing(options.reference_dir) ? String[] :
        [fig5_reference_path(options.reference_dir, drive)
         for drive in (:longitudinal, :transversal)]
    reference_identity = isempty(reference_paths) ? "no-reference" :
        join((bytes2hex(sha256(read(path))) for path in reference_paths), ":")
    reference_provider = if isempty(reference_paths)
        nothing
    else
        curves = Dict(
            drive => load_fig5_reference(path)
            for (drive, path) in
                zip((:longitudinal, :transversal), reference_paths))
        drive -> curves[drive]
    end
    return run_fig5(
        fig5, options.output_dir;
        adapter_provider,
        run_identity=bytes2hex(sha256(
            repr((run_config, reference_identity)))),
        resume=options.resume,
        parallel_mode=options.parallel,
        reference_provider)
end

if abspath(PROGRAM_FILE) == @__FILE__
    fig5_cli_main()
end
