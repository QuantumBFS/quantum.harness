using Test
using LinearAlgebra

include(joinpath(@__DIR__, "FiniteAbelianNCMoment.jl"))
using .FiniteAbelianNCMoment

@testset "word normalization and symmetry lifting" begin
    commuting = Set([(1, 2)])
    @test normalize_word((2, 1), commuting) == (1, 2)
    @test normalize_word((1, 2, 1), commuting) == (2,)
    @test normalize_word((1, 2, 1), Set{Tuple{Int,Int}}()) == (1, 2, 1)
    @test normalize_word((1, 1, 2, 2), Set{Tuple{Int,Int}}()) == ()
    @test moment_key((2, 1), Set{Tuple{Int,Int}}()) == (2, 1)
    @test word_character((1, 2, 1), UInt64[0x1, 0x2]) == 0x2

    chsh = chsh_z2(order=1)
    @test length(enumerate_words(chsh)) == 5
    @test word_character((1, 3), chsh.generator_characters) == 0x0
    @test word_character((1,), chsh.generator_characters) == 0x1
end

@testset "non-invariant or non-Hermitian Hamiltonians are rejected" begin
    @test_throws ArgumentError NCProblem(
        "invalid", [:A, :B];
        generator_characters=[0x1, 0x0], group_rank=1,
        hamiltonian=Dict((:A,) => 1.0), order=1,
    )
    @test_throws ArgumentError NCProblem(
        "non-Hermitian", [:A, :B];
        hamiltonian=Dict((:A, :B) => 1.0), order=1,
    )
end

@testset "dense and character-reduced affine moment SDPs" begin
    for problem in (chsh_z2(order=1), pauli_z2xz2(order=2))
        dense = solve_moment_sdp(problem; formulation=:dense)
        reduced = solve_moment_sdp(problem; formulation=:reduced)

        @test dense.termination_status == FiniteAbelianNCMoment.MOI.OPTIMAL
        @test reduced.termination_status == FiniteAbelianNCMoment.MOI.OPTIMAL
        @test dense.free_moment_count > reduced.free_moment_count
        @test dense.free_moment_count == length(dense.moments)
        @test reduced.free_moment_count < length(reduced.moments)
        @test abs(dense.objective - reduced.objective) <= 1.0e-7
        @test dense.minimum_eigenvalue >= -1.0e-7
        @test reduced.minimum_eigenvalue >= -1.0e-7
        @test dense.equality_residual <= 1.0e-8
        @test reduced.equality_residual <= 1.0e-8
        @test dense.objective_residual <= 1.0e-8
        @test reduced.objective_residual <= 1.0e-8

        characters = [word_character(word, problem.generator_characters) for word in reduced.basis]
        for i in eachindex(characters), j in eachindex(characters)
            if characters[i] != characters[j]
                @test abs(reduced.moment_matrix[i, j]) <= 1.0e-10
            end
        end
        @test reduced.block_cubic_proxy > 1.0
    end

    chsh_dense = solve_moment_sdp(chsh_z2(order=1); formulation=:dense)
    @test chsh_dense.objective ≈ 2sqrt(2) atol=1.0e-7
    pauli_dense = solve_moment_sdp(pauli_z2xz2(order=2); formulation=:dense)
    @test pauli_dense.objective ≈ 2.0 atol=1.0e-7
end
