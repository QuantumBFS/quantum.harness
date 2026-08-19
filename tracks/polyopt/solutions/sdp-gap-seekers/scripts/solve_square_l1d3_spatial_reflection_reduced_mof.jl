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
    "square-j1-j2-l1d3-spatial-reflection-real-solve-result-v1"
const RUNMETA_SCHEMA =
    "square-j1-j2-l1d3-spatial-reflection-real-mof-runmeta-v1"
const REDUCTION_SCHEMAS = Dict(
    "source_assembly" => "primal-gap-assembly-v1",
    "exact_v4_reduction" => "primal-gap-exact-v4-reduction-v1",
    "exact_conjugation_reduction" =>
        "primal-gap-exact-v4-conjugation-real-reduction-v1",
    "exact_spin_axis_reduction" =>
        "primal-gap-exact-v4-conjugation-real-spin-axis-involution-v1",
    "exact_full_spin_reduction" =>
        "primal-gap-exact-v4-conjugation-real-full-spin-permutation-v1",
    "exact_full_spin_cone_reduction" =>
        "primal-gap-exact-v4-conjugation-real-full-spin-cone-orbit-reduction-v1",
    "exact_full_spin_isotypic_reduction" =>
        "primal-gap-exact-v4-conjugation-real-full-spin-isotypic-v1",
    "exact_spatial_reflection_reduction" =>
        "primal-gap-exact-v4-conjugation-real-full-spin-isotypic-spatial-reflection-v1",
)
const EXPECTED_SOURCE_FILES = Set([
    "tracks/polyopt/solutions/sdp-gap-seekers/scripts/" *
    "build_square_l1d3_spatial_reflection_reduced_mof.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "ConjugationSymmetryReduction.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/ExactSymmetryReduction.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "FullSpinConeReducedPrimalGapJuMP.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "FullSpinConeReduction.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "FullSpinIsotypicPrimalGapJuMP.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "FullSpinIsotypicReduction.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "FullSpinPermutationPrimalGapJuMP.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "FullSpinPermutationReduction.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/GenericGapModel.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapAssembly.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapJuMP.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapSymbolics.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "ReducedPrimalGapAssembly.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "SpatialReflectionPrimalGapJuMP.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "SpatialReflectionReduction.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "SpinAxisInvolutionPrimalGapJuMP.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "SpinAxisInvolutionReduction.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/SquareJ1J2Prototype.jl",
])

function progress(message::AbstractString)
    println("[square-l1d3-spatial-solve] ", message)
    flush(stdout)
end

function validate_input_files(options)
    for (path, label) in (
        (options.model, "MOF"),
        (options.runmeta, "runmeta"),
        (options.checksums, "SHA256SUMS"),
    )
        isfile(path) || throw(ArgumentError("$label missing: $path"))
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
        error("MOF, runmeta, and SHA256SUMS must share one directory")
    get(ENV, "SQUARE_L1D3_DYNAMIC_INPUT", "0") == "1" ||
        error("SQUARE_L1D3_DYNAMIC_INPUT must be exactly 1")
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
        error("input must stay under the repository results directory")

    manifest = B.read_checksum_manifest(options.checksums)
    B.require_keys(
        manifest,
        Set(["model.mof.json", "runmeta.toml"]),
        "input checksum manifest",
    )
    model_sha256 = B.file_sha256(options.model)
    runmeta_sha256 = B.file_sha256(options.runmeta)
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
    return (
        model_sha256=model_sha256,
        runmeta_sha256=runmeta_sha256,
        checksums_sha256=B.file_sha256(options.checksums),
        output_relative=relpath(input_real, options.repository_root),
    )
end

function validate_setup(setup, expected_gamma::AbstractString)
    B.require_equal(setup["model"], "square-j1-j2", "model")
    B.require_equal(setup["patch_level"], 1, "patch level L")
    B.require_equal(setup["degree_d"], 3, "polynomial degree d")
    B.require_equal(setup["state_class"], "unrestricted", "state class")
    B.require_equal(
        setup["physical_boundary_condition"],
        "none-local-consistency-window",
        "physical boundary condition",
    )
    B.require_rational_metadata(
        setup["j1"], "1", "1", "1//1", 1.0, "J1 coupling",
    )
    B.require_rational_metadata(
        setup["g_j2_over_j1"],
        "1",
        "2",
        "1//2",
        0.5,
        "J2/J1 coupling",
    )
    B.require_equal(expected_gamma, "2//1", "runner gamma lock")
    B.require_rational_metadata(
        setup["gamma"], "2", "1", "2//1", 2.0, "gamma",
    )
    return
end

function positive_int(value, label::AbstractString)
    value isa Integer && value > 0 ||
        error("$label must be a positive integer")
    return Int(value)
end

function dimension_vector(value, label::AbstractString)
    value isa AbstractVector && !isempty(value) ||
        error("$label must be a nonempty dimension vector")
    return [positive_int(entry, "$label entry") for entry in value]
end

function contained_source_path(
    repository_root::AbstractString,
    relative::AbstractString,
)
    isabspath(relative) && error("source hash path must be relative")
    path = normpath(joinpath(repository_root, relative))
    prefix = repository_root * Base.Filesystem.path_separator
    startswith(path, prefix) ||
        error("source hash path escapes repository: $relative")
    return path
end

function validate_runmeta(runmeta, input_files, options)
    B.require_equal(
        runmeta["schema_version"], RUNMETA_SCHEMA, "runmeta schema",
    )
    B.require_equal(
        runmeta["claim_level"],
        "solver_free_exact_equivalent_spatial_reflection_real_reduction",
        "claim level",
    )
    B.require_equal(runmeta["solver_invoked"], false, "solver flag")
    B.require_equal(
        runmeta["optimizer_attached"], false, "optimizer flag",
    )
    B.require_equal(
        runmeta["output_relative"],
        input_files.output_relative,
        "runmeta output path",
    )
    B.require_equal(
        runmeta["mof"]["filename"], "model.mof.json", "MOF filename",
    )
    B.require_equal(
        runmeta["mof"]["sha256"],
        input_files.model_sha256,
        "runmeta MOF SHA-256",
    )
    B.require_equal(
        runmeta["mof"]["bytes"], filesize(options.model), "MOF bytes",
    )
    validate_setup(runmeta["setup"], options.expected_gamma)

    for (section, schema) in REDUCTION_SCHEMAS
        B.require_equal(
            runmeta[section]["schema"],
            schema,
            "$section schema",
        )
    end
    source_assembly = runmeta["source_assembly"]
    B.require_equal(
        source_assembly["moment_count"],
        3_535_570,
        "formal L1d3 source moment count",
    )
    B.require_equal(
        source_assembly["positive_dimension"],
        5_239,
        "one-symbol L1d3 positive side",
    )
    B.require_equal(
        source_assembly["gap_dimension"],
        7,
        "one-symbol L1d3 gap side",
    )

    sections = [
        "exact_v4_reduction",
        "exact_conjugation_reduction",
        "exact_spin_axis_reduction",
        "exact_full_spin_reduction",
        "exact_full_spin_cone_reduction",
        "exact_full_spin_isotypic_reduction",
        "exact_spatial_reflection_reduction",
    ]
    moment_counts = Int[]
    for section in sections
        table = runmeta[section]
        push!(
            moment_counts,
            positive_int(table["moment_count"], "$section moment count"),
        )
        dimension_vector(
            table["positive_block_dimensions"],
            "$section positive block dimensions",
        )
        dimension_vector(
            table["gap_block_dimensions"],
            "$section gap block dimensions",
        )
        table["equality_count"] isa Integer &&
            table["equality_count"] >= 0 ||
            error("$section equality count must be nonnegative")
    end
    all(diff(moment_counts) .<= 0) ||
        error("reduction moment counts are not monotone nonincreasing")

    truth_sections = [
        "exact_spin_axis_reduction",
        "exact_full_spin_reduction",
        "exact_full_spin_cone_reduction",
        "exact_full_spin_isotypic_reduction",
        "exact_spatial_reflection_reduction",
    ]
    for section in truth_sections
        B.require_equal(
            runmeta[section]["truth_checks_exhaustive"],
            true,
            "$section exhaustive truth gate",
        )
    end
    spatial = runmeta["exact_spatial_reflection_reduction"]
    for field in (
        "site_map_involutive",
        "hamiltonian_invariant",
        "coefficient_covariant",
        "equality_space_invariant",
        "stable_cross_blocks_zero",
        "stable_bases_invertible",
    )
        B.require_equal(spatial[field], true, "spatial $field")
    end
    positive_dimensions = dimension_vector(
        spatial["positive_block_dimensions"],
        "spatial positive dimensions",
    )
    gap_dimensions = dimension_vector(
        spatial["gap_block_dimensions"],
        "spatial gap dimensions",
    )
    all_dimensions = [positive_dimensions; gap_dimensions]
    expected_triangle_entries =
        sum(dimension * (dimension + 1) ÷ 2 for dimension in all_dimensions)
    B.require_equal(
        spatial["real_psd_triangle_entries"],
        expected_triangle_entries,
        "spatial real PSD triangle entries",
    )
    B.require_equal(
        spatial["maximum_psd_side_dimension"],
        maximum(all_dimensions),
        "spatial maximum PSD side",
    )
    B.require_equal(
        spatial["source_moment_count"],
        runmeta["exact_full_spin_isotypic_reduction"]["moment_count"],
        "spatial source moment count",
    )

    replay = runmeta["replay"]
    B.require_equal(replay["passed"], true, "MOF replay")
    B.require_equal(
        replay["variable_count"],
        spatial["moment_count"],
        "replay variable count",
    )
    B.require_equal(
        replay["psd_constraint_count"],
        length(all_dimensions),
        "replay PSD block count",
    )
    replay_dimensions = Dict(
        String(name) => Int(dimension)
        for (name, dimension) in replay["psd_block_dimensions"]
    )
    B.require_equal(
        sort!(collect(values(replay_dimensions))),
        sort!(copy(all_dimensions)),
        "replay PSD dimensions",
    )
    equality_count = Int(spatial["equality_count"])
    B.require_equal(
        replay["constraint_count_excluding_variable_sets"],
        1 + equality_count + length(replay_dimensions),
        "replay constraint count",
    )

    source = runmeta["source"]
    B.require_equal(
        source["dirty_paths_at_build"], String[], "source dirty paths",
    )
    files_sha256 = source["files_sha256"]
    B.require_keys(
        files_sha256, EXPECTED_SOURCE_FILES, "source hash inventory",
    )
    verified_source_hashes = Dict{String,String}()
    for relative in sort!(collect(EXPECTED_SOURCE_FILES))
        path = contained_source_path(options.repository_root, relative)
        isfile(path) || error("recorded source file is missing: $relative")
        actual = B.file_sha256(path)
        B.require_equal(
            actual,
            files_sha256[relative],
            "source SHA-256 for $relative",
        )
        verified_source_hashes[relative] = actual
    end

    report = Dict(
        "passed" => true,
        "schema" => RUNMETA_SCHEMA,
        "source_commit" => source["git_commit"],
        "source_tree" => source["git_tree"],
        "source_file_sha256" => verified_source_hashes,
        "source_problem_sha256" => source_assembly["problem_sha256"],
        "source_assembly_sha256" => source_assembly["assembly_sha256"],
        "spatial_assembly_sha256" => spatial["assembly_sha256"],
        "spatial_coefficient_map_sha256" =>
            spatial["coefficient_map_sha256"],
    )
    specification = (
        variable_count=Int(spatial["moment_count"]),
        equality_count=equality_count,
        psd_dimensions=replay_dimensions,
        triangle_entries=expected_triangle_entries,
    )
    return (report=report, specification=specification)
end

function validate_reloaded_model(model::JuMP.Model, specification)
    B.require_equal(
        JuMP.num_variables(model),
        specification.variable_count,
        "MOF variable count",
    )
    expected_constraints =
        1 + specification.equality_count +
        length(specification.psd_dimensions)
    B.require_equal(
        JuMP.num_constraints(
            model;
            count_variable_in_set_constraints=false,
        ),
        expected_constraints,
        "MOF constraint count excluding variable sets",
    )
    B.require_equal(
        JuMP.objective_sense(model),
        JuMP.MOI.FEASIBILITY_SENSE,
        "MOF objective sense",
    )
    normalization = JuMP.constraint_by_name(model, "normalization")
    isnothing(normalization) && error("MOF lost normalization")
    JuMP.constraint_object(normalization).set isa JuMP.MOI.EqualTo{Float64} ||
        error("normalization changed set type")
    for index in 1:specification.equality_count
        name = "spatial_reflection_equality[$index]"
        reference = JuMP.constraint_by_name(model, name)
        isnothing(reference) && error("MOF lost $name")
        JuMP.constraint_object(reference).set isa JuMP.MOI.EqualTo{Float64} ||
            error("$name changed set type")
    end

    psd_constraint_count = 0
    for (function_type, set_type) in JuMP.list_of_constraint_types(model)
        set_type <: JuMP.MOI.HermitianPositiveSemidefiniteConeTriangle &&
            error("MOF unexpectedly contains a Hermitian PSD cone")
        set_type <: JuMP.MOI.PositiveSemidefiniteConeTriangle || continue
        psd_constraint_count += length(
            JuMP.all_constraints(model, function_type, set_type),
        )
    end
    B.require_equal(
        psd_constraint_count,
        length(specification.psd_dimensions),
        "MOF PSD constraint count",
    )
    value_shapes = Dict{String,String}()
    for (name, dimension) in specification.psd_dimensions
        reference = JuMP.constraint_by_name(model, name)
        isnothing(reference) && error("MOF lost PSD block $name")
        object = JuMP.constraint_object(reference)
        object.set isa JuMP.MOI.PositiveSemidefiniteConeTriangle ||
            error("$name changed cone type")
        B.require_equal(
            object.set.side_dimension,
            dimension,
            "$name side dimension",
        )
        value_shapes[name] = string(typeof(reference.shape))
    end
    return Dict(
        "passed" => true,
        "variable_count" => specification.variable_count,
        "constraint_count_excluding_variable_sets" =>
            expected_constraints,
        "psd_constraint_count" => psd_constraint_count,
        "psd_block_dimensions" => specification.psd_dimensions,
        "jump_value_shapes" => value_shapes,
        "max_psd_side_dimension" =>
            maximum(values(specification.psd_dimensions)),
        "real_psd_triangle_entries" =>
            specification.triangle_entries,
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
        error("packed real PSD value has the wrong length")
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
    return matrix
end

function solution_diagnostics(model, specification, audit_tolerance)
    normalization = B.affine_residual(
        JuMP.constraint_by_name(model, "normalization"),
    )
    equalities = Dict{String,Any}()
    maximum_absolute_equality_residual = 0.0
    maximum_normalized_equality_residual = 0.0
    for index in 1:specification.equality_count
        name = "spatial_reflection_equality[$index]"
        diagnostic = B.affine_residual(
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
    for name in sort!(collect(keys(specification.psd_dimensions)))
        dimension = specification.psd_dimensions[name]
        matrix = reconstruct_symmetric_constraint(
            JuMP.constraint_by_name(model, name),
            dimension,
        )
        symmetry_residual = maximum(abs, matrix - transpose(matrix))
        eigenvalues = eigvals(Symmetric(matrix))
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
        maximum_normalized_equality_residual <= audit_tolerance &&
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

function write_primal_values(path, model, input_hashes)
    variables = JuMP.all_variables(model)
    values = JuMP.value.(variables)
    all(isfinite, values) ||
        error("solver returned a nonfinite primal variable")
    names = JuMP.name.(variables)
    length(unique(names)) == length(names) ||
        error("reloaded MOF variable names are not unique")
    all(!isempty, names) ||
        error("reloaded MOF contains an unnamed variable")
    temporary = path * ".tmp"
    ispath(path) && error("refusing existing primal-value artifact")
    ispath(temporary) && error("refusing existing temporary artifact")
    open(temporary, "w") do io
        println(
            io,
            "# schema=square-j1-j2-l1d3-spatial-reflection-primal-values-v1",
        )
        println(io, "# model_mof_sha256=", input_hashes.model_sha256)
        println(io, "# runmeta_sha256=", input_hashes.runmeta_sha256)
        println(io, "index\tname\tfloat64_bits")
        for (index, (name, value)) in enumerate(zip(names, values))
            println(io, index, '\t', name, '\t', bitstring(value))
        end
    end
    mv(temporary, path)
    return Dict(
        "schema_version" =>
            "square-j1-j2-l1d3-spatial-reflection-primal-values-v1",
        "filename" => basename(path),
        "variable_count" => length(variables),
        "bytes" => filesize(path),
        "sha256" => B.file_sha256(path),
        "encoding" => "index-tab-name-tab-ieee754-binary64-bits",
    )
end

function main(arguments::Vector{String}=ARGS)
    options = B.parse_args(arguments)
    isnothing(options) && return 0
    wall_start = time()
    result = Dict(
        "schema_version" => RESULT_SCHEMA,
        "started_at_utc" => Dates.format(
            now(UTC), dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        ),
        "completed" => false,
        "classification" => "unknown",
        "expected_gamma" => options.expected_gamma,
        "audit_tolerance" => options.audit_tolerance,
        "time_limit_seconds" => options.time_limit_seconds,
        "threads" => options.threads,
        "representation" =>
            "exact-v4-conjugation-full-spin-isotypic-spatial-reflection-real-symmetric",
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
        progress("validating immutable L1d3 spatial MOF and source hashes")
        input_files = validate_input_files(options)
        result["input_hashes"] = Dict(
            "model_mof_sha256" => input_files.model_sha256,
            "runmeta_sha256" => input_files.runmeta_sha256,
            "checksums_sha256" => input_files.checksums_sha256,
        )
        validated = validate_runmeta(
            TOML.parsefile(options.runmeta),
            input_files,
            options,
        )
        result["runmeta_validation"] = validated.report
        result["runner_commit"] = B.git_output(
            options.repository_root, "rev-parse", "HEAD",
        )
        result["runner_tree"] = B.git_output(
            options.repository_root, "rev-parse", "HEAD^{tree}",
        )
        result["runner_source_sha256"] =
            B.file_sha256(abspath(@__FILE__))

        progress("reloading and structurally validating the reduced MOF")
        reload_start = time()
        model = JuMP.read_from_file(options.model)
        result["mof_reload_wall_seconds"] = time() - reload_start
        result["model_validation"] = validate_reloaded_model(
            model, validated.specification,
        )

        progress(
            "preflight passed; attaching Mosek with " *
            "threads=$(options.threads), " *
            "time_limit=$(options.time_limit_seconds)s",
        )
        JuMP.set_optimizer(model, MosekTools.Optimizer)
        JuMP.set_time_limit_sec(
            model, Float64(options.time_limit_seconds),
        )
        JuMP.set_optimizer_attribute(
            model, "MSK_IPAR_NUM_THREADS", options.threads,
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
        result["statuses"] = Dict(
            "termination" => string(termination),
            "primal" => string(primal),
            "dual" => string(dual),
            "raw" => B.safe_string(
                () -> JuMP.raw_status(model), "unavailable",
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
            result["primal_values"] = write_primal_values(
                joinpath(dirname(options.output), "primal-values.tsv"),
                model,
                input_files,
            )
            progress("auditing every equality and real PSD block")
            solution_diagnostics(
                model,
                validated.specification,
                options.audit_tolerance,
            )
        else
            Dict(
                "available" => false,
                "reason" => "solver_returned_no_primal_values",
            )
        end
        result["solution_diagnostics"] = diagnostics
        result["classification"] = B.classify_result(
            termination, primal, dual, diagnostics,
        )
        result["completed"] = true
        exit_code = 0
    catch exception
        result["classification"] = "runner_failure"
        result["exception"] = Dict(
            "type" => string(typeof(exception)),
            "message" => sprint(showerror, exception),
            "stacktrace" => sprint(
                Base.show_backtrace, catch_backtrace(),
            ),
        )
        progress("FAILED: $(sprint(showerror, exception))")
    finally
        result["finished_at_utc"] = Dates.format(
            now(UTC), dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
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
