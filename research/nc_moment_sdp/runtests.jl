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
    @test result.compile_seconds >= 0.0
    @test result.model_build_seconds >= 0.0
    @test result.optimize_seconds >= result.solver_solve_seconds >= 0.0
    @test result.barrier_iterations >= 0
    @test result.jump_variable_count == result.coordinate_count
    @test result.jump_constraint_count > 0
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

@testset "operational finite-Abelian PSD cone reduction" begin
    for problem in (chsh_z2(order=1), pauli_z2xz2(order=2),
                    equality_localizer_benchmark(symmetry=true))
        dense = solve_moment_sdp(problem; formulation=:dense)
        reduced = solve_moment_sdp(problem; formulation=:symmetry)
        @test dense.objective ≈ reduced.objective atol=1.0e-7
        @test reduced.formulation == :symmetry
        @test sum(reduced.moment_cone_sizes) == length(reduced.basis)
        @test maximum(reduced.moment_cone_sizes) < only(dense.moment_cone_sizes)
        @test reduced.coordinate_count <= dense.coordinate_count
        @test reduced.block_cubic_proxy > 1.0
        @test reduced.minimum_eigenvalue >= -1.0e-7
        @test reduced.equality_residual <= 1.0e-8
        @test reduced.localizer_residual <= 1.0e-8
        @test reduced.objective_residual <= 1.0e-7
    end

    for order in 1:3
        dense = solve_moment_sdp(chsh_z2(order=order); formulation=:dense)
        reduced = solve_moment_sdp(chsh_z2(order=order); formulation=:symmetry)
        @test dense.objective ≈ reduced.objective atol=1.0e-7
        @test maximum(reduced.moment_cone_sizes) < only(dense.moment_cone_sizes)
        @test reduced.coordinate_count < dense.coordinate_count
        @test reduced.block_cubic_proxy > 1.0
    end

    constrained = solve_moment_sdp(equality_localizer_benchmark(symmetry=true);
                                   formulation=:symmetry)
    @test length(constrained.localizer_cone_sizes) == 1
    @test length(only(constrained.localizer_cone_sizes)) > 1
    @test sum(only(constrained.localizer_cone_sizes)) == 3

    backend = LegacyInvolutionBackend([:A, :B])
    noninvariant = NCProblem("non-invariant objective", backend;
        objective=polynomial(backend, Dict((:A,) => 1.0)),
        generator_characters=[0x1, 0x0], group_rank=1, order=1)
    @test_throws ArgumentError compile_symmetry(noninvariant)
    @test_throws ArgumentError compile_symmetry(complex_pauli_benchmark())
end

@testset "non-Abelian SU(2) moment and localizer reduction" begin
    problem = heisenberg_su2(order=2)
    basis = enumerate_words(problem)
    Jx, Jy, Jz = su2_generators(problem.backend, basis)
    @test norm(Jx * Jy - Jy * Jx - im * Jz, Inf) <= 1.0e-12
    @test norm(Jy * Jz - Jz * Jy - im * Jx, Inf) <= 1.0e-12
    @test norm(Jz * Jx - Jx * Jz - im * Jy, Inf) <= 1.0e-12

    decomposition = su2_decomposition(problem.backend, basis)
    @test [(part.spin, part.multiplicity) for part in decomposition] ==
          [(0, 2), (1, 3), (2, 1)]
    @test sum((2part.spin + 1) * part.multiplicity for part in decomposition) == length(basis)
    @test all(norm(part.highest_weight_basis' * part.highest_weight_basis -
                   I(part.multiplicity), Inf) <= 1.0e-10 for part in decomposition)

    ir = compile_su2(problem)
    @test ir isa CompiledSU2IR
    @test [block.spin for block in ir.moment_blocks] == [0, 1, 2]
    @test [block.multiplicity for block in ir.moment_blocks] == [2, 3, 1]
    @test sum((2block.spin + 1) * block.multiplicity for block in ir.moment_blocks) ==
          length(ir.basis)

    dense = solve_moment_sdp(problem; formulation=:dense)
    reduced = solve_moment_sdp(problem; formulation=:su2)
    @test dense.objective ≈ -3.0 atol=1.0e-7
    @test dense.objective ≈ reduced.objective atol=1.0e-7
    @test reduced.formulation == :su2
    @test reduced.moment_cone_sizes == [2, 3, 1]
    @test sum(reduced.moment_cone_sizes) < only(dense.moment_cone_sizes)
    @test reduced.block_cubic_proxy > 1.0
    @test reduced.minimum_eigenvalue >= -1.0e-7
    @test reduced.equality_residual <= 1.0e-8
    @test reduced.objective_residual <= 1.0e-7

    dense_spectrum = sort(eigvals(Hermitian(reduced.moment_matrix)))
    compressed_spectrum = Float64[]
    forms = Dict(zip(ir.moment_words, ir.moment_forms))
    coordinate_system = zeros(ComplexF64, length(ir.moment_words), ir.coordinate_count)
    moment_values = zeros(ComplexF64, length(ir.moment_words))
    for (row, word) in enumerate(ir.moment_words)
        moment_values[row] = reduced.moments[word] - forms[word].constant
        for (index, coefficient) in forms[word].terms
            coordinate_system[row, index] = coefficient
        end
    end
    coordinates = [real(coordinate_system); imag(coordinate_system)] \ [real(moment_values); imag(moment_values)]
    for block in ir.moment_blocks
        values = FiniteAbelianNCMoment._matrix_values(block.pencil, coordinates)
        append!(compressed_spectrum, repeat(eigvals(Hermitian(values)); outer=2block.spin + 1))
    end
    @test dense_spectrum ≈ sort(compressed_spectrum) atol=1.0e-7

    constrained = heisenberg_su2(order=2, localizer=true)
    constrained_dense = solve_moment_sdp(constrained; formulation=:dense)
    constrained_su2 = solve_moment_sdp(constrained; formulation=:su2)
    @test constrained_dense.objective ≈ constrained_su2.objective atol=1.0e-7
    @test constrained_su2.objective ≈ -1.0 atol=1.0e-7
    @test constrained_su2.localizer_cone_sizes == [[1, 2]]
    @test sum(only(constrained_su2.localizer_cone_sizes)) <
          only(only(constrained_dense.localizer_cone_sizes))
    @test constrained_su2.localizer_residual <= 1.0e-8

    @test_throws ArgumentError compile_su2(complex_pauli_benchmark())
    @test_throws ArgumentError compile_su2(pauli_z2xz2())
    mixed_metadata = NCProblem("SU2 scalar with Z2 metadata", problem.backend;
        objective=problem.objective, generator_characters=fill(0x1, 6),
        group_rank=1, order=2, sense=:Min)
    @test_throws ArgumentError compile_su2(mixed_metadata)
    tiny_nonscalar = NCProblem("tiny non-scalar", problem.backend;
        objective=polynomial(problem.backend, Dict((:Z1,) => 1.0e-13)),
        order=1, sense=:Min)
    @test_throws ArgumentError compile_su2(tiny_nonscalar)
    @test_throws ArgumentError compile_su2(equality_localizer_benchmark())
    @test_throws ArgumentError solve_moment_sdp(problem; formulation=:symmetry)
end

@testset "legacy benchmark compatibility" begin
    chsh = solve_moment_sdp(chsh_z2(order=1))
    pauli = solve_moment_sdp(pauli_z2xz2(order=2))
    @test chsh.objective ≈ 2sqrt(2) atol=1.0e-7
    @test pauli.objective ≈ 2.0 atol=1.0e-7
    @test chsh.minimum_eigenvalue >= -1.0e-7
    @test pauli.minimum_eigenvalue >= -1.0e-7
end
