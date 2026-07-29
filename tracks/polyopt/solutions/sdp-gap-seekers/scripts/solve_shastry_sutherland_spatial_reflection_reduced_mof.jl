#!/usr/bin/env julia

module BaselineRunnerUtilities
include(joinpath(
    @__DIR__,
    "solve_shastry_sutherland_reduced_mof.jl",
))
end

using Dates
using LinearAlgebra
using SHA
using Sockets
using TOML
using JuMP
using Mosek
using MosekTools

const B = BaselineRunnerUtilities
const RESULT_SCHEMA =
    "shastry-sutherland-spatial-reflection-real-solve-result-v1"
const RUNMETA_SCHEMA =
    "shastry-sutherland-spatial-reflection-real-mof-runmeta-v1"
const SPATIAL_REDUCTION_SCHEMA =
    "primal-gap-exact-v4-conjugation-real-full-spin-isotypic-spatial-reflection-v1"
const SOURCE_COMMIT =
    "f1fb24ceb1a6ba110abbcb06307a9833bc90b524"
const SOURCE_TREE =
    "e6288e6214d0e1cd6cd4a97535d4a80d99de99fe"
const SOURCE_BRANCH = "bohr/spatial-reflection-verify"

# Filled only from the checksummed xH5 builder run at SOURCE_COMMIT.
const EXPECTED_INPUTS = Dict(
    "0//1" => (
        model_sha256=
            "5d770e3320ef9f2c6af7d3b763b7d05c2a316a245a114f98881c79007da2cf95",
        runmeta_sha256=
            "3b1269a8cf86e4eee63607fd8ec2a492e21ed8080496b131cd179e0b92720c1e",
        output_relative=
            "tracks/polyopt/solutions/sdp-gap-seekers/results/" *
            "ss-spatial-reflection-real-g0p8-gamma0-builder-20260729-r1",
    ),
    "1//2" => (
        model_sha256=
            "526700018f93a1ee5bd4955f6e75a56669a805ca50e3b1671b341789409a899e",
        runmeta_sha256=
            "388db534571005ec8268987accc17f8e8d2a4b9b9c44ad57f181bacf2d29d44a",
        output_relative=
            "tracks/polyopt/solutions/sdp-gap-seekers/results/" *
            "ss-spatial-reflection-real-g0p8-gamma0p5-builder-20260729-r1",
    ),
)

const EXPECTED_PSD_DIMENSIONS = Dict(
    "spatial_reflection_positive_centered_rx0_ry0_s3_trivial_spatial_plus_real_psd" => 21,
    "spatial_reflection_positive_centered_rx0_ry0_s3_trivial_spatial_minus_real_psd" => 15,
    "spatial_reflection_positive_centered_rx0_ry0_s3_standard_representative_spatial_plus_real_psd" => 21,
    "spatial_reflection_positive_centered_rx0_ry0_s3_standard_representative_spatial_minus_real_psd" => 15,
    "spatial_reflection_positive_centered_rx1_ry0_eigen_plus_spatial_plus_real_psd" => 21,
    "spatial_reflection_positive_centered_rx1_ry0_eigen_plus_spatial_minus_real_psd" => 15,
    "spatial_reflection_positive_centered_rx1_ry0_eigen_minus_spatial_plus_real_psd" => 24,
    "spatial_reflection_positive_centered_rx1_ry0_eigen_minus_spatial_minus_real_psd" => 21,
    "spatial_reflection_positive_scalar_rx0_ry0_s3_trivial_spatial_plus_real_psd" => 22,
    "spatial_reflection_positive_scalar_rx0_ry0_s3_trivial_spatial_minus_real_psd" => 15,
    "spatial_reflection_positive_scalar_rx0_ry0_s3_standard_representative_spatial_plus_real_psd" => 21,
    "spatial_reflection_positive_scalar_rx0_ry0_s3_standard_representative_spatial_minus_real_psd" => 15,
    "spatial_reflection_positive_scalar_rx1_ry0_eigen_plus_spatial_plus_real_psd" => 21,
    "spatial_reflection_positive_scalar_rx1_ry0_eigen_plus_spatial_minus_real_psd" => 15,
    "spatial_reflection_positive_scalar_rx1_ry0_eigen_minus_spatial_plus_real_psd" => 24,
    "spatial_reflection_positive_scalar_rx1_ry0_eigen_minus_spatial_minus_real_psd" => 21,
    "spatial_reflection_gap_gap_active_rx1_ry0_eigen_minus_spatial_plus_real_psd" => 1,
)

const EXPECTED_SOURCE_FILES = Set([
    "tracks/polyopt/solutions/sdp-gap-seekers/scripts/" *
    "build_shastry_sutherland_spatial_reflection_reduced_mof.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "ConjugationSymmetryReduction.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/ExactSymmetryReduction.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/" *
    "FullSpinConeReducedPrimalGapJuMP.jl",
    "tracks/polyopt/solutions/sdp-gap-seekers/src/FullSpinConeReduction.jl",
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

const EXPECTED_LAYER_FIELDS = Dict(
    "source_assembly" => Dict(
        "schema" => "primal-gap-assembly-v1",
        "moment_count" => 74_602,
        "positive_dimension" => 703,
        "gap_dimension" => 7,
        "stationarity_equality_count" => 3,
    ),
    "exact_v4_reduction" => Dict(
        "schema" => "primal-gap-exact-v4-reduction-v1",
        "moment_count" => 19_108,
        "eliminated_moment_count" => 55_494,
        "positive_block_dimensions" =>
            [108, 81, 81, 81, 109, 81, 81, 81],
        "gap_block_dimensions" => [1, 1, 1],
        "equality_count" => 3,
    ),
    "exact_conjugation_reduction" => Dict(
        "schema" => "primal-gap-exact-v4-conjugation-real-reduction-v1",
        "moment_count" => 16_660,
        "eliminated_conjugation_odd_moment_count" => 2_448,
        "positive_block_dimensions" =>
            [108, 81, 81, 81, 109, 81, 81, 81],
        "gap_block_dimensions" => [1, 1, 1],
        "equality_count" => 0,
        "real_psd_triangle_entries" => 31_810,
    ),
    "exact_spin_axis_reduction" => Dict(
        "schema" =>
            "primal-gap-exact-v4-conjugation-real-spin-axis-involution-v1",
        "moment_count" => 8_803,
        "eliminated_spin_axis_moment_count" => 7_857,
        "positive_block_dimensions" =>
            [72, 36, 81, 36, 45, 73, 36, 81, 36, 45],
        "gap_block_dimensions" => [1, 1],
        "equality_count" => 0,
        "real_psd_triangle_entries" => 16_707,
        "maximum_psd_side_dimension" => 81,
        "coefficient_count" => 31_810,
        "stable_cross_entry_count" => 8_460,
        "hamiltonian_invariant" => true,
        "coefficient_covariant" => true,
        "stable_cross_blocks_zero" => true,
        "equality_space_invariant" => true,
        "truth_checks_exhaustive" => true,
    ),
    "exact_full_spin_reduction" => Dict(
        "schema" =>
            "primal-gap-exact-v4-conjugation-real-full-spin-permutation-v1",
        "moment_count" => 3_250,
        "eliminated_from_conjugation_moment_count" => 13_410,
        "eliminated_from_spin_axis_moment_count" => 5_553,
        "positive_block_dimensions" =>
            [72, 36, 81, 36, 45, 73, 36, 81, 36, 45],
        "gap_block_dimensions" => [1, 1],
        "equality_count" => 0,
        "real_psd_triangle_entries" => 16_707,
        "maximum_psd_side_dimension" => 81,
        "coefficient_check_count" => 190_860,
        "hamiltonian_invariant" => true,
        "coefficient_covariant" => true,
        "conjugation_inventory_closed" => true,
        "conjugation_action_unsigned" => true,
        "equality_space_invariant" => true,
        "truth_checks_exhaustive" => true,
    ),
    "exact_full_spin_cone_reduction" => Dict(
        "schema" =>
            "primal-gap-exact-v4-conjugation-real-full-spin-cone-orbit-reduction-v1",
        "moment_count" => 3_250,
        "eliminated_unused_moment_count" => 0,
        "removed_orbit_cone_count" => 3,
        "positive_block_dimensions" => [72, 36, 36, 45, 73, 36, 36, 45],
        "gap_block_dimensions" => [1],
        "equality_count" => 0,
        "real_psd_triangle_entries" => 10_064,
        "maximum_psd_side_dimension" => 73,
        "orbit_block_count" => 3,
        "orbit_block_dimensions" => [1, 81, 81],
        "orbit_entry_count" => 6_643,
        "stable_cross_entry_count" => 3_240,
        "stable_basis_dimensions" => [1, 81, 81],
        "gauge_mixed_entry_count" => 0,
        "orbit_projection_exact" => true,
        "orbit_congruence_exact" => true,
        "stable_cross_blocks_zero" => true,
        "stable_bases_invertible" => true,
        "gauge_phases_well_formed" => true,
        "gauge_phase_classes_aligned" => true,
        "gauge_mixed_entries_zero" => true,
        "truth_checks_exhaustive" => true,
    ),
    "exact_full_spin_isotypic_reduction" => Dict(
        "schema" =>
            "primal-gap-exact-v4-conjugation-real-full-spin-isotypic-v1",
        "moment_count" => 3_250,
        "eliminated_unused_moment_count" => 0,
        "positive_block_dimensions" => [36, 36, 36, 45, 37, 36, 36, 45],
        "gap_block_dimensions" => [1],
        "equality_count" => 0,
        "real_psd_triangle_entries" => 6_104,
        "maximum_psd_side_dimension" => 45,
        "source_block_dimensions" => [108, 109],
        "trivial_block_dimensions" => [36, 37],
        "standard_block_dimensions" => [36, 36],
        "singleton_orbit_count" => 1,
        "triple_orbit_count" => 72,
        "cross_entry_count" => 7_848,
        "standard_proportionality_factor" => 3,
        "standard_relation_entry_count" => 1_332,
        "basis_dimensions" => [108, 109],
        "row_actions_unsigned" => true,
        "conjugation_rows_even" => true,
        "involution_exact" => true,
        "cross_blocks_zero" => true,
        "standard_blocks_proportional" => true,
        "bases_invertible" => true,
        "truth_checks_exhaustive" => true,
    ),
    "exact_spatial_reflection_reduction" => Dict(
        "schema" => SPATIAL_REDUCTION_SCHEMA,
        "source_moment_count" => 3_250,
        "moment_count" => 1_711,
        "eliminated_spatial_moment_count" => 1_539,
        "positive_block_dimensions" =>
            [21, 15, 21, 15, 21, 15, 24, 21,
             22, 15, 21, 15, 21, 15, 24, 21],
        "gap_block_dimensions" => [1],
        "equality_count" => 0,
        "real_psd_triangle_entries" => 3_191,
        "maximum_psd_side_dimension" => 24,
        "site_map_involutive" => true,
        "hamiltonian_invariant" => true,
        "coefficient_covariant" => true,
        "coefficient_count" => 6_104,
        "equality_space_invariant" => true,
        "stable_cross_blocks_zero" => true,
        "stable_cross_entry_count" => 2_913,
        "stable_bases_invertible" => true,
        "stable_basis_dimensions" => [36, 36, 36, 45, 37, 36, 36, 45, 1],
        "truth_checks_exhaustive" => true,
    ),
    "replay" => Dict(
        "passed" => true,
        "variable_count" => 1_711,
        "constraint_count_excluding_variable_sets" => 18,
        "psd_constraint_count" => 17,
        "psd_cone_type" => "PositiveSemidefiniteConeTriangle",
    ),
)

function progress(message::AbstractString)
    println("[ss-spatial-reflection-solve] ", message)
    flush(stdout)
end

function dynamic_scan_input_enabled()
    value = get(ENV, "SS_SCAN_DYNAMIC_INPUT", "0")
    value in ("0", "1") ||
        error("SS_SCAN_DYNAMIC_INPUT must be exactly 0 or 1")
    return value == "1"
end

function git_blob_sha256(
    repository_root::AbstractString,
    commit::AbstractString,
    relative::AbstractString,
)
    bytes = read(Cmd(
        `git show $(commit):$(relative)`;
        dir=repository_root,
    ))
    return bytes2hex(sha256(bytes))
end

function require_expected_fields(actual, expected, label::AbstractString)
    actual isa AbstractDict || error("$label is not a dictionary")
    for key in sort!(collect(keys(expected)))
        haskey(actual, key) || error("$label is missing $key")
        expected_value = expected[key]
        actual_value = actual[key]
        if expected_value isa AbstractDict
            require_expected_fields(
                actual_value,
                expected_value,
                "$label.$key",
            )
        else
            B.require_equal(actual_value, expected_value, "$label.$key")
        end
    end
    return
end

function validate_input_files(
    model_path::AbstractString,
    runmeta_path::AbstractString,
    checksums_path::AbstractString,
    expected_gamma::AbstractString,
    repository_root::AbstractString;
    expected_inputs=EXPECTED_INPUTS,
)
    dynamic_input = dynamic_scan_input_enabled()
    if !dynamic_input
        expected_gamma in keys(expected_inputs) ||
            error("expected gamma must be exactly 0//1 or 1//2")
    end
    for path in (model_path, runmeta_path, checksums_path)
        isfile(path) || throw(ArgumentError("input missing: $path"))
    end
    basename(model_path) == "model.mof.json" ||
        error("MOF basename must be model.mof.json")
    basename(runmeta_path) == "runmeta.toml" ||
        error("runmeta basename must be runmeta.toml")
    basename(checksums_path) == "SHA256SUMS" ||
        error("checksum basename must be SHA256SUMS")
    input_directory = dirname(model_path)
    dirname(runmeta_path) == input_directory &&
        dirname(checksums_path) == input_directory ||
        error("MOF, runmeta, and checksums must share one directory")

    output_relative = relpath(input_directory, repository_root)
    expected = dynamic_input ? nothing : expected_inputs[expected_gamma]
    if dynamic_input
        results_root = realpath(joinpath(
            repository_root,
            "tracks",
            "polyopt",
            "solutions",
            "sdp-gap-seekers",
            "results",
        ))
        input_real = realpath(input_directory)
        startswith(input_real, results_root * "/") ||
            error(
                "dynamic scan input must stay under the repository " *
                "results directory",
            )
    else
        B.require_equal(
            output_relative,
            expected.output_relative,
            "immutable input directory",
        )
    end
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
    if !dynamic_input
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
    end
    return (
        model_sha256=model_sha256,
        runmeta_sha256=runmeta_sha256,
        checksums_sha256=B.file_sha256(checksums_path),
        output_relative=output_relative,
    )
end

function validate_setup(setup, expected_gamma::AbstractString)
    require_expected_fields(
        setup,
        Dict(
            "model" => "shastry-sutherland",
            "patch_level" => 1,
            "degree_d" => 2,
            "state_class" => "unrestricted",
            "physical_boundary_condition" =>
                "none-local-consistency-window",
        ),
        "setup",
    )
    B.require_rational_metadata(
        setup["g_square_over_dimer"],
        "4",
        "5",
        "4//5",
        0.8,
        "square-over-dimer coupling",
    )
    gamma_fields = split(expected_gamma, "//")
    length(gamma_fields) == 2 ||
        error("canonical gamma is malformed: $expected_gamma")
    gamma_value =
        parse(BigInt, gamma_fields[1]) // parse(BigInt, gamma_fields[2])
    B.require_rational_metadata(
        setup["gamma"],
        gamma_fields[1],
        gamma_fields[2],
        expected_gamma,
        Float64(gamma_value),
        "gamma",
    )
    return
end

function validate_top_level_metadata(
    runmeta,
    input_files,
    expected_gamma::AbstractString,
)
    B.require_equal(
        runmeta["schema_version"],
        RUNMETA_SCHEMA,
        "runmeta schema",
    )
    B.require_equal(
        runmeta["claim_level"],
        "solver_free_exact_equivalent_spatial_reflection_real_reduction",
        "runmeta claim level",
    )
    B.require_equal(runmeta["solver_invoked"], false, "solver flag")
    B.require_equal(
        runmeta["optimizer_attached"],
        false,
        "optimizer flag",
    )
    B.require_equal(
        runmeta["output_relative"],
        input_files.output_relative,
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
    return
end

function validate_runmeta(
    runmeta,
    input_files,
    expected_gamma::AbstractString,
    repository_root::AbstractString,
)
    validate_top_level_metadata(runmeta, input_files, expected_gamma)
    for (layer, expected) in EXPECTED_LAYER_FIELDS
        haskey(runmeta, layer) || error("runmeta is missing $layer")
        require_expected_fields(runmeta[layer], expected, layer)
    end
    replay_dimensions = Dict(
        String(name) => Int(dimension)
        for (name, dimension) in
            runmeta["replay"]["psd_block_dimensions"]
    )
    B.require_equal(
        replay_dimensions,
        EXPECTED_PSD_DIMENSIONS,
        "builder replay PSD inventory",
    )

    source = runmeta["source"]
    if dynamic_scan_input_enabled()
        B.require_equal(
            source["git_commit"],
            B.git_output(repository_root, "rev-parse", "HEAD"),
            "dynamic source commit",
        )
        B.require_equal(
            source["git_tree"],
            B.git_output(repository_root, "rev-parse", "HEAD^{tree}"),
            "dynamic source tree",
        )
        B.require_equal(
            source["git_branch"],
            B.git_output(
                repository_root,
                "symbolic-ref",
                "--short",
                "HEAD",
            ),
            "dynamic source branch",
        )
    else
        B.require_equal(source["git_commit"], SOURCE_COMMIT, "source commit")
        B.require_equal(source["git_tree"], SOURCE_TREE, "source tree")
        B.require_equal(source["git_branch"], SOURCE_BRANCH, "source branch")
    end
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
        actual = dynamic_scan_input_enabled() ?
                 B.file_sha256(path) :
                 git_blob_sha256(
                     repository_root,
                     SOURCE_COMMIT,
                     relative,
                 )
        B.require_equal(
            actual,
            files_sha256[relative],
            "source SHA-256 for $relative",
        )
        verified_source_hashes[relative] = actual
    end
    return Dict(
        "passed" => true,
        "source_commit" => source["git_commit"],
        "source_tree" => source["git_tree"],
        "source_file_sha256" => verified_source_hashes,
        "spatial_assembly_sha256" =>
            runmeta["exact_spatial_reflection_reduction"]["assembly_sha256"],
        "spatial_coefficient_map_sha256" =>
            runmeta["exact_spatial_reflection_reduction"]["coefficient_map_sha256"],
    )
end

function validate_reloaded_model(
    model::JuMP.Model;
    expected_psd_dimensions=EXPECTED_PSD_DIMENSIONS,
)
    B.require_equal(JuMP.num_variables(model), 1_711, "MOF variables")
    B.require_equal(
        JuMP.num_constraints(
            model;
            count_variable_in_set_constraints=false,
        ),
        18,
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
    B.require_equal(psd_constraint_count, 17, "MOF PSD constraint count")

    dimensions = Dict{String,Int}()
    value_shapes = Dict{String,String}()
    for (name, expected_dimension) in expected_psd_dimensions
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
        "constraint_count_excluding_variable_sets" => 18,
        "psd_constraint_count" => psd_constraint_count,
        "psd_block_dimensions" => dimensions,
        "jump_value_shapes" => value_shapes,
        "max_psd_side_dimension" => maximum(values(dimensions)),
        "real_psd_triangle_entries" => 3_191,
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
            matrix[row, column] = Float64(raw_value[index])
            matrix[column, row] = Float64(raw_value[index])
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
        reconstructed =
            reconstruct_symmetric_constraint(reference, dimension)
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

function write_primal_values(
    path::AbstractString,
    model::JuMP.Model,
    input_hashes,
)
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
    ispath(path) && error("refusing existing primal-value artifact: $path")
    ispath(temporary) &&
        error("refusing existing temporary primal-value artifact: $temporary")
    open(temporary, "w") do io
        println(
            io,
            "# schema=shastry-sutherland-spatial-reflection-primal-values-v1",
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
            "shastry-sutherland-spatial-reflection-primal-values-v1",
        "filename" => basename(path),
        "variable_count" => length(variables),
        "bytes" => filesize(path),
        "sha256" => B.file_sha256(path),
        "encoding" => "index-tab-name-tab-ieee754-binary64-bits",
    )
end

function classify_spatial_result(
    termination,
    primal,
    dual,
    diagnostics,
)
    if termination == JuMP.MOI.OPTIMAL &&
       primal == JuMP.MOI.FEASIBLE_POINT &&
       dual == JuMP.MOI.FEASIBLE_POINT
        return diagnostics["passed"] ?
               "feasible_residual_checked_float" :
               "feasible_status_failed_residual_audit"
    end
    baseline = B.classify_result(
        termination,
        primal,
        dual,
        diagnostics,
    )
    startswith(
        baseline,
        "infeasibility_candidate",
    ) && return baseline
    return "unknown"
end

function main(arguments::Vector{String}=ARGS)
    options = B.parse_args(arguments)
    isnothing(options) && return 0
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
            "exact-v4-conjugation-full-spin-isotypic-spatial-reflection-real",
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
        progress("validating immutable spatial-reflection inputs")
        input_files = validate_input_files(
            options.model,
            options.runmeta,
            options.checksums,
            options.expected_gamma,
            options.repository_root,
        )
        result["input_hashes"] = Dict(
            "model_mof_sha256" => input_files.model_sha256,
            "runmeta_sha256" => input_files.runmeta_sha256,
            "checksums_sha256" => input_files.checksums_sha256,
        )

        progress("validating fixed setup, seven exact reductions, and source hashes")
        runmeta = TOML.parsefile(options.runmeta)
        result["runmeta_validation"] = validate_runmeta(
            runmeta,
            input_files,
            options.expected_gamma,
            options.repository_root,
        )
        result["source_commit"] = runmeta["source"]["git_commit"]
        result["runner_commit"] =
            B.git_output(options.repository_root, "rev-parse", "HEAD")
        result["runner_tree"] =
            B.git_output(options.repository_root, "rev-parse", "HEAD^{tree}")
        result["runner_source_sha256"] =
            B.file_sha256(abspath(@__FILE__))

        progress("reloading MOF and validating 17 named real PSD cones")
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
            progress("exporting exact IEEE-754 primal variable bits")
            result["primal_values"] = write_primal_values(
                joinpath(dirname(options.output), "primal-values.tsv"),
                model,
                input_files,
            )
            progress("independently reconstructing all 17 PSD blocks")
            solution_diagnostics(model, options.audit_tolerance)
        else
            Dict(
                "available" => false,
                "reason" => "solver_returned_no_primal_values",
            )
        end
        result["solution_diagnostics"] = diagnostics
        result["classification"] = classify_spatial_result(
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
