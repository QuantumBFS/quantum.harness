# Directional-derivative diagnosis for the DEFECTIVE plaquette, center (2,1)
# (= plaquette_op_at(2) in comprehension order; labeled "#3" in the continuation
# log's loop order). Sections (c) and (d) only; (a)(b) already verified.
include(joinpath(@__DIR__, "..", "scripts", "ad_staged_gd.jl"))
using Printf, Random, JLD2, Zygote

const CKPT = joinpath(@__DIR__, "..", "..", "..", "results", "20260729-090528-ad-staged-gd")
const ST = Stage("diag", 20, 1.0e-10, 500, 1.0e-6, 1)

# plaquette center (2,1): sites [(r−1,c),(r,c),(r,c+1)] = [(1,1),(2,1),(2,2)]
function slow_plaq_op()
    lat = fill(UP, 2, 2)
    Hp = empty_localoperator(lat)
    PEPSKit.add_term!(Hp, [CartesianIndex(1, 1), CartesianIndex(2, 1), CartesianIndex(2, 2)],
                      plaq_op(1.0, UP))
    return Hp
end

d = load(joinpath(CKPT, "contC_step10.jld2"))
ψ = InfinitePEPS(d["tensors"])
env, _ = stage_env(ψ, ST)

bnd = SimultaneousCTMRG(; tol = 1.0e-10, maxiter = 500, verbosity = 0)
galg = PEPSKit.GradientAlgorithm(; alg = :FixedPointGradient, tol = 1.0e-6, maxiter = 10)
function grad_of(costop)
    E, gs = withgradient(ψ) do ψv
        env′, info = PEPSKit.hook_pullback(leading_boundary, env, ψv, bnd; alg_rrule = galg)
        return cost_function(ψv, env′, costop)
    end
    return E, only(gs)
end
frobnorm(g) = sqrt(sum(norm.(g.A) .^ 2))

Hslow = slow_plaq_op()
B3check = -real(expectation_value(ψ, Hslow, env))
println(@sprintf("defective plaquette (2,1): ⟨B_p⟩ = %+.10f (deficit %.6f)", B3check, 1 - B3check))
flush(stdout)

E_tot, gE = grad_of(H0)
ngE = frobnorm(gE)
println(@sprintf("energy gradient: ‖g_E‖ = %.6e", ngE)); flush(stdout)

B3, gB3 = grad_of(Hslow)   # cost = −⟨B_(2,1)⟩
ngB3 = frobnorm(gB3)
dir = [-gE.A[i, j] / ngE for i in 1:2, j in 1:2]
dB3_dalpha = -real(sum(dot(gB3.A[i, j], dir[i, j]) for i in 1:2, j in 1:2))
println(@sprintf("defective term: −⟨B_(2,1)⟩ = %+.10f, ‖g_{B(2,1)}‖ = %.6e", B3, ngB3))
println(@sprintf("d⟨B_(2,1)⟩/dα along energy-descent −g_E/‖g_E‖ = %+.6e", dB3_dalpha))
println(@sprintf("cosine(g_E, g_{{B(2,1)}}) = %+.6f",
                 real(sum(dot(gE.A[i, j], gB3.A[i, j]) for i in 1:2, j in 1:2)) / (ngE * ngB3)))
flush(stdout)

println("\ncost of lifting the defective plaquette: E along ±g_{B(2,1)}"); flush(stdout)
for (sgn, tag) in [(-1.0, "−g_B (lift ⟨B⟩ up)"), (+1.0, "+g_B (push down)")]
    dirB = [sgn * gB3.A[i, j] / ngB3 for i in 1:2, j in 1:2]
    for α in [1e-2, 5e-2]
        ψt = InfinitePEPS([ψ.A[i, j] + α * dirB[i, j] for i in 1:2, j in 1:2])
        envt, _ = stage_env(ψt, ST)
        Et = cost_function(ψt, envt, H0)
        B3t = -real(expectation_value(ψt, Hslow, envt))
        println(@sprintf("  %s α = %.2f: E = %+.8f, ⟨B_(2,1)⟩ = %+.8f", tag, α, Et, B3t))
        flush(stdout)
    end
end
