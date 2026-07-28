using LinearAlgebra
using Random
using UniformTEMPO

"""
Independent dense reference for one augmented step.

The augmented vector uses Julia's column-major vectorization of a χ×4
`(bond, Liouville)` matrix, so `i = a + χ * (s - 1)`.
"""
function dense_step_reference(q, left_channel, right_channel)
    χ = size(q, 1)
    n = 4χ
    Q = zeros(promote_type(eltype(q), eltype(left_channel), eltype(right_channel)), n, n)
    basis = zeros(eltype(Q), χ, 4)
    after_left = similar(basis)
    after_q = similar(basis)
    after_right = similar(basis)
    q_dense = reshape(q, n, n)
    for j in 1:n
        fill!(basis, 0)
        basis[j] = 1
        mul!(after_left, basis, transpose(left_channel))
        mul!(vec(after_q), q_dense, vec(after_left))
        mul!(after_right, after_q, transpose(right_channel))
        Q[:, j] .= vec(after_right)
    end
    return Q
end

function dense_period_reference(q, left_channels, right_channels)
    χ = size(q, 1)
    QF = Matrix{ComplexF64}(I, 4χ, 4χ)
    for phase in eachindex(left_channels, right_channels)
        QF = dense_step_reference(q, left_channels[phase], right_channels[phase]) * QF
    end
    return QF
end

function random_channels(rng, M)
    left = [randn(rng, ComplexF64, 4, 4) for _ in 1:M]
    right = [randn(rng, ComplexF64, 4, 4) for _ in 1:M]
    return left, right
end

@testset "matrix-free augmented Floquet operators" begin
    rng = MersenneTwister(0xF10)

    @testset "layout convention" begin
        layout = AugmentedLayout(3)
        @test layout.bond_dimension == 3
        @test layout.liouville_dimension == 4
        @test layout.augmented_dimension == 12
        @test composite_index(layout, 1, 1) == 1
        @test composite_index(layout, 3, 1) == 3
        @test composite_index(layout, 1, 2) == 4
        @test_throws BoundsError composite_index(layout, 0, 1)
        @test_throws BoundsError composite_index(layout, 1, 5)
    end

    @testset "step agrees with explicit χ≤3 reference" begin
        for χ in 1:3
            q = randn(rng, ComplexF64, χ, 4, χ, 4)
            left, right = random_channels(rng, 1)
            step = StepOperator(q, left[1], right[1])
            work = StepWorkspace(step)
            x = randn(rng, ComplexF64, 4χ)
            y = similar(x)
            apply_step!(y, x, step, work)
            @test y ≈ dense_step_reference(q, left[1], right[1]) * x rtol=5e-13 atol=5e-13
        end
    end

    @testset "period and adjoint agree with explicit χ≤3 reference" begin
        for χ in 1:3
            M = 4
            q = randn(rng, ComplexF64, χ, 4, χ, 4)
            left, right = random_channels(rng, M)
            floquet = FloquetOperator(q, left, right)
            work = StepWorkspace(floquet)
            x = randn(rng, ComplexF64, 4χ)
            y = randn(rng, ComplexF64, 4χ)
            qfx = similar(x)
            qfdag_y = similar(y)
            apply_period!(qfx, x, floquet, work)
            apply_period_adjoint!(qfdag_y, y, floquet, work)
            dense = dense_period_reference(q, left, right)
            @test qfx ≈ dense * x rtol=1e-12 atol=1e-12
            @test qfdag_y ≈ adjoint(dense) * y rtol=1e-12 atol=1e-12
            @test dot(y, qfx) ≈ dot(qfdag_y, x) rtol=1e-12 atol=1e-12
        end
    end

    @testset "period stores one q kernel and precomputes physical half steps" begin
        χ = 2
        M = 5
        ωd = 1.3
        dt = 2π / (ωd * M)
        q = randn(rng, ComplexF64, χ, 4, χ, 4)
        adapter = UniformIFAdapter(q, ones(ComplexF64, χ), ones(ComplexF64, χ),
                                   uniform_if_metadata(SpinBosonModel(), dt, 1.0e-7))
        floquet = FloquetOperator(adapter, SpinBosonModel(), ωd, M, dt)
        @test size(floquet) == (4χ, 4χ)
        @test length(floquet.left_channels) == M
        @test length(floquet.right_channels) == M
        @test pointer(floquet.q_matrix) == pointer(floquet.q_storage)

        h(t) = system_hamiltonian(SpinBosonModel(), t, ωd)
        u_left = exp(-im * h(dt / 4) * (dt / 2))
        u_right = exp(-im * h(3dt / 4) * (dt / 2))
        @test floquet.left_channels[1] ≈ kron(transpose(conj(u_left)), u_left)
        @test floquet.right_channels[1] ≈ kron(transpose(conj(u_right)), u_right)
    end

    @testset "dense opt-in refuses unsafe memory" begin
        χ = 3
        q = randn(rng, ComplexF64, χ, 4, χ, 4)
        left, right = random_channels(rng, 2)
        floquet = FloquetOperator(q, left, right)
        bytes = estimated_dense_bytes(floquet)
        @test bytes == (4χ)^2 * sizeof(ComplexF64)
        @test_throws ArgumentError dense_floquet(floquet; memory_limit_bytes=bytes - 1)
        @test dense_floquet(floquet; memory_limit_bytes=bytes) ≈
              dense_period_reference(q, left, right)
    end

    @testset "hot actions reuse workspace without M-scaled allocation" begin
        χ = 3
        q = randn(rng, ComplexF64, χ, 4, χ, 4)
        left2, right2 = random_channels(rng, 2)
        left20, right20 = random_channels(rng, 20)
        short = FloquetOperator(q, left2, right2)
        long = FloquetOperator(q, left20, right20)
        short_work = StepWorkspace(short)
        long_work = StepWorkspace(long)
        x = randn(rng, ComplexF64, 4χ)
        y = similar(x)
        apply_period!(y, x, short, short_work)
        apply_period!(y, x, long, long_work)
        short_alloc = @allocated apply_period!(y, x, short, short_work)
        long_alloc = @allocated apply_period!(y, x, long, long_work)
        @test short_alloc <= 256
        @test long_alloc <= short_alloc + 64
    end

    @testset "solver-facing operator reuses its owned workspace" begin
        χ = 100
        M = 20
        q = randn(rng, ComplexF64, χ, 4, χ, 4)
        left, right = random_channels(rng, M)
        floquet = FloquetOperator(q, left, right)
        solver_operator = FloquetLinearOperator(floquet)
        solver_adjoint = adjoint(solver_operator)
        x = randn(rng, ComplexF64, 4χ)
        y = similar(x)
        mul!(y, solver_operator, x)
        mul!(y, solver_adjoint, x)
        @test @allocated(mul!(y, solver_operator, x)) == 0
        @test @allocated(mul!(y, solver_adjoint, x)) == 0
        @test y ≈ adjoint(dense_floquet(floquet;
                                        memory_limit_bytes=estimated_dense_bytes(floquet))) * x
    end

    @testset "real UniformTEMPO evolve guards q-axis compatibility" begin
        χ = 3
        dt = 0.08
        q = randn(rng, ComplexF64, χ, 4, χ, 4)
        v_right = randn(rng, ComplexF64, χ)
        v_left = transpose(randn(rng, ComplexF64, χ))
        pt = UniformTEMPO.UniformPTMPO(2, dt, q, v_right, v_left)
        initial = randn(rng, ComplexF64, χ, 4)
        model = SpinBosonModel(drive=:transversal)
        omega_d = 1.7
        h_s(t) = system_hamiltonian(model, t, omega_d)
        left = UniformTEMPO.local_channel((0.0, dt / 2), h_s)
        right = UniformTEMPO.local_channel((dt / 2, dt), h_s)
        step = StepOperator(q, left, right)
        actual = similar(vec(initial))
        apply_step!(actual, vec(initial), step, StepWorkspace(step))
        expected = UniformTEMPO.evolve(pt, initial, 1, h_s; return_full=true)
        @test actual ≈ vec(expected) rtol=1e-12 atol=1e-12
    end
end
