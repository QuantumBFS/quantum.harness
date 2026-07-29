#!/usr/bin/env julia

include(joinpath(@__DIR__, "build_shastry_full_state_spin_spatial_mof.jl"))
include(joinpath(
    TRACK_ROOT,
    "src",
    "ShastryFullStateSpinIsotypicReduction.jl",
))
using .ShastryFullStateSpinIsotypicReduction
include(joinpath(
    TRACK_ROOT,
    "src",
    "ShastryFullStateSpinIsotypicPrimalGapJuMP.jl",
))
using .ShastryFullStateSpinIsotypicPrimalGapJuMP

const SPIN_ISOTYPIC_RUNMETA_SCHEMA =
    "shastry-l1d2-full-state-spin-isotypic-mof-v1"

function spin_isotypic_source_dict()
    source = spin_spatial_source_dict()
    for file in (
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastryFullStateSpinIsotypicReduction.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastryFullStateSpinIsotypicPrimalGapJuMP.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_shastry_full_state_spin_isotypic_mof.jl",
    )
        source["files_sha256"][file] =
            file_sha256(joinpath(REPOSITORY_ROOT, file))
    end
    return source
end

function spin_isotypic_report_dict(report)
    return Dict(
        "source_moments" => report.source_moments,
        "spin_isotypic_moments" => report.spin_isotypic_moments,
        "eliminated_unused_moments" => report.eliminated_unused_moments,
        "positive_block_dimensions" => report.positive_block_dimensions,
        "gap_block_dimensions" => report.gap_block_dimensions,
        "equality_count" => report.equality_count,
        "psd_triangle_entries" => report.psd_triangle_entries,
        "maximum_side" => report.maximum_side,
    )
end

function spin_isotypic_truth_dict(truth)
    return Dict(
        "exact" => truth.exact,
        "trivial_blocks_exact" => truth.trivial_blocks_exact,
        "nontrivial_positive_orbits_exact" =>
            truth.nontrivial_positive_orbits_exact,
        "nontrivial_gap_orbits_exact" =>
            truth.nontrivial_gap_orbits_exact,
        "nontrivial_comparison_count" =>
            truth.nontrivial_comparison_count,
        "retained_block_dimensions" =>
            truth.retained_block_dimensions,
        "expected_block_dimensions" =>
            truth.expected_block_dimensions,
    )
end

function verify_reloaded_spin_isotypic_model(
    model::JuMP.Model,
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly,
)
    report =
        shastry_full_state_spin_isotypic_reduced_assembly_report(assembly)
    JuMP.num_variables(model) == report.spin_isotypic_moments ||
        error("MOF variable count changed during reload")
    isnothing(JuMP.constraint_by_name(model, "normalization")) &&
        error("MOF lost normalization")
    for index in eachindex(assembly.equalities)
        name = "shastry_l1d2_spin_isotypic_equality[$index]"
        isnothing(JuMP.constraint_by_name(model, name)) &&
            error("MOF lost equality $index")
    end
    for block in [assembly.positive_blocks; assembly.gap_blocks]
        name = shastry_full_state_spin_isotypic_block_name(block)
        reference = JuMP.constraint_by_name(model, name)
        isnothing(reference) && error("MOF lost PSD block $name")
        set = JuMP.constraint_object(reference).set
        set isa JuMP.MOI.PositiveSemidefiniteConeTriangle ||
            error("$name changed cone type during reload")
        set.side_dimension == length(block.rows) ||
            error("$name changed side dimension during reload")
    end
    return true
end

function spin_isotypic_main(arguments::Vector{String}=ARGS)
    options = parse_args(arguments)
    isnothing(options) && return
    source = spin_isotypic_source_dict()
    mkpath(options.output)
    checkpoint_path = joinpath(options.output, "runmeta.toml")
    metadata = Dict(
        "schema_version" => SPIN_ISOTYPIC_RUNMETA_SCHEMA,
        "state" => "running",
        "created_at_utc" => Dates.format(
            now(UTC),
            dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        ),
        "mode" => string(options.mode),
        "output_relative" => options.output_relative,
        "source" => source,
        "setup" => Dict(
            "hamiltonian" =>
                "H=sum_dimer S_i.S_j + g sum_square_nn S_i.S_j",
            "model" => "shastry-sutherland",
            "g_square_over_dimer" => rational_dict(options.coupling),
            "gamma" => rational_dict(options.gamma),
            "patch_level" => 1,
            "degree_d" => 2,
            "basis" => "complete-state-polynomial-v1",
            "stationarity" => "complete-inner-state-v1",
            "physical_boundary_condition" =>
                "none-local-consistency-window",
            "state_class" => "unrestricted",
            "exact_additional_reduction" =>
                "spin-S3-moment-quotient-and-isotypic-cone-blocking",
        ),
        "stages" => Dict{String,Any}(),
    )
    write_checkpoint(checkpoint_path, metadata)

    progress("assemble complete L=1,d=2 state-polynomial primal")
    problem = GapProblem(
        square_patch_geometry(1),
        shastry_sutherland_model(options.coupling),
        options.gamma,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:full_state_polynomial, 1),
    )
    primal_measurement = @timed assemble_primal_gap(
        problem;
        stationarity_spec=StationaritySpec(:full_inner_state, 1),
    )
    primal = primal_measurement.value
    metadata["stages"]["primal"] = measurement_dict(primal_measurement)
    metadata["primal"] = Dict(
        "assembly_sha256" => primal.assembly_sha256,
        "problem_sha256" => primal.problem_sha256,
        "positive_dimension" => length(primal.positive_basis.entries),
        "gap_dimension" => length(primal.gap_basis.entries),
        "moment_count" => length(primal.moments),
        "stationarity_equality_count" =>
            length(primal.stationarity_equalities),
    )
    write_checkpoint(checkpoint_path, metadata)

    progress("exact V4, conjugation, anti-diagonal, and spin quotient")
    v4_measurement = @timed assemble_full_state_v4_reduced_primal(primal)
    v4 = v4_measurement.value
    metadata["stages"]["v4"] = measurement_dict(v4_measurement)
    real_measurement = @timed assemble_full_state_real_reduced_primal(v4)
    real_reduced = real_measurement.value
    metadata["stages"]["conjugation"] =
        measurement_dict(real_measurement)
    spatial_measurement =
        @timed assemble_shastry_full_state_spatial_reduced_primal(real_reduced)
    spatial = spatial_measurement.value
    metadata["stages"]["spatial"] = measurement_dict(spatial_measurement)
    spin_measurement =
        @timed assemble_shastry_full_state_spin_spatial_reduced_primal(spatial)
    spin_spatial = spin_measurement.value
    metadata["stages"]["spin_spatial"] =
        measurement_dict(spin_measurement)
    metadata["spin_spatial_truth"] =
        spin_spatial_truth_dict(something(spin_spatial.truth))
    write_checkpoint(checkpoint_path, metadata)

    progress("exact S3 isotypic cone blocking")
    isotypic_measurement =
        @timed assemble_shastry_full_state_spin_isotypic_reduced_primal(
            spin_spatial,
        )
    isotypic = isotypic_measurement.value
    report =
        shastry_full_state_spin_isotypic_reduced_assembly_report(isotypic)
    metadata["stages"]["spin_isotypic"] =
        measurement_dict(isotypic_measurement)
    metadata["reduced"] = spin_isotypic_report_dict(report)
    metadata["reduced"]["assembly_sha256"] = isotypic.assembly_sha256
    metadata["reduced"]["coefficient_map_sha256"] =
        isotypic.coefficient_map_sha256
    metadata["spin_isotypic_truth"] =
        spin_isotypic_truth_dict(something(isotypic.truth))
    write_checkpoint(checkpoint_path, metadata)

    if options.mode == :mof
        progress("materialize, write, and reload optimizer-free MOF")
        jump_measurement =
            @timed build_shastry_full_state_spin_isotypic_jump_primal(
                isotypic,
            )
        jump_model = jump_measurement.value
        metadata["stages"]["jump"] = measurement_dict(jump_measurement)
        write_checkpoint(checkpoint_path, metadata)
        mof_path = joinpath(options.output, "model.mof.json")
        write_measurement =
            @timed JuMP.write_to_file(jump_model.model, mof_path)
        metadata["stages"]["write_mof"] =
            measurement_dict(write_measurement)
        metadata["mof_sha256"] = file_sha256(mof_path)
        replay_measurement = @timed JuMP.read_from_file(mof_path)
        verify_reloaded_spin_isotypic_model(
            replay_measurement.value,
            isotypic,
        )
        metadata["stages"]["reload_mof"] =
            measurement_dict(replay_measurement)
    end

    metadata["state"] = "complete"
    metadata["completed_at_utc"] = Dates.format(
        now(UTC),
        dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
    )
    write_checkpoint(checkpoint_path, metadata)
    progress("complete")
end

if abspath(PROGRAM_FILE) == @__FILE__
    spin_isotypic_main()
end
