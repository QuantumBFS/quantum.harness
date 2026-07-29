#!/usr/bin/env julia

using Dates
using SHA
using Sockets
using TOML
using JuMP
using Mosek
using MosekTools

const RESULT_SCHEMA = "square-primal-smoke-result-v1"
const MOSEK_NUM_THREADS_ATTRIBUTE = "MSK_IPAR_NUM_THREADS"
const MOSEK_SOLVE_FORM_ATTRIBUTE = "MSK_IPAR_INTPNT_SOLVE_FORM"

# Forced MSK_SOLVE_DUAL is OPT-IN (env var). Default lets Mosek choose its own
# form, which is what the γ=0 run actually used (Mosek picked primal after
# presolve, see LEAD_RUNG_A_GAMMA_ZERO_RESULT_AND_NEXT_PROBES). Forcing dual was
# observed to hang nondeterministically past the solver time-limit on γ=0 (job
# 22990714) -- see notes/worker-gamma-quarter-attempt-and-feishu-landscape-2026-07-29.md.
forced_dual_solve_form() =
    lowercase(get(ENV, "RUNG_FORCE_DUAL_SOLVE_FORM", "")) in ("1", "true", "yes")

function progress(message::AbstractString)
    println("[square-primal-solve] ", message)
    flush(stdout)
end

function usage()
    println(
        """
        Usage:
          julia --project=julia-env solve_square_primal_mof.jl \\
            --model <model.mof.json> \\
            --runmeta <runmeta.toml> \\
            --output <result.toml> \\
            --expected-basis-family <family> \\
            --expected-positive-dimension <n> \\
            --expected-gap-dimension <n> \\
            --expected-gamma <canonical-rational> \\
            [--time-limit-seconds 1800] [--threads 16]

        Reads a previously verified Square direct-primal MOF, validates its
        SHA-256 and intended basis identity against runmeta, attaches Mosek,
        and performs one feasibility solve. Raw MOI statuses are always
        written, including on exceptions.
        """,
    )
end

function parse_positive_int(text::String, flag::String)
    value = tryparse(Int, text)
    isnothing(value) &&
        throw(ArgumentError("$flag requires an integer"))
    value > 0 ||
        throw(ArgumentError("$flag must be positive"))
    return value
end

function parse_args(args::Vector{String})
    values = Dict{String,String}()
    index = 1
    while index <= length(args)
        argument = args[index]
        if argument in ("-h", "--help")
            usage()
            return nothing
        elseif argument in (
            "--model",
            "--runmeta",
            "--output",
            "--expected-basis-family",
            "--expected-positive-dimension",
            "--expected-gap-dimension",
            "--expected-gamma",
            "--time-limit-seconds",
            "--threads",
        )
            index < length(args) ||
                throw(ArgumentError("$argument requires a value"))
            values[argument] = args[index + 1]
            index += 2
        else
            throw(ArgumentError("unknown argument: $argument"))
        end
    end
    for required in (
        "--model",
        "--runmeta",
        "--output",
        "--expected-basis-family",
        "--expected-positive-dimension",
        "--expected-gap-dimension",
        "--expected-gamma",
    )
        haskey(values, required) ||
            throw(ArgumentError("$required is required"))
    end
    time_limit = parse_positive_int(
        get(values, "--time-limit-seconds", "1800"),
        "--time-limit-seconds",
    )
    threads = parse_positive_int(
        get(values, "--threads", "16"),
        "--threads",
    )
    return (
        model=values["--model"],
        runmeta=values["--runmeta"],
        output=values["--output"],
        expected_basis_family=values["--expected-basis-family"],
        expected_positive_dimension=parse_positive_int(
            values["--expected-positive-dimension"],
            "--expected-positive-dimension",
        ),
        expected_gap_dimension=parse_positive_int(
            values["--expected-gap-dimension"],
            "--expected-gap-dimension",
        ),
        expected_gamma=values["--expected-gamma"],
        time_limit_seconds=time_limit,
        threads=threads,
    )
end

file_sha256(path::AbstractString) =
    bytes2hex(open(sha256, path))

function peak_rss_kib()
    status_path = "/proc/self/status"
    isfile(status_path) || return -1
    for line in eachline(status_path)
        startswith(line, "VmHWM:") || continue
        fields = split(line)
        length(fields) >= 2 || return -1
        return parse(Int, fields[2])
    end
    return -1
end

function safe_string(function_call, fallback::String)
    try
        return string(function_call())
    catch exception
        return fallback * ":" * string(typeof(exception))
    end
end

function safe_number(function_call)
    try
        value = function_call()
        value isa Real || return Dict(
            "available" => false,
            "reason" => "not_real",
        )
        isfinite(value) || return Dict(
            "available" => false,
            "reason" => "not_finite",
        )
        return Dict(
            "available" => true,
            "value" => Float64(value),
        )
    catch exception
        return Dict(
            "available" => false,
            "reason" => string(typeof(exception)),
        )
    end
end

function classify_status(
    termination,
    primal,
)
    if termination in (
        JuMP.MOI.OPTIMAL,
        JuMP.MOI.LOCALLY_SOLVED,
        JuMP.MOI.ALMOST_OPTIMAL,
    ) && primal in (
        JuMP.MOI.FEASIBLE_POINT,
        JuMP.MOI.NEARLY_FEASIBLE_POINT,
    )
        return "feasible_candidate"
    elseif primal in (
        JuMP.MOI.INFEASIBILITY_CERTIFICATE,
        JuMP.MOI.NEARLY_INFEASIBILITY_CERTIFICATE,
    )
        return "infeasibility_candidate_requires_ray_replay"
    end
    return "unknown"
end

function set_mosek_num_threads!(model::JuMP.Model, threads::Int)
    threads > 0 ||
        throw(ArgumentError("Mosek thread count must be positive"))
    JuMP.set_optimizer_attribute(
        model,
        MOSEK_NUM_THREADS_ATTRIBUTE,
        threads,
    )
    return nothing
end

function set_mosek_dual_solve_form!(model::JuMP.Model)
    JuMP.set_optimizer_attribute(
        model,
        MOSEK_SOLVE_FORM_ATTRIBUTE,
        Int(Mosek.MSK_SOLVE_DUAL.value),
    )
    return nothing
end

function mosek_task_summary(
    optimizer::MosekTools.Optimizer,
    attach_wall_seconds::Float64,
)
    task = optimizer.task
    num_bar_variables = Mosek.getnumbarvar(task)
    return Dict(
        "schema_version" => "square-primal-mosek-preopt-v1",
        "attach_wall_seconds" => attach_wall_seconds,
        "peak_process_rss_kib_after_attach" => peak_rss_kib(),
        "scalar_variable_count" => Mosek.getnumvar(task),
        "linear_constraint_count" => Mosek.getnumcon(task),
        "scalar_matrix_nonzero_count" => Mosek.getnumanz(task),
        "semidefinite_variable_count" => num_bar_variables,
        "semidefinite_dimensions" => [
            Mosek.getdimbarvarj(task, index)
            for index in 1:num_bar_variables
        ],
        "semidefinite_constraint_nonzero_count" =>
            Mosek.getnumbaranz(task),
        "solve_form" => forced_dual_solve_form() ? "dual_forced" : "mosek_default",
        "solve_form_parameter" =>
            forced_dual_solve_form() ? Int(Mosek.MSK_SOLVE_DUAL.value) : -1,
    )
end

function validate_input(
    model_path::String,
    runmeta_path::String,
    expected_basis_family::String,
    expected_positive_dimension::Int,
    expected_gap_dimension::Int,
    expected_gamma::String,
)
    isfile(model_path) ||
        throw(ArgumentError("MOF does not exist: $model_path"))
    isfile(runmeta_path) ||
        throw(ArgumentError("runmeta does not exist: $runmeta_path"))
    runmeta = TOML.parsefile(runmeta_path)
    runmeta["schema_version"] in (
        "square-primal-mof-runmeta-v1",
        "square-conic-mof-runmeta-v1",
    ) ||
        error("unexpected runmeta schema")
    runmeta["solver_invoked"] == false ||
        error("input runmeta is not a solver-free Gate B artifact")
    expected_sha256 = runmeta["mof"]["sha256"]
    actual_sha256 = file_sha256(model_path)
    actual_sha256 == expected_sha256 ||
        error("MOF SHA-256 does not match runmeta")
    runmeta["setup"]["model"] == "square-j1-j2" ||
        error("runmeta model is not square-j1-j2")
    validate_expected_gamma(runmeta, expected_gamma)
    runmeta["setup"]["g_j2_over_j1"]["canonical"] == "1//2" ||
        error("smoke solve is locked to g=1/2")
    runmeta["setup"]["degree_d"] == 2 ||
        error("smoke solve is locked to d=2")
    runmeta["setup"]["outer_site_count"] == 9 ||
        error("smoke solve is locked to the 9-site outer patch")
    runmeta["setup"]["inner_site_count"] == 1 ||
        error("smoke solve is locked to the 1-site inner patch")
    basis = runmeta["basis"]
    basis["positive_family"] == expected_basis_family ||
        error("positive basis family differs from the explicit launch expectation")
    basis["gap_family"] == expected_basis_family ||
        error("gap basis family differs from the explicit launch expectation")
    basis["positive_family_version"] == 1 ||
        error("smoke solve accepts only positive basis family version 1")
    basis["gap_family_version"] == 1 ||
        error("smoke solve accepts only gap basis family version 1")
    basis["positive_dimension"] == expected_positive_dimension ||
        error("positive basis dimension differs from the explicit launch expectation")
    basis["gap_dimension"] == expected_gap_dimension ||
        error("gap basis dimension differs from the explicit launch expectation")
    return runmeta, actual_sha256
end

function validate_expected_gamma(runmeta, expected_gamma::String)
    actual_gamma = runmeta["setup"]["gamma"]["canonical"]
    actual_gamma == expected_gamma ||
        error("runmeta gamma differs from the explicit launch expectation")
    return actual_gamma
end

function write_result(path::String, result)
    parent = dirname(path)
    isempty(parent) || mkpath(parent)
    temporary = path * ".tmp"
    open(temporary, "w") do io
        TOML.print(io, result; sorted=true)
    end
    mv(temporary, path; force=true)
    return path
end

function main(args::Vector{String}=ARGS)
    options = parse_args(args)
    isnothing(options) && return 0
    started_at = now(UTC)
    result = Dict(
        "schema_version" => RESULT_SCHEMA,
        "started_at_utc" => Dates.format(
            started_at,
            dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        ),
        "completed" => false,
        "classification" => "unknown",
        "model_path" => options.model,
        "runmeta_path" => options.runmeta,
        "time_limit_seconds" => options.time_limit_seconds,
        "threads" => options.threads,
        "launch_expectation" => Dict(
            "basis_family" => options.expected_basis_family,
            "positive_dimension" => options.expected_positive_dimension,
            "gap_dimension" => options.expected_gap_dimension,
            "gamma_canonical" => options.expected_gamma,
        ),
        "runtime" => Dict(
            "julia_version" => string(VERSION),
            "julia_executable" => Base.julia_cmd().exec[1],
            "jump_version" => string(Base.pkgversion(JuMP)),
            "mathoptinterface_version" =>
                string(Base.pkgversion(JuMP.MOI)),
            "mosek_version" => string(Base.pkgversion(Mosek)),
            "mosektools_version" => string(Base.pkgversion(MosekTools)),
            "slurm_job_id" => get(ENV, "SLURM_JOB_ID", "not_under_slurm"),
            "slurm_cpus_per_task" =>
                get(ENV, "SLURM_CPUS_PER_TASK", "unavailable"),
            "hostname" => gethostname(),
        ),
    )

    exit_code = 1
    wall_start = time()
    try
        progress("validating Gate B MOF and runmeta")
        runmeta, mof_sha256 = validate_input(
            options.model,
            options.runmeta,
            options.expected_basis_family,
            options.expected_positive_dimension,
            options.expected_gap_dimension,
            options.expected_gamma,
        )
        result["mof_sha256"] = mof_sha256
        result["input_assembly_sha256"] =
            runmeta["exact_assembly"]["assembly_sha256"]
        result["input_problem_sha256"] =
            runmeta["exact_assembly"]["problem_sha256"]
        result["input_moment_count"] =
            runmeta["exact_assembly"]["moment_count"]

        progress("reading MOF")
        model = JuMP.read_from_file(options.model)
        JuMP.num_variables(model) == runmeta["replay"]["variable_count"] ||
            error("MOF variable count differs from runmeta")
        JuMP.num_constraints(
            model;
            count_variable_in_set_constraints=false,
        ) == runmeta["replay"]["constraint_count_excluding_variable_sets"] ||
            error("MOF constraint count differs from runmeta")

        progress(
            "attaching Mosek; threads=$(options.threads), " *
            "time_limit=$(options.time_limit_seconds)s",
        )
        JuMP.set_optimizer(model, MosekTools.Optimizer)
        JuMP.set_time_limit_sec(model, Float64(options.time_limit_seconds))
        set_mosek_num_threads!(model, options.threads)
        forced_dual_solve_form() && set_mosek_dual_solve_form!(model)

        progress("copying bridged model to Mosek")
        attach_start = time()
        JuMP.MOI.Utilities.attach_optimizer(model)
        attach_wall_seconds = time() - attach_start
        progress(
            "Mosek task attached after " *
            "$(round(attach_wall_seconds; digits=3))s",
        )

        mosek_optimizer = JuMP.unsafe_backend(model)
        preopt_path = joinpath(dirname(options.output), "preopt.toml")
        preopt = mosek_task_summary(
            mosek_optimizer,
            attach_wall_seconds,
        )
        write_result(preopt_path, preopt)
        progress(
            "Mosek task: scalar_variables=" *
            "$(preopt["scalar_variable_count"]), constraints=" *
            "$(preopt["linear_constraint_count"]), PSD_dimensions=" *
            "$(preopt["semidefinite_dimensions"]), solve_form=dual",
        )

        mosek_log_path = joinpath(dirname(options.output), "mosek.log")
        mosek_log_io = open(mosek_log_path, "w")
        Mosek.putstreamfunc(
            mosek_optimizer.task,
            Mosek.MSK_STREAM_LOG,
            message -> begin
                print(mosek_log_io, message)
                flush(mosek_log_io)
            end,
        )

        progress(
            forced_dual_solve_form() ?
            "optimize! started (solve form forced to dual)" :
            "optimize! started (solve form left to Mosek default)",
        )
        solve_start = time()
        try
            JuMP.optimize!(model)
        finally
            flush(mosek_log_io)
            close(mosek_log_io)
        end
        solve_wall_seconds = time() - solve_start
        progress("optimize! returned after $(round(solve_wall_seconds; digits=3))s")

        termination = JuMP.termination_status(model)
        primal = JuMP.primal_status(model)
        dual = JuMP.dual_status(model)
        result["completed"] = true
        result["classification"] = classify_status(termination, primal)
        result["statuses"] = Dict(
            "termination" => string(termination),
            "primal" => string(primal),
            "dual" => string(dual),
            "raw" => safe_string(
                () -> JuMP.raw_status(model),
                "unavailable",
            ),
            "result_count" => JuMP.result_count(model),
            "has_values" => JuMP.has_values(model),
            "has_duals" => JuMP.has_duals(model),
        )
        result["solver"] = Dict(
            "solve_wall_seconds" => solve_wall_seconds,
            "solver_reported_solve_time_seconds" => safe_number(
                () -> JuMP.solve_time(model),
            ),
            "objective_value" => safe_number(
                () -> JuMP.objective_value(model),
            ),
            "dual_objective_value" => safe_number(
                () -> JuMP.dual_objective_value(model),
            ),
            "relative_gap" => safe_number(
                () -> JuMP.relative_gap(model),
            ),
        )
        exit_code = 0
    catch exception
        result["exception"] = Dict(
            "type" => string(typeof(exception)),
            "message" => sprint(showerror, exception),
            "stacktrace" => sprint(
                Base.show_backtrace,
                catch_backtrace(),
            ),
        )
        progress("FAILED: $(sprint(showerror, exception))")
    finally
        result["finished_at_utc"] = Dates.format(
            now(UTC),
            dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        )
        result["total_wall_seconds"] = time() - wall_start
        result["peak_process_rss_kib"] = peak_rss_kib()
        write_result(options.output, result)
        progress("result written to $(options.output)")
    end
    return exit_code
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(main())
end
