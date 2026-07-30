#!/usr/bin/env julia

module BaselineRunnerUtilities
include(joinpath(
    @__DIR__,
    "solve_shastry_sutherland_reduced_mof.jl",
))
end

using Dates
using LinearAlgebra
using Sockets
using TOML
using JuMP
using Mosek
using MosekTools

const B = BaselineRunnerUtilities
const RESULT_SCHEMA =
    "shastry-sutherland-conjugation-real-solve-result-v1"
const RUNMETA_SCHEMA =
    "shastry-sutherland-conjugation-real-mof-runmeta-v1"
const V4_REDUCTION_SCHEMA = "primal-gap-exact-v4-reduction-v1"
const CONJUGATION_REDUCTION_SCHEMA =
    "primal-gap-exact-v4-conjugation-real-reduction-v1"
const SOURCE_COMMIT =
    "25a8311d12d24b5495c531a9741249180ed28b4f"
const SOURCE_TREE =
    "36399c1b71631dac2b63dade7d910df86e9117d0"

const EXPECTED_INPUTS = Dict(
    "0//1" => (
        model_sha256=
            "0a2c9166eb033a2e782ab91a062491961a5d8139a1b04e80f6f564d1a75a6e14",
        runmeta_sha256=
            "9b1f92a83de02ca1998d898e2892cd72fe0d159a9067b00e0ee6f74f3d7a14ae",
        output_relative=
            "tracks/polyopt/solutions/sdp-gap-seekers/results/" *
            "ss-conjugation-real-g0p8-gamma0-builder-20260729-r4",
    ),
    "1//2" => (
        model_sha256=
            "b50d66a48a45de0f2a25e411ab3dcc6a06f3a99b06626951277ae09686062707",
        runmeta_sha256=
            "80c1c6fc8c72d7a41bc17a2e0dcf3a93caca83d3c795c9bbdf3bc2f4f734e75e",
        output_relative=
            "tracks/polyopt/solutions/sdp-gap-seekers/results/" *
            "ss-conjugation-real-g0p8-gamma0p5-builder-20260729-r4",
    ),
)

const EXPECTED_PSD_DIMENSIONS = Dict(
    "positive_centered_rx0_ry0_real_psd" => 108,
    "positive_centered_rx0_ry1_real_psd" => 81,
    "positive_centered_rx1_ry0_real_psd" => 81,
    "positive_centered_rx1_ry1_real_psd" => 81,
    "positive_scalar_rx0_ry0_real_psd" => 109,
    "positive_scalar_rx0_ry1_real_psd" => 81,
    "positive_scalar_rx1_ry0_real_psd" => 81,
    "positive_scalar_rx1_ry1_real_psd" => 81,
    "gap_gap_active_rx0_ry1_real_psd" => 1,
    "gap_gap_active_rx1_ry0_real_psd" => 1,
    "gap_gap_active_rx1_ry1_real_psd" => 1,
)

const EXPECTED_SOURCE_FILES = Set([
    "tracks/polyopt/solutions/sdp-gap-seekers/" *
    "scripts/build_shastry_sutherland_conjugation_reduced_mof.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "ConjugationReducedPrimalGapJuMP.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "ConjugationSymmetryReduction.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "ExactSymmetryReduction.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/GenericGapModel.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapAssembly.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapJuMP.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapSymbolics.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "ReducedPrimalGapAssembly.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "ReducedPrimalGapJuMP.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "SquareJ1J2Prototype.jl",
])

function progress(message::AbstractString)
    println("[ss-conjugation-solve] ", message)
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

function validate_input_files(
    model_path::String,
    runmeta_path::String,
    checksums_path::String,
    expected_gamma::String,
)
    isfile(model_path) ||
        throw(ArgumentError("MOF missing: $model_path"))
    isfile(runmeta_path) ||
        throw(ArgumentError("runmeta missing: $runmeta_path"))
    basename(model_path) == "model.mof.json" ||
        error("MOF basename must be model.mof.json")
    basename(runmeta_path) == "runmeta.toml" ||
        error("runmeta basename must be runmeta.toml")

    manifest = B.read_checksum_manifest(checksums_path)
    model_sha256 = B.file_sha256(model_path)
    runmeta_sha256 = B.file_sha256(runmeta_path)
    B.require_equal(
        model_sha256,
        manifest["model.mof.json"],
        "MOF SHA-256 versus SHA256SUMS",
    )
    B.require_equal(
        runmeta_sha256,
        manifest["runmeta.toml"],
        "runmeta SHA-256 versus SHA256SUMS",
    )
    expected = EXPECTED_INPUTS[expected_gamma]
    B.require_equal(
        model_sha256,
        expected.model_sha256,
        "MOF SHA-256 versus immutable allowlist",
    )
    B.require_equal(
        runmeta_sha256,
        expected.runmeta_sha256,
        "runmeta SHA-256 versus immutable allowlist",
    )
    return (
        model_sha256=model_sha256,
        runmeta_sha256=runmeta_sha256,
        checksums_sha256=B.file_sha256(checksums_path),
    )
end

function validate_setup(setup, expected_gamma::String)
    B.require_equal(setup["model"], "shastry-sutherland", "model")
    B.require_equal(setup["patch_level"], 1, "patch level")
    B.require_equal(setup["degree_d"], 2, "polynomial degree")
    B.require_equal(setup["state_class"], "unrestricted", "state class")
    B.require_equal(
        setup["physical_boundary_condition"],
        "none-local-consistency-window",
        "physical boundary condition",
    )
    B.require_rational_metadata(
        setup["g_square_over_dimer"],
        "4",
        "5",
        "4//5",
        0.8,
        "square-over-dimer coupling",
    )
    if expected_gamma == "0//1"
        B.require_rational_metadata(
            setup["gamma"],
            "0",
            "1",
            "0//1",
            0.0,
            "gamma",
        )
    else
        B.require_rational_metadata(
            setup["gamma"],
            "1",
            "2",
            "1//2",
            0.5,
            "gamma",
        )
    end
    return
end

function validate_runmeta(
    runmeta,
    input_files,
    expected_gamma::String,
    repository_root::String,
)
    B.require_equal(
        runmeta["schema_version"],
        RUNMETA_SCHEMA,
        "runmeta schema",
    )
    B.require_equal(
        runmeta["claim_level"],
        "solver_free_exact_equivalent_conjugation_real_reduction",
        "runmeta claim level",
    )
    B.require_equal(runmeta["solver_invoked"], false, "solver flag")
    B.require_equal(
        runmeta["optimizer_attached"],
        false,
        "optimizer flag",
    )
    expected = EXPECTED_INPUTS[expected_gamma]
    B.require_equal(
        runmeta["output_relative"],
        expected.output_relative,
        "runmeta output path",
    )
    B.require_equal(
        runmeta["mof"]["filename"],
        "model.mof.json",
        "runmeta MOF filename",
    )
    B.require_equal(
        runmeta["mof"]["sha256"],
        input_files.model_sha256,
        "runmeta MOF SHA-256",
    )
    validate_setup(runmeta["setup"], expected_gamma)

    source_assembly = runmeta["source_assembly"]
    B.require_equal(
        source_assembly["moment_count"],
        74_602,
        "source moment count",
    )
    B.require_equal(
        source_assembly["positive_dimension"],
        703,
        "source positive dimension",
    )
    B.require_equal(
        source_assembly["gap_dimension"],
        7,
        "source gap dimension",
    )
    B.require_equal(
        source_assembly["stationarity_equality_count"],
        3,
        "source equality count",
    )

    v4 = runmeta["exact_v4_reduction"]
    B.require_equal(v4["schema"], V4_REDUCTION_SCHEMA, "V4 schema")
    B.require_equal(v4["moment_count"], 19_108, "V4 moment count")
    B.require_equal(
        v4["eliminated_moment_count"],
        55_494,
        "V4 eliminated moment count",
    )
    B.require_equal(
        v4["positive_block_dimensions"],
        [108, 81, 81, 81, 109, 81, 81, 81],
        "V4 positive block dimensions",
    )
    B.require_equal(
        v4["gap_block_dimensions"],
        [1, 1, 1],
        "V4 gap block dimensions",
    )
    B.require_equal(v4["equality_count"], 3, "V4 equality count")
    B.require_equal(
        v4["truth_checks_exhaustive"],
        true,
        "V4 exhaustive truth flag",
    )

    conjugation = runmeta["exact_conjugation_reduction"]
    B.require_equal(
        conjugation["schema"],
        CONJUGATION_REDUCTION_SCHEMA,
        "conjugation schema",
    )
    B.require_equal(
        conjugation["moment_count"],
        16_660,
        "conjugation moment count",
    )
    B.require_equal(
        conjugation["eliminated_conjugation_odd_moment_count"],
        2_448,
        "conjugation eliminated moment count",
    )
    B.require_equal(
        conjugation["positive_block_dimensions"],
        [108, 81, 81, 81, 109, 81, 81, 81],
        "real positive block dimensions",
    )
    B.require_equal(
        conjugation["gap_block_dimensions"],
        [1, 1, 1],
        "real gap block dimensions",
    )
    B.require_equal(
        conjugation["equality_count"],
        0,
        "real equality count",
    )
    B.require_equal(
        conjugation["real_psd_triangle_entries"],
        31_810,
        "real PSD coordinate count",
    )
    B.require_equal(
        conjugation["generic_hermitian_bridge_triangle_entries"],
        126_525,
        "generic Hermitian bridge coordinate count",
    )
    B.require_equal(
        conjugation["coefficient_count"],
        31_810,
        "conjugation coefficient count",
    )
    for field in (
        "hamiltonian_invariant",
        "coefficient_covariant",
        "realified_coefficients_real",
        "equality_space_invariant",
        "truth_checks_exhaustive",
    )
        B.require_equal(
            conjugation[field],
            true,
            "conjugation $field",
        )
    end

    replay = runmeta["replay"]
    B.require_equal(replay["passed"], true, "builder replay gate")
    B.require_equal(replay["variable_count"], 16_660, "replay variables")
    B.require_equal(
        replay["constraint_count_excluding_variable_sets"],
        12,
        "replay constraint count",
    )
    B.require_equal(
        replay["psd_cone_type"],
        "PositiveSemidefiniteConeTriangle",
        "replay cone type",
    )
    replay_dimensions = Dict(
        String(name) => Int(dimension)
        for (name, dimension) in replay["psd_block_dimensions"]
    )
    B.require_equal(
        replay_dimensions,
        EXPECTED_PSD_DIMENSIONS,
        "replay PSD inventory",
    )

    source = runmeta["source"]
    B.require_equal(source["git_commit"], SOURCE_COMMIT, "source commit")
    B.require_equal(source["git_tree"], SOURCE_TREE, "source tree")
    B.require_equal(
        source["git_branch"],
        "bohr/challenge88-ss-reduced-runner",
        "source branch",
    )
    B.require_equal(
        source["dirty_paths_at_build"],
        String[],
        "source dirty paths",
    )
    files_sha256 = source["files_sha256"]
    B.require_keys(
        files_sha256,
        EXPECTED_SOURCE_FILES,
        "source hash inventory",
    )
    verified_source_hashes = Dict{String,String}()
    for relative in sort!(collect(EXPECTED_SOURCE_FILES))
        path = B.contained_source_path(repository_root, relative)
        isfile(path) || error("recorded source file is missing: $relative")
        actual = B.file_sha256(path)
        B.require_equal(
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
        "source_problem_sha256" =>
            source_assembly["problem_sha256"],
        "source_assembly_sha256" =>
            source_assembly["assembly_sha256"],
        "v4_assembly_sha256" => v4["assembly_sha256"],
        "v4_coefficient_map_sha256" =>
            v4["coefficient_map_sha256"],
        "conjugation_assembly_sha256" =>
            conjugation["assembly_sha256"],
        "conjugation_coefficient_map_sha256" =>
            conjugation["coefficient_map_sha256"],
    )
end

function validate_reloaded_model(model::JuMP.Model)
    B.require_equal(JuMP.num_variables(model), 16_660, "MOF variables")
    B.require_equal(
        JuMP.num_constraints(
            model;
            count_variable_in_set_constraints=false,
        ),
        12,
        "MOF constraint count excluding variable sets",
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

    psd_constraint_count = 0
    for (function_type, set_type) in JuMP.list_of_constraint_types(model)
        set_type <: JuMP.MOI.HermitianPositiveSemidefiniteConeTriangle &&
            error("MOF unexpectedly contains a Hermitian PSD cone")
        set_type <: JuMP.MOI.PositiveSemidefiniteConeTriangle ||
            continue
        psd_constraint_count += length(
            JuMP.all_constraints(model, function_type, set_type),
        )
    end
    B.require_equal(psd_constraint_count, 11, "MOF PSD constraint count")

    dimensions = Dict{String,Int}()
    value_shapes = Dict{String,String}()
    for (name, expected_dimension) in EXPECTED_PSD_DIMENSIONS
        reference = JuMP.constraint_by_name(model, name)
        isnothing(reference) && error("MOF lost PSD block $name")
        object = JuMP.constraint_object(reference)
        object.set isa JuMP.MOI.PositiveSemidefiniteConeTriangle ||
            error("$name changed cone type")
        B.require_equal(
            object.set.side_dimension,
            expected_dimension,
            "$name side dimension",
        )
        dimensions[name] = expected_dimension
        value_shapes[name] = string(typeof(reference.shape))
    end
    return Dict(
        "passed" => true,
        "variable_count" => JuMP.num_variables(model),
        "constraint_count_excluding_variable_sets" => 12,
        "psd_constraint_count" => psd_constraint_count,
        "psd_block_dimensions" => dimensions,
        "jump_value_shapes" => value_shapes,
        "max_psd_side_dimension" => maximum(values(dimensions)),
        "real_psd_triangle_entries" => 31_810,
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
    packed = Float64.(raw_value)
    matrix = zeros(Float64, dimension, dimension)
    index = 0
    for column in 1:dimension
        for row in 1:column
            index += 1
            matrix[row, column] = packed[index]
            matrix[column, row] = packed[index]
        end
    end
    index == expected_length ||
        error("internal symmetric packing reconstruction failure")
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
    for name in sort!(collect(keys(EXPECTED_PSD_DIMENSIONS)))
        reference = JuMP.constraint_by_name(model, name)
        dimension = EXPECTED_PSD_DIMENSIONS[name]
        reconstructed = reconstruct_symmetric_constraint(
            reference,
            dimension,
        )
        symmetry_residual = maximum(
            abs,
            reconstructed - transpose(reconstructed),
        )
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
        "representation" =>
            "exact-v4-conjugation-invariant-real-symmetric",
        "mosek_solve_form" => solve_form.label,
        "runtime" => Dict(
            "julia_version" => string(VERSION),
            "julia_executable" => Base.julia_cmd().exec[1],
            "jump_version" => string(Base.pkgversion(JuMP)),
            "mathoptinterface_version" =>
                string(Base.pkgversion(JuMP.MOI)),
            "mosek_version" => string(Base.pkgversion(Mosek)),
            "mosektools_version" =>
                string(Base.pkgversion(MosekTools)),
            "slurm_job_id" =>
                get(ENV, "SLURM_JOB_ID", "not_under_slurm"),
            "slurm_cpus_per_task" =>
                get(ENV, "SLURM_CPUS_PER_TASK", "unavailable"),
            "slurm_mem_per_node" =>
                get(ENV, "SLURM_MEM_PER_NODE", "unavailable"),
            "hostname" => gethostname(),
        ),
    )

    exit_code = 1
    try
        progress("validating immutable real MOF, runmeta, and SHA256SUMS")
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

        progress("validating fixed setup, both exact reductions, and source hashes")
        runmeta = TOML.parsefile(options.runmeta)
        result["runmeta_validation"] = validate_runmeta(
            runmeta,
            input_files,
            options.expected_gamma,
            options.repository_root,
        )
        result["source_commit"] = runmeta["source"]["git_commit"]
        result["runner_commit"] = B.git_output(
            options.repository_root,
            "rev-parse",
            "HEAD",
        )
        result["runner_tree"] = B.git_output(
            options.repository_root,
            "rev-parse",
            "HEAD^{tree}",
        )
        result["runner_source_sha256"] =
            B.file_sha256(abspath(@__FILE__))

        progress("reloading MOF and validating 11 named real PSD cones")
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
            "MSK_IPAR_NUM_THREADS",
            options.threads,
        )
        JuMP.set_optimizer_attribute(
            model,
            "MSK_IPAR_INTPNT_SOLVE_FORM",
            solve_form.value,
        )

        progress("optimize! started; solve_form=$(solve_form.label)")
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
            "solver_reported_solve_time_seconds" => B.safe_number(
                () -> JuMP.solve_time(model),
            ),
            "objective_value" => B.safe_number(
                () -> JuMP.objective_value(model),
            ),
            "dual_objective_value" => B.safe_number(
                () -> JuMP.dual_objective_value(model),
            ),
            "relative_gap" =>
                B.safe_number(() -> JuMP.relative_gap(model)),
        )

        diagnostics = if JuMP.has_values(model)
            progress("reconstructing all 11 real symmetric PSD blocks")
            solution_diagnostics(model, options.audit_tolerance)
        else
            Dict(
                "available" => false,
                "reason" => "solver_returned_no_primal_values",
            )
        end
        result["solution_diagnostics"] = diagnostics
        result["classification"] = B.classify_result(
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
        result["peak_process_rss_kib"] = B.peak_rss_kib()
        B.write_result(options.output, result)
        progress("result written to $(options.output)")
    end
    return exit_code
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(main())
end
