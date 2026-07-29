#!/usr/bin/env julia

using Dates
using Mosek
using SHA
using TOML

const MOSEK_RAY_REPLAY_SCHEMA =
    "mosek-primal-infeasibility-ray-replay-v2"
const REPLAY_MOSEK_RAY_MAGIC = collect(codeunits("SSMOSEKRAYV1\n"))

replay_file_sha256(path::AbstractString) = bytes2hex(open(sha256, path))
read_ray_u64(io::IO) = ltoh(read(io, UInt64))

function read_ray_float64_vector(io::IO)
    count = Int(read_ray_u64(io))
    values = Vector{Float64}(undef, count)
    for index in eachindex(values)
        values[index] = reinterpret(Float64, ltoh(read(io, UInt64)))
    end
    return values
end

function read_mosek_infeasibility_ray(path::AbstractString)
    return open(path, "r") do io
        read(io, length(REPLAY_MOSEK_RAY_MAGIC)) == REPLAY_MOSEK_RAY_MAGIC ||
            error("Mosek ray magic mismatch")
        problem_status_code = Int(read_ray_u64(io))
        solution_status_code = Int(read_ray_u64(io))
        constraint_count = Int(read_ray_u64(io))
        scalar_variable_count = Int(read_ray_u64(io))
        cone_count = Int(read_ray_u64(io))
        semidefinite_variable_count = Int(read_ray_u64(io))
        vectors = [read_ray_float64_vector(io) for _ in 1:7]
        bar_count = Int(read_ray_u64(io))
        bar_count == semidefinite_variable_count ||
            error("Mosek ray semidefinite count mismatch")
        bar_dimensions = Int[]
        bar_duals = Vector{Vector{Float64}}()
        for _ in 1:bar_count
            push!(bar_dimensions, Int(read_ray_u64(io)))
            push!(bar_duals, read_ray_float64_vector(io))
        end
        eof(io) || error("Mosek ray artifact has trailing bytes")
        return (
            problem_status_code=problem_status_code,
            solution_status_code=solution_status_code,
            constraint_count=constraint_count,
            scalar_variable_count=scalar_variable_count,
            cone_count=cone_count,
            semidefinite_variable_count=semidefinite_variable_count,
            y=vectors[1],
            slc=vectors[2],
            suc=vectors[3],
            slx=vectors[4],
            sux=vectors[5],
            snx=vectors[6],
            doty=vectors[7],
            bar_dimensions=bar_dimensions,
            bar_duals=bar_duals,
        )
    end
end

function replay_usage()
    println(
        "Usage: julia replay_mosek_infeasibility_artifact.jl " *
        "--task TASK.task --ray RAY.bin --output REPORT.toml " *
        "--expected-task-sha256 HEX --expected-ray-sha256 HEX " *
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
            "--ray",
            "--output",
            "--expected-task-sha256",
            "--expected-ray-sha256",
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
        "--ray",
        "--output",
        "--expected-task-sha256",
        "--expected-ray-sha256",
    )
        haskey(values, required) ||
            throw(ArgumentError("$required is required"))
    end
    tolerance = parse(Float64, get(values, "--tolerance", "1e-7"))
    isfinite(tolerance) && tolerance > 0.0 ||
        throw(ArgumentError("--tolerance must be finite and positive"))
    return (
        task=values["--task"],
        ray=values["--ray"],
        output=values["--output"],
        expected_task_sha256=lowercase(values["--expected-task-sha256"]),
        expected_ray_sha256=lowercase(values["--expected-ray-sha256"]),
        tolerance=tolerance,
    )
end

function mosek_ray_replay_report(
    task_path::AbstractString,
    ray_path::AbstractString;
    expected_task_sha256::AbstractString,
    expected_ray_sha256::AbstractString,
    tolerance::Float64=1e-7,
)
    task_sha256 = replay_file_sha256(task_path)
    ray_sha256 = replay_file_sha256(ray_path)
    task_sha256 == lowercase(expected_task_sha256) ||
        error("Mosek task SHA-256 mismatch")
    ray_sha256 == lowercase(expected_ray_sha256) ||
        error("Mosek ray SHA-256 mismatch")
    ray = read_mosek_infeasibility_ray(ray_path)

    audit = Mosek.maketask() do task
        Mosek.readdata(task, task_path)
        numcon = Int(Mosek.getnumcon(task))
        numvar = Int(Mosek.getnumvar(task))
        numcone = Int(Mosek.getnumcone(task))
        numbarvar = Int(Mosek.getnumbarvar(task))
        (numcon, numvar, numcone, numbarvar) == (
            ray.constraint_count,
            ray.scalar_variable_count,
            ray.cone_count,
            ray.semidefinite_variable_count,
        ) || error("Mosek task and ray dimensions differ")
        length(ray.y) == numcon || error("ray y length mismatch")
        length(ray.slc) == numcon || error("ray slc length mismatch")
        length(ray.suc) == numcon || error("ray suc length mismatch")
        length(ray.slx) == numvar || error("ray slx length mismatch")
        length(ray.sux) == numvar || error("ray sux length mismatch")
        length(ray.snx) == numvar || error("ray snx length mismatch")
        for index in 1:numbarvar
            Int(Mosek.getdimbarvarj(task, index)) ==
                ray.bar_dimensions[index] ||
                error("ray semidefinite dimension mismatch")
        end

        Mosek.putsolutionnew(
            task,
            Mosek.MSK_SOL_ITR,
            fill(Mosek.MSK_SK_UNK, numcon),
            fill(Mosek.MSK_SK_UNK, numvar),
            fill(Mosek.MSK_SK_UNK, numcone),
            nothing,
            nothing,
            ray.y,
            ray.slc,
            ray.suc,
            ray.slx,
            ray.sux,
            ray.snx,
            ray.doty,
        )
        for index in 1:numbarvar
            Mosek.putbarsj(
                task,
                Mosek.MSK_SOL_ITR,
                index,
                ray.bar_duals[index],
            )
        end
        Mosek.updatesolutioninfo(task, Mosek.MSK_SOL_ITR)
        information = Mosek.getsolutioninfonew(task, Mosek.MSK_SOL_ITR)
        dual_norms = Mosek.getdualsolutionnorms(task, Mosek.MSK_SOL_ITR)
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
        normalized_separation = dual_objective / ray_scale
        status_passed =
            ray.problem_status_code ==
                Mosek.MSK_PRO_STA_PRIM_INFEAS.value &&
            ray.solution_status_code ==
                Mosek.MSK_SOL_STA_PRIM_INFEAS_CER.value
        residual_passed = finite && normalized_dual_violation <= tolerance
        separation_passed = finite && normalized_separation > tolerance
        passed = status_passed && residual_passed && separation_passed
        return Dict(
            "source_problem_status_code" => ray.problem_status_code,
            "source_solution_status_code" => ray.solution_status_code,
            "status_passed" => status_passed,
            "finite" => finite,
            "dual_objective" => dual_objective,
            "dual_norms" => Float64[dual_norms...],
            "dual_violations" => dual_violations,
            "maximum_dual_violation" => maximum_dual_violation,
            "ray_scale" => ray_scale,
            "normalized_dual_violation" => normalized_dual_violation,
            "normalized_separation" => normalized_separation,
            "residual_passed" => residual_passed,
            "separation_passed" => separation_passed,
            "passed" => passed,
            "constraint_count" => numcon,
            "scalar_variable_count" => numvar,
            "semidefinite_variable_count" => numbarvar,
            "cone_count" => numcone,
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
            "mosek_infeasibility_ray_replayed_float" :
            "mosek_infeasibility_ray_replay_failed",
        "tolerance" => tolerance,
        "task" => Dict(
            "path" => abspath(task_path),
            "bytes" => filesize(task_path),
            "sha256" => task_sha256,
        ),
        "ray" => Dict(
            "path" => abspath(ray_path),
            "bytes" => filesize(ray_path),
            "sha256" => ray_sha256,
        ),
        "audit" => audit,
        "scope" =>
            "fresh-task floating Farkas-ray replay; not exact arithmetic",
    )
end

function replay_mosek_infeasibility_main(arguments::Vector{String}=ARGS)
    options = parse_replay_args(arguments)
    isnothing(options) && return
    ispath(options.output) &&
        error("refusing existing replay report: $(options.output)")
    report = mosek_ray_replay_report(
        options.task,
        options.ray;
        expected_task_sha256=options.expected_task_sha256,
        expected_ray_sha256=options.expected_ray_sha256,
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
