using Test

include(joinpath(@__DIR__, "..", "src", "SquareJ1J2Prototype.jl"))
using .SquareJ1J2Prototype

@testset "square patch geometry" begin
    for L in 1:4
        patch = square_patch(L; g=1//2)
        side = 2L + 1
        @test length(patch.sites) == side^2
        @test length(patch.inner_ids) == (side - 2)^2
        @test count(b -> b.kind == :J1, patch.bonds) == 2side * (side - 1)
        @test count(b -> b.kind == :J2, patch.bonds) == 2(side - 1)^2
        @test validate_inner_buffer(patch)
        @test length(unique((b.kind, b.i, b.j) for b in patch.bonds)) ==
              length(patch.bonds)
    end
end

@testset "Pauli canonicalization" begin
    one, identity = pauli_word([(1, :X), (1, :X)])
    @test one == 1
    @test isempty(identity.ops)

    phase_xy, xy = pauli_word([(1, :X), (1, :Y)])
    phase_yx, yx = pauli_word([(1, :Y), (1, :X)])
    _, z = pauli_word([(1, :Z)])
    @test phase_xy == im
    @test phase_yx == -im
    @test xy == z == yx

    phase_12, word_12 = pauli_word([(1, :X), (2, :Y)])
    phase_21, word_21 = pauli_word([(2, :Y), (1, :X)])
    @test phase_12 == phase_21 == 1
    @test word_12 == word_21

    _, x = pauli_word([(1, :X)])
    _, y = pauli_word([(1, :Y)])
    phase_left, left = multiply_words(x, y)
    phase_right, right = multiply_words(y, x)
    @test phase_left == im
    @test phase_right == -im
    @test left == right == z
end

@testset "bare Pauli basis counts" begin
    for nsites in 0:6, d in 0:4
        words = enumerate_pauli_words(nsites, d)
        @test length(words) == operator_word_count(nsites, d)
        @test length(unique(words)) == length(words)
    end
    @test operator_word_count(9, 2) == 352
    @test operator_word_count(25, 2) == 2776
end

@testset "full state-polynomial formal counts" begin
    @test full_state_basis_count_by_degree(1, 0) == BigInt[1]
    @test full_state_basis_count_by_degree(1, 1) == BigInt[1, 6]
    @test full_state_basis_count_by_degree(1, 2) == BigInt[1, 6, 15]
    @test full_state_basis_count(9, 2) == 1810
    @test one_symbol_lift_count(9, 2) == 703

    for nsites in 1:8
        counts = [full_state_basis_count(nsites, d) for d in 0:4]
        @test issorted(counts)
    end
end

@testset "storage estimates" begin
    @test dense_complex_matrix_bytes(10) == 1600
    @test real_embedding_matrix_bytes(10) == 3200
end

include(joinpath(@__DIR__, "..", "src", "LocalSpinIdentities.jl"))
using .LocalSpinIdentities

@testset "exact local spin identities" begin
    checks = local_identity_checks()
    for (name, result) in checks
        if result isa Bool
            @test result
        end
    end
    @test checks["bond_projector_traces"] == (1, 3)
    @test checks["triangle_projector_traces"] == (4, 4)
    @test checks["plaquette_projector_traces"] == (2, 9, 5)
    @test checks["joint_projector_traces"] == (1, 3, 3, 1, 3, 5)
end

include(joinpath(@__DIR__, "..", "src", "GenericGapModel.jl"))
using .GenericGapModel

@testset "generic solver-free problem adapter" begin
    for (L, expected_j1_bonds, expected_j2_bonds) in (
        (1, 12, 8),
        (2, 40, 32),
        (3, 84, 72),
    )
        patch = square_patch_geometry(L)
        model = square_j1j2_model(1//2)
        @test validate_model_buffer(model, patch)
        terms = instantiate_terms(model, patch)
        @test count(term -> term.tag == :J1, terms) == 3expected_j1_bonds
        @test count(term -> term.tag == :J2, terms) == 3expected_j2_bonds
        @test all(iszero ∘ imag ∘ (term -> term.coefficient), terms)
        @test all(
            term -> real(term.coefficient) == 1//4,
            filter(term -> term.tag == :J1, terms),
        )
        @test all(
            term -> real(term.coefficient) == 1//8,
            filter(term -> term.tag == :J2, terms),
        )
    end

    patch = square_patch_geometry(1)
    model = square_j1j2_model(1//2)
    integer_model = square_j1j2_model(0)
    @test all(
        term -> term.coefficient isa ComplexF64,
        instantiate_terms(integer_model, patch),
    )
    structured_problem = GapProblem(
        patch,
        model,
        1//10,
        2;
        basis_mode=:one_symbol,
    )
    structured_plan = assembly_plan(structured_problem)
    @test structured_plan.local_terms == 60
    @test structured_plan.positive_basis_dimension == 703
    @test structured_plan.gap_basis_dimension == 7
    @test !structured_plan.symmetry_declared
    @test structured_plan.problem_sha256 ==
          assembly_plan(structured_problem).problem_sha256

    complete_problem = GapProblem(
        patch,
        model,
        1//10,
        2;
        basis_mode=:full_count_only,
    )
    complete_plan = assembly_plan(complete_problem)
    @test complete_plan.positive_basis_dimension == 1810
    @test complete_plan.gap_basis_dimension == 7
    @test complete_plan.problem_sha256 != structured_plan.problem_sha256

    symmetric_problem = GapProblem(
        patch,
        model,
        1//10,
        2;
        basis_mode=:one_symbol,
        symmetry=ExplicitStateSymmetry("D4", ["C4", "mirror"]),
    )
    symmetric_plan = assembly_plan(symmetric_problem)
    @test symmetric_plan.symmetry_declared
    @test symmetric_plan.problem_sha256 != structured_plan.problem_sha256

    supports, coefficients = legacy_ncpoly_data(structured_problem)
    @test length(supports) == length(coefficients) == 60
    @test all(length(support) == 2 for support in supports)
    @test count(==(Float64(1//4)), coefficients) == 36
    @test count(==(Float64(1//8)), coefficients) == 24

    changed_model = square_j1j2_model(107//200)
    changed_patch = square_patch_geometry(1)
    changed_problem = GapProblem(changed_patch, changed_model, 1//10, 2)
    @test assembly_plan(changed_problem).problem_sha256 !=
          structured_plan.problem_sha256

    bad_sites = [Site(0, 0)]
    bad_patch = LocalPatch("bad-unbuffered", 0, bad_sites, Dict(Site(0, 0) => 1), [1])
    @test !validate_model_buffer(model, bad_patch)
    @test_throws ArgumentError GapProblem(bad_patch, model, 0//1, 2)
end

include(joinpath(@__DIR__, "..", "src", "SmallEDOracle.jl"))
using .SmallEDOracle

@testset "small finite-patch ED construction oracle" begin
    comparison = compare_hamiltonian_builders(1; g=1//2)
    @test comparison.max_builder_difference == 0
    @test comparison.hermiticity_error == 0
    @test comparison.trace == 0
end

include(joinpath(@__DIR__, "legacy_inventory_format_tests.jl"))
