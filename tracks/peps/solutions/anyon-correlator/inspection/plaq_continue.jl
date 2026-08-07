# Mechanism probe: take the random-init ungraded SU state (stalled at
# ⟨A⟩=1, ⟨B⟩≈0.5) and continue with PLAQUETTE GATES ONLY.
#   ⟨B⟩ -> 1  => star/plaquette competition was the blocker (truncation can grow loops)
#   ⟨B⟩ stalls => the SU truncation metric itself cannot grow loop order
include(joinpath(@__DIR__, "..", "scripts", "tc_peps.jl"))
using Printf, Random

UP, UV = UPSPACE, uspace(2)
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

function plaq_circuit(dt)
    g = PEPSKit.gate_to_mpo(pauli_gate3(phys_tmap(PLAQ_B_mat(), 3, UP), dt, 1.0))
    gates = Pair{Vector{CartesianIndex{2}}, Any}[]
    for r in 1:2, c in 1:2
        push!(gates, [CartesianIndex(r - 1, c), CartesianIndex(r, c), CartesianIndex(r, c + 1)] => g)
    end
    return PEPSKit.LocalCircuit(fill(UP, 2, 2), gates)
end

function show(ψ, env, tag, i)
    en = CTMRGEnv(env)
    E = real(expectation_value(ψ, H0, en))
    a, b = stabs(ψ, en)
    @printf("  %s %-4d E_cell ≈ %+.6f  ⟨A⟩ = %s  ⟨B⟩ = %s\n", tag, i, E,
            join([@sprintf("%.4f", x) for x in a], " "), join([@sprintf("%.4f", x) for x in b], " "))
    flush(stdout)
end

# --- reproduce the stalled random-init state (seed 1, full circuit) ---
Random.seed!(1)
T0 = random_merged_tensor_VP(randn(2, 2, 2, 2), randn(2, 2, 2), randn(2, 2, 2), UP, UV)
ψ = InfinitePEPS(fill(T0, 2, 2))
env = init_suweight(ψ, UV)
alg = SimpleUpdate(; trunc = PEPSKit._get_fixedspacetrunc(ψ), imaginary_time = true)
full = build_su_circuit(0.05; P = UP)
for i in 1:200
    global ψ, env
    ψ, env, _ = PEPSKit.su_iter(ψ, full, alg, env)
end
println("stalled state after 200 full-circuit sweeps:")
show(ψ, env, "full", 200)

# --- continue with plaquette gates only ---
plaq = plaq_circuit(0.05)
for i in 1:300
    global ψ, env
    ψ, env, _ = PEPSKit.su_iter(ψ, plaq, alg, env)
    (i == 1 || i % 25 == 0) && show(ψ, env, "plaq", i)
end

en, _ = leading_boundary(CTMRGEnv(randn, ComplexF64, ψ, uenv(20)), ψ; tol = 1e-8, maxiter = 500, verbosity = 0)
E = real(expectation_value(ψ, H0, en))
a, b = stabs(ψ, en)
@printf("FINAL: E_cell = %+.10f, ⟨A⟩ = %s, ⟨B⟩ = %s\n", E,
        join([@sprintf("%.6f", x) for x in a], " "), join([@sprintf("%.6f", x) for x in b], " "))
flush(stdout)
