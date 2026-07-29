using Test
using LinearAlgebra

include(joinpath(@__DIR__, "FiniteAbelianNCMoment.jl"))
using .FiniteAbelianNCMoment

@testset "generators, immutable words, and algebra backends" begin
    system = GeneratorSystem([:a, :astar]; adjoint=[2, 1])
    @test system.adjoint == (2, 1)
    @test_throws ArgumentError GeneratorSystem([:a, :b]; adjoint=[2, 2])
    @test !ismutabletype(NCWord)

    commuting = Set([(1, 2)])
    @test normalize_word((2, 1), commuting) == (1, 2)
    @test normalize_word((1, 2, 1), commuting) == (2,)
    @test normalize_word((1, 2, 1), Set{Tuple{Int,Int}}()) == (1, 2, 1)
    @test normalize_word((1, 1, 2, 2), Set{Tuple{Int,Int}}()) == ()
    @test moment_key((2, 1), Set{Tuple{Int,Int}}()) == (2, 1)

    pauli = PauliBackend([(:X, 1, :X), (:Y, 1, :Y), (:Z, 1, :Z),
                          (:X2, 2, :X), (:Y2, 2, :Y), (:Z2, 2, :Z)])
    @test reduce_word(pauli, NCWord(1, 2)) == ReducedMonomial(0.0 + 1.0im, NCWord(3))
    @test reduce_word(pauli, NCWord(2, 1)) == ReducedMonomial(0.0 - 1.0im, NCWord(3))
    @test reduce_word(pauli, NCWord(4, 1)) == ReducedMonomial(1.0 + 0.0im, NCWord(1, 4))
    @test reduce_word(pauli, NCWord(1, 2, 3)) == ReducedMonomial(0.0 + 1.0im, NCWord())
end

@testset "sparse complex polynomials and validation" begin
    backend = LegacyInvolutionBackend([:A, :B])
    poly = polynomial(backend, Dict((:A, :B) => 1.0 + 2.0im,
                                    (:B, :A) => 1.0 - 2.0im))
    @test eltype(values(poly.terms)) == ComplexF64
    @test star(backend, poly).terms == poly.terms
    @test_throws ArgumentError NCProblem("non-Hermitian", backend;
        objective=polynomial(backend, Dict((:A, :B) => 1.0)), order=1)
    @test_throws ArgumentError NCProblem("excess degree", backend;
        objective=polynomial(backend, Dict(() => 0.0)),
        equalities=[polynomial(backend, Dict((:A, :B, :A) => 1.0,
                                            (:A, :B, :A) => 1.0))], order=1)
end

@testset "immutable compiled dense affine IR" begin
    problem = complex_pauli_benchmark()
    ir = compile_dense(problem)
    @test !ismutabletype(CompiledDenseIR)
    @test ir.problem === problem
    @test ir.coordinate_count == 4
    @test length(ir.moment_words) == 4
    @test all(length(form.terms) == 1 for form in ir.moment_forms)
    @test FiniteAbelianNCMoment._form_difference_norm(
        ir.moment_matrix[1][2],
        FiniteAbelianNCMoment._conjugate_form(ir.moment_matrix[2][1]),
    ) <= 1.0e-14

    constrained = compile_dense(equality_localizer_benchmark())
    @test length(constrained.equalities) == 16 # every degree-admissible u* g v
    @test length(constrained.localizers) == 1
    @test length(constrained.localizers[1].basis) == 3
end

@testset "complex Pauli moment SDP" begin
    problem = complex_pauli_benchmark()
    result = solve_moment_sdp(problem)
    @test result.termination_status == FiniteAbelianNCMoment.MOI.OPTIMAL
    @test result.objective ≈ 1.0 atol=1.0e-8
    @test evaluate_moment(result, problem.backend, (1, 2)) ≈ 0.0 + 1.0im atol=1.0e-8
    @test abs(imag(evaluate_moment(result, problem.backend, (1, 2)))) >= 0.99
    @test result.minimum_eigenvalue >= -1.0e-8
    @test result.coordinate_consistency_residual <= 1.0e-10
    @test result.hermiticity_residual <= 1.0e-10
    @test result.equality_residual <= 1.0e-9
    @test result.objective_residual <= 1.0e-8
end

@testset "equalities and inequality localizers" begin
    problem = equality_localizer_benchmark()
    result = solve_moment_sdp(problem)
    @test result.objective ≈ 1.0 atol=1.0e-8
    @test length(result.localizer_minimum_eigenvalues) == 1
    @test result.minimum_eigenvalue >= -1.0e-8
    @test result.localizer_minimum_eigenvalues[1] >= -1.0e-8
    @test result.localizer_minimum_eigenvalues[1] != result.minimum_eigenvalue
    @test result.equality_residual <= 1.0e-8
    @test result.localizer_residual <= 1.0e-8
    @test result.objective_residual <= 1.0e-8
end

@testset "legacy benchmark compatibility" begin
    chsh = solve_moment_sdp(chsh_z2(order=1))
    pauli = solve_moment_sdp(pauli_z2xz2(order=2))
    @test chsh.objective ≈ 2sqrt(2) atol=1.0e-7
    @test pauli.objective ≈ 2.0 atol=1.0e-7
    @test chsh.minimum_eigenvalue >= -1.0e-7
    @test pauli.minimum_eigenvalue >= -1.0e-7
end
