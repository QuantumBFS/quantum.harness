using Test
using LinearAlgebra
using Random
using JuMP
using MosekTools

include("KullCGRDM.jl")
using .KullCGRDM

relative_error(A, B) = norm(A - B) / max(norm(A), norm(B), eps(Float64))
hs_inner(A, B) = tr(A' * B)

function random_density(rng, dimension)
    X = randn(rng, ComplexF64, dimension, dimension)
    rho = X * X'
    rho / tr(rho)
end

function cyclic_shift_operator(d, n)
    dims = ntuple(_ -> d, n)
    linear = LinearIndices(dims)
    U = zeros(ComplexF64, d^n, d^n)
    for state in CartesianIndices(dims)
        shifted = (Tuple(state)[2:end]..., state[1])
        U[linear[shifted...], linear[state]] = 1
    end
    U
end

function translation_invariant_density(rng, d, n)
    rho = random_density(rng, d^n)
    U = cyclic_shift_operator(d, n)
    sum(U^shift * rho * (U')^shift for shift in 0:n-1) / n
end

function leading_marginal(rho, d, n, m)
    reduced = rho
    dims = ntuple(_ -> d, n)
    for _ in n:-1:m+1
        reduced = partial_trace(reduced, dims, length(dims))
        dims = dims[1:end-1]
    end
    reduced
end

const QUIET = Dict("MSK_IPAR_LOG" => 0)

@testset "Kull author-aligned coarse-grained RDM" begin
    product = product_frozen_mps(ComplexF64[1, 2im])
    map_d2 = random_canonical_frozen_mps(2, 2; seed=4109)
    map_d3 = random_canonical_frozen_mps(2, 3; seed=788)

    @testset "author default, explicit regression, and dimensions" begin
        @test author_default_k0(2, 2) == 3
        @test author_default_k0(2, 3) == 4
        for D in 1:8
            k0 = author_default_k0(2, D)
            @test 2^k0 > D^2
            @test k0 == 1 || 2^(k0 - 1) <= D^2
        end

        default = build_kull_primal(HEISENBERG_H; frozen=map_d2, depth=3)
        @test default.metadata["k0"] == 3
        @test default.metadata["rho_support"] == 4
        @test default.metadata["omega_physical_support_offset"] == 2
        @test size(default.rho3) == (16, 16)
        @test sort(collect(keys(default.omegas))) == [3]
        @test size(default.omegas[3]) == (16, 16)
        @test default.inventory.psd_block_dimensions == [16, 16]

        regression = build_kull_primal(HEISENBERG_H; frozen=map_d2, depth=4, k0=2)
        @test regression.metadata["k0"] == 2
        @test regression.metadata["rho_support"] == 3
        @test size(regression.rho3) == (8, 8)
        @test sort(collect(keys(regression.omegas))) == [2, 3, 4]
        @test regression.inventory.psd_block_dimensions == [8, 16, 16, 16]
        @test length(regression.constraints[:bottom]) == 128
        @test length(regression.constraints[:flow]) == 256

        practical = build_kull_primal(HEISENBERG_H; depth=3)
        @test practical.metadata["k0"] == 2
        @test isempty(practical.omegas)
        @test size(practical.rho3) == (8, 8)
        @test practical.metadata["map_fingerprint"] === nothing
        @test_throws ArgumentError build_kull_primal(HEISENBERG_H;
            frozen=map_d2, depth=2)
    end

    @testset "exact axes, direct products, and adjoints" begin
        expected_W2 = transpose(kron(ComplexF64[1, 2im] / sqrt(5),
            ComplexF64[1, 2im] / sqrt(5)))
        @test W2(product) ≈ expected_W2 atol=1e-15 rtol=0
        @test AXIS_CONTRACT.A == (:virtual_left, :physical, :virtual_right)
        @test AXIS_CONTRACT.omega ==
            (:physical_left, :virtual_left, :virtual_right, :physical_right)

        for frozen in (product, map_d3), m in 1:6
            @test relative_error(direct_Wm(frozen, m), recursive_Wm(frozen, m)) < 1e-11
        end
        @test bottom_bridge_operators(map_d3; k0=3).V0 ≈ direct_Wm(map_d3, 3; start_site=2)

        rng = MersenneTwister(2782)
        dims = (2, 3, 2)
        X = randn(rng, ComplexF64, prod(dims), prod(dims))
        Ytrace = randn(rng, ComplexF64, 4, 4)
        @test abs(hs_inner(Ytrace, partial_trace(X, dims, 2)) -
            hs_inner(partial_trace_adjoint(Ytrace, dims, 2), X)) /
            max(abs(hs_inner(Ytrace, partial_trace(X, dims, 2))), 1) < 1e-11
        K = randn(rng, ComplexF64, 5, prod(dims))
        Yforward = randn(rng, ComplexF64, 5, 5)
        @test abs(hs_inner(Yforward, forward_map(K, X)) -
            hs_inner(forward_map_adjoint(K, Yforward), X)) /
            max(abs(hs_inner(Yforward, forward_map(K, X))), 1) < 1e-11
    end

    @testset "synthetic feasibility for k0 = 2 and 3" begin
        rng = MersenneTwister(3856)
        d, n = 2, 7
        physical = translation_invariant_density(rng, d, n)
        rhos = Dict(m => leading_marginal(physical, d, n, m) for m in 3:n)

        for frozen in (product, map_d3), k0 in (2, 3)
            omegas = Dict{Int,Matrix{ComplexF64}}()
            omega_dims = Dict{Int,Tuple}()
            for key in k0:n-2
                support = key + 2
                omegas[key], omega_dims[key] = compress_physical_rdm(frozen, rhos[support], support)
                @test omega_dims[key] == (d, size(site_tensor(frozen, 2), 1),
                    size(site_tensor(frozen, support - 1), 3), d)
                @test minimum(eigvals(Hermitian(omegas[key]))) > -1e-11
            end

            bridge = bottom_bridge_operators(frozen; k0)
            rho0 = rhos[k0 + 1]
            @test relative_error(forward_map(bridge.to_trace_physical_left, rho0),
                partial_trace(omegas[k0], omega_dims[k0], 1)) < 1e-11
            @test relative_error(forward_map(bridge.to_trace_physical_right, rho0),
                partial_trace(omegas[k0], omega_dims[k0], 4)) < 1e-11

            for key in k0:n-3
                flow = flow_operators(frozen, key)
                @test relative_error(forward_map(flow.to_trace_physical_left, omegas[key]),
                    partial_trace(omegas[key + 1], omega_dims[key + 1], 1)) < 1e-11
                @test relative_error(forward_map(flow.to_trace_physical_right, omegas[key]),
                    partial_trace(omegas[key + 1], omega_dims[key + 1], 4)) < 1e-11
            end
        end
    end

    @testset "primal monotonicity and dual correction" begin
        optimizer = MosekTools.Optimizer
        base = build_kull_primal(HEISENBERG_H; depth=3, k0=2, optimizer,
            solver_settings=QUIET)
        level2 = build_kull_primal(HEISENBERG_H; frozen=map_d2, depth=2, k0=2,
            optimizer, solver_settings=QUIET)
        level3 = build_kull_primal(HEISENBERG_H; frozen=map_d2, depth=3, k0=2,
            optimizer, solver_settings=QUIET)
        base_result = solve_kull_primal!(base; print_inventory=false)
        level2_result = solve_kull_primal!(level2; print_inventory=false)
        level3_result = solve_kull_primal!(level3; print_inventory=false)
        @test base_result.clean
        @test level2_result.clean
        @test level3_result.clean
        @test level2_result.lower_bound_candidate >= base_result.lower_bound_candidate - 1e-7
        @test level3_result.lower_bound_candidate >= level2_result.lower_bound_candidate - 1e-7
        @test level3_result.lower_bound_candidate <= EXACT_ENERGY + 1e-7

        shifted_h = HEISENBERG_H + 0.037 * Matrix{ComplexF64}(I, 4, 4)
        shifted = build_kull_primal(shifted_h; frozen=map_d2, depth=2, k0=2,
            optimizer, solver_settings=QUIET)
        shifted_result = solve_kull_primal!(shifted; print_inventory=false)
        certificate = reconstruct_dual_certificate(shifted)
        @test shifted_result.clean
        @test isfinite(certificate.residual_correction)
        @test certificate.residual_correction >= 0
        @test certificate.corrected_lower_bound <= shifted_result.lower_bound_candidate + 1e-7
        @test certificate.maximum_stationarity_residual >= 0
        @test isfinite(certificate.corrected_lower_bound)
        @test certificate.map_fingerprint == map_d2.fingerprint
    end

    @testset "MATLAB D=2 regression benchmark" begin
        optimizer = MosekTools.Optimizer
        # External oracle: IlyaKull/RDM_Constraints_Renormalization at
        # 2e9015fff5d9bc5b170cdc6cee98fbbb928decda, MATLAB R2026a, YALMIP/MOSEK.
        a, b = sqrt(0.7), sqrt(0.3)
        A = zeros(ComplexF64, 2, 2, 2)
        A[:,1,:] = Diagonal([a,b])
        A[:,2,:] = [0 a; b 0]
        matlab_map = FrozenUniformMPS([A]; canonical_gauge=:left,
            canonical_residual=norm(sum(A[:,s,:]' * A[:,s,:] for s in 1:2) - I))
        @test rank(W2(matlab_map)) == 4
        @test norm(W2(matlab_map)) ≈ sqrt(2) atol=1e-14

        matlab_references = Dict(2 => -0.499999995222174, 3 => -0.499622710742075)
        for depth in (2, 3)
            problem = build_kull_primal(HEISENBERG_H; frozen=matlab_map,
                depth, k0=2, optimizer, solver_settings=QUIET)
            result = solve_kull_primal!(problem; print_inventory=false)
            @test result.clean
            @test result.lower_bound_candidate ≈ matlab_references[depth] atol=2e-8 rtol=0
        end
    end
end
