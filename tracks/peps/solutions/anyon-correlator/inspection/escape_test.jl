# Escape test: SU product-state attractor + random perturbation -> AD fixedpoint.
# Hypothesis: if AD climbs to E < -0.6, the product state is a saddle with a
# defective near-zero gradient, and perturb-then-AD is a valid escape.
# STATUS: inconclusive (aborted before completion); superseded by the cleaner
# gate_isolation.jl / plaq_continue.jl probes. Kept for the record.
include(joinpath(@__DIR__, "..", "scripts", "tc_peps.jl"))
using Printf, Random

H0, _ = toric_code_hamiltonian(0.0, 0.0)
Random.seed!(1)
Vd2 = vspace(2)
ψ = InfinitePEPS(randn, ComplexF64, fill(PSPACE, 2, 2), fill(Vd2, 2, 2))
circuit = build_su_circuit(0.05)
alg = SimpleUpdate(; trunc = PEPSKit._get_fixedspacetrunc(ψ), imaginary_time = true)
env = init_suweight(ψ, 2)
for i in 1:150
    global ψ, env
    ψ, env, _ = PEPSKit.su_iter(ψ, circuit, alg, env)
end

# perturb: add small random intertwiner noise to each tensor
Random.seed!(999)
noise = InfinitePEPS(randn, ComplexF64, fill(PSPACE, 2, 2), fill(Vd2, 2, 2))
ψp = InfinitePEPS([normalize(ψ.A[r, c] + 0.05 * noise.A[r, c], Inf) for r in 1:2, c in 1:2])

envp, _ = leading_boundary(CTMRGEnv(randn, ComplexF64, ψp, envspace(20)), ψp;
                           tol = 1e-8, maxiter = 500, verbosity = 0)
E0 = real(expectation_value(ψp, H0, envp)) / 8
@printf("perturbed SU state: E/N = %+.8f\n", E0)
flush(stdout)

boundary_alg = (; tol = 1.0e-10, alg = :SimultaneousCTMRG,
                trunc = (; alg = :FixedSpaceTruncation), maxiter = 500)
gradient_alg = (; tol = 1.0e-6, alg = :FixedPointGradient, maxiter = 10)
optimizer_alg = (; alg = :LBFGS, tol = 1.0e-7, maxiter = 30,
                 lbfgs_memory = 16, ls_maxiter = 3, ls_maxfg = 3)
ψo, envo, E, info = fixedpoint(H0, ψp, envp; boundary_alg, gradient_alg,
                               optimizer_alg, reuse_env = true, verbosity = 3)
@printf("post-AD: E/N = %+.10f, gradnorm = %.3e, fg evals = %d\n",
        E / 8, info.gradnorms[end], info.fg_evaluations)
println("E trajectory: ", join([@sprintf("%.6f", c / 8) for c in info.costs], " -> "))
flush(stdout)
