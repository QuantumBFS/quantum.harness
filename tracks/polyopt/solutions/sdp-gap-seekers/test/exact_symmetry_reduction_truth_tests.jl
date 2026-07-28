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
end
