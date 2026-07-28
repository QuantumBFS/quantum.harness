using LinearAlgebra

function one_phase_floquet(matrix::AbstractMatrix)
    n = size(matrix, 1)
    size(matrix, 2) == n || throw(ArgumentError("test map must be square"))
    n % 4 == 0 || throw(ArgumentError("test map dimension must be 4χ"))
    χ = n ÷ 4
    q = reshape(ComplexF64.(matrix), χ, 4, χ, 4)
    identity_channel = Matrix{ComplexF64}(I, 4, 4)
    return FloquetOperator(q, [identity_channel], [identity_channel])
end

function nonnormal_stationary_map()
    right = ComplexF64[0.7, 0, 0, 0.3]
    basis = ComplexF64[
        right[1] 0 0 1
        0        1 0 0
        0        0 1 0
        right[4] 0 0 -1
    ]
    eigenvalues = ComplexF64[1, 0.91 + 0.03im, 0.7, 0.4]
    return basis * Diagonal(eigenvalues) / basis, right, eigenvalues
end

@testset "Floquet steady-state Krylov eigensolve" begin
    matrix, expected_right, eigenvalues = nonnormal_stationary_map()
    floquet = one_phase_floquet(matrix)
    result = solve_floquet_steady_state(floquet;
        candidate_count=3, tolerance=1e-11, max_iterations=200)

    @test result.backend == :krylov
    @test result.converged
    @test result.fallback_used == false
    @test result.eigenvalue ≈ 1 atol=1e-10
    @test result.subleading_eigenvalue ≈ eigenvalues[2] atol=1e-8
    @test result.spectral_gap ≈ 1 - abs(eigenvalues[2]) atol=1e-8
    @test result.right_residual < 1e-10
    @test result.left_residual < 1e-10
    @test result.iterations >= 0
    @test result.matvec_count > 0
    @test dot(result.left_vector, result.right_vector) ≈ 1 atol=1e-10
    @test norm(result.right_vector / result.right_vector[1] -
               expected_right / expected_right[1]) < 1e-8
    diagnostics = floquet_eigen_diagnostics(result)
    @test diagnostics.lambda0 == result.eigenvalue
    @test diagnostics.backend == "krylov"
    @test diagnostics.converged
end

@testset "physical eigenvalue is selected closest to one" begin
    # The largest-magnitude candidate is deliberately not the physical λ=1.
    matrix = Diagonal(ComplexF64[1.02, 1.0, 0.8, 0.5])
    result = solve_floquet_steady_state(one_phase_floquet(matrix);
        candidate_count=2, tolerance=1e-12)
    @test result.eigenvalue ≈ 1 atol=1e-11
end

@testset "complex biorthogonal normalization convention" begin
    basis = ComplexF64[
        1 + im  1  0  0
        2       0  1  0
        0       1  0  1
        1 - im  0  0  1
    ]
    matrix = basis * Diagonal(ComplexF64[1, 0.8 + 0.1im, 0.6, 0.3]) / basis
    result = solve_floquet_steady_state(one_phase_floquet(matrix);
        candidate_count=3, tolerance=1e-11)
    @test dot(result.left_vector, result.right_vector) ≈ 1 atol=1e-9
    @test norm(adjoint(matrix) * result.left_vector -
               conj(result.eigenvalue) * result.left_vector) /
          norm(result.left_vector) < 1e-9
end

@testset "UniformTEMPO left boundary reduction and diagnostics" begin
    χ = 2
    augmented = ComplexF64[
        0.6, 0.1, # ρ11 bond components
        0.0, 0.0, # ρ21
        0.0, 0.0, # ρ12
        0.2, 0.1, # ρ22
    ]
    v_left = ComplexF64[1, 2]
    expected = ComplexF64[0.8 0; 0 0.4]
    reduced = reduce_system_state(augmented, v_left;
                                  normalize=false)
    @test reduced.density_matrix ≈ expected
    @test reduced.trace ≈ 1.2
    @test reduced.hermiticity_error == 0
    @test reduced.minimum_eigenvalue ≈ 0.4

    normalized = reduce_system_state(augmented, v_left)
    @test tr(normalized.density_matrix) ≈ 1
    # A raw sum over the bond index would give diag(0.7,0.3), proving that
    # reduction follows UniformTEMPO's v_l contraction instead.
    @test normalized.density_matrix ≈ expected / 1.2
end

@testset "period iteration fallback reports convergence and failure" begin
    matrix, _, _ = nonnormal_stationary_map()
    floquet = one_phase_floquet(matrix)
    converged = solve_floquet_steady_state(floquet;
        backend=:period_iteration, tolerance=1e-9,
        max_iterations=500, initial_vector=ones(ComplexF64, 4))
    @test converged.backend == :period_iteration
    @test converged.fallback_used
    @test converged.converged
    @test converged.iterations > 0
    @test converged.right_residual < 1e-8

    failed = solve_floquet_steady_state(floquet;
        backend=:period_iteration, tolerance=1e-14,
        max_iterations=1, initial_vector=ones(ComplexF64, 4))
    @test failed.fallback_used
    @test !failed.converged
    @test failed.nonconvergence_reason == :maximum_iterations
end

@testset "micromotion caches states and closes one period" begin
    identity4 = Matrix{ComplexF64}(I, 4, 4)
    floquet = FloquetOperator(reshape(identity4, 1, 4, 1, 4),
                              [identity4, identity4],
                              [identity4, identity4])
    initial = ComplexF64[0.75, 0, 0, 0.25]
    model = SpinBosonModel()
    motion = micromotion_states(floquet, initial, ComplexF64[1], model;
                                omega_d=2.0, exact_dt=π / 2)
    @test length(motion.phase_states) == 3
    @test all(length(state) == 4 for state in motion.phase_states)
    @test motion.augmented_closure < 1e-14
    @test motion.reduced_closure < 1e-14
    @test length(motion.sigma_x) == 3
    @test length(motion.sigma_y) == 3
    @test length(motion.sigma_z) == 3
    @test length(motion.system_energy) == 3
    @test length(motion.drive_power) == 3
    @test motion.sigma_z[1] ≈ 0.5
end

@testset "warm start requires exact dt, q identity, and layout" begin
    vector = ComplexF64[1, 0, 0, 0]
    warm = FloquetWarmStart(vector, 0.1, "cache-a", AugmentedLayout(1))
    @test validate_warm_start(warm, 0.1, "cache-a", AugmentedLayout(1)) == vector
    @test_throws ArgumentError validate_warm_start(
        warm, nextfloat(0.1), "cache-a", AugmentedLayout(1))
    @test_throws ArgumentError validate_warm_start(
        warm, 0.1, "cache-b", AugmentedLayout(1))
    @test_throws ArgumentError validate_warm_start(
        warm, 0.1, "cache-a", AugmentedLayout(2))
end
