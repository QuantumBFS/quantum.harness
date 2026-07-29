#!/usr/bin/env julia
# M2 core experiment (plan Track 2): N=14 arms with ε_cmp bookkeeping.
#   B8        rdm=8 fresh baseline
#   A_n       rdm=8 + CG(n), n = 6, 9, 13   (tower from vumps_A_D2.json)
#   B10-E/C   CONFIG A N=14 energy & cost = the fresh isolated M0-C stock arm
# Sign rules (THEOREM_CONTRACT §3): ΔCG8 = E(A_n*) − E(B8) ≥ −ε_cmp mandatory;
# Δreplace = E(A_n*) − E(B10-E) unconstrained, reported signed.
# ε_cmp(a,b) = (g_a+g_b) + κ·(pfeas_a+dfeas_a+pfeas_b+dfeas_b) + (s_a+s_b).
using JuMP, Mosek, MosekTools, LinearAlgebra, SparseArrays, Printf, SHA
include(joinpath(@__DIR__, "gsb_cg.jl"))
include(joinpath(@__DIR__, "tower_gen.jl"))

const N = 14
const S_TOWER = 4e-16          # generator assembly residual (oracle rows, V3)
const B10E = -0.447396368481   # M0-C configA stock N=14 (fresh, isolated)

# ---- load the VUMPS tensor exactly as persisted --------------------------------
function load_As()
    s = read(joinpath(@__DIR__, "vumps_A_D2.json"), String)
    grab(key) = begin
        m = match(Regex("\"$key\":\\[\\[(.*?)\\],\\[(.*?)\\]\\]"), s)
        [parse.(Float64, split(m.captures[i], ",")) for i in 1:2]
    end
    [[Matrix{ComplexF64}(reshape(grab("A$(i)_re")[μ] .+ 1im .* grab("A$(i)_im")[μ], 2, 2))
      for μ in 1:2] for i in 1:2]
end
A = load_As()
@assert all(norm(sum(A[i][μ]' * A[i][μ] for μ in 1:2) - I) < 1e-10 for i in 1:2)

# ---- one arm: solve with stdout captured, parse Mosek residuals ----------------
supp = [[1, 4]]; coe = [3 / 4]
function arm(label; tower = nothing)
    log = joinpath(@__DIR__, "m2_$(label).mosek.log")
    t0 = time()
    E = redirect_stdout(open(log, "w")) do
        GSB_cg(supp, coe, N, 4; extra = 4, rdm = 8, pso = 0, lso = false,
               QUIET = true, tower = tower)[1]
    end
    wall = time() - t0
    # last interior-point iteration line: ITE PFEAS DFEAS GFEAS PRSTATUS POBJ DOBJ MU TIME
    pfeas = dfeas = mu = NaN
    for l in readlines(log)
        m = match(r"^\s*\d+\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+[\d.eE+-]+\s+\S+\s+[\d.eE+-]+\s+[\d.eE+-]+\s+([\d.eE+-]+)\s", l)
        m !== nothing && ((pfeas, dfeas, mu) = parse.(Float64, m.captures))
    end
    s = tower === nothing ? 0.0 : S_TOWER
    @printf("%-6s E=%.12f  wall=%5.1fs  pfeas=%.1e dfeas=%.1e mu=%.1e\n",
            label, E, wall, pfeas, dfeas, mu)
    (; label, E, wall, pfeas, dfeas, mu, s)
end

κ = maximum(abs, coe)  # problem-scale factor, code-generated from coefficients
εc(a, b) = (a.mu + b.mu) + κ * (a.pfeas + a.dfeas + b.pfeas + b.dfeas) + (a.s + b.s)

println("== M2 arms, N=$N, tensor=vumps_A_D2 (D=2) ==")
B8  = arm("B8")
A6  = arm("A6";  tower = build_tower(N, 6, A))
A9  = arm("A9";  tower = build_tower(N, 9, A))
A13 = arm("A13"; tower = build_tower(N, 13, A))

out = String[]
classify(Δ, ε) = Δ > ε ? "resolved-positive" : Δ < -ε ? "NEGATIVE(BUG?)" : "unresolved"
for X in (A6, A9, A13)
    Δ = X.E - B8.E; ε = εc(X, B8)
    push!(out, @sprintf("ΔCG8(%s) = %+.3e  ε_cmp=%.1e  -> %s", X.label, Δ, ε, classify(Δ, ε)))
end
# monotonicity gate E6 ≤ E9 ≤ E13 within ε_cmp
mono = A9.E >= A6.E - εc(A9, A6) && A13.E >= A9.E - εc(A13, A9)
push!(out, "monotonicity E6≤E9≤E13: " * (mono ? "PASS" : "FAIL"))
# saturation (two consecutive intervals below threshold)
g1 = (A9.E - A6.E) / 3; g2 = (A13.E - A9.E) / 4
thr = max(5e-8, 0.05 * (A13.E - B8.E))
push!(out, @sprintf("per-level gains g(6→9)=%.2e g(9→13)=%.2e thr=%.2e -> %s",
    g1, g2, thr, (g1 < thr && g2 < thr) ? "saturated at n*≤6" :
                 (g2 < thr ? "check larger n before claiming" : "no saturation observed")))
# Δreplace, signed, no constraint
Δr = A13.E - B10E
push!(out, @sprintf("Δreplace = E(A13) − E(B10-E) = %+.3e  (B10-E=%.12f; NO sign rule)", Δr, B10E))
push!(out, @sprintf("context: E(B8)=%.12f  B10E−B8 = %.3e (what rdm=10 adds over rdm=8)",
    B8.E, B10E - B8.E))
foreach(println, out)
open(joinpath(@__DIR__, "m2_results.txt"), "w") do io
    println(io, "M2 arms N=$N seedless(VUMPS json) ", "julia $(VERSION)")
    foreach(l -> println(io, l), out)
end
