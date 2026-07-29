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
using MosekTools

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
        "retained_block_dimensions" =>
            truth.retained_block_dimensions,
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
        "schema_version" => options.patch_level == 1 ?
            SPIN_ISOTYPIC_RUNMETA_SCHEMA :
            "shastry-l$(options.patch_level)d2-full-state-spin-isotypic-preflight-v1",
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
            "patch_level" => options.patch_level,
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
        "intermediate_truth_mode" => options.patch_level == 1 ?
            "exhaustive-coefficient-gates" :
            "preflight-structural-assembly-final-isotypic-gate",
    )
    write_checkpoint(checkpoint_path, metadata)

    progress(
        "assemble complete L=$(options.patch_level),d=2 " *
        "state-polynomial primal",
    )
    problem = GapProblem(
        square_patch_geometry(options.patch_level),
        shastry_sutherland_model(options.coupling),
        options.gamma,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:full_state_polynomial, 1),
    )
    on_demand_moments =
        options.patch_level > 1 ||
        get(ENV, "SHASTRY_ON_DEMAND_MOMENTS", "0") == "1"
    primal_measurement = @timed assemble_primal_gap(
        problem;
        stationarity_spec=StationaritySpec(:full_inner_state, 1),
        materialize_coefficients=options.patch_level == 1 &&
                                 get(
                                     ENV,
                                     "SHASTRY_STRUCTURAL_PRIMAL",
                                     "0",
                                 ) != "1",
        structural_moment_filter=options.patch_level > 1 ||
                                 get(
                                     ENV,
                                     "SHASTRY_FILTER_PRIMAL_MOMENTS",
                                     "0",
                                 ) == "1" ?
                                 :v4_conjugation_even :
                                 :all,
        materialize_moment_inventory=!on_demand_moments,
    )
    primal = primal_measurement.value
    metadata["stages"]["primal"] = measurement_dict(primal_measurement)
    metadata["primal"] = Dict(
        "assembly_sha256" => primal.assembly_sha256,
        "problem_sha256" => primal.problem_sha256,
        "positive_dimension" => length(primal.positive_basis.entries),
        "gap_dimension" => length(primal.gap_basis.entries),
        "moment_count" => length(primal.moments),
        "moment_inventory" => on_demand_moments ?
            "deferred-on-demand-v1" :
            "materialized-v1",
        "stationarity_equality_count" =>
            length(primal.stationarity_equalities),
    )
    write_checkpoint(checkpoint_path, metadata)

    progress("exact V4, conjugation, anti-diagonal, and spin quotient")
    structural_intermediate =
        options.patch_level > 1 ||
        get(ENV, "SHASTRY_STRUCTURAL_INTERMEDIATE", "0") == "1"
    exhaustive_intermediate_truth =
        options.patch_level == 1 && !structural_intermediate
    metadata["intermediate_assembly"] = structural_intermediate ?
        "structural-deferred-coefficients-v1" :
        "materialized-coefficients-v1"
    v4_measurement = @timed assemble_full_state_v4_reduced_primal(
        primal;
        verify_truth=exhaustive_intermediate_truth,
        materialize_coefficients=!structural_intermediate,
    )
    v4 = v4_measurement.value
    metadata["stages"]["v4"] = measurement_dict(v4_measurement)
    real_measurement = @timed assemble_full_state_real_reduced_primal(
        v4;
        verify_truth=exhaustive_intermediate_truth,
        materialize_coefficients=!structural_intermediate,
    )
    real_reduced = real_measurement.value
    metadata["stages"]["conjugation"] =
        measurement_dict(real_measurement)
    spatial_measurement =
        @timed assemble_shastry_full_state_spatial_reduced_primal(
            real_reduced;
            verify_truth=exhaustive_intermediate_truth,
            materialize_coefficients=!structural_intermediate,
        )
    spatial = spatial_measurement.value
    metadata["stages"]["spatial"] = measurement_dict(spatial_measurement)
    spin_measurement =
        @timed assemble_shastry_full_state_spin_spatial_reduced_primal(
            spatial;
            verify_truth=exhaustive_intermediate_truth,
            verify_source_covariance=exhaustive_intermediate_truth,
            materialize_coefficients=!structural_intermediate,
        )
    spin_spatial = spin_measurement.value
    metadata["stages"]["spin_spatial"] =
        measurement_dict(spin_measurement)
    if exhaustive_intermediate_truth
        metadata["spin_spatial_truth"] =
            spin_spatial_truth_dict(something(spin_spatial.truth))
    end
    write_checkpoint(checkpoint_path, metadata)

    materialize_isotypic_coefficients =
        options.mode in (:preflight, :mof)
    progress(
        !materialize_isotypic_coefficients ?
        "exact S3 structural cone blocking" :
        "exact S3 isotypic cone blocking",
    )
    isotypic_measurement =
        @timed assemble_shastry_full_state_spin_isotypic_reduced_primal(
            spin_spatial,
            verify_truth=exhaustive_intermediate_truth,
            materialize_coefficients=materialize_isotypic_coefficients,
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
    metadata["coefficient_inventory"] = !materialize_isotypic_coefficients ?
        "deferred-structural-v1" :
        "materialized-exact-v1"
    if !isnothing(isotypic.truth)
        metadata["spin_isotypic_truth"] =
            spin_isotypic_truth_dict(something(isotypic.truth))
    end
    write_checkpoint(checkpoint_path, metadata)

    if options.mode in (:mof, :solve)
        progress(
            options.mode == :mof ?
            "materialize, write, and reload optimizer-free MOF" :
            "stream exact coefficients directly into Mosek",
        )
        if options.mode == :solve
            threads = parse(
                Int,
                get(
                    ENV,
                    "SS_MOSEK_THREADS",
                    get(ENV, "SLURM_CPUS_PER_TASK", "1"),
                ),
            )
            time_limit_seconds = parse(
                Float64,
                get(ENV, "SS_MOSEK_TIME_LIMIT_SECONDS", "43200"),
            )
            log_level =
                parse(Int, get(ENV, "SS_MOSEK_LOG_LEVEL", "1"))
            direct_model = JuMP.direct_model(MosekTools.Optimizer())
            JuMP.set_time_limit_sec(direct_model, time_limit_seconds)
            JuMP.set_optimizer_attribute(
                direct_model,
                "MSK_IPAR_NUM_THREADS",
                threads,
            )
            JuMP.set_optimizer_attribute(
                direct_model,
                "MSK_IPAR_LOG",
                log_level,
            )
            jump_measurement = @timed(
                build_shastry_full_state_spin_isotypic_streaming_jump_primal(
                    isotypic;
                    model=direct_model,
                )
            )
        else
            jump_measurement =
                @timed build_shastry_full_state_spin_isotypic_jump_primal(
                    isotypic,
                )
        end
        jump_model = jump_measurement.value
        metadata["stages"]["jump"] = measurement_dict(jump_measurement)
        if options.mode == :solve
            metadata["reduced"]["spin_isotypic_moments"] =
                length(jump_model.moment_variables)
            metadata["reduced"]["coefficient_map_sha256"] =
                jump_model.coefficient_map_sha256
            metadata["reduced"]["assembly_sha256"] =
                jump_model.assembly_sha256
            metadata["coefficient_inventory"] =
                "streamed-direct-to-solver-v1"
        end
        write_checkpoint(checkpoint_path, metadata)
    end

    if options.mode == :mof
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
    elseif options.mode == :solve
        progress(
            "optimize direct Mosek model; threads=$threads, " *
            "time_limit=$(time_limit_seconds)s",
        )
        solve_measurement = @timed JuMP.optimize!(jump_model.model)
        metadata["stages"]["solve"] = measurement_dict(solve_measurement)
        metadata["solve"] = Dict(
            "termination_status" =>
                string(JuMP.termination_status(jump_model.model)),
            "primal_status" => string(JuMP.primal_status(jump_model.model)),
            "dual_status" => string(JuMP.dual_status(jump_model.model)),
            "raw_status" => try
                JuMP.raw_status(jump_model.model)
            catch exception
                "unavailable: " * sprint(showerror, exception)
            end,
            "result_count" => JuMP.result_count(jump_model.model),
            "has_values" => JuMP.has_values(jump_model.model),
            "has_duals" => JuMP.has_duals(jump_model.model),
            "solver_reported_solve_time_seconds" => try
                JuMP.solve_time(jump_model.model)
            catch
                NaN
            end,
            "threads" => threads,
            "time_limit_seconds" => time_limit_seconds,
        )
        write_checkpoint(checkpoint_path, metadata)
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
