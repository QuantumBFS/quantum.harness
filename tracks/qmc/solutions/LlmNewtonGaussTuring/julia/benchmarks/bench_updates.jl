# Reproducible validation and performance benchmarks for the loop and line kernels.
#
# Usage:
#   julia -t 8 benchmarks/bench_updates.jl <validate|efficiency|scaling|epsilon> [output-dir]
# Fast-run lengths can be overridden with TFIM_<PROFILE>_* environment variables.

include(joinpath(@__DIR__, "..", "src", "TIM_lattice_line.jl"))
include(joinpath(@__DIR__, "..", "src", "TIM_lattice_ED.jl"))

using Dates
using LinearAlgebra
using Printf
using Sockets
using Statistics

const OBSERVABLES = ("E", "mx", "m2", "m4")
const DEFAULT_OUTPUT = joinpath(@__DIR__, "..", "data", "processed",
                                "tfim-lineupdate-julia-20260730")

envint(name, default) = parse(Int, get(ENV, name, string(default)))

function write_csv(path, header, rows)
    mkpath(dirname(path))
    open(path, "w") do io
        println(io, join(header, ','))
        for row in rows
            println(io, join(row, ','))
        end
    end
end

function write_metadata(output_dir, profile)
    commit = readchomp(`git -C $(joinpath(@__DIR__, "..")) rev-parse HEAD`)
    command = join([Base.julia_cmd().exec[1]; Base.ARGS], ' ')
    timestamp = Dates.format(now(), dateformat"yyyy-mm-ddTHH:MM:SS")
    lattice_suffix = profile == "epsilon" ? get(ENV, "TFIM_EPSILON_LATTICE", "") : ""
    metadata_tag = isempty(lattice_suffix) ? profile : "$(profile)-$(lattice_suffix)"
    open(joinpath(output_dir, "metadata-$(metadata_tag).txt"), "w") do io
        println(io, "run_id=tfim-lineupdate-julia-20260730")
        println(io, "profile=$profile")
        println(io, "timestamp=$timestamp")
        println(io, "source_commit=$commit")
        println(io, "julia_version=$(VERSION)")
        println(io, "julia_threads=$(Threads.nthreads())")
        println(io, "hostname=$(gethostname())")
        println(io, "command=$command")
        for name in sort(filter(name -> startswith(name, "TFIM_"), collect(keys(ENV))))
            println(io, "env.$name=$(ENV[name])")
        end
    end
end

function grow_operator_window!(s::Sim)
    target = floor(Int, 1.25 * s.nh)
    if target > s.lm
        target <= s.ll || error("operator list overflow: target=$target capacity=$(s.ll)")
        s.lm = target
    end
end

function prepare_chain(lattice, Lx, Ly, Gamma, beta, seed, algorithm;
                       thermalization, nt = 1, epsilon = 0.5)
    s = Sim(lattice, Lx, Ly, -1.0, 0.0, Gamma, beta, seed)
    algorithm == :line && set_bond_epsilon!(s, epsilon)
    _, classes = color_lattice(Symbol(lattice), Lx, Ly, s.N, s.bond)
    sc = LineScratch(s.N, max(nt, 1), seed)
    for _ in 1:thermalization
        dupdate!(s)
        algorithm == :line ? line_sweep!(s, sc, classes; nt = nt) : lupdate!(s)
        grow_operator_window!(s)
    end
    return s, classes, sc
end

function tau_int_sokal(values; window_factor = 5.0, maxlag = nothing)
    n = length(values)
    n >= 20 || error("tau_int requires at least 20 samples")
    centered = values .- mean(values)
    variance = dot(centered, centered) / n
    variance > 0 || return (0.5, 0, true)
    limit = isnothing(maxlag) ? min(n - 1, max(100, n ÷ 5)) : min(maxlag, n - 1)
    tau = 0.5
    for lag in 1:limit
        rho = dot(@view(centered[1:n-lag]), @view(centered[lag+1:n])) /
              ((n - lag) * variance)
        tau += rho
        if lag >= 3 && lag >= window_factor * max(tau, 0.5)
            return (max(tau, 0.5), lag, true)
        end
    end
    return (max(tau, 0.5), limit, false)
end

function sample_chain(lattice, Lx, Ly, Gamma, beta, seed, algorithm;
                      thermalization, sweeps, nt = 1, epsilon = 0.5,
                      keep_series = false)
    s, classes, sc = prepare_chain(lattice, Lx, Ly, Gamma, beta, seed, algorithm;
                                   thermalization = thermalization, nt = nt,
                                   epsilon = epsilon)
    series = Matrix{Float64}(undef, sweeps, 4)
    accepted = 0
    proposed = 0
    nh_sum = 0.0
    elapsed = @elapsed for sweep in 1:sweeps
        dupdate!(s)
        if algorithm == :line
            a, p = line_sweep!(s, sc, classes; nt = nt)
            accepted += a
            proposed += p
        else
            lupdate!(s)
        end
        grow_operator_window!(s)
        series[sweep, :] .= measure(s)
        nh_sum += s.nh
    end
    stats = NamedTuple[]
    for (column, observable) in enumerate(OBSERVABLES)
        values = @view series[:, column]
        tau, window, converged = tau_int_sokal(values)
        variance = var(values; corrected = true)
        stderr = sqrt(2tau * variance / sweeps)
        push!(stats, (observable = observable, mean = mean(values), stderr = stderr,
                      tau = tau, window = window, converged = converged,
                      ess_per_second = sweeps / (2tau * elapsed)))
    end
    acceptance = algorithm == :line ? accepted / max(proposed, 1) : NaN
    return (stats = stats, elapsed = elapsed, sweep_seconds = elapsed / sweeps,
            acceptance = acceptance, mean_nh = nh_sum / sweeps,
            series = keep_series ? series : nothing, N = s.N)
end

function validation_profile(output_dir)
    thermalization = envint("TFIM_VALIDATE_THERM", 5000)
    sweeps = envint("TFIM_VALIDATE_SWEEPS", 30000)
    cases = (("triangular", 3, 3, 4.768, 2.0),
             ("honeycomb", 2, 2, 2.1325, 2.0))
    rows = Vector{Vector{Any}}()
    failed = false
    for (case_index, (lattice, Lx, Ly, Gamma, beta)) in enumerate(cases)
        H, N = build_H(lattice, Lx, Ly, -1.0, 0.0, Gamma)
        hermiticity = opnorm(H - H')
        lambda, vectors = eigen(Symmetric(H))
        exact = thermal_obs(lambda, vectors, N, beta)
        for (algorithm_index, (algorithm, nt)) in enumerate(((:line, 1), (:loop, 1), (:line, min(4, Threads.nthreads()))))
            seed = 2026073000 + 100case_index + algorithm_index
            result = sample_chain(lattice, Lx, Ly, Gamma, beta, seed, algorithm;
                                  thermalization = thermalization, sweeps = sweeps, nt = nt)
            for (observable, exact_value, stat) in zip(("E", "mx", "m2"),
                                                       (exact[1], exact[2], exact[4]),
                                                       result.stats[1:3])
                zscore = abs(stat.mean - exact_value) / max(stat.stderr, eps())
                pass = zscore <= 4 && hermiticity <= 1e-12 && stat.converged
                failed |= !pass
                push!(rows, Any[lattice, algorithm, nt, Lx, Ly, N, beta, -1.0,
                                Gamma, observable, exact_value, stat.mean, stat.stderr,
                                stat.tau, stat.window, stat.converged, zscore, pass,
                                hermiticity, thermalization, sweeps, seed])
                @printf("%s %-4s nt=%d %-2s exact=% .8f qmc=% .8f +/- %.2g z=%.2f %s\n",
                        lattice, string(algorithm), nt, observable, exact_value,
                        stat.mean, stat.stderr, zscore, pass ? "PASS" : "FAIL")
            end
        end
    end
    header = ["lattice", "algorithm", "threads", "Lx", "Ly", "N", "beta", "J",
              "Gamma", "observable", "exact", "qmc_mean", "qmc_stderr", "tau_int",
              "tau_window", "tau_converged", "z_score", "pass", "hermiticity_error",
              "thermalization_sweeps", "measurement_sweeps", "seed"]
    write_csv(joinpath(output_dir, "validation.csv"), header, rows)
    failed && error("validation gate failed; see validation.csv")
end

function efficiency_profile(output_dir)
    thermalization = envint("TFIM_EFFICIENCY_THERM", 5000)
    sweeps = envint("TFIM_EFFICIENCY_SWEEPS", 20000)
    cases = (("triangular", 12, 12, 4.76811, 24.0),
             ("honeycomb", 8, 8, 2.13250, 16.0))
    rows = Vector{Vector{Any}}()
    series_rows = Vector{Vector{Any}}()
    for (case_index, (lattice, Lx, Ly, Gamma, beta)) in enumerate(cases)
        for (algorithm_index, algorithm) in enumerate((:loop, :line))
            seed = 2026073100 + 100case_index + algorithm_index
            result = sample_chain(lattice, Lx, Ly, Gamma, beta, seed, algorithm;
                                  thermalization = thermalization, sweeps = sweeps,
                                  keep_series = true)
            for stat in result.stats
                push!(rows, Any[lattice, algorithm, Lx, Ly, result.N, beta, -1.0, Gamma,
                                0.5, 1, stat.observable, stat.mean, stat.stderr, stat.tau,
                                stat.window, stat.converged, result.sweep_seconds,
                                stat.ess_per_second, result.acceptance, result.mean_nh,
                                thermalization, sweeps, seed])
            end
            for sweep in 1:sweeps
                push!(series_rows, Any[lattice, algorithm, sweep,
                                      result.series[sweep, 1], result.series[sweep, 2],
                                      result.series[sweep, 3], result.series[sweep, 4]])
            end
            @printf("efficiency %-10s %-4s: %.1f sweep/s, acc=%.3f\n",
                    lattice, string(algorithm), 1 / result.sweep_seconds, result.acceptance)
        end
    end
    header = ["lattice", "algorithm", "Lx", "Ly", "N", "beta", "J", "Gamma",
              "epsilon", "threads", "observable", "mean", "stderr", "tau_int",
              "tau_window", "tau_converged", "sweep_seconds", "ess_per_second",
              "acceptance", "mean_operator_count", "thermalization_sweeps",
              "measurement_sweeps", "seed"]
    write_csv(joinpath(output_dir, "efficiency.csv"), header, rows)
    write_csv(joinpath(output_dir, "efficiency_series.csv"),
              ["lattice", "algorithm", "sweep", "E", "mx", "m2", "m4"], series_rows)
end

function scaling_profile(output_dir)
    thermalization = envint("TFIM_SCALING_THERM", 1000)
    sweeps = envint("TFIM_SCALING_SWEEPS", 500)
    cases = (("triangular", 24, 24, 4.76811, 48.0),
             ("honeycomb", 12, 12, 2.13250, 24.0))
    thread_counts = filter(n -> n <= Threads.nthreads(), (1, 2, 4, 8))
    rows = Vector{Vector{Any}}()
    for (case_index, (lattice, Lx, Ly, Gamma, beta)) in enumerate(cases)
        baseline_color = NaN
        baseline_full = NaN
        for nt in thread_counts
            seed = 2026073200 + 100case_index + nt
            s, classes, sc = prepare_chain(lattice, Lx, Ly, Gamma, beta, seed, :line;
                                           thermalization = thermalization, nt = nt)
            diagonal_time = 0.0
            list_time = 0.0
            color_time = 0.0
            measure_time = 0.0
            accepted = 0
            proposed = 0
            for _ in 1:sweeps
                diagonal_time += @elapsed dupdate!(s)
                list_time += @elapsed build_site_lists!(s, sc.lists)
                color_time += @elapsed begin
                    a, p = update_color_classes!(s, sc, classes; nt = nt)
                    accepted += a
                    proposed += p
                end
                measure_time += @elapsed measure(s)
                grow_operator_window!(s)
            end
            color_per_sweep = color_time / sweeps
            full_per_sweep = (diagonal_time + list_time + color_time + measure_time) / sweeps
            if nt == 1
                baseline_color = color_per_sweep
                baseline_full = full_per_sweep
            end
            push!(rows, Any[lattice, Lx, Ly, s.N, beta, Gamma, nt, length(classes),
                            minimum(length.(classes)), maximum(length.(classes)),
                            diagonal_time / sweeps, list_time / sweeps, color_per_sweep,
                            measure_time / sweeps, full_per_sweep,
                            baseline_color / color_per_sweep, baseline_full / full_per_sweep,
                            accepted / max(proposed, 1), thermalization, sweeps, seed])
            @printf("scaling %-10s nt=%d color=%.3fx full=%.3fx\n", lattice, nt,
                    baseline_color / color_per_sweep, baseline_full / full_per_sweep)
        end
    end
    header = ["lattice", "Lx", "Ly", "N", "beta", "Gamma", "threads", "colors",
              "min_class_size", "max_class_size", "diagonal_seconds", "list_seconds",
              "color_seconds", "measure_seconds", "full_seconds", "color_speedup",
              "full_speedup", "acceptance", "thermalization_sweeps", "timed_sweeps", "seed"]
    write_csv(joinpath(output_dir, "scaling.csv"), header, rows)
end

function epsilon_profile(output_dir)
    thermalization = envint("TFIM_EPSILON_THERM", 3000)
    sweeps = envint("TFIM_EPSILON_SWEEPS", 10000)
    all_cases = (("triangular", 12, 12, 4.76811, 24.0),
                 ("honeycomb", 8, 8, 2.13250, 16.0))
    lattice_filter = get(ENV, "TFIM_EPSILON_LATTICE", "")
    cases = isempty(lattice_filter) ? all_cases :
            filter(case -> case[1] == lattice_filter, all_cases)
    isempty(cases) && error("unknown TFIM_EPSILON_LATTICE=$lattice_filter")
    rows = Vector{Vector{Any}}()
    for (case_index, (lattice, Lx, Ly, Gamma, beta)) in enumerate(cases)
        for (epsilon_index, epsilon) in enumerate((0.25, 0.5, 1.0))
            seed = 2026073300 + 100case_index + epsilon_index
            result = sample_chain(lattice, Lx, Ly, Gamma, beta, seed, :line;
                                  thermalization = thermalization, sweeps = sweeps,
                                  epsilon = epsilon)
            for stat in result.stats
                push!(rows, Any[lattice, Lx, Ly, result.N, beta, Gamma, epsilon,
                                stat.observable, stat.mean, stat.stderr, stat.tau,
                                stat.window, stat.converged, result.sweep_seconds,
                                stat.ess_per_second, result.acceptance, result.mean_nh,
                                thermalization, sweeps, seed])
            end
            @printf("epsilon %-10s eps=%.2f acc=%.3f nh=%.1f\n", lattice, epsilon,
                    result.acceptance, result.mean_nh)
        end
    end
    header = ["lattice", "Lx", "Ly", "N", "beta", "Gamma", "epsilon", "observable",
              "mean", "stderr", "tau_int", "tau_window", "tau_converged",
              "sweep_seconds", "ess_per_second", "acceptance", "mean_operator_count",
              "thermalization_sweeps", "measurement_sweeps", "seed"]
    output_name = isempty(lattice_filter) ? "epsilon.csv" : "epsilon-$(lattice_filter).csv"
    write_csv(joinpath(output_dir, output_name), header, rows)
end

length(ARGS) >= 1 || error("profile required: validate, efficiency, scaling, or epsilon")
profile = ARGS[1]
output_dir = length(ARGS) >= 2 ? abspath(ARGS[2]) : abspath(DEFAULT_OUTPUT)
mkpath(output_dir)
write_metadata(output_dir, profile)
if profile == "validate"
    validation_profile(output_dir)
elseif profile == "efficiency"
    efficiency_profile(output_dir)
elseif profile == "scaling"
    scaling_profile(output_dir)
elseif profile == "epsilon"
    epsilon_profile(output_dir)
else
    error("unknown profile: $profile")
end
