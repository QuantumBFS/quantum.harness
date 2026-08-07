# Decisive plaquette/star gate isolation test (ungraded, SU-only).
#   Plaquette-only SU from |+⟩^N (A=1 sector): must converge to the TC ground state.
#   Star-only SU from |0⟩^N (B=1 sector): mirror test, same target.
# Checkpoint after 1 sweep: ⟨B⟩ = tanh(2 dt) = 0.09967 (dt = 0.05).
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

"Product-state iPEPS: bit = 0 -> |0⟩^N (Z basis), bit = 1 -> |+⟩^N (X basis)."
function product_peps(bit::Int)
    T = zeros(2, 2, 2, 2, 2, 2)
    if bit == 0
        T[1, 1, 1, 1, 1, 1] = 1.0          # pE = 0, pN = 0 (Z=+1)
    else
        T[:, :, 1, 1, 1, 1] .= 0.5         # |+⟩ on both qubits (uniform in Z basis)
    end
    data = reshape(reshape(T, 4, 2, 2, 2, 2), 4, 16)
    return InfinitePEPS(fill(TensorMap(ComplexF64.(data), UP, UV ⊗ UV ⊗ UV' ⊗ UV'), 2, 2))
end

function circuit_only(kind::Symbol, dt)
    lattice = fill(UP, 2, 2)
    gates = Pair{Vector{CartesianIndex{2}}, Any}[]
    if kind == :plaq
        g = PEPSKit.gate_to_mpo(pauli_gate3(phys_tmap(PLAQ_B_mat(), 3, UP), dt, 1.0))
        for r in 1:2, c in 1:2
            push!(gates, [CartesianIndex(r - 1, c), CartesianIndex(r, c), CartesianIndex(r, c + 1)] => g)
        end
    else
        g = PEPSKit.gate_to_mpo(pauli_gate3(phys_tmap(STAR_A_mat(), 3, UP), dt, 1.0))
        for r in 1:2, c in 1:2
            push!(gates, [CartesianIndex(r, c - 1), CartesianIndex(r, c), CartesianIndex(r + 1, c)] => g)
        end
    end
    return PEPSKit.LocalCircuit(lattice, gates)
end

function run_case(name, bit, kind, nstep = 150)
    println("\n=== $name ==="); flush(stdout)
    ψ = product_peps(bit)
    env = init_suweight(ψ, UV)
    alg = SimpleUpdate(; trunc = PEPSKit._get_fixedspacetrunc(ψ), imaginary_time = true)
    circuit = circuit_only(kind, 0.05)
    for i in 1:nstep
        ψ, env, ϵ = PEPSKit.su_iter(ψ, circuit, alg, env)
        if i == 1 || i % 25 == 0
            en = CTMRGEnv(env)
            E = real(expectation_value(ψ, H0, en))
            a, b = stabs(ψ, en)
            @printf("  sweep %-3d E_cell ≈ %+.6f  ⟨A⟩ = %s  ⟨B⟩ = %s\n", i, E,
                    join([@sprintf("%.4f", x) for x in a], " "),
                    join([@sprintf("%.4f", x) for x in b], " "))
            flush(stdout)
        end
    end
    en, _ = leading_boundary(CTMRGEnv(randn, ComplexF64, ψ, uenv(20)), ψ; tol = 1e-8, maxiter = 500, verbosity = 0)
    E = real(expectation_value(ψ, H0, en))
    a, b = stabs(ψ, en)
    @printf("  FINAL: E_cell = %+.10f, ⟨A⟩ = %s, ⟨B⟩ = %s\n", E,
            join([@sprintf("%.6f", x) for x in a], " "), join([@sprintf("%.6f", x) for x in b], " "))
    flush(stdout)
    return E
end

println("prediction after 1 plaquette sweep: ⟨B⟩ = tanh(0.1) = ", tanh(0.1))
run_case("plaquette-only SU from |+⟩^N", 1, :plaq)
run_case("star-only SU from |0⟩^N", 0, :star)
