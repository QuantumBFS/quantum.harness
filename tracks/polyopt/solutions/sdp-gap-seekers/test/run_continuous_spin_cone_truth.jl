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
    "ContinuousSpinConeReduction.jl",
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
using .ContinuousSpinConeReduction

@testset "exact continuous-spin l=2 cone reduction" begin
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
    continuous = assemble_continuous_spin_reduced_primal(
        isotypic;
        verify_truth=false,
    )

    truth = continuous_spin_l2_cone_redundancy_truth(continuous)
    @test truth.exact
    @test truth.duplicate_cone_dimensions == [36, 36]
    @test truth.row_map_ranks == [36, 36]
    @test truth.component_rows_canonical
    @test truth.component_squared_norms == [2]
    @test truth.coefficient_congruence_exact
    @test truth.coefficient_entry_count == 1_332
    @test truth.nonzero_coefficient_entry_count > 0
    @test truth.proportionality_factor == 1

    reduced = assemble_continuous_spin_cone_reduced_primal(
        continuous;
        verify_truth=false,
    )
    repeated = assemble_continuous_spin_cone_reduced_primal(
        continuous;
        verify_truth=false,
    )
    report = continuous_spin_cone_reduced_assembly_report(reduced)
    @test report.continuous_spin_moments == length(continuous.moments)
    @test report.positive_block_dimensions ==
          [36, 36, 45, 37, 36, 45]
    @test report.gap_block_dimensions == [1]
    @test report.equality_count == 0
    @test report.real_psd_triangle_entries == 4_772
    @test report.maximum_psd_side_dimension == 45
    @test reduced.coefficient_map_sha256 ==
          repeated.coefficient_map_sha256
    @test reduced.assembly_sha256 == repeated.assembly_sha256

    println(
        "[continuous-spin-cone-truth] moments=",
        report.continuous_spin_moments,
        ", duplicate_dims=",
        truth.duplicate_cone_dimensions,
        ", row_ranks=",
        truth.row_map_ranks,
        ", compared_entries=",
        truth.coefficient_entry_count,
        ", retained_psd_entries=",
        report.real_psd_triangle_entries,
    )
    flush(stdout)
end
