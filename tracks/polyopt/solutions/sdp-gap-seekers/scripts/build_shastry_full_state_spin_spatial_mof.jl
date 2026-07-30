#!/usr/bin/env julia

# Reuse the ratified full-state setup and its serialization helpers. Including
# this file does not invoke its main entrypoint.
include(joinpath(@__DIR__, "build_shastry_full_state_spatial_mof.jl"))
include(joinpath(
    TRACK_ROOT,
    "src",
    "ShastryFullStateSpinSpatialReduction.jl",
))
using .ShastryFullStateSpinSpatialReduction
include(joinpath(
    TRACK_ROOT,
    "src",
    "ShastryFullStateSpinSpatialPrimalGapJuMP.jl",
))
using .ShastryFullStateSpinSpatialPrimalGapJuMP
include(joinpath(
    TRACK_ROOT,
    "src",
    "ShastryFullStateSpinSpatialOracle.jl",
))
using .ShastryFullStateSpinSpatialOracle

const SPIN_SPATIAL_RUNMETA_SCHEMA =
    "shastry-l1d2-full-state-spin-spatial-mof-v1"

function spin_spatial_source_dict()
    files = [
        "tracks/polyopt/solutions/sdp-gap-seekers/src/SquareJ1J2Prototype.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/GenericGapModel.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapSymbolics.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapAssembly.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapJuMP.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ExactSymmetryReduction.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ReducedPrimalGapAssembly.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ConjugationSymmetryReduction.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/FullStateSymmetryReduction.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastryFullStateSpatialReduction.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastryFullStateSpatialPrimalGapJuMP.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastryFullStateSpinSpatialReduction.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastryFullStateSpinSpatialPrimalGapJuMP.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastrySutherlandOracle.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastrySutherlandPrimalOracle.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastryFullStateSpatialOracle.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastryFullStateSpinSpatialOracle.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_shastry_full_state_spatial_mof.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_shastry_full_state_spin_spatial_mof.jl",
    ]
    dirty = git_output("status", "--porcelain", "--untracked-files=all")
    isempty(dirty) ||
        error("refusing to build from a dirty checkout")
    return Dict(
        "git_commit" => git_output("rev-parse", "HEAD"),
        "git_tree" => git_output("rev-parse", "HEAD^{tree}"),
        "git_branch" => git_output("symbolic-ref", "--short", "HEAD"),
        "files_sha256" => Dict(
            file => file_sha256(joinpath(REPOSITORY_ROOT, file))
            for file in files
        ),
    )
end

function spin_spatial_report_dict(report)
    return Dict(
        "source_moments" => report.source_moments,
        "spin_spatial_moments" => report.spin_spatial_moments,
        "eliminated_spin_moments" => report.eliminated_spin_moments,
        "positive_block_dimensions" =>
            report.positive_block_dimensions,
        "gap_block_dimensions" => report.gap_block_dimensions,
        "equality_count" => report.equality_count,
        "psd_triangle_entries" => report.psd_triangle_entries,
        "maximum_side" => report.maximum_side,
    )
end

function spin_spatial_truth_dict(truth)
    source = something(truth.source_truth)
    return Dict(
        "exact" => truth.exact,
        "source_covariance_exact" => truth.source_covariance_exact,
        "equality_space_invariant" => truth.equality_space_invariant,
        "source_moments" => truth.source_moments,
        "quotient_moments" => truth.quotient_moments,
        "eliminated_moments" => truth.eliminated_moments,
        "hamiltonian_invariant" => source.hamiltonian_invariant,
        "row_actions_close" => source.row_actions_close,
        "coefficient_covariant" => source.coefficient_covariant,
        "coefficient_count" => source.coefficient_count,
        "source_equality_space_invariant" =>
            source.equality_space_invariant,
    )
end

function verify_reloaded_spin_spatial_model(
    model::JuMP.Model,
    assembly::ShastryFullStateSpinSpatialReducedPrimalAssembly,
)
    report =
        shastry_full_state_spin_spatial_reduced_assembly_report(assembly)
    JuMP.num_variables(model) == report.spin_spatial_moments ||
        error("MOF variable count changed during reload")
    isnothing(JuMP.constraint_by_name(model, "normalization")) &&
        error("MOF lost normalization")
    for index in eachindex(assembly.equalities)
        name = "shastry_l1d2_spin_spatial_equality[$index]"
        isnothing(JuMP.constraint_by_name(model, name)) &&
            error("MOF lost equality $index")
    end
    for block in [assembly.positive_blocks; assembly.gap_blocks]
        name = shastry_full_state_spin_spatial_block_name(block)
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

function spin_spatial_main(arguments::Vector{String}=ARGS)
    options = parse_args(arguments)
    isnothing(options) && return
    source = spin_spatial_source_dict()
    mkpath(options.output)
    checkpoint_path = joinpath(options.output, "runmeta.toml")
    metadata = Dict(
        "schema_version" => SPIN_SPATIAL_RUNMETA_SCHEMA,
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
                "proper-spin-axis-permutations-S3-after-anti-diagonal",
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

    progress("exact centered/scalar and V4 reduction")
    v4_measurement =
        @timed assemble_full_state_v4_reduced_primal(primal)
    v4 = v4_measurement.value
    metadata["stages"]["v4"] = measurement_dict(v4_measurement)
    write_checkpoint(checkpoint_path, metadata)

    progress("exact conjugation realification")
    real_measurement =
        @timed assemble_full_state_real_reduced_primal(v4)
    real_reduced = real_measurement.value
    metadata["stages"]["conjugation"] =
        measurement_dict(real_measurement)
    write_checkpoint(checkpoint_path, metadata)

    progress("target-specific anti-diagonal truth and quotient")
    spatial_measurement =
        @timed assemble_shastry_full_state_spatial_reduced_primal(
            real_reduced,
        )
    spatial = spatial_measurement.value
    metadata["stages"]["spatial"] =
        measurement_dict(spatial_measurement)
    write_checkpoint(checkpoint_path, metadata)

    progress("exact proper spin-axis covariance and moment quotient")
    spin_measurement =
        @timed assemble_shastry_full_state_spin_spatial_reduced_primal(
            spatial,
        )
    spin_spatial = spin_measurement.value
    report =
        shastry_full_state_spin_spatial_reduced_assembly_report(
            spin_spatial,
        )
    metadata["stages"]["spin_spatial"] =
        measurement_dict(spin_measurement)
    metadata["reduced"] = spin_spatial_report_dict(report)
    metadata["reduced"]["assembly_sha256"] =
        spin_spatial.assembly_sha256
    metadata["reduced"]["coefficient_map_sha256"] =
        spin_spatial.coefficient_map_sha256
    metadata["spin_spatial_truth"] =
        spin_spatial_truth_dict(something(spin_spatial.truth))
    write_checkpoint(checkpoint_path, metadata)

    if iszero(options.coupling)
        progress("analytic g=0 dimer truth on every final PSD block")
        oracle_measurement =
            @timed evaluate_shastry_spin_spatial_dimer_primal(
                spin_spatial,
            )
        oracle = oracle_measurement.value
        oracle.equalities_exact_zero ||
            error("g=0 dimer oracle violates a reduced equality")
        oracle.positive_minimum >= -1e-9 ||
            error("g=0 dimer oracle violates the positive cone")
        oracle.gap_minimum >= -1e-9 ||
            error("g=0 dimer oracle violates the gap cone")
        metadata["stages"]["dimer_oracle"] =
            measurement_dict(oracle_measurement)
        metadata["dimer_oracle"] = Dict(
            "equalities_exact_zero" => oracle.equalities_exact_zero,
            "positive_minimum" => oracle.positive_minimum,
            "gap_minimum" => oracle.gap_minimum,
            "positive_block_minima" => oracle.positive_minima,
            "gap_block_minima" => oracle.gap_minima,
        )
        write_checkpoint(checkpoint_path, metadata)
    end

    if options.mode == :mof
        progress("materialize optimizer-free real PSD JuMP model")
        jump_measurement =
            @timed build_shastry_full_state_spin_spatial_jump_primal(
                spin_spatial,
            )
        jump_model = jump_measurement.value
        metadata["stages"]["jump"] =
            measurement_dict(jump_measurement)
        write_checkpoint(checkpoint_path, metadata)

        progress("write and reload MOF")
        mof_path = joinpath(options.output, "model.mof.json")
        write_measurement =
            @timed JuMP.write_to_file(jump_model.model, mof_path)
        metadata["stages"]["write_mof"] =
            measurement_dict(write_measurement)
        metadata["mof_sha256"] = file_sha256(mof_path)
        replay_measurement = @timed JuMP.read_from_file(mof_path)
        verify_reloaded_spin_spatial_model(
            replay_measurement.value,
            spin_spatial,
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
    spin_spatial_main()
end
