using Test

const SOURCE_ROOT = normpath(joinpath(@__DIR__, "..", "src"))

for source_file in (
    "SquareJ1J2Prototype.jl",
    "GenericGapModel.jl",
    "PrimalGapSymbolics.jl",
    "PrimalGapAssembly.jl",
    "ExactSymmetryReduction.jl",
    "ReducedPrimalGapAssembly.jl",
    "ConjugationSymmetryReduction.jl",
    "SpinAxisInvolutionReduction.jl",
    "FullSpinPermutationReduction.jl",
    "FullSpinConeReduction.jl",
    "FullSpinIsotypicReduction.jl",
    "ContinuousSpinMomentReduction.jl",
)
    include(joinpath(SOURCE_ROOT, source_file))
end

using .GenericGapModel
using .PrimalGapAssembly
using .ReducedPrimalGapAssembly
using .ConjugationSymmetryReduction
using .SpinAxisInvolutionReduction
using .FullSpinPermutationReduction
using .FullSpinConeReduction
using .FullSpinIsotypicReduction
using .ContinuousSpinMomentReduction

@testset "exact continuous-spin moment reduction" begin
    problem = GapProblem(
        square_patch_geometry(1),
        shastry_sutherland_model(4//5),
        1//2,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:one_symbol_lift, 1),
    )
    primal = assemble_primal_gap(problem)
    v4 = assemble_reduced_primal(primal)
    conjugation = assemble_conjugation_reduced_primal(v4)
    spin_axis = assemble_spin_axis_reduced_primal(
        conjugation;
        verify_truth=false,
    )
    full_spin = assemble_full_spin_reduced_primal(
        spin_axis;
        verify_truth=false,
    )
    cone = assemble_full_spin_cone_reduced_primal(
        full_spin;
        verify_truth=false,
    )
    isotypic = assemble_full_spin_isotypic_reduced_primal(
        cone;
        verify_truth=false,
    )

    truth = continuous_spin_moment_truth(isotypic)
    @test truth.exact
    @test truth.source_moment_count == 3_250
    @test 0 < truth.invariant_moment_count <
          truth.source_moment_count
    @test truth.eliminated_moment_count ==
          truth.source_moment_count - truth.invariant_moment_count
    @test truth.skeleton_count > 0
    @test truth.rank_two_skeleton_count > 0
    @test truth.rank_four_skeleton_count > 0
    @test truth.substitutions_complete
    @test truth.pivots_exact
    @test truth.rational_rotation_invariant
    @test truth.rational_rotation_component_check_count > 0
    @test truth.rational_rotation_orthogonal
    @test truth.rational_rotation_determinant == 1

    reduced = assemble_continuous_spin_reduced_primal(
        isotypic;
        verify_truth=false,
    )
    repeated = assemble_continuous_spin_reduced_primal(
        isotypic;
        verify_truth=false,
    )
    report = continuous_spin_reduced_assembly_report(reduced)
    @test report.source_isotypic_moments == 3_250
    @test report.continuous_spin_moments ==
          truth.invariant_moment_count
    @test report.eliminated_continuous_spin_moments ==
          truth.eliminated_moment_count
    @test report.positive_block_dimensions ==
          [36, 36, 36, 45, 37, 36, 36, 45]
    @test report.gap_block_dimensions == [1]
    @test report.equality_count == 0
    @test report.real_psd_triangle_entries == 6_104
    @test report.maximum_psd_side_dimension == 45
    @test reduced.coefficient_map_sha256 ==
          repeated.coefficient_map_sha256
    @test reduced.assembly_sha256 == repeated.assembly_sha256

    println(
        "[continuous-spin-truth] source_moments=",
        truth.source_moment_count,
        ", invariant_moments=",
        truth.invariant_moment_count,
        ", skeletons=",
        truth.skeleton_count,
        ", rank2_skeletons=",
        truth.rank_two_skeleton_count,
        ", rank4_skeletons=",
        truth.rank_four_skeleton_count,
        ", rotation_checks=",
        truth.rational_rotation_component_check_count,
        ", psd_entries=",
        report.real_psd_triangle_entries,
    )
    flush(stdout)
end
