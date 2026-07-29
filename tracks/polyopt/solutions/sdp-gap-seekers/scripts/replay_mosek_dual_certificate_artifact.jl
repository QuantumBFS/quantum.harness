#!/usr/bin/env julia

using Dates
using Mosek
using SHA
using TOML

const MOSEK_DUAL_CERTIFICATE_REPLAY_SCHEMA =
    "mosek-dual-certificate-primal-replay-v1"
const REPLAY_MOSEK_DUAL_CERTIFICATE_MAGIC =
    collect(codeunits("SSMOSEKCERTV1\n"))

certificate_file_sha256(path::AbstractString) =
    bytes2hex(open(sha256, path))
read_certificate_u64(io::IO) = ltoh(read(io, UInt64))

function read_certificate_float64_vector(io::IO)
    count = Int(read_certificate_u64(io))
    values = Vector{Float64}(undef, count)
    for index in eachindex(values)
        values[index] = reinterpret(
            Float64,
            ltoh(read(io, UInt64)),
        )
    end
    return values
end

function read_mosek_dual_certificate(path::AbstractString)
    return open(path, "r") do io
        read(io, length(REPLAY_MOSEK_DUAL_CERTIFICATE_MAGIC)) ==
            REPLAY_MOSEK_DUAL_CERTIFICATE_MAGIC ||
            error("Mosek dual-certificate magic mismatch")
        problem_status_code = Int(read_certificate_u64(io))
        solution_status_code = Int(read_certificate_u64(io))
        constraint_count = Int(read_certificate_u64(io))
        scalar_variable_count = Int(read_certificate_u64(io))
        cone_count = Int(read_certificate_u64(io))
        affine_conic_constraint_count =
            Int(read_certificate_u64(io))
        semidefinite_variable_count =
            Int(read_certificate_u64(io))
        scalar_values = read_certificate_float64_vector(io)
        bar_count = Int(read_certificate_u64(io))
        bar_count == semidefinite_variable_count || error(
            "Mosek dual-certificate semidefinite count mismatch",
        )
        bar_dimensions = Int[]
        semidefinite_values = Vector{Vector{Float64}}()
        for _ in 1:bar_count
            push!(bar_dimensions, Int(read_certificate_u64(io)))
            push!(
                semidefinite_values,
                read_certificate_float64_vector(io),
            )
        end
        eof(io) || error(
            "Mosek dual-certificate artifact has trailing bytes",
        )
        length(scalar_values) == scalar_variable_count || error(
            "Mosek dual-certificate scalar count mismatch",
        )
        return (
            problem_status_code=problem_status_code,
            solution_status_code=solution_status_code,
            constraint_count=constraint_count,
            scalar_variable_count=scalar_variable_count,
            cone_count=cone_count,
            affine_conic_constraint_count=
                affine_conic_constraint_count,
            semidefinite_variable_count=
                semidefinite_variable_count,
            scalar_values=scalar_values,
            bar_dimensions=bar_dimensions,
            semidefinite_values=semidefinite_values,
        )
    end
end

function dual_certificate_replay_usage()
    println(
        "Usage: julia replay_mosek_dual_certificate_artifact.jl " *
        "--task TASK.task --certificate CERTIFICATE.bin " *
        "--output REPORT.toml --expected-task-sha256 HEX " *
        "--expected-certificate-sha256 HEX [--tolerance 1e-7]",
    )
end

function parse_dual_certificate_replay_args(arguments::Vector{String})
    values = Dict{String,String}()
    index = 1
    while index <= length(arguments)
        argument = arguments[index]
        if argument in ("-h", "--help")
            dual_certificate_replay_usage()
            return nothing
        elseif argument in (
            "--task",
            "--certificate",
            "--output",
            "--expected-task-sha256",
            "--expected-certificate-sha256",
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
        "--certificate",
        "--output",
        "--expected-task-sha256",
        "--expected-certificate-sha256",
    )
        haskey(values, required) ||
            throw(ArgumentError("$required is required"))
    end
    tolerance = parse(Float64, get(values, "--tolerance", "1e-7"))
    isfinite(tolerance) && tolerance > 0.0 ||
        throw(ArgumentError("--tolerance must be finite and positive"))
    return (
        task=values["--task"],
        certificate=values["--certificate"],
        output=values["--output"],
        expected_task_sha256=
            lowercase(values["--expected-task-sha256"]),
        expected_certificate_sha256=
            lowercase(values["--expected-certificate-sha256"]),
        tolerance=tolerance,
    )
end

function mosek_dual_certificate_replay_report(
    task_path::AbstractString,
    certificate_path::AbstractString;
    expected_task_sha256::AbstractString,
    expected_certificate_sha256::AbstractString,
    tolerance::Float64=1e-7,
)
    task_sha256 = certificate_file_sha256(task_path)
    certificate_sha256 =
        certificate_file_sha256(certificate_path)
    task_sha256 == lowercase(expected_task_sha256) ||
        error("Mosek dual-certificate task SHA-256 mismatch")
    certificate_sha256 == lowercase(expected_certificate_sha256) ||
        error("Mosek dual-certificate SHA-256 mismatch")
    certificate = read_mosek_dual_certificate(certificate_path)

    audit = Mosek.maketask() do task
        Mosek.readdata(task, task_path)
        numcon = Int(Mosek.getnumcon(task))
        numvar = Int(Mosek.getnumvar(task))
        numcone = Int(Mosek.getnumcone(task))
        numacc = Int(Mosek.getnumacc(task))
        numbarvar = Int(Mosek.getnumbarvar(task))
        (numcon, numvar, numcone, numacc, numbarvar) == (
            certificate.constraint_count,
            certificate.scalar_variable_count,
            certificate.cone_count,
            certificate.affine_conic_constraint_count,
            certificate.semidefinite_variable_count,
        ) || error("Mosek task and dual-certificate dimensions differ")
        for index in 1:numbarvar
            Int(Mosek.getdimbarvarj(task, index)) ==
                certificate.bar_dimensions[index] || error(
                "Mosek dual-certificate matrix dimension mismatch",
            )
        end

        Mosek.putsolutionnew(
            task,
            Mosek.MSK_SOL_ITR,
            fill(Mosek.MSK_SK_UNK, numcon),
            fill(Mosek.MSK_SK_UNK, numvar),
            fill(Mosek.MSK_SK_UNK, numcone),
            nothing,
            certificate.scalar_values,
            nothing,
            nothing,
            nothing,
            nothing,
            nothing,
            nothing,
            nothing,
        )
        for index in 1:numbarvar
            Mosek.putbarxj(
                task,
                Mosek.MSK_SOL_ITR,
                index,
                certificate.semidefinite_values[index],
            )
        end
        Mosek.updatesolutioninfo(task, Mosek.MSK_SOL_ITR)
        information =
            Mosek.getsolutioninfonew(task, Mosek.MSK_SOL_ITR)
        primal_norms =
            Mosek.getprimalsolutionnorms(task, Mosek.MSK_SOL_ITR)
        primal_violations = Float64[information[2:8]...]
        finite = all(isfinite, information[1:8]) &&
                 all(isfinite, primal_norms)
        maximum_primal_violation = maximum(abs, primal_violations)

        bound_keys, lower_bounds, upper_bounds =
            Mosek.getconboundslice(task, 1, numcon + 1)
        identity_rhs_count = count(
            index ->
                bound_keys[index] == Mosek.MSK_BK_FX &&
                lower_bounds[index] == -1.0 &&
                upper_bounds[index] == -1.0,
            eachindex(bound_keys),
        )
        zero_rhs_count = count(
            index ->
                bound_keys[index] == Mosek.MSK_BK_FX &&
                lower_bounds[index] == 0.0 &&
                upper_bounds[index] == 0.0,
            eachindex(bound_keys),
        )
        certificate_system_passed =
            identity_rhs_count == 1 && zero_rhs_count == numcon - 1
        source_status_passed =
            certificate.problem_status_code ==
                Mosek.MSK_PRO_STA_PRIM_AND_DUAL_FEAS.value &&
            certificate.solution_status_code ==
                Mosek.MSK_SOL_STA_OPTIMAL.value
        residual_passed = finite &&
                          maximum_primal_violation <= tolerance
        passed = source_status_passed &&
                 certificate_system_passed &&
                 residual_passed
        return Dict(
            "source_problem_status_code" =>
                certificate.problem_status_code,
            "source_solution_status_code" =>
                certificate.solution_status_code,
            "source_status_passed" => source_status_passed,
            "certificate_system_passed" =>
                certificate_system_passed,
            "identity_rhs_count" => identity_rhs_count,
            "zero_rhs_count" => zero_rhs_count,
            "finite" => finite,
            "primal_objective" => Float64(information[1]),
            "primal_norms" => Float64[primal_norms...],
            "primal_violations" => primal_violations,
            "maximum_primal_violation" =>
                maximum_primal_violation,
            "residual_passed" => residual_passed,
            "passed" => passed,
            "constraint_count" => numcon,
            "scalar_variable_count" => numvar,
            "semidefinite_variable_count" => numbarvar,
            "semidefinite_packed_value_count" =>
                sum(length, certificate.semidefinite_values; init=0),
        )
    end
    return Dict(
        "schema_version" =>
            MOSEK_DUAL_CERTIFICATE_REPLAY_SCHEMA,
        "replay_script_sha256" =>
            certificate_file_sha256(@__FILE__),
        "created_at_utc" => Dates.format(
            now(UTC),
            dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        ),
        "classification" => audit["passed"] ?
            "mosek_dual_certificate_replayed_float" :
            "mosek_dual_certificate_replay_failed",
        "tolerance" => tolerance,
        "task" => Dict(
            "path" => abspath(task_path),
            "bytes" => filesize(task_path),
            "sha256" => task_sha256,
        ),
        "certificate" => Dict(
            "path" => abspath(certificate_path),
            "bytes" => filesize(certificate_path),
            "sha256" => certificate_sha256,
        ),
        "audit" => audit,
        "scope" =>
            "fresh-task floating primal certificate replay; not exact arithmetic",
    )
end

function replay_mosek_dual_certificate_main(
    arguments::Vector{String}=ARGS,
)
    options = parse_dual_certificate_replay_args(arguments)
    isnothing(options) && return
    ispath(options.output) &&
        error("refusing existing replay report: $(options.output)")
    report = mosek_dual_certificate_replay_report(
        options.task,
        options.certificate;
        expected_task_sha256=options.expected_task_sha256,
        expected_certificate_sha256=
            options.expected_certificate_sha256,
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
        "[mosek-dual-certificate-replay] ",
        report["classification"],
        " maximum_primal_violation=",
        report["audit"]["maximum_primal_violation"],
    )
    flush(stdout)
    report["audit"]["passed"] ||
        error("Mosek dual-certificate replay failed")
end

if abspath(PROGRAM_FILE) == @__FILE__
    replay_mosek_dual_certificate_main()
end
