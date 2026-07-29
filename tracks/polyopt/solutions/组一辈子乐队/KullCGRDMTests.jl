using Test
using LinearAlgebra
using Random
using JuMP
using MosekTools

include("KullCGRDM.jl")
using .KullCGRDM
include("VUMPSProducer.jl")
using .VUMPSProducer
include("MPSKitAdapter.jl")
using .MPSKitAdapter

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
    two_site_map = FrozenUniformMPS([
        random_canonical_frozen_mps(2, 2; seed=901).tensors[1],
        random_canonical_frozen_mps(2, 2; seed=902).tensors[1]])

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

    @testset "two-site parity-aware fallback" begin
        problem = build_kull_primal(HEISENBERG_H; frozen=two_site_map, depth=4, k0=2)
        @test sort(collect(keys(problem.omegas))) ==
            [(2,1), (2,2), (3,1), (3,2), (4,1), (4,2)]
        @test problem.metadata["omega_start_parities"] == [1, 2]
        @test problem.metadata["omega_key_scheme"] == "(depth,start_parity)"
        @test problem.inventory.psd_block_dimensions == [8; fill(16, 6)]
        @test problem.inventory.psd_block_count == 7
        @test length(problem.constraints[:bottom]) == 256
        @test length(problem.constraints[:flow]) == 512
        @test problem.metadata["coefficient_policy"]["complete_interval_enclosure"] === false

        rng = MersenneTwister(7741)
        d, n = 2, 7
        physical = translation_invariant_density(rng, d, n)
        rhos = Dict(m => leading_marginal(physical, d, n, m) for m in 3:n)
        omegas = Dict{Tuple{Int,Int},Matrix{ComplexF64}}()
        dims = Dict{Tuple{Int,Int},Tuple}()
        for key in 2:n-2, parity in 1:2
            support = key + 2
            omegas[(key, parity)], dims[(key, parity)] = compress_physical_rdm(
                two_site_map, rhos[support], support; start_site=parity)
        end
        for parity in 1:2
            bridge = bottom_bridge_operators(two_site_map; k0=2, start_site=parity)
            @test relative_error(forward_map(bridge.to_trace_physical_left, rhos[3]),
                partial_trace(omegas[(2, parity)], dims[(2, parity)], 1)) < 1e-11
            @test relative_error(forward_map(bridge.to_trace_physical_right, rhos[3]),
                partial_trace(omegas[(2, parity)], dims[(2, parity)], 4)) < 1e-11
        end
        for key in 2:n-3, parity in 1:2
            flow = flow_operators(two_site_map, key; start_site=parity)
            switched = 3 - parity
            @test relative_error(forward_map(flow.to_trace_physical_left,
                    omegas[(key, switched)]),
                partial_trace(omegas[(key + 1, parity)], dims[(key + 1,parity)], 1)) < 1e-11
            @test relative_error(forward_map(flow.to_trace_physical_right,
                    omegas[(key, parity)]),
                partial_trace(omegas[(key + 1,parity)], dims[(key + 1,parity)], 4)) < 1e-11
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
        @test certificate.maximum_stationarity_residual < 1e-7
        @test !certificate.trace_nonincreasing
        @test certificate.trace_envelope > 1
        @test isfinite(certificate.corrected_lower_bound)
        @test certificate.map_fingerprint == map_d2.fingerprint
    end

    @testset "symmetric XXZ VUMPS adapter" begin
        settings = VUMPSSettings(D=2, unitcell=2, delta=0.5, symmetry=:u1,
            maxiter=5, tol=1e-5, seed=812, verbosity=0)
        spaces = u1_bond_spaces(8, 8)
        @test sort(dense_u1_charges(spaces.coarse)) == [-6, -4, -2, 0, 0, 2, 4, 6]
        @test sort(dense_u1_charges(spaces.internal)) == [-7, -5, -3, -1, 1, 3, 5, 7]
        produced = run_u1_vumps(D=2, internal_D=2, delta=0.5,
            maxiter=5, tol=1e-5, seed=812, verbosity=0)
        blocked = freeze_u1_blocked_mpskit(produced.state, produced.record)
        @test produced.record["symmetry"] == "u1"
        @test produced.record["delta"] == 0.5
        @test produced.record["internal_D"] == 2
        @test blocked.symmetry.physical_charges == [2, 0, 0, -2]
        @test length(blocked.symmetry.virtual_charges) == 2
        @test size(only(blocked.frozen.tensors)) == (2, 4, 2)
        @test mps_charge_residual(blocked.frozen, blocked.symmetry) < 1e-12
        @test blocked.frozen.canonical_residual < 1e-10
        @test blocked.metadata["charge_residual"] == 0
        @test blocked.metadata["physical_charges"] == [2, 0, 0, -2]
        @test blocked.metadata["coarse_bond_dimension"] == 2

        h = blocked_xxz_hamiltonian(0.5)
        problem = build_kull_primal(h; frozen=blocked.frozen, depth=2, k0=2,
            symmetry=blocked.symmetry, optimizer=MosekTools.Optimizer,
            solver_settings=QUIET)
        result = solve_kull_primal!(problem; print_inventory=false)
        certificate = reconstruct_dual_certificate(problem)
        @test isfinite(result.lower_bound_candidate)
        @test result.constraint_residual < 1e-7
        @test certificate.maximum_stationarity_residual < 1e-7
        @test certificate.corrected_lower_bound <= result.lower_bound_candidate + 1e-7
        @test maximum(problem.inventory.psd_block_dimensions) < 64

        @test_throws ArgumentError run_u1_vumps(D=2, internal_D=3,
            delta=0.5, maxiter=1)
        @test_throws ArgumentError run_vumps(VUMPSSettings(D=2, unitcell=1,
            delta=0.5, symmetry=:u1, maxiter=1))
    end

    @testset "XXZ U(1) block-PSD regression" begin
        delta = 0.5
        physical_charges = [2, 0, 0, -2]
        virtual_charges = [-1, 1]
        symmetry = U1Symmetry(physical_charges, virtual_charges)
        A = zeros(ComplexF64, 2, 4, 2)
        A[1,1,2] = sqrt(0.3)
        A[2,2,2] = sqrt(0.7)
        A[1,3,1] = sqrt(0.7)
        A[2,4,1] = sqrt(0.3)
        symmetric_map = FrozenUniformMPS([A]; canonical_gauge=:left,
            canonical_residual=norm(sum(A[:,s,:]' * A[:,s,:] for s in 1:4) - I))
        h = blocked_xxz_hamiltonian(delta)

        @test mps_charge_residual(symmetric_map, symmetry) == 0
        @test equivariance_residual(h,
            product_charges(physical_charges, physical_charges),
            product_charges(physical_charges, physical_charges)) == 0
        coarse_charges = product_charges(-virtual_charges, virtual_charges)
        @test equivariance_residual(direct_Wm(symmetric_map, 2), coarse_charges,
            product_charges(physical_charges, physical_charges)) == 0
        bridge = bottom_bridge_operators(symmetric_map; k0=2)
        @test equivariance_residual(bridge.to_trace_physical_left,
            product_charges(-virtual_charges, virtual_charges, physical_charges),
            product_charges(physical_charges, physical_charges, physical_charges)) == 0
        @test equivariance_residual(bridge.to_trace_physical_right,
            product_charges(physical_charges, -virtual_charges, virtual_charges),
            product_charges(physical_charges, physical_charges, physical_charges)) == 0
        flow = flow_operators(symmetric_map, 2)
        omega_charges = product_charges(physical_charges, -virtual_charges,
            virtual_charges, physical_charges)
        @test equivariance_residual(flow.to_trace_physical_left,
            product_charges(-virtual_charges, virtual_charges, physical_charges),
            omega_charges) == 0
        @test equivariance_residual(flow.to_trace_physical_right,
            product_charges(physical_charges, -virtual_charges, virtual_charges),
            omega_charges) == 0
        @test sort(length.(last.(charge_sectors(product_charges(
            physical_charges, physical_charges, physical_charges))))) ==
            [1, 1, 6, 6, 15, 15, 20]

        dense = build_kull_primal(h; frozen=symmetric_map, depth=3, k0=2,
            optimizer=MosekTools.Optimizer, solver_settings=QUIET)
        blocked = build_kull_primal(h; frozen=symmetric_map, depth=3, k0=2,
            symmetry, optimizer=MosekTools.Optimizer, solver_settings=QUIET)
        @test sort(collect(keys(blocked.omegas))) == [2, 3]
        @test dense.inventory.psd_block_dimensions == [64, 64, 64]
        @test blocked.inventory.psd_block_dimensions == repeat(
            [1, 6, 15, 20, 15, 6, 1], 3)
        @test blocked.inventory.real_scalar_variables == 2772
        @test blocked.inventory.real_scalar_variables < dense.inventory.real_scalar_variables / 4

        dense_result = solve_kull_primal!(dense; print_inventory=false)
        blocked_result = solve_kull_primal!(blocked; print_inventory=false)
        @test dense_result.clean
        @test blocked_result.clean
        @test blocked_result.lower_bound_candidate ≈ dense_result.lower_bound_candidate atol=2e-7 rtol=0
        certificate = reconstruct_dual_certificate(blocked)
        @test certificate.maximum_stationarity_residual < 2e-7
        @test certificate.corrected_lower_bound <= blocked_result.lower_bound_candidate + 2e-7
        @test all(norm(certificate.psd_duals[name] -
            certificate.psd_duals[name]') < 1e-10 for name in keys(certificate.psd_duals))
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
