# Seed probe: does random-init SU ever land in the true-TC basin (E -> -1)
# rather than the cycle-gas attractor (E = -0.5)?
include(joinpath(@__DIR__, "..", "scripts", "tc_peps.jl"))
using Printf, Random

H0, _ = toric_code_hamiltonian(0.0, 0.0)
lat = fill(PSPACE, 2, 2)
Hs = empty_localoperator(lat)
PEPSKit.add_term!(Hs, [CartesianIndex(1, 0), CartesianIndex(1, 1), CartesianIndex(2, 1)], star_op())
Hp = empty_localoperator(lat)
PEPSKit.add_term!(Hp, [CartesianIndex(0, 1), CartesianIndex(1, 1), CartesianIndex(1, 2)], plaq_op())

for seed in [1, 2, 3, 7, 11, 42]
    Random.seed!(seed)
    Vd2 = vspace(2)
    ψ = InfinitePEPS(randn, ComplexF64, fill(PSPACE, 2, 2), fill(Vd2, 2, 2))
    circuit = build_su_circuit(0.05)
    alg = SimpleUpdate(; trunc = PEPSKit._get_fixedspacetrunc(ψ), imaginary_time = true)
    env = init_suweight(ψ, 2)
    for i in 1:150
        ψ, env, _ = PEPSKit.su_iter(ψ, circuit, alg, env)
    end
    en, _ = leading_boundary(CTMRGEnv(randn, ComplexF64, ψ, envspace(16)), ψ;
                             tol = 1e-6, maxiter = 300, verbosity = 0)
    E = real(expectation_value(ψ, H0, en)) / 8
    A = -real(expectation_value(ψ, Hs, en))
    B = -real(expectation_value(ψ, Hp, en))
    @printf("seed %3d: E/N = %+.6f, ⟨A⟩ = %+.4f, ⟨B⟩ = %+.4f\n", seed, E, A, B)
    flush(stdout)
end
