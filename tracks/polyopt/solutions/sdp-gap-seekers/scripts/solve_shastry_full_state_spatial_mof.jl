#!/usr/bin/env julia

module BaselineRunnerUtilities
include(joinpath(@__DIR__, "solve_shastry_sutherland_reduced_mof.jl"))
end

using Dates
using LinearAlgebra
using Sockets
using TOML
using JuMP
using Mosek
using MosekTools

const B = BaselineRunnerUtilities
const RESULT_SCHEMA = "shastry-l1d2-full-state-solve-result-v2"
const RUNMETA_SCHEMA = "shastry-l1d2-full-state-spatial-mof-v1"
const SPIN_SPATIAL_RUNMETA_SCHEMA =
    "shastry-l1d2-full-state-spin-spatial-mof-v1"
const SPIN_ISOTYPIC_RUNMETA_SCHEMA =
    "shastry-l1d2-full-state-spin-isotypic-mof-v1"

function progress(message::AbstractString)
    println("[ss-full-state-spatial-solve] ", message)
    flush(stdout)
end

function requested_solve_form()
    label = lowercase(get(ENV, "SS_MOSEK_SOLVE_FORM", "free"))
    forms = Dict(
        "free" => Mosek.MSK_SOLVE_FREE,
        "primal" => Mosek.MSK_SOLVE_PRIMAL,
        "dual" => Mosek.MSK_SOLVE_DUAL,
    )
    haskey(forms, label) ||
        throw(
            ArgumentError(
                "SS_MOSEK_SOLVE_FORM must be free, primal, or dual",
            ),
        )
    return (label=label, value=forms[label])
end

function requested_log_level()
    text = get(ENV, "SS_MOSEK_LOG_LEVEL", "1")
    value = tryparse(Int, text)
    isnothing(value) &&
        throw(ArgumentError("SS_MOSEK_LOG_LEVEL must be an integer"))
    0 <= value <= 10 ||
        throw(ArgumentError("SS_MOSEK_LOG_LEVEL must be between 0 and 10"))
    return value
end

function canonical_parts(canonical::AbstractString)
    fields = split(canonical, "//")
    length(fields) == 2 ||
        error("noncanonical rational metadata: $canonical")
    numerator = parse(BigInt, fields[1])
    denominator = parse(BigInt, fields[2])
    denominator > 0 || error("rational denominator must be positive")
    return (
        numerator=string(numerator),
        denominator=string(denominator),
        float64=Float64(numerator / denominator),
    )
end

function validate_input_files(options)
    for path in (options.model, options.runmeta, options.checksums)
        isfile(path) || throw(ArgumentError("input file missing: $path"))
    end
    basename(options.model) == "model.mof.json" ||
        error("MOF basename must be model.mof.json")
    basename(options.runmeta) == "runmeta.toml" ||
        error("runmeta basename must be runmeta.toml")
    basename(options.checksums) == "SHA256SUMS" ||
        error("checksum basename must be SHA256SUMS")
    input_directory = dirname(options.model)
    dirname(options.runmeta) == input_directory &&
        dirname(options.checksums) == input_directory ||
        error("MOF, runmeta, and checksum manifest must share one directory")

    results_root = realpath(joinpath(
        options.repository_root,
        "tracks",
        "polyopt",
        "solutions",
        "sdp-gap-seekers",
        "results",
    ))
    input_real = realpath(input_directory)
    startswith(input_real, results_root * "/") ||
        error("input must stay below the repository results directory")

    manifest = B.read_checksum_manifest(options.checksums)
    model_sha256 = B.file_sha256(options.model)
    runmeta_sha256 = B.file_sha256(options.runmeta)
    B.require_equal(
        model_sha256,
        manifest["model.mof.json"],
        "MOF SHA-256 versus manifest",
    )
    B.require_equal(
        runmeta_sha256,
        manifest["runmeta.toml"],
        "runmeta SHA-256 versus manifest",
    )
    return (
        directory=input_real,
        output_relative=relpath(input_real, options.repository_root),
        model_sha256=model_sha256,
        runmeta_sha256=runmeta_sha256,
        checksums_sha256=B.file_sha256(options.checksums),
    )
end

function validate_runmeta(runmeta, input_files, options)
    runmeta_schema = runmeta["schema_version"]
    runmeta_schema in (
        RUNMETA_SCHEMA,
        SPIN_SPATIAL_RUNMETA_SCHEMA,
        SPIN_ISOTYPIC_RUNMETA_SCHEMA,
    ) ||
        error("unsupported runmeta schema: $runmeta_schema")
    B.require_equal(runmeta["state"], "complete", "runmeta state")
    B.require_equal(runmeta["mode"], "mof", "runmeta mode")
    B.require_equal(
        runmeta["output_relative"],
        input_files.output_relative,
        "runmeta output path",
    )
    B.require_equal(
        runmeta["mof_sha256"],
        input_files.model_sha256,
        "runmeta MOF SHA-256",
    )

    setup = runmeta["setup"]
    B.require_equal(setup["model"], "shastry-sutherland", "model")
    B.require_equal(setup["patch_level"], 1, "patch level")
    B.require_equal(setup["degree_d"], 2, "degree")
    B.require_equal(
        setup["basis"],
        "complete-state-polynomial-v1",
        "basis",
    )
    B.require_equal(
        setup["stationarity"],
        "complete-inner-state-v1",
        "stationarity",
    )
    B.require_equal(setup["state_class"], "unrestricted", "state class")
    B.require_equal(
        setup["physical_boundary_condition"],
        "none-local-consistency-window",
        "boundary convention",
    )
    B.require_rational_metadata(
        setup["g_square_over_dimer"],
        "4",
        "5",
        "4//5",
        0.8,
        "coupling",
    )
    gamma_parts = canonical_parts(options.expected_gamma)
    B.require_rational_metadata(
        setup["gamma"],
        gamma_parts.numerator,
        gamma_parts.denominator,
        options.expected_gamma,
        gamma_parts.float64,
        "gamma",
    )

    primal = runmeta["primal"]
    B.require_equal(primal["positive_dimension"], 1_810, "positive basis")
    B.require_equal(primal["gap_dimension"], 7, "gap basis")
    B.require_equal(
        primal["stationarity_equality_count"],
        12,
        "stationarity equalities",
    )

    reduced = runmeta["reduced"]
    B.require_equal(reduced["equality_count"], 0, "reduced equalities")
    if runmeta_schema == SPIN_ISOTYPIC_RUNMETA_SCHEMA
        B.require_equal(reduced["maximum_side"], 135, "maximum PSD side")
        B.require_equal(
            reduced["psd_triangle_entries"],
            75_967,
            "PSD triangle entries",
        )
        B.require_equal(
            sort!(Int.(reduced["positive_block_dimensions"])),
            sort!([
                135, 135, 135, 108, 108, 108,
                90, 90, 90, 72, 72, 72,
                66, 66, 51, 51, 49, 48, 33, 33,
            ]),
            "positive block dimensions",
        )
        B.require_equal(
            sort!(Int.(reduced["gap_block_dimensions"])),
            [1, 1, 1],
            "gap block dimensions",
        )
    else
        B.require_equal(reduced["maximum_side"], 198, "maximum PSD side")
        B.require_equal(
            reduced["psd_triangle_entries"],
            112_387,
            "PSD triangle entries",
        )
        B.require_equal(
            sort!(Int.(reduced["positive_block_dimensions"])),
            sort!([
                198, 153, 135, 108, 135, 108, 135, 108,
                145, 99, 90, 72, 90, 72, 90, 72,
            ]),
            "positive block dimensions",
        )
        B.require_equal(
            sort!(Int.(reduced["gap_block_dimensions"])),
            [1, 1, 1],
            "gap block dimensions",
        )
    end
    if runmeta_schema == RUNMETA_SCHEMA
        B.require_equal(
            reduced["source_moments"],
            72_172,
            "pre-spatial source moments",
        )
        B.require_equal(
            reduced["spatial_moments"],
            37_009,
            "spatial moments",
        )
    elseif runmeta_schema == SPIN_SPATIAL_RUNMETA_SCHEMA
        B.require_equal(
            setup["exact_additional_reduction"],
            "proper-spin-axis-permutations-S3-after-anti-diagonal",
            "spin-spatial reduction label",
        )
        B.require_equal(
            reduced["source_moments"],
            37_009,
            "pre-spin spatial moments",
        )
        quotient_moments = Int(reduced["spin_spatial_moments"])
        eliminated_moments = Int(reduced["eliminated_spin_moments"])
        quotient_moments > 0 ||
            error("spin-spatial quotient must retain at least one moment")
        quotient_moments + eliminated_moments == 37_009 ||
            error("spin-spatial moment accounting is inconsistent")

        truth = runmeta["spin_spatial_truth"]
        for key in (
            "exact",
            "source_covariance_exact",
            "equality_space_invariant",
            "hamiltonian_invariant",
            "row_actions_close",
            "coefficient_covariant",
            "source_equality_space_invariant",
        )
            B.require_equal(truth[key], true, "spin-spatial truth $key")
        end
        B.require_equal(
            truth["source_moments"],
            37_009,
            "truth source moments",
        )
        B.require_equal(
            truth["quotient_moments"],
            quotient_moments,
            "truth quotient moments",
        )
        B.require_equal(
            truth["eliminated_moments"],
            eliminated_moments,
            "truth eliminated moments",
        )
        Int(truth["coefficient_count"]) > 0 ||
            error("spin-spatial truth checked no PSD coefficients")
    else
        B.require_equal(
            setup["exact_additional_reduction"],
            "spin-S3-moment-quotient-and-isotypic-cone-blocking",
            "spin-isotypic reduction label",
        )
        B.require_equal(
            reduced["source_moments"],
            7_231,
            "pre-isotypic source moments",
        )
        quotient_moments = Int(reduced["spin_isotypic_moments"])
        eliminated_moments = Int(reduced["eliminated_unused_moments"])
        quotient_moments > 0 ||
            error("spin-isotypic model must retain at least one moment")
        quotient_moments + eliminated_moments == 7_231 ||
            error("spin-isotypic moment accounting is inconsistent")

        spin_truth = runmeta["spin_spatial_truth"]
        for key in (
            "exact",
            "source_covariance_exact",
            "equality_space_invariant",
            "hamiltonian_invariant",
            "row_actions_close",
            "coefficient_covariant",
            "source_equality_space_invariant",
        )
            B.require_equal(spin_truth[key], true, "spin-spatial truth $key")
        end
        B.require_equal(
            spin_truth["quotient_moments"],
            7_231,
            "spin-spatial quotient moments",
        )

        isotypic_truth = runmeta["spin_isotypic_truth"]
        for key in (
            "exact",
            "trivial_blocks_exact",
        )
            B.require_equal(
                isotypic_truth[key],
                true,
                "spin-isotypic truth $key",
            )
        end
        B.require_equal(
            sort!(Int.(isotypic_truth["retained_block_dimensions"])),
            sort!([
                135, 135, 135, 108, 108, 108,
                90, 90, 90, 72, 72, 72,
                66, 66, 51, 51, 49, 48, 33, 33,
                1, 1, 1,
            ]),
            "spin-isotypic truth block dimensions",
        )
        Int(isotypic_truth["nontrivial_comparison_count"]) > 0 ||
            error("spin-isotypic truth checked no orbit coefficients")
    end

    source = runmeta["source"]
    source_commit = source["git_commit"]
    ancestor_check = Cmd(
        `git merge-base --is-ancestor $source_commit HEAD`;
        dir=options.repository_root,
    )
    success(ancestor_check) ||
        error("builder commit is not an ancestor of the runner checkout")
    verified_hashes = Dict{String,String}()
    for (relative, expected_sha256) in source["files_sha256"]
        path = B.contained_source_path(options.repository_root, relative)
        isfile(path) || error("recorded source file is missing: $relative")
        actual_sha256 = B.file_sha256(path)
        B.require_equal(
            actual_sha256,
            expected_sha256,
            "source SHA-256 for $relative",
        )
        verified_hashes[relative] = actual_sha256
    end
    return Dict(
        "passed" => true,
        "schema" => runmeta_schema,
        "source_commit" => source_commit,
        "source_tree" => source["git_tree"],
        "source_file_sha256" => verified_hashes,
        "primal_assembly_sha256" => primal["assembly_sha256"],
        "reduced_assembly_sha256" => reduced["assembly_sha256"],
        "coefficient_map_sha256" => reduced["coefficient_map_sha256"],
    )
end

function reduced_moment_count(runmeta)
    reduced = runmeta["reduced"]
    schema = runmeta["schema_version"]
    if schema == RUNMETA_SCHEMA
        return Int(reduced["spatial_moments"])
    elseif schema == SPIN_SPATIAL_RUNMETA_SCHEMA
        return Int(reduced["spin_spatial_moments"])
    elseif schema == SPIN_ISOTYPIC_RUNMETA_SCHEMA
        return Int(reduced["spin_isotypic_moments"])
    end
    error("unsupported runmeta schema: $schema")
end

function real_psd_constraints(model::JuMP.Model)
    constraints = JuMP.ConstraintRef[]
    for (function_type, set_type) in JuMP.list_of_constraint_types(model)
        set_type <: JuMP.MOI.HermitianPositiveSemidefiniteConeTriangle &&
            error("MOF unexpectedly contains a Hermitian PSD cone")
        set_type <: JuMP.MOI.PositiveSemidefiniteConeTriangle ||
            continue
        append!(
            constraints,
            JuMP.all_constraints(model, function_type, set_type),
        )
    end
    return constraints
end

function validate_reloaded_model(model::JuMP.Model, runmeta)
    reduced = runmeta["reduced"]
    B.require_equal(
        JuMP.num_variables(model),
        reduced_moment_count(runmeta),
        "MOF variables",
    )
    B.require_equal(
        JuMP.objective_sense(model),
        JuMP.MOI.FEASIBILITY_SENSE,
        "MOF objective sense",
    )
    normalization = JuMP.constraint_by_name(model, "normalization")
    isnothing(normalization) && error("MOF lost normalization")
    JuMP.constraint_object(normalization).set isa
        JuMP.MOI.EqualTo{Float64} ||
        error("normalization changed set type")

    constraints = real_psd_constraints(model)
    names = String[JuMP.name(reference) for reference in constraints]
    all(name -> !isempty(name), names) ||
        error("MOF contains an unnamed PSD block")
    length(unique(names)) == length(names) ||
        error("MOF contains duplicate PSD block names")
    dimensions = Dict(
        JuMP.name(reference) =>
            JuMP.constraint_object(reference).set.side_dimension
        for reference in constraints
    )
    expected_dimensions = Int[
        reduced["positive_block_dimensions"]...,
        reduced["gap_block_dimensions"]...,
    ]
    B.require_equal(
        sort!(collect(values(dimensions))),
        sort!(expected_dimensions),
        "MOF PSD dimensions",
    )
    expected_psd_count =
        length(reduced["positive_block_dimensions"]) +
        length(reduced["gap_block_dimensions"])
    B.require_equal(
        length(constraints),
        expected_psd_count,
        "MOF PSD block count",
    )
    triangle_entries =
        sum(dimension * (dimension + 1) ÷ 2 for dimension in values(dimensions))
    B.require_equal(
        triangle_entries,
        Int(reduced["psd_triangle_entries"]),
        "MOF PSD triangle entries",
    )
    constraint_count = JuMP.num_constraints(
        model;
        count_variable_in_set_constraints=false,
    )
    expected_constraint_count =
        1 + Int(reduced["equality_count"]) + expected_psd_count
    B.require_equal(
        constraint_count,
        expected_constraint_count,
        "MOF constraint count excluding variable sets",
    )
    return Dict(
        "passed" => true,
        "variable_count" => JuMP.num_variables(model),
        "constraint_count_excluding_variable_sets" => constraint_count,
        "psd_constraint_count" => length(constraints),
        "psd_block_dimensions" => dimensions,
        "max_psd_side_dimension" => maximum(values(dimensions)),
        "real_psd_triangle_entries" => triangle_entries,
    )
end

function reconstruct_symmetric_constraint(
    reference::JuMP.ConstraintRef,
    dimension::Int,
)
    raw_value = JuMP.value(reference)
    if raw_value isa Symmetric || raw_value isa AbstractMatrix
        matrix = Matrix{Float64}(raw_value)
        size(matrix) == (dimension, dimension) ||
            error("matrix-shaped cone value has the wrong size")
        return matrix
    end
    raw_value isa AbstractVector ||
        error("unsupported real PSD cone value shape $(typeof(raw_value))")
    expected_length = dimension * (dimension + 1) ÷ 2
    length(raw_value) == expected_length ||
        error(
            "packed real PSD value has length $(length(raw_value)); " *
            "expected $expected_length",
        )
    matrix = zeros(Float64, dimension, dimension)
    index = 0
    for column in 1:dimension
        for row in 1:column
            index += 1
            value = Float64(raw_value[index])
            matrix[row, column] = value
            matrix[column, row] = value
        end
    end
    return matrix
end

function solution_diagnostics(
    model::JuMP.Model,
    audit_tolerance::Float64,
)
    normalization = B.affine_residual(
        JuMP.constraint_by_name(model, "normalization"),
    )
    blocks = Dict{String,Any}()
    worst_psd_violation = 0.0
    worst_normalized_psd_violation = 0.0
    for reference in real_psd_constraints(model)
        name = JuMP.name(reference)
        dimension =
            JuMP.constraint_object(reference).set.side_dimension
        reconstructed =
            reconstruct_symmetric_constraint(reference, dimension)
        symmetry_residual = maximum(abs, reconstructed - reconstructed')
        eigenvalues = eigvals(Symmetric(reconstructed))
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
            "symmetry_residual" => Float64(symmetry_residual),
            "psd_violation" => violation,
            "spectral_scale" => spectral_scale,
            "normalized_psd_violation" => normalized_violation,
        )
    end
    passed =
        normalization["normalized_residual"] <= audit_tolerance &&
        worst_normalized_psd_violation <= audit_tolerance &&
        all(
            block["symmetry_residual"] <= audit_tolerance
            for block in values(blocks)
        )
    return Dict(
        "available" => true,
        "passed" => passed,
        "audit_tolerance" => audit_tolerance,
        "normalization" => normalization,
        "affine_equalities" => Dict{String,Any}(),
        "maximum_absolute_affine_equality_residual" => 0.0,
        "maximum_normalized_affine_equality_residual" => 0.0,
        "psd_blocks" => blocks,
        "worst_psd_violation" => worst_psd_violation,
        "worst_normalized_psd_violation" =>
            worst_normalized_psd_violation,
    )
end

function main(arguments::Vector{String}=ARGS)
    options = B.parse_args(arguments)
    isnothing(options) && return 0
    solve_form = requested_solve_form()
    log_level = requested_log_level()
    wall_start = time()
    result = Dict(
        "schema_version" => RESULT_SCHEMA,
        "started_at_utc" => Dates.format(
            now(UTC),
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
        "requested_solve_form" => solve_form.label,
        "mosek_log_level" => log_level,
        "runtime" => Dict(
            "julia_version" => string(VERSION),
            "julia_executable" => Base.julia_cmd().exec[1],
            "jump_version" => string(Base.pkgversion(JuMP)),
            "mathoptinterface_version" =>
                string(Base.pkgversion(JuMP.MOI)),
            "mosek_version" => string(Base.pkgversion(Mosek)),
            "mosektools_version" => string(Base.pkgversion(MosekTools)),
            "slurm_job_id" => get(ENV, "SLURM_JOB_ID", "not_under_slurm"),
            "hostname" => gethostname(),
        ),
    )

    exit_code = 1
    try
        progress("validating immutable MOF, runmeta, and source hashes")
        input_files = validate_input_files(options)
        runmeta = TOML.parsefile(options.runmeta)
        result["input_hashes"] = Dict(
            "model_mof_sha256" => input_files.model_sha256,
            "runmeta_sha256" => input_files.runmeta_sha256,
            "checksums_sha256" => input_files.checksums_sha256,
        )
        result["runmeta_validation"] =
            validate_runmeta(runmeta, input_files, options)
        result["source_commit"] = runmeta["source"]["git_commit"]
        result["runner_commit"] =
            B.git_output(options.repository_root, "rev-parse", "HEAD")
        result["runner_tree"] =
            B.git_output(options.repository_root, "rev-parse", "HEAD^{tree}")
        result["runner_source_sha256"] = B.file_sha256(abspath(@__FILE__))

        progress("reloading MOF and validating all named real PSD cones")
        reload_start = time()
        model = JuMP.read_from_file(options.model)
        result["mof_reload_wall_seconds"] = time() - reload_start
        result["model_validation"] =
            validate_reloaded_model(model, runmeta)

        progress(
            "preflight passed; attaching Mosek with " *
            "threads=$(options.threads), " *
            "time_limit=$(options.time_limit_seconds)s",
        )
        JuMP.set_optimizer(model, MosekTools.Optimizer)
        JuMP.set_time_limit_sec(model, Float64(options.time_limit_seconds))
        JuMP.set_optimizer_attribute(
            model,
            "MSK_IPAR_NUM_THREADS",
            options.threads,
        )
        JuMP.set_optimizer_attribute(
            model,
            "MSK_IPAR_INTPNT_SOLVE_FORM",
            solve_form.value,
        )
        JuMP.set_optimizer_attribute(
            model,
            "MSK_IPAR_LOG",
            log_level,
        )

        progress(
            "optimize! started; solve_form=$(solve_form.label), " *
            "log_level=$log_level",
        )
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
        result["statuses"] = Dict(
            "termination" => string(termination),
            "primal" => string(primal),
            "dual" => string(dual),
            "raw" => B.safe_string(
                () -> JuMP.raw_status(model),
                "unavailable",
            ),
            "result_count" => JuMP.result_count(model),
            "has_values" => JuMP.has_values(model),
            "has_duals" => JuMP.has_duals(model),
        )
        result["solver"] = Dict(
            "solve_wall_seconds" => solve_wall_seconds,
            "solver_reported_solve_time_seconds" =>
                B.safe_number(() -> JuMP.solve_time(model)),
            "objective_value" =>
                B.safe_number(() -> JuMP.objective_value(model)),
            "dual_objective_value" =>
                B.safe_number(() -> JuMP.dual_objective_value(model)),
            "relative_gap" =>
                B.safe_number(() -> JuMP.relative_gap(model)),
        )

        diagnostics = if JuMP.has_values(model)
            progress("reconstructing and auditing all real PSD blocks")
            solution_diagnostics(model, options.audit_tolerance)
        else
            Dict(
                "available" => false,
                "reason" => "solver_returned_no_primal_values",
            )
        end
        result["solution_diagnostics"] = diagnostics
        result["classification"] =
            B.classify_result(termination, primal, dual, diagnostics)
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
        result["peak_process_rss_kib"] = B.peak_rss_kib()
        B.write_result(options.output, result)
        progress("result written to $(options.output)")
    end
    return exit_code
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(main())
end
