include(joinpath(@__DIR__, "..", "src", "ExactSymmetryReduction.jl"))
using .ExactSymmetryReduction
include(joinpath(@__DIR__, "..", "src", "ReducedPrimalGapAssembly.jl"))
using .ReducedPrimalGapAssembly
include(joinpath(@__DIR__, "..", "src", "ReducedPrimalGapJuMP.jl"))
using .ReducedPrimalGapJuMP
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "ConjugationSymmetryReduction.jl",
))
using .ConjugationSymmetryReduction
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "ConjugationReducedPrimalGapJuMP.jl",
))
using .ConjugationReducedPrimalGapJuMP
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "SpinAxisInvolutionReduction.jl",
))
using .SpinAxisInvolutionReduction
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "SpinAxisInvolutionPrimalGapJuMP.jl",
))
using .SpinAxisInvolutionPrimalGapJuMP
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "FullSpinPermutationReduction.jl",
))
using .FullSpinPermutationReduction
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "FullSpinPermutationPrimalGapJuMP.jl",
))
using .FullSpinPermutationPrimalGapJuMP
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "FullSpinConeReduction.jl",
))
using .FullSpinConeReduction
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "FullSpinConeReducedPrimalGapJuMP.jl",
))
using .FullSpinConeReducedPrimalGapJuMP
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "FullSpinIsotypicReduction.jl",
))
using .FullSpinIsotypicReduction
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "FullSpinIsotypicPrimalGapJuMP.jl",
))
using .FullSpinIsotypicPrimalGapJuMP
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "FullStateSymmetryReduction.jl",
))
using .FullStateSymmetryReduction
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "ShastryFullStateSpatialReduction.jl",
))
using .ShastryFullStateSpatialReduction
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "ShastryFullStateSpatialPrimalGapJuMP.jl",
))
using .ShastryFullStateSpatialPrimalGapJuMP
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "ShastryFullStateSpinSpatialReduction.jl",
))
using .ShastryFullStateSpinSpatialReduction
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "ShastryFullStateSpinSpatialPrimalGapJuMP.jl",
))
using .ShastryFullStateSpinSpatialPrimalGapJuMP
using JuMP

@testset "exact M/K/V4 reduction truth" begin
    problem = GapProblem(
        square_patch_geometry(1),
        shastry_sutherland_model(4//5),
        1//2,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:one_symbol_lift, 1),
    )
    assembly = assemble_primal_gap(problem)

    positive_truth = positive_reduction_truth(assembly.positive_basis)
    @test positive_truth.exact
    @test positive_truth.centered_formula_exact
    @test positive_truth.scalar_formula_exact
    @test positive_truth.original_dimension == 703
    @test positive_truth.centered_dimension == 351
    @test positive_truth.scalar_dimension == 352
    @test positive_truth.original_upper_entries == 247_456
    @test positive_truth.centered_scalar_upper_entries == 123_904
    @test positive_truth.v4_upper_entries == 31_807
    @test sort(collect(values(positive_truth.centered_block_sizes))) ==
          [81, 81, 81, 108]
    @test sort(collect(values(positive_truth.scalar_block_sizes))) ==
          [81, 81, 81, 109]

    gap_truth = gap_facial_reduction_truth(assembly)
    @test gap_truth.exact
    @test gap_truth.original_dimension == 7
    @test gap_truth.active_dimension == 3
    @test gap_truth.null_dimension == 4
    @test gap_truth.cross_polynomial_count > 0
    @test gap_truth.cross_equality_count > 0

    moment_truth = invariant_moment_inventory(assembly.moments)
    @test moment_truth.original_count == 74_602
    @test moment_truth.invariant_count == 19_108
    @test moment_truth.eliminated_count == 55_494
    @test sort(collect(values(moment_truth.by_character))) ==
          [18_498, 18_498, 18_498, 19_108]

    reduced = assemble_reduced_primal(assembly)
    repeated = assemble_reduced_primal(assembly; verify_truth=false)
    report = reduced_assembly_report(reduced)
    @test report.source_moments == 74_602
    @test report.reduced_moments == 19_108
    @test report.eliminated_moments == 55_494
    @test sort(report.positive_block_dimensions) ==
          [81, 81, 81, 81, 81, 81, 108, 109]
    @test report.gap_block_dimensions == [1, 1, 1]
    @test report.equality_count == 3
    @test reduced.coefficient_map_sha256 ==
          repeated.coefficient_map_sha256
    @test reduced.assembly_sha256 == repeated.assembly_sha256

    jump_model = build_reduced_jump_primal(reduced)
    @test JuMP.num_variables(jump_model.model) == 19_108
    @test length(jump_model.equality_constraints) == 3
    @test length(jump_model.psd_constraints) == 11
    @test sort(collect(
        JuMP.constraint_object(constraint).set.side_dimension
        for constraint in jump_model.psd_constraints
    )) == [1, 1, 1, 81, 81, 81, 81, 81, 81, 108, 109]
    @test jump_model.assembly_sha256 == reduced.assembly_sha256

    conjugation_truth = conjugation_reduction_truth(reduced)
    @test conjugation_truth.exact
    @test conjugation_truth.hamiltonian_invariant
    @test conjugation_truth.coefficient_covariant
    @test conjugation_truth.coefficient_count == 31_810
    @test conjugation_truth.realified_coefficients_real
    @test conjugation_truth.equality_space_invariant

    real_reduced = assemble_conjugation_reduced_primal(reduced)
    real_repeated = assemble_conjugation_reduced_primal(
        reduced;
        verify_truth=false,
    )
    real_report = conjugation_reduced_assembly_report(real_reduced)
    @test real_report.source_moments == 74_602
    @test real_report.v4_moments == 19_108
    @test real_report.real_moments < real_report.v4_moments
    @test real_report.eliminated_conjugation_odd_moments > 0
    @test real_report.positive_block_dimensions ==
          report.positive_block_dimensions
    @test real_report.gap_block_dimensions == report.gap_block_dimensions
    @test real_report.equality_count <= report.equality_count
    @test real_report.real_psd_triangle_entries == 31_810
    @test real_report.generic_hermitian_bridge_triangle_entries == 126_525
    @test all(
        key -> !conjugation_odd(key),
        real_reduced.moments,
    )
    @test real_reduced.coefficient_map_sha256 ==
          real_repeated.coefficient_map_sha256
    @test real_reduced.assembly_sha256 == real_repeated.assembly_sha256

    real_jump_model =
        build_conjugation_reduced_jump_primal(real_reduced)
    @test JuMP.num_variables(real_jump_model.model) ==
          real_report.real_moments
    @test length(real_jump_model.equality_constraints) ==
          real_report.equality_count
    @test length(real_jump_model.psd_constraints) == 11
    @test sort(collect(
        JuMP.constraint_object(constraint).set.side_dimension
        for constraint in real_jump_model.psd_constraints
    )) == [1, 1, 1, 81, 81, 81, 81, 81, 81, 108, 109]
    @test all(
        JuMP.constraint_object(constraint).set isa
        JuMP.MOI.PositiveSemidefiniteConeTriangle
        for constraint in real_jump_model.psd_constraints
    )
    @test real_jump_model.assembly_sha256 == real_reduced.assembly_sha256

    general_v4 = assemble_full_state_v4_reduced_primal(assembly)
    general_v4_truth = full_state_v4_reduction_truth(assembly)
    general_v4_report = full_state_v4_reduced_assembly_report(general_v4)
    @test general_v4_truth.exact
    @test general_v4_truth.original_positive_dimension == 703
    @test general_v4_truth.centered_dimension == 351
    @test general_v4_truth.scalar_dimension == 352
    @test general_v4.moments == reduced.moments
    @test general_v4.equalities == reduced.equalities
    @test general_v4_report.positive_block_dimensions ==
          report.positive_block_dimensions
    @test general_v4_report.gap_block_dimensions ==
          report.gap_block_dimensions
    @test length(general_v4.positive_blocks) ==
          length(reduced.positive_blocks)
    @test length(general_v4.gap_blocks) == length(reduced.gap_blocks)
    for (general_block, legacy_block) in zip(
        [general_v4.positive_blocks; general_v4.gap_blocks],
        [reduced.positive_blocks; reduced.gap_blocks],
    )
        @test general_block.role == legacy_block.role
        @test general_block.family == legacy_block.family
        @test general_block.character == legacy_block.character
        @test length(general_block.rows) == length(legacy_block.rows)
        for index in eachindex(general_block.rows)
            general_row = general_block.rows[index]
            legacy_row = legacy_block.rows[index]
            expected_source = if legacy_row.family == :scalar
                scalar_row(legacy_row.word)
            else
                bare_row(legacy_row.word)
            end
            @test general_row.source == expected_source
        end
        for row in eachindex(general_block.rows)
            for column in row:length(general_block.rows)
                @test full_state_v4_block_entry(
                    general_v4,
                    general_block,
                    general_block.rows[row],
                    general_block.rows[column],
                ) == reduced_block_entry(
                    reduced,
                    legacy_block,
                    legacy_block.rows[row],
                    legacy_block.rows[column],
                )
            end
        end
    end

    general_real = assemble_full_state_real_reduced_primal(general_v4)
    general_real_truth =
        full_state_conjugation_reduction_truth(general_v4)
    general_real_report =
        full_state_real_reduced_assembly_report(general_real)
    @test general_real_truth.exact
    @test general_real_truth.coefficient_count == 31_810
    @test general_real.moments == real_reduced.moments
    @test general_real.equalities == real_reduced.equalities
    @test general_real_report.positive_block_dimensions ==
          real_report.positive_block_dimensions
    @test general_real_report.gap_block_dimensions ==
          real_report.gap_block_dimensions
    for (general_block, legacy_block) in zip(
        [general_real.positive_blocks; general_real.gap_blocks],
        [real_reduced.source.positive_blocks; real_reduced.source.gap_blocks],
    )
        for row in eachindex(general_block.rows)
            for column in row:length(general_block.rows)
                @test full_state_real_block_entry(
                    general_real,
                    general_block,
                    general_block.rows[row],
                    general_block.rows[column],
                ) == conjugation_real_block_entry(
                    real_reduced,
                    legacy_block,
                    legacy_block.rows[row],
                    legacy_block.rows[column],
                )
            end
        end
    end

    shastry_spatial_truth =
        shastry_spatial_reduction_truth(general_real)
    @test shastry_spatial_truth.exact
    @test shastry_spatial_truth.hamiltonian_invariant
    @test shastry_spatial_truth.equality_space_invariant
    @test shastry_spatial_truth.row_actions_close
    @test shastry_spatial_truth.coefficient_covariant
    @test shastry_spatial_truth.coefficient_count == 31_810
    @test shastry_spatial_truth.split_cross_zero
    @test shastry_spatial_truth.split_cross_count > 0
    general_spatial =
        assemble_shastry_full_state_spatial_reduced_primal(
            general_real;
            verify_truth=false,
        )
    general_spatial_repeated =
        assemble_shastry_full_state_spatial_reduced_primal(
            general_real;
            verify_truth=false,
        )
    general_spatial_report =
        shastry_full_state_spatial_reduced_assembly_report(
            general_spatial,
        )
    @test general_spatial_report.source_moments ==
          length(general_real.moments)
    @test general_spatial_report.spatial_moments <
          general_spatial_report.source_moments
    @test general_spatial_report.psd_triangle_entries <
          general_real_report.real_triangle_entries
    @test general_spatial.coefficient_map_sha256 ==
          general_spatial_repeated.coefficient_map_sha256
    @test general_spatial.assembly_sha256 ==
          general_spatial_repeated.assembly_sha256
    general_spatial_jump =
        build_shastry_full_state_spatial_jump_primal(
            general_spatial,
        )
    @test JuMP.num_variables(general_spatial_jump.model) ==
          general_spatial_report.spatial_moments
    @test length(general_spatial_jump.equality_constraints) ==
          general_spatial_report.equality_count
    @test length(general_spatial_jump.psd_constraints) ==
          length(general_spatial.positive_blocks) +
          length(general_spatial.gap_blocks)
    @test sort(collect(
        JuMP.constraint_object(constraint).set.side_dimension
        for constraint in general_spatial_jump.psd_constraints
    )) == sort([
        general_spatial_report.positive_block_dimensions;
        general_spatial_report.gap_block_dimensions
    ])
    @test all(
        JuMP.constraint_object(constraint).set isa
        JuMP.MOI.PositiveSemidefiniteConeTriangle
        for constraint in general_spatial_jump.psd_constraints
    )
    @test general_spatial_jump.assembly_sha256 ==
          general_spatial.assembly_sha256

    spin_axis_truth = spin_axis_reduction_truth(real_reduced)
    @test spin_axis_truth.exact
    @test spin_axis_truth.hamiltonian_invariant
    @test spin_axis_truth.coefficient_covariant
    @test spin_axis_truth.coefficient_count == 31_810
    @test spin_axis_truth.stable_cross_blocks_zero
    @test spin_axis_truth.stable_cross_entry_count == 8_460
    @test spin_axis_truth.equality_space_invariant

    spin_axis_reduced = assemble_spin_axis_reduced_primal(
        real_reduced;
        verify_truth=false,
    )
    spin_axis_repeated = assemble_spin_axis_reduced_primal(
        real_reduced;
        verify_truth=false,
    )
    spin_axis_report =
        spin_axis_reduced_assembly_report(spin_axis_reduced)
    @test spin_axis_report.source_moments == 74_602
    @test spin_axis_report.v4_moments == 19_108
    @test spin_axis_report.conjugation_real_moments ==
          real_report.real_moments
    @test spin_axis_report.spin_axis_moments <
          spin_axis_report.conjugation_real_moments
    @test spin_axis_report.eliminated_spin_axis_moments > 0
    @test spin_axis_report.forced_zero_moments == 0
    @test spin_axis_report.positive_block_dimensions ==
          [72, 36, 81, 36, 45, 73, 36, 81, 36, 45]
    @test spin_axis_report.gap_block_dimensions == [1, 1]
    @test spin_axis_report.equality_count == 0
    @test spin_axis_report.real_psd_triangle_entries == 16_707
    @test spin_axis_report.maximum_psd_side_dimension == 81
    @test spin_axis_reduced.coefficient_map_sha256 ==
          spin_axis_repeated.coefficient_map_sha256
    @test spin_axis_reduced.assembly_sha256 ==
          spin_axis_repeated.assembly_sha256

    spin_axis_jump_model =
        build_spin_axis_reduced_jump_primal(spin_axis_reduced)
    @test JuMP.num_variables(spin_axis_jump_model.model) ==
          spin_axis_report.spin_axis_moments
    @test isempty(spin_axis_jump_model.equality_constraints)
    @test length(spin_axis_jump_model.psd_constraints) == 12
    @test sort(collect(
        JuMP.constraint_object(constraint).set.side_dimension
        for constraint in spin_axis_jump_model.psd_constraints
    )) == [1, 1, 36, 36, 36, 36, 45, 45, 72, 73, 81, 81]
    @test all(
        JuMP.constraint_object(constraint).set isa
        JuMP.MOI.PositiveSemidefiniteConeTriangle
        for constraint in spin_axis_jump_model.psd_constraints
    )
    @test spin_axis_jump_model.assembly_sha256 ==
          spin_axis_reduced.assembly_sha256
    println(
        "[spin-axis-truth] moments=",
        spin_axis_report.spin_axis_moments,
        ", eliminated=",
        spin_axis_report.eliminated_spin_axis_moments,
        ", forced_zero=",
        spin_axis_report.forced_zero_moments,
        ", psd_entries=",
        spin_axis_report.real_psd_triangle_entries,
    )
    flush(stdout)

    full_spin_truth = full_spin_permutation_truth(real_reduced)
    @test full_spin_truth.exact
    @test full_spin_truth.hamiltonian_invariant
    @test full_spin_truth.coefficient_covariant
    @test full_spin_truth.coefficient_check_count == 6 * 31_810
    @test full_spin_truth.conjugation_inventory_closed
    @test full_spin_truth.conjugation_action_unsigned
    @test full_spin_truth.equality_space_invariant
    @test full_spin_truth.source_moment_count == 16_660
    @test full_spin_truth.quotient_moment_count <
          spin_axis_report.spin_axis_moments
    @test full_spin_truth.eliminated_moment_count > 7_857
    println(
        "[full-spin-truth] moments=",
        full_spin_truth.quotient_moment_count,
        ", eliminated=",
        full_spin_truth.eliminated_moment_count,
        ", coefficient_checks=",
        full_spin_truth.coefficient_check_count,
    )
    flush(stdout)

    full_spin_reduced = assemble_full_spin_reduced_primal(
        spin_axis_reduced;
        verify_truth=false,
    )
    full_spin_repeated = assemble_full_spin_reduced_primal(
        spin_axis_reduced;
        verify_truth=false,
    )
    full_spin_report =
        full_spin_reduced_assembly_report(full_spin_reduced)
    @test full_spin_report.source_moments == 74_602
    @test full_spin_report.v4_moments == 19_108
    @test full_spin_report.conjugation_real_moments == 16_660
    @test full_spin_report.spin_axis_moments == 8_803
    @test full_spin_report.full_spin_moments == 3_250
    @test full_spin_report.eliminated_from_conjugation == 13_410
    @test full_spin_report.eliminated_from_spin_axis == 5_553
    @test full_spin_report.positive_block_dimensions ==
          spin_axis_report.positive_block_dimensions
    @test full_spin_report.gap_block_dimensions == [1, 1]
    @test full_spin_report.equality_count == 0
    @test full_spin_report.real_psd_triangle_entries == 16_707
    @test full_spin_report.maximum_psd_side_dimension == 81
    @test full_spin_reduced.coefficient_map_sha256 ==
          full_spin_repeated.coefficient_map_sha256
    @test full_spin_reduced.assembly_sha256 ==
          full_spin_repeated.assembly_sha256

    full_spin_jump_model =
        build_full_spin_reduced_jump_primal(full_spin_reduced)
    @test JuMP.num_variables(full_spin_jump_model.model) == 3_250
    @test isempty(full_spin_jump_model.equality_constraints)
    @test length(full_spin_jump_model.psd_constraints) == 12
    @test sort(collect(
        JuMP.constraint_object(constraint).set.side_dimension
        for constraint in full_spin_jump_model.psd_constraints
    )) == [1, 1, 36, 36, 36, 36, 45, 45, 72, 73, 81, 81]
    @test all(
        JuMP.constraint_object(constraint).set isa
        JuMP.MOI.PositiveSemidefiniteConeTriangle
        for constraint in full_spin_jump_model.psd_constraints
    )
    @test full_spin_jump_model.assembly_sha256 ==
          full_spin_reduced.assembly_sha256

    cone_truth =
        full_spin_nontrivial_cone_redundancy_truth(full_spin_reduced)
    @test cone_truth.exact
    @test cone_truth.orbit_block_count == 3
    @test cone_truth.orbit_block_dimensions == [1, 81, 81]
    @test cone_truth.orbit_projection_exact
    @test cone_truth.orbit_congruence_exact
    @test cone_truth.orbit_entry_count == 6_643
    @test cone_truth.stable_cross_blocks_zero
    @test cone_truth.stable_cross_entry_count == 3_240
    @test cone_truth.stable_bases_invertible
    @test cone_truth.stable_basis_dimensions == [1, 81, 81]
    @test cone_truth.gauge_phases_well_formed
    @test cone_truth.gauge_phase_classes_aligned
    @test cone_truth.gauge_mixed_entries_zero
    @test cone_truth.gauge_mixed_entry_count == 0

    cone_reduced = assemble_full_spin_cone_reduced_primal(
        full_spin_reduced;
        verify_truth=false,
    )
    cone_repeated = assemble_full_spin_cone_reduced_primal(
        full_spin_reduced;
        verify_truth=false,
    )
    cone_report =
        full_spin_cone_reduced_assembly_report(cone_reduced)
    @test cone_report.source_full_spin_moments == 3_250
    @test cone_report.cone_reduced_moments <= 3_250
    @test cone_report.eliminated_unused_moments >= 0
    @test cone_report.removed_orbit_cones == 3
    @test cone_report.positive_block_dimensions ==
          [72, 36, 36, 45, 73, 36, 36, 45]
    @test cone_report.gap_block_dimensions == [1]
    @test cone_report.equality_count == 0
    @test cone_report.real_psd_triangle_entries == 10_064
    @test cone_report.maximum_psd_side_dimension == 73
    @test cone_reduced.coefficient_map_sha256 ==
          cone_repeated.coefficient_map_sha256
    @test cone_reduced.assembly_sha256 ==
          cone_repeated.assembly_sha256

    cone_jump_model =
        build_full_spin_cone_reduced_jump_primal(cone_reduced)
    @test JuMP.num_variables(cone_jump_model.model) ==
          cone_report.cone_reduced_moments
    @test isempty(cone_jump_model.equality_constraints)
    @test length(cone_jump_model.psd_constraints) == 9
    @test sort(collect(
        JuMP.constraint_object(constraint).set.side_dimension
        for constraint in cone_jump_model.psd_constraints
    )) == [1, 36, 36, 36, 36, 45, 45, 72, 73]
    @test all(
        JuMP.constraint_object(constraint).set isa
        JuMP.MOI.PositiveSemidefiniteConeTriangle
        for constraint in cone_jump_model.psd_constraints
    )
    @test cone_jump_model.assembly_sha256 ==
          cone_reduced.assembly_sha256
    println(
        "[full-spin-cone-truth] moments=",
        cone_report.cone_reduced_moments,
        ", removed_cones=",
        cone_report.removed_orbit_cones,
        ", psd_entries=",
        cone_report.real_psd_triangle_entries,
        ", congruence_checks=",
        cone_truth.orbit_entry_count,
    )
    flush(stdout)

    isotypic_truth = full_spin_trivial_isotypic_truth(cone_reduced)
    @test isotypic_truth.exact
    @test isotypic_truth.source_dimensions == [108, 109]
    @test isotypic_truth.trivial_dimensions == [36, 37]
    @test isotypic_truth.standard_dimensions == [36, 36]
    @test isotypic_truth.singleton_orbit_count == 1
    @test isotypic_truth.triple_orbit_count == 72
    @test isotypic_truth.row_actions_unsigned
    @test isotypic_truth.conjugation_rows_even
    @test isotypic_truth.involution_exact
    @test isotypic_truth.cross_blocks_zero
    @test isotypic_truth.cross_entry_count == 7_848
    @test isotypic_truth.standard_blocks_proportional
    @test isotypic_truth.standard_proportionality_factor == 3
    @test isotypic_truth.standard_relation_entry_count == 1_332
    @test isotypic_truth.bases_invertible
    @test isotypic_truth.basis_dimensions == [108, 109]

    isotypic_reduced = assemble_full_spin_isotypic_reduced_primal(
        cone_reduced;
        verify_truth=false,
    )
    isotypic_repeated = assemble_full_spin_isotypic_reduced_primal(
        cone_reduced;
        verify_truth=false,
    )
    isotypic_report =
        full_spin_isotypic_reduced_assembly_report(isotypic_reduced)
    @test isotypic_report.source_full_spin_moments == 3_250
    @test isotypic_report.isotypic_moments <= 3_250
    @test isotypic_report.eliminated_unused_moments >= 0
    @test isotypic_report.positive_block_dimensions ==
          [36, 36, 36, 45, 37, 36, 36, 45]
    @test isotypic_report.gap_block_dimensions == [1]
    @test isotypic_report.equality_count == 0
    @test isotypic_report.real_psd_triangle_entries == 6_104
    @test isotypic_report.maximum_psd_side_dimension == 45
    @test isotypic_reduced.coefficient_map_sha256 ==
          isotypic_repeated.coefficient_map_sha256
    @test isotypic_reduced.assembly_sha256 ==
          isotypic_repeated.assembly_sha256

    isotypic_jump_model =
        build_full_spin_isotypic_reduced_jump_primal(isotypic_reduced)
    @test JuMP.num_variables(isotypic_jump_model.model) ==
          isotypic_report.isotypic_moments
    @test isempty(isotypic_jump_model.equality_constraints)
    @test length(isotypic_jump_model.psd_constraints) == 9
    @test sort(collect(
        JuMP.constraint_object(constraint).set.side_dimension
        for constraint in isotypic_jump_model.psd_constraints
    )) == [1, 36, 36, 36, 36, 36, 37, 45, 45]
    @test all(
        JuMP.constraint_object(constraint).set isa
        JuMP.MOI.PositiveSemidefiniteConeTriangle
        for constraint in isotypic_jump_model.psd_constraints
    )
    @test isotypic_jump_model.assembly_sha256 ==
          isotypic_reduced.assembly_sha256
    println(
        "[full-spin-isotypic-truth] moments=",
        isotypic_report.isotypic_moments,
        ", psd_entries=",
        isotypic_report.real_psd_triangle_entries,
        ", cross_checks=",
        isotypic_truth.cross_entry_count,
        ", standard_checks=",
        isotypic_truth.standard_relation_entry_count,
    )
    flush(stdout)
end

@testset "V4 character multiplication and projection" begin
    _, x = pauli_word([(1, :X)])
    _, y = pauli_word([(1, :Y)])
    _, z = pauli_word([(1, :Z)])
    _, xx = pauli_word([(1, :X), (2, :X)])
    _, xy = pauli_word([(1, :X), (2, :Y)])

    @test v4_character(PauliWord()) == V4Character(false, false)
    @test v4_character(x) == V4Character(false, true)
    @test v4_character(y) == V4Character(true, false)
    @test v4_character(z) == V4Character(true, true)
    @test v4_character(xx) == V4Character(false, false)
    @test v4_character(xy) == V4Character(true, true)

    invariant = positive_entry(bare_row(x), bare_row(x))
    noninvariant = positive_entry(bare_row(x), bare_row(y))
    @test v4_invariant_projection(invariant) == invariant
    @test iszero(v4_invariant_projection(noninvariant))

    @test !conjugation_odd(x)
    @test conjugation_odd(y)
    @test !conjugation_odd(z)
    @test conjugation_sign(x) == 1
    @test conjugation_sign(y) == -1

    x_sign, transformed_x = spin_axis_involution(x)
    y_sign, transformed_y = spin_axis_involution(y)
    z_sign, transformed_z = spin_axis_involution(z)
    @test x_sign == 1
    @test y_sign == -1
    @test z_sign == 1
    @test transformed_x == z
    @test transformed_y == y
    @test transformed_z == x
    @test spin_axis_involution(transformed_x) == (1, x)
    @test spin_axis_involution(transformed_y) == (-1, y)
    @test spin_axis_character(v4_character(x)) == v4_character(z)
    @test spin_axis_character(v4_character(y)) == v4_character(y)

    @test length(SPIN_AXIS_PERMUTATIONS) == 6
    @test count(
        permutation -> permutation_sign(permutation) == 1,
        SPIN_AXIS_PERMUTATIONS,
    ) == 3
    @test count(
        permutation -> permutation_sign(permutation) == -1,
        SPIN_AXIS_PERMUTATIONS,
    ) == 3
    swap_xy = (UInt8(2), UInt8(1), UInt8(3))
    cycle_xyz = (UInt8(2), UInt8(3), UInt8(1))
    @test full_spin_permutation(x, swap_xy) == (-1, y)
    @test full_spin_permutation(y, swap_xy) == (-1, x)
    @test full_spin_permutation(z, swap_xy) == (-1, z)
    @test full_spin_permutation(x, cycle_xyz) == (1, y)
    @test full_spin_character(v4_character(x), swap_xy) ==
          v4_character(y)
    @test full_spin_character(v4_character(z), swap_xy) ==
          v4_character(z)
end
