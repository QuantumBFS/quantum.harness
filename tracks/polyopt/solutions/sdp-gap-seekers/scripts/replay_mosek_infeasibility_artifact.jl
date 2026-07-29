#!/usr/bin/env julia

using Dates
using Mosek
using SHA
using TOML

const MOSEK_RAY_REPLAY_SCHEMA =
    "mosek-primal-infeasibility-ray-replay-v1"

function replay_file_sha256(path::AbstractString)
    return bytes2hex(open(sha256, path))
end

function replay_usage()
    println(
        "Usage: julia replay_mosek_infeasibility_artifact.jl " *
        "--task TASK.task.gz --solution SOLUTION.sol --output REPORT.toml " *
        "--expected-task-sha256 HEX --expected-solution-sha256 HEX " *
        "[--tolerance 1e-7]",
    )
end

function parse_replay_args(arguments::Vector{String})
    values = Dict{String,String}()
    index = 1
    while index <= length(arguments)
        argument = arguments[index]
        if argument in ("-h", "--help")
            replay_usage()
            return nothing
        elseif argument in (
            "--task",
            "--solution",
            "--output",
            "--expected-task-sha256",
            "--expected-solution-sha256",
            "--tolerance",
        )
            index < length(arguments) ||
                throw(ArgumentError("$argument requires a value"))
            values[argument] = arguments[index + 1]
            index += 2
        else
            throw(ArgumentError("unknown argument: $argument"))
        end
    end
    for required in (
        "--task",
        "--solution",
        "--output",
        "--expected-task-sha256",
        "--expected-solution-sha256",
    )
        haskey(values, required) ||
            throw(ArgumentError("$required is required"))
    end
    tolerance = parse(Float64, get(values, "--tolerance", "1e-7"))
    isfinite(tolerance) && tolerance > 0.0 ||
        throw(ArgumentError("--tolerance must be finite and positive"))
    return (
        task=values["--task"],
        solution=values["--solution"],
        output=values["--output"],
        expected_task_sha256=lowercase(
            values["--expected-task-sha256"],
        ),
        expected_solution_sha256=lowercase(
            values["--expected-solution-sha256"],
        ),
        tolerance=tolerance,
    )
end

function mosek_ray_replay_report(
    task_path::AbstractString,
    solution_path::AbstractString;
    expected_task_sha256::AbstractString,
    expected_solution_sha256::AbstractString,
    tolerance::Float64=1e-7,
)
    task_sha256 = replay_file_sha256(task_path)
    solution_sha256 = replay_file_sha256(solution_path)
    task_sha256 == lowercase(expected_task_sha256) ||
        error("Mosek task SHA-256 mismatch")
    solution_sha256 == lowercase(expected_solution_sha256) ||
        error("Mosek solution SHA-256 mismatch")

    audit = Mosek.maketask() do task
        Mosek.readdata(task, task_path)
        Mosek.readsolution(task, Mosek.MSK_SOL_ITR, solution_path)
        Mosek.solutiondef(task, Mosek.MSK_SOL_ITR) ||
            error("reloaded task has no interior solution")

        problem_status = Mosek.getprosta(task, Mosek.MSK_SOL_ITR)
        solution_status = Mosek.getsolsta(task, Mosek.MSK_SOL_ITR)
        information = Mosek.getsolutioninfonew(task, Mosek.MSK_SOL_ITR)
        dual_norms = Mosek.getdualsolutionnorms(
            task,
            Mosek.MSK_SOL_ITR,
        )
        dual_objective = Float64(information[9])
        dual_violations = Float64.(information[10:14])
        finite = all(isfinite, information) && all(isfinite, dual_norms)
        ray_scale = maximum((
            1.0,
            abs(dual_objective),
            maximum(abs, dual_norms),
        ))
        maximum_dual_violation = maximum(abs, dual_violations)
        normalized_dual_violation = maximum_dual_violation / ray_scale
        normalized_separation = abs(dual_objective) / ray_scale
        status_passed =
            problem_status == Mosek.MSK_PRO_STA_PRIM_INFEAS &&
            solution_status == Mosek.MSK_SOL_STA_PRIM_INFEAS_CER
        residual_passed =
            finite && normalized_dual_violation <= tolerance
        separation_passed =
            finite && normalized_separation > tolerance
        passed = status_passed && residual_passed && separation_passed

        return Dict(
            "problem_status" => string(problem_status),
            "solution_status" => string(solution_status),
            "status_passed" => status_passed,
            "finite" => finite,
            "dual_objective" => dual_objective,
            "dual_norms" => collect(Float64, dual_norms),
            "dual_violations" => dual_violations,
            "maximum_dual_violation" => maximum_dual_violation,
            "ray_scale" => ray_scale,
            "normalized_dual_violation" => normalized_dual_violation,
            "normalized_separation" => normalized_separation,
            "residual_passed" => residual_passed,
            "separation_passed" => separation_passed,
            "passed" => passed,
            "constraint_count" => Int(Mosek.getnumcon(task)),
            "scalar_variable_count" => Int(Mosek.getnumvar(task)),
            "semidefinite_variable_count" =>
                Int(Mosek.getnumbarvar(task)),
            "cone_count" => Int(Mosek.getnumcone(task)),
        )
    end

    return Dict(
        "schema_version" => MOSEK_RAY_REPLAY_SCHEMA,
        "replay_script_sha256" => replay_file_sha256(@__FILE__),
        "created_at_utc" => Dates.format(
            now(UTC),
            dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        ),
        "classification" => audit["passed"] ?
            "mosek_native_infeasibility_ray_replayed_float" :
            "mosek_native_infeasibility_ray_replay_failed",
        "tolerance" => tolerance,
        "task" => Dict(
            "path" => abspath(task_path),
            "bytes" => filesize(task_path),
            "sha256" => task_sha256,
        ),
        "solution" => Dict(
            "path" => abspath(solution_path),
            "bytes" => filesize(solution_path),
            "sha256" => solution_sha256,
        ),
        "audit" => audit,
        "scope" =>
            "fresh-task Mosek-native floating ray replay; not exact arithmetic",
    )
end

function replay_mosek_infeasibility_main(arguments::Vector{String}=ARGS)
    options = parse_replay_args(arguments)
    isnothing(options) && return
    ispath(options.output) &&
        error("refusing existing replay report: $(options.output)")
    report = mosek_ray_replay_report(
        options.task,
        options.solution;
        expected_task_sha256=options.expected_task_sha256,
        expected_solution_sha256=options.expected_solution_sha256,
        tolerance=options.tolerance,
    )
    temporary = options.output * ".tmp"
    ispath(temporary) &&
        error("refusing existing replay temporary report: $temporary")
    open(temporary, "w") do io
        TOML.print(io, report; sorted=true)
    end
    mv(temporary, options.output)
    println(
        "[mosek-ray-replay] ",
        report["classification"],
        " normalized_dual_violation=",
        report["audit"]["normalized_dual_violation"],
        " normalized_separation=",
        report["audit"]["normalized_separation"],
    )
    flush(stdout)
    report["audit"]["passed"] || error("infeasibility ray replay failed")
end

if abspath(PROGRAM_FILE) == @__FILE__
    replay_mosek_infeasibility_main()
end
