# D-sweep: full-circuit ungraded SU from random init at D = 3, 4, 6.
# Two init families: (a) random V/P contraction at bond dim D (user's route),
# (b) direct random merged rank-6 tensors.
include(joinpath(@__DIR__, "..", "scripts", "tc_peps.jl"))
using Printf, Random

UP = UPSPACE
H0, _ = toric_code_hamiltonian(0.0, 0.0; P = UP)
lat = fill(UP, 2, 2)
s_op, p_op = star_op(1.0, UP), plaq_op(1.0, UP)

function stabs(ψ, env)
    a = Float64[]; b = Float64[]
    for r in 1:2, c in 1:2
        Hs = empty_localoperator(lat)
        PEPSKit.add_term!(Hs, [CartesianIndex(r, c - 1), CartesianIndex(r, c), CartesianIndex(r + 1, c)], s_op)
        push!(a, -real(expectation_value(ψ, Hs, env)))
        Hp = empty_localoperator(lat)
        PEPSKit.add_term!(Hp, [CartesianIndex(r - 1, c), CartesianIndex(r, c), CartesianIndex(r, c + 1)], p_op)
        push!(b, -real(expectation_value(ψ, Hp, env)))
    end
    return a, b
end

"(a) Merged tensor from random V/P at bond dim D: V(D,D,D,D), PE/PN(2,D,D)."
function random_merged_tensor_VP_D(D, P, Vsp)
    V_arr = randn(D, D, D, D)
    PE_arr = randn(2, D, D)
    PN_arr = randn(2, D, D)
    T = zeros(2, 2, D, D, D, D)  # [pE, pN, n, e, s, w]
    for pE in 1:2, pN in 1:2, n in 1:D, e in 1:D, s in 1:D, w in 1:D
        val = 0.0
        for a in 1:D, b in 1:D
            val += V_arr[b, a, s, w] * PE_arr[pE, a, e] * PN_arr[pN, b, n]
        end
        T[pE, pN, n, e, s, w] = val
    end
    data = reshape(reshape(T, 4, D, D, D, D), 4, D^4)
    return normalize!(TensorMap(ComplexF64.(data), P, Vsp ⊗ Vsp ⊗ Vsp' ⊗ Vsp'), Inf)
end

"(b) Direct random merged rank-6 tensor (physical 2×2 fused, virtual D)."
function random_merged_tensor_direct(D, P, Vsp)
    T = randn(2, 2, D, D, D, D)
    data = reshape(reshape(T, 4, D, D, D, D), 4, D^4)
    return normalize!(TensorMap(ComplexF64.(data), P, Vsp ⊗ Vsp ⊗ Vsp' ⊗ Vsp'), Inf)
end

function run_case(D, init; seed = 1, nstep = 400)
    println("\n=== D = $D, init = $init (full circuit, seed $seed) ==="); flush(stdout)
    UV = uspace(D)
    Random.seed!(seed)
    maker = init == :VP ? random_merged_tensor_VP_D : random_merged_tensor_direct
    ψ = InfinitePEPS([maker(D, UP, UV) for _ in 1:2, _ in 1:2])
    circuit = build_su_circuit(0.05; P = UP)
    alg = SimpleUpdate(; trunc = PEPSKit._get_fixedspacetrunc(ψ), imaginary_time = true)
    env = init_suweight(ψ, UV)
    env_prev = deepcopy(env)
    for i in 1:nstep
        ψ, env, ϵ = PEPSKit.su_iter(ψ, circuit, alg, env)
        if i % 50 == 0 || i == 1
            diff = PEPSKit.compare_weights(env_prev, env)
            E = real(expectation_value(ψ, H0, CTMRGEnv(env)))
            @printf("  iter %-4d E_cell ≈ %+.6f  |Δλ| = %.2e  ϵ = %.2e\n", i, E, diff, ϵ)
            flush(stdout)
            env_prev = deepcopy(env)
            diff < 1e-10 && break
        end
    end
    en, _ = leading_boundary(CTMRGEnv(randn, ComplexF64, ψ, uenv(max(20, 2 * D^2))), ψ;
                             tol = 1e-8, maxiter = 500, verbosity = 0)
    E = real(expectation_value(ψ, H0, en))
    a, b = stabs(ψ, en)
    @printf("  FINAL D=%d %s: E_cell = %+.8f (per edge spin %+.8f)\n", D, init, E, E / 8)
    @printf("    ⟨A⟩ = %s\n    ⟨B⟩ = %s\n",
            join([@sprintf("%.6f", x) for x in a], " "), join([@sprintf("%.6f", x) for x in b], " "))
    flush(stdout)
    return E
end

for D in [3, 4, 6]
    run_case(D, :VP)
    run_case(D, :direct)
end
