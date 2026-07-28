#!/usr/bin/env julia

using Dates
using LinearAlgebra
using SHA
using Sockets
using TOML
using JuMP
using Mosek
using MosekTools

const RESULT_SCHEMA = "shastry-sutherland-reduced-solve-result-v1"
const RUNMETA_SCHEMA = "shastry-sutherland-reduced-mof-runmeta-v1"
const REDUCTION_SCHEMA = "primal-gap-exact-v4-reduction-v1"
const SOURCE_COMMIT = "5e84422586c8de8acb58699a1102a28353291562"
const SOURCE_TREE = "aa8cd5a915b1f3bc2c7f6811022aab209533a2a2"

const EXPECTED_INPUTS = Dict(
    "0//1" => (
        model_sha256=
            "38bf66fad11dce926a8da099199a05f4e0b1929a606a947b68bec331f1c3995d",
        runmeta_sha256=
            "b0d5b6b4c36ceda645fb6d891120e04001512dbf7aaea5cbfbfa0bfbdcecda8f",
        output_relative=
            "tracks/polyopt/solutions/sdp-gap-seekers/results/" *
            "ss-reduced-g0p8-gamma0-local-baseline-20260728",
    ),
    "1//2" => (
        model_sha256=
            "ad5d2db33a3f8d89abbb625aec5089075815659649444103d403146183bd8011",
        runmeta_sha256=
            "9b65e31cb16d52b118e5566e07231f62e936df68957801f312dba447494422bb",
        output_relative=
            "tracks/polyopt/solutions/sdp-gap-seekers/results/" *
            "ss-reduced-g0p8-gamma0p5-local-preflight-20260728",
    ),
)

const EXPECTED_PSD_DIMENSIONS = Dict(
    "positive_centered_rx0_ry0_psd" => 108,
    "positive_centered_rx0_ry1_psd" => 81,
    "positive_centered_rx1_ry0_psd" => 81,
    "positive_centered_rx1_ry1_psd" => 81,
    "positive_scalar_rx0_ry0_psd" => 109,
    "positive_scalar_rx0_ry1_psd" => 81,
    "positive_scalar_rx1_ry0_psd" => 81,
    "positive_scalar_rx1_ry1_psd" => 81,
    "gap_gap_active_rx0_ry1_psd" => 1,
    "gap_gap_active_rx1_ry0_psd" => 1,
    "gap_gap_active_rx1_ry1_psd" => 1,
)

const EXPECTED_SOURCE_FILES = Set([
    "tracks/polyopt/solutions/sdp-gap-seekers/" *
    "scripts/build_shastry_sutherland_reduced_mof.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/ExactSymmetryReduction.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/GenericGapModel.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapAssembly.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapJuMP.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapSymbolics.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/ReducedPrimalGapAssembly.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/ReducedPrimalGapJuMP.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/SquareJ1J2Prototype.jl",
])

function progress(message::AbstractString)
    println("[ss-reduced-solve] ", message)
    flush(stdout)
end

function usage()
    println(
        """
        Usage:
          julia --project=<locked-env> solve_shastry_sutherland_reduced_mof.jl \\
            --model <model.mof.json> \\
            --runmeta <runmeta.toml> \\
            --checksums <SHA256SUMS> \\
            --expected-gamma <0|1/2> \\
            --repository-root <checkout> \\
            --output <result.toml> \\
            [--time-limit-seconds 7200] [--threads 16] \\
            [--audit-tolerance 1e-7]

        Fail-closed runner for the two immutable exact-reduced
        Shastry--Sutherland MOF inputs. It validates the artifact pair,
        source hashes, fixed physical setup, exact reduction inventory, and
        the reloaded MOF structure before attaching Mosek.
        """,
    )
end

function parse_positive_int(text::String, flag::String)
    value = tryparse(Int, text)
    isnothing(value) && throw(ArgumentError("$flag requires an integer"))
    value > 0 || throw(ArgumentError("$flag must be positive"))
    return value
end

function parse_positive_float(text::String, flag::String)
    value = tryparse(Float64, text)
    isnothing(value) && throw(ArgumentError("$flag requires a number"))
    isfinite(value) && value > 0 ||
        throw(ArgumentError("$flag must be finite and positive"))
    return value
end

function canonical_gamma(text::String)
    text in ("0", "0/1", "0//1") && return "0//1"
    text in ("1/2", "1//2") && return "1//2"
    throw(ArgumentError("--expected-gamma must be 0 or 1/2"))
end

function parse_args(arguments::Vector{String})
    values = Dict{String,String}()
    value_flags = (
        "--model",
        "--runmeta",
        "--checksums",
        "--expected-gamma",
        "--repository-root",
        "--output",
        "--time-limit-seconds",
        "--threads",
        "--audit-tolerance",
    )
    index = 1
    while index <= length(arguments)
        argument = arguments[index]
        if argument in ("-h", "--help")
            usage()
            return nothing
        elseif argument in value_flags
            index < length(arguments) ||
                throw(ArgumentError("$argument requires a value"))
            haskey(values, argument) &&
                throw(ArgumentError("$argument was supplied more than once"))
            values[argument] = arguments[index + 1]
            index += 2
        else
            throw(ArgumentError("unknown argument: $argument"))
        end
    end
    required = (
        "--model",
        "--runmeta",
        "--checksums",
        "--expected-gamma",
        "--repository-root",
        "--output",
    )
    for flag in required
        haskey(values, flag) || throw(ArgumentError("$flag is required"))
    end
    return (
        model=abspath(values["--model"]),
        runmeta=abspath(values["--runmeta"]),
        checksums=abspath(values["--checksums"]),
        expected_gamma=canonical_gamma(values["--expected-gamma"]),
        repository_root=realpath(values["--repository-root"]),
        output=abspath(values["--output"]),
        time_limit_seconds=parse_positive_int(
            get(values, "--time-limit-seconds", "7200"),
            "--time-limit-seconds",
        ),
        threads=parse_positive_int(
            get(values, "--threads", "16"),
            "--threads",
        ),
        audit_tolerance=parse_positive_float(
            get(values, "--audit-tolerance", "1e-7"),
            "--audit-tolerance",
        ),
    )
end

file_sha256(path::AbstractString) = bytes2hex(open(sha256, path))

function peak_rss_kib()
    isfile("/proc/self/status") || return -1
    for line in eachline("/proc/self/status")
        startswith(line, "VmHWM:") || continue
        fields = split(line)
        return length(fields) >= 2 ? parse(Int, fields[2]) : -1
    end
    return -1
end

function git_output(repository_root::String, arguments...)
    return readchomp(Cmd(`git $(arguments)`; dir=repository_root))
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
        value isa Real ||
            return Dict("available" => false, "reason" => "not_real")
        isfinite(value) ||
            return Dict("available" => false, "reason" => "not_finite")
        return Dict("available" => true, "value" => Float64(value))
    catch exception
        return Dict(
            "available" => false,
            "reason" => string(typeof(exception)),
        )
    end
end

function require_equal(actual, expected, label::String)
    actual == expected ||
        error("$label mismatch: expected $(repr(expected)), got $(repr(actual))")
    return actual
end

function require_keys(table, expected, label::String)
    actual = Set(String.(keys(table)))
    actual == expected ||
        error(
            "$label key mismatch: expected $(sort!(collect(expected))), " *
            "got $(sort!(collect(actual)))",
        )
    return
end

function read_checksum_manifest(path::String)
    isfile(path) || throw(ArgumentError("checksum manifest missing: $path"))
    entries = Dict{String,String}()
    for (line_number, raw_line) in enumerate(eachline(path))
        line = strip(raw_line)
        isempty(line) && continue
        matched = match(r"^([0-9a-f]{64})  ([^/]+)$", line)
        isnothing(matched) &&
            error("malformed SHA256SUMS line $line_number")
        digest, filename = matched.captures
        haskey(entries, filename) &&
            error("duplicate SHA256SUMS entry for $filename")
        entries[filename] = digest
    end
    require_keys(
        entries,
        Set(["model.mof.json", "runmeta.toml"]),
        "SHA256SUMS",
    )
    return entries
end

function require_rational_metadata(
    table,
    numerator::String,
    denominator::String,
    canonical::String,
    float64::Float64,
    label::String,
)
    require_keys(
        table,
        Set(["numerator", "denominator", "canonical", "float64"]),
        label,
    )
    require_equal(table["numerator"], numerator, "$label numerator")
    require_equal(table["denominator"], denominator, "$label denominator")
    require_equal(table["canonical"], canonical, "$label canonical")
    require_equal(table["float64"], float64, "$label Float64")
    return
end

function contained_source_path(repository_root::String, relative::String)
    isabspath(relative) &&
        error("runmeta source path is absolute: $relative")
    candidate = realpath(joinpath(repository_root, relative))
    separator = string(Base.Filesystem.path_separator)
    (
        candidate == repository_root ||
        startswith(candidate, repository_root * separator)
    ) || error("runmeta source path escapes repository: $relative")
    return candidate
end

function validate_input_files(
    model_path::String,
    runmeta_path::String,
    checksums_path::String,
    expected_gamma::String,
)
    isfile(model_path) || throw(ArgumentError("MOF missing: $model_path"))
    isfile(runmeta_path) ||
        throw(ArgumentError("runmeta missing: $runmeta_path"))
    basename(model_path) == "model.mof.json" ||
        error("MOF basename must be model.mof.json")
    basename(runmeta_path) == "runmeta.toml" ||
        error("runmeta basename must be runmeta.toml")

    manifest = read_checksum_manifest(checksums_path)
    actual_model_sha256 = file_sha256(model_path)
    actual_runmeta_sha256 = file_sha256(runmeta_path)
    require_equal(
        actual_model_sha256,
        manifest["model.mof.json"],
        "MOF SHA-256 versus SHA256SUMS",
    )
    require_equal(
        actual_runmeta_sha256,
        manifest["runmeta.toml"],
        "runmeta SHA-256 versus SHA256SUMS",
    )

    expected = EXPECTED_INPUTS[expected_gamma]
    require_equal(
        actual_model_sha256,
        expected.model_sha256,
        "MOF SHA-256 versus immutable allowlist",
    )
    require_equal(
        actual_runmeta_sha256,
        expected.runmeta_sha256,
        "runmeta SHA-256 versus immutable allowlist",
    )
    return (
        model_sha256=actual_model_sha256,
        runmeta_sha256=actual_runmeta_sha256,
        checksums_sha256=file_sha256(checksums_path),
        expected=expected,
    )
end

function validate_runmeta(
    runmeta,
    input_files,
    expected_gamma::String,
    repository_root::String,
)
    require_equal(
        runmeta["schema_version"],
        RUNMETA_SCHEMA,
        "runmeta schema",
    )
    require_equal(
        runmeta["claim_level"],
        "solver_free_exact_equivalent_reduction",
        "input claim level",
    )
    require_equal(runmeta["solver_invoked"], false, "solver_invoked")
    require_equal(runmeta["optimizer_attached"], false, "optimizer_attached")
    require_equal(
        runmeta["output_relative"],
        input_files.expected.output_relative,
        "original output path",
    )
    require_equal(
        runmeta["mof"]["filename"],
        "model.mof.json",
        "runmeta MOF filename",
    )
    require_equal(
        runmeta["mof"]["sha256"],
        input_files.model_sha256,
        "runmeta MOF SHA-256",
    )

    setup = runmeta["setup"]
    require_equal(setup["model"], "shastry-sutherland", "model")
    require_equal(setup["patch_level"], 1, "patch level")
    require_equal(setup["degree_d"], 2, "polynomial degree")
    require_equal(setup["state_class"], "unrestricted", "state class")
    require_equal(
        setup["physical_boundary_condition"],
        "none-local-consistency-window",
        "physical boundary condition",
    )
    require_rational_metadata(
        setup["g_square_over_dimer"],
        "4",
        "5",
        "4//5",
        0.8,
        "square-over-dimer coupling",
    )
    if expected_gamma == "0//1"
        require_rational_metadata(
            setup["gamma"],
            "0",
            "1",
            "0//1",
            0.0,
            "gamma",
        )
    else
        require_rational_metadata(
            setup["gamma"],
            "1",
            "2",
            "1//2",
            0.5,
            "gamma",
        )
    end

    source_assembly = runmeta["source_assembly"]
    require_equal(
        source_assembly["moment_count"],
        74_602,
        "source moment count",
    )
    require_equal(
        source_assembly["positive_dimension"],
        703,
        "source positive dimension",
    )
    require_equal(
        source_assembly["gap_dimension"],
        7,
        "source gap dimension",
    )
    require_equal(
        source_assembly["stationarity_equality_count"],
        3,
        "source equality count",
    )

    reduction = runmeta["exact_reduction"]
    require_equal(reduction["schema"], REDUCTION_SCHEMA, "reduction schema")
    require_equal(reduction["moment_count"], 19_108, "reduced moment count")
    require_equal(
        reduction["eliminated_moment_count"],
        55_494,
        "eliminated moment count",
    )
    require_equal(
        reduction["positive_block_dimensions"],
        [108, 81, 81, 81, 109, 81, 81, 81],
        "positive block dimensions",
    )
    require_equal(
        reduction["gap_block_dimensions"],
        [1, 1, 1],
        "gap block dimensions",
    )
    require_equal(reduction["equality_count"], 3, "reduced equality count")
    require_equal(
        reduction["truth_checks_exhaustive"],
        true,
        "exhaustive truth-check flag",
    )

    replay = runmeta["replay"]
    require_equal(replay["passed"], true, "builder replay gate")
    require_equal(replay["variable_count"], 19_108, "replay variable count")
    require_equal(
        replay["constraint_count_excluding_variable_sets"],
        15,
        "replay constraint count",
    )
    replay_dimensions = Dict(
        String(name) => Int(dimension)
        for (name, dimension) in replay["psd_block_dimensions"]
    )
    require_equal(
        replay_dimensions,
        EXPECTED_PSD_DIMENSIONS,
        "replay PSD inventory",
    )

    source = runmeta["source"]
    require_equal(source["git_commit"], SOURCE_COMMIT, "source commit")
    require_equal(source["git_tree"], SOURCE_TREE, "source tree")
    require_equal(
        source["git_branch"],
        "explore/shastry-sutherland-exact-reduction",
        "source branch",
    )
    require_equal(
        source["dirty_paths_at_build"],
        String[],
        "source dirty paths",
    )
    files_sha256 = source["files_sha256"]
    require_keys(files_sha256, EXPECTED_SOURCE_FILES, "source hash inventory")
    verified_source_hashes = Dict{String,String}()
    for relative in sort!(collect(EXPECTED_SOURCE_FILES))
        path = contained_source_path(repository_root, relative)
        isfile(path) || error("recorded source file is missing: $relative")
        actual = file_sha256(path)
        require_equal(
            actual,
            files_sha256[relative],
            "source SHA-256 for $relative",
        )
        verified_source_hashes[relative] = actual
    end

    return Dict(
        "passed" => true,
        "schema" => RUNMETA_SCHEMA,
        "source_commit" => source["git_commit"],
        "source_tree" => source["git_tree"],
        "source_file_sha256" => verified_source_hashes,
        "source_problem_sha256" => source_assembly["problem_sha256"],
        "source_assembly_sha256" => source_assembly["assembly_sha256"],
        "reduced_assembly_sha256" => reduction["assembly_sha256"],
        "coefficient_map_sha256" => reduction["coefficient_map_sha256"],
    )
end

function validate_reloaded_model(model::JuMP.Model)
    require_equal(JuMP.num_variables(model), 19_108, "MOF variable count")
    require_equal(
        JuMP.num_constraints(
            model;
            count_variable_in_set_constraints=false,
        ),
        15,
        "MOF constraint count excluding variable sets",
    )
    require_equal(
        JuMP.objective_sense(model),
        JuMP.MOI.FEASIBILITY_SENSE,
        "MOF objective sense",
    )

    normalization = JuMP.constraint_by_name(model, "normalization")
    isnothing(normalization) && error("MOF lost normalization")
    normalization_object = JuMP.constraint_object(normalization)
    normalization_object.set isa JuMP.MOI.EqualTo{Float64} ||
        error("normalization changed set type")

    for index in 1:3
        reference = JuMP.constraint_by_name(
            model,
            "reduced_equality[$index]",
        )
        isnothing(reference) && error("MOF lost reduced equality $index")
        JuMP.constraint_object(reference).set isa JuMP.MOI.EqualTo{Float64} ||
            error("reduced equality $index changed set type")
    end

    psd_constraint_count = 0
    for (function_type, set_type) in JuMP.list_of_constraint_types(model)
        set_type <: JuMP.MOI.HermitianPositiveSemidefiniteConeTriangle ||
            continue
        psd_constraint_count += length(
            JuMP.all_constraints(model, function_type, set_type),
        )
    end
    require_equal(psd_constraint_count, 11, "MOF PSD constraint count")

    dimensions = Dict{String,Int}()
    for (name, expected_dimension) in EXPECTED_PSD_DIMENSIONS
        reference = JuMP.constraint_by_name(model, name)
        isnothing(reference) && error("MOF lost PSD block $name")
        object = JuMP.constraint_object(reference)
        object.set isa JuMP.MOI.HermitianPositiveSemidefiniteConeTriangle ||
            error("$name changed cone type")
        require_equal(
            object.set.side_dimension,
            expected_dimension,
            "$name side dimension",
        )
        reference.shape isa JuMP.HermitianMatrixShape ||
            error("$name lost Hermitian matrix shape")
        require_equal(
            reference.shape.side_dimension,
            expected_dimension,
            "$name shape dimension",
        )
        dimensions[name] = expected_dimension
    end
    return Dict(
        "passed" => true,
        "variable_count" => JuMP.num_variables(model),
        "constraint_count_excluding_variable_sets" => 15,
        "psd_constraint_count" => psd_constraint_count,
        "psd_block_dimensions" => dimensions,
        "max_psd_side_dimension" => maximum(values(dimensions)),
    )
end

function affine_residual(reference::JuMP.ConstraintRef)
    object = JuMP.constraint_object(reference)
    object.set isa JuMP.MOI.EqualTo{Float64} ||
        error("affine residual requested for non-equality constraint")
    function_value = Float64(JuMP.value(reference))
    target = Float64(object.set.value)
    residual = abs(function_value - target)
    expression = JuMP.jump_function(object)
    scale = max(1.0, abs(target))
    if expression isa JuMP.GenericAffExpr
        term_magnitude = abs(Float64(expression.constant))
        for (variable, coefficient) in expression.terms
            term_magnitude +=
                abs(Float64(coefficient) * Float64(JuMP.value(variable)))
        end
        scale = max(scale, term_magnitude)
    else
        scale = max(scale, abs(function_value))
    end
    return Dict(
        "value" => function_value,
        "target" => target,
        "absolute_residual" => residual,
        "scale" => scale,
        "normalized_residual" => residual / scale,
    )
end

function solution_diagnostics(
    model::JuMP.Model,
    audit_tolerance::Float64,
)
    normalization = affine_residual(
        JuMP.constraint_by_name(model, "normalization"),
    )
    equalities = Dict{String,Any}()
    maximum_absolute_equality_residual = 0.0
    maximum_normalized_equality_residual = 0.0
    for index in 1:3
        name = "reduced_equality[$index]"
        diagnostic = affine_residual(
            JuMP.constraint_by_name(model, name),
        )
        equalities[name] = diagnostic
        maximum_absolute_equality_residual = max(
            maximum_absolute_equality_residual,
            diagnostic["absolute_residual"],
        )
        maximum_normalized_equality_residual = max(
            maximum_normalized_equality_residual,
            diagnostic["normalized_residual"],
        )
    end

    blocks = Dict{String,Any}()
    worst_psd_violation = 0.0
    worst_normalized_psd_violation = 0.0
    for name in sort!(collect(keys(EXPECTED_PSD_DIMENSIONS)))
        reference = JuMP.constraint_by_name(model, name)
        reconstructed = Matrix{ComplexF64}(JuMP.value(reference))
        dimension = EXPECTED_PSD_DIMENSIONS[name]
        size(reconstructed) == (dimension, dimension) ||
            error("$name reconstructed with the wrong matrix size")
        hermiticity_residual = maximum(
            abs,
            reconstructed - reconstructed',
        )
        eigenvalues = eigvals(Hermitian(reconstructed))
        minimum_eigenvalue = Float64(minimum(eigenvalues))
        spectral_scale = max(1.0, maximum(abs, eigenvalues))
        violation = max(0.0, -minimum_eigenvalue)
        normalized_violation = violation / spectral_scale
        worst_psd_violation = max(worst_psd_violation, violation)
        worst_normalized_psd_violation = max(
            worst_normalized_psd_violation,
            normalized_violation,
        )
        blocks[name] = Dict(
            "dimension" => dimension,
            "minimum_eigenvalue" => minimum_eigenvalue,
            "maximum_absolute_eigenvalue" =>
                Float64(maximum(abs, eigenvalues)),
            "hermiticity_residual" => Float64(hermiticity_residual),
            "psd_violation" => violation,
            "spectral_scale" => spectral_scale,
            "normalized_psd_violation" => normalized_violation,
        )
    end

    passed =
        normalization["normalized_residual"] <= audit_tolerance &&
        maximum_normalized_equality_residual <= audit_tolerance &&
        worst_normalized_psd_violation <= audit_tolerance &&
        all(
            block["hermiticity_residual"] <= audit_tolerance
            for block in values(blocks)
        )
    return Dict(
        "available" => true,
        "passed" => passed,
        "audit_tolerance" => audit_tolerance,
        "normalization" => normalization,
        "affine_equalities" => equalities,
        "maximum_absolute_affine_equality_residual" =>
            maximum_absolute_equality_residual,
        "maximum_normalized_affine_equality_residual" =>
            maximum_normalized_equality_residual,
        "psd_blocks" => blocks,
        "worst_psd_violation" => worst_psd_violation,
        "worst_normalized_psd_violation" =>
            worst_normalized_psd_violation,
    )
end

function classify_result(termination, primal, dual, diagnostics)
    feasible_termination = termination in (
        JuMP.MOI.OPTIMAL,
        JuMP.MOI.LOCALLY_SOLVED,
        JuMP.MOI.ALMOST_OPTIMAL,
    )
    feasible_primal = primal in (
        JuMP.MOI.FEASIBLE_POINT,
        JuMP.MOI.NEARLY_FEASIBLE_POINT,
    )
    if feasible_termination && feasible_primal
        return diagnostics["passed"] ?
               "feasible_residual_checked_float" :
               "feasible_status_failed_residual_audit"
    end
    if termination in (
        JuMP.MOI.INFEASIBLE,
        JuMP.MOI.ALMOST_INFEASIBLE,
        JuMP.MOI.INFEASIBLE_OR_UNBOUNDED,
    ) || primal in (
        JuMP.MOI.INFEASIBILITY_CERTIFICATE,
        JuMP.MOI.NEARLY_INFEASIBILITY_CERTIFICATE,
    ) || dual in (
        JuMP.MOI.INFEASIBILITY_CERTIFICATE,
        JuMP.MOI.NEARLY_INFEASIBILITY_CERTIFICATE,
    )
        return "infeasibility_candidate_requires_independent_ray_replay"
    end
    return "unknown"
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

function main(arguments::Vector{String}=ARGS)
    options = parse_args(arguments)
    isnothing(options) && return 0
    started_at = now(UTC)
    wall_start = time()
    result = Dict(
        "schema_version" => RESULT_SCHEMA,
        "started_at_utc" => Dates.format(
            started_at,
            dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        ),
        "completed" => false,
        "classification" => "unknown",
        "expected_gamma" => options.expected_gamma,
        "model_path" => options.model,
        "runmeta_path" => options.runmeta,
        "checksums_path" => options.checksums,
        "audit_tolerance" => options.audit_tolerance,
        "time_limit_seconds" => options.time_limit_seconds,
        "threads" => options.threads,
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
            "slurm_mem_per_node" =>
                get(ENV, "SLURM_MEM_PER_NODE", "unavailable"),
            "hostname" => gethostname(),
        ),
    )

    exit_code = 1
    try
        progress("validating immutable MOF, runmeta, and SHA256SUMS")
        input_files = validate_input_files(
            options.model,
            options.runmeta,
            options.checksums,
            options.expected_gamma,
        )
        result["input_hashes"] = Dict(
            "model_mof_sha256" => input_files.model_sha256,
            "runmeta_sha256" => input_files.runmeta_sha256,
            "checksums_sha256" => input_files.checksums_sha256,
        )

        progress("validating ratified setup, reduction inventory, and source hashes")
        runmeta = TOML.parsefile(options.runmeta)
        result["runmeta_validation"] = validate_runmeta(
            runmeta,
            input_files,
            options.expected_gamma,
            options.repository_root,
        )
        result["source_commit"] = runmeta["source"]["git_commit"]
        result["runner_commit"] = git_output(
            options.repository_root,
            "rev-parse",
            "HEAD",
        )
        result["runner_tree"] = git_output(
            options.repository_root,
            "rev-parse",
            "HEAD^{tree}",
        )
        result["runner_source_sha256"] = file_sha256(abspath(@__FILE__))

        progress("reloading MOF and validating exact named cone structure")
        reload_start = time()
        model = JuMP.read_from_file(options.model)
        result["mof_reload_wall_seconds"] = time() - reload_start
        result["model_validation"] = validate_reloaded_model(model)

        progress(
            "preflight passed; attaching Mosek with " *
            "threads=$(options.threads), " *
            "time_limit=$(options.time_limit_seconds)s",
        )
        JuMP.set_optimizer(model, MosekTools.Optimizer)
        JuMP.set_time_limit_sec(
            model,
            Float64(options.time_limit_seconds),
        )
        JuMP.set_optimizer_attribute(
            model,
            Mosek.MSK_IPAR_NUM_THREADS,
            options.threads,
        )

        progress("optimize! started")
        solve_start = time()
        JuMP.optimize!(model)
        solve_wall_seconds = time() - solve_start
        progress(
            "optimize! returned after " *
            "$(round(solve_wall_seconds; digits=3))s",
        )

        termination = JuMP.termination_status(model)
        primal = JuMP.primal_status(model)
        dual = JuMP.dual_status(model)
        statuses = Dict(
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
        result["statuses"] = statuses
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
            "relative_gap" => safe_number(() -> JuMP.relative_gap(model)),
        )

        diagnostics = if JuMP.has_values(model)
            progress("reconstructing all 11 Hermitian PSD blocks")
            solution_diagnostics(model, options.audit_tolerance)
        else
            Dict(
                "available" => false,
                "reason" => "solver_returned_no_primal_values",
            )
        end
        result["solution_diagnostics"] = diagnostics
        result["classification"] = classify_result(
            termination,
            primal,
            dual,
            diagnostics,
        )
        result["completed"] = true
        exit_code = 0
    catch exception
        result["classification"] = "runner_failure"
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
