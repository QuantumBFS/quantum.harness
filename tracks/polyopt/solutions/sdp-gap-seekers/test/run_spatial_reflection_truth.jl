using Test

const SOURCE_ROOT = normpath(joinpath(@__DIR__, "..", "src"))

for source_file in (
    "SquareJ1J2Prototype.jl",
    "GenericGapModel.jl",
    "PrimalGapSymbolics.jl",
    "PrimalGapAssembly.jl",
    "PrimalGapJuMP.jl",
    "ExactSymmetryReduction.jl",
    "ReducedPrimalGapAssembly.jl",
    "ReducedPrimalGapJuMP.jl",
    "ConjugationSymmetryReduction.jl",
    "ConjugationReducedPrimalGapJuMP.jl",
    "SpinAxisInvolutionReduction.jl",
    "SpinAxisInvolutionPrimalGapJuMP.jl",
    "FullSpinPermutationReduction.jl",
    "FullSpinPermutationPrimalGapJuMP.jl",
    "FullSpinConeReduction.jl",
    "FullSpinConeReducedPrimalGapJuMP.jl",
    "FullSpinIsotypicReduction.jl",
    "FullSpinIsotypicPrimalGapJuMP.jl",
    "SpatialReflectionReduction.jl",
    "SpatialReflectionPrimalGapJuMP.jl",
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
using .SpatialReflectionReduction
using .SpatialReflectionPrimalGapJuMP
using JuMP

@testset "exact anti-diagonal spatial-reflection reduction" begin
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
    spin_axis = assemble_spin_axis_reduced_primal(conjugation)
    full_spin = assemble_full_spin_reduced_primal(spin_axis)
    cone = assemble_full_spin_cone_reduced_primal(full_spin)
    isotypic = assemble_full_spin_isotypic_reduced_primal(cone)

    truth = spatial_reflection_reduction_truth(isotypic)
    @test truth.exact
    @test truth.site_map_involutive
    @test truth.hamiltonian_invariant
    @test truth.source_moment_count == length(isotypic.moments)
    @test truth.quotient_moment_count <= truth.source_moment_count
    @test truth.eliminated_moment_count >= 0
    @test truth.raw_nonrepresentative_count > 0
    @test truth.coefficient_covariant
    @test truth.coefficient_count == 6_104
    @test truth.equality_space_invariant
    @test truth.stable_cross_blocks_zero
    @test truth.stable_cross_entry_count > 0
    @test truth.stable_bases_invertible

    reduced = assemble_spatial_reflection_reduced_primal(
        isotypic;
        verify_truth=false,
    )
    repeated = assemble_spatial_reflection_reduced_primal(
        isotypic;
        verify_truth=false,
    )
    report = spatial_reflection_reduced_assembly_report(reduced)
    @test report.source_isotypic_moments == length(isotypic.moments)
    @test report.spatial_moments <= report.source_isotypic_moments
    @test report.eliminated_spatial_moments >= 0
    @test report.positive_block_dimensions ==
          truth.positive_block_dimensions
    @test report.gap_block_dimensions == truth.gap_block_dimensions
    @test report.equality_count == 0
    @test report.maximum_psd_side_dimension <
          maximum(length.(getfield.(isotypic.positive_blocks, :rows)))
    @test reduced.coefficient_map_sha256 ==
          repeated.coefficient_map_sha256
    @test reduced.assembly_sha256 == repeated.assembly_sha256

    jump_model = build_spatial_reflection_reduced_jump_primal(reduced)
    @test JuMP.num_variables(jump_model.model) == report.spatial_moments
    @test isempty(jump_model.equality_constraints)
    @test length(jump_model.psd_constraints) ==
          length(report.positive_block_dimensions) +
          length(report.gap_block_dimensions)
    @test sort(collect(
        JuMP.constraint_object(constraint).set.side_dimension
        for constraint in jump_model.psd_constraints
    )) == sort([
        report.positive_block_dimensions;
        report.gap_block_dimensions
    ])
    @test all(
        JuMP.constraint_object(constraint).set isa
        JuMP.MOI.PositiveSemidefiniteConeTriangle
        for constraint in jump_model.psd_constraints
    )
    @test jump_model.assembly_sha256 == reduced.assembly_sha256

    println(
        "[spatial-reflection-truth] source_moments=",
        truth.source_moment_count,
        ", quotient_moments=",
        truth.quotient_moment_count,
        ", positive_dims=",
        report.positive_block_dimensions,
        ", gap_dims=",
        report.gap_block_dimensions,
        ", psd_entries=",
        report.real_psd_triangle_entries,
        ", cross_checks=",
        truth.stable_cross_entry_count,
    )
    flush(stdout)
end
