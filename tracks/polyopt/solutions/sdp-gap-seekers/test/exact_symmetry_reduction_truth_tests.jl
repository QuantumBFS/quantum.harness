include(joinpath(@__DIR__, "..", "src", "ExactSymmetryReduction.jl"))
using .ExactSymmetryReduction
include(joinpath(@__DIR__, "..", "src", "ReducedPrimalGapAssembly.jl"))
using .ReducedPrimalGapAssembly
include(joinpath(@__DIR__, "..", "src", "ReducedPrimalGapJuMP.jl"))
using .ReducedPrimalGapJuMP
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
end
