#!/usr/bin/env julia
# hybrid_test.jl — first coupled NPA + ω-tower runs at small N (rdm=8 arms).
#
# Gates (order matters; each blocks the next):
#   H0  generator oracle (oracle_check): reduce! interpretation, ρ3(y)
#       reconstruction, and every emitted row satisfied by the physical ED
#       assignment to ≤ 1e-10 — validates R and S on the PRIMAL side.
#   H1  plumbing no-op: tower with zero rows ≡ stock (|Δ| ≤ 1e-9).
#   H2  ΔCG8 = E(rdm8+CG(n)) − E(rdm8) ≥ −ε   (THEOREM_CONTRACT §3)
#   H3  E_hybrid ≤ E0(N)/N + ε                 (validity — the decisive check)
#   H4  monotone in n: E(CG(6)) ≤ E(CG(9)) + ε on N=12
# ε here = 5e-7 (conservative multiple of the 1e-8 solver tolerances; the
# formal ε_cmp bookkeeping happens in the M2 runner, not this smoke).
#
# A-tensor: seeded random left-canonical (validity is A-independent; bound
# IMPROVEMENT magnitude is meaningless for random A — VUMPS tensors are the
# M2 job). Usage: julia -t 2 --project=julia-env hybrid_test.jl

using JuMP, Mosek, MosekTools, LinearAlgebra, SparseArrays, Random, Printf
include(joinpath(@__DIR__, "gsb_cg.jl"))      # loads QMBCertify + fork
include(joinpath(@__DIR__, "tower_gen.jl"))   # includes tower_lib.jl

const EPS = 5e-7
Random.seed!(20260728)
A = random_left_canonical(2)

supp = [[1, 4]]; coe = [3 / 4]
gsb(N; tower = nothing) = GSB_cg(supp, coe, N, 4; extra = 4, rdm = 8, pso = 0,
                                 lso = false, QUIET = true, tower = tower)[1]

ok = true
report = String[]
function gate!(name, cond, msg)
    global ok &= cond
    line = @sprintf("%-4s %s  %s", name, cond ? "PASS" : "FAIL", msg)
    push!(report, line); println(line); flush(stdout)
end

# ---- H0: generator oracle at N=10, n=6 --------------------------------------
oc = oracle_check(10, 6, A)
gate!("H0", oc.pass, @sprintf("oracle: reduce %.1e  reconstruct %.1e  rows %.1e (E0/N = %.10f)",
    oc.worst_reduce, oc.worst_reconstruct, oc.worst_row, oc.E0 / 10))

# ---- H1: plumbing no-op ------------------------------------------------------
t0 = time()
E_base10 = gsb(10)
t_base = time() - t0
noop = (nrows = 0, ycoef = Vector{Vector{Tuple{Vector{UInt16},Float64}}}(),
        zblocks = @NamedTuple{dim::Int, entries::Vector{Tuple{Int,Int,Int,Float64}}}[],
        brows = Tuple{Int,Float64}[])
E_noop = gsb(10; tower = noop)
gate!("H1", abs(E_noop - E_base10) <= 1e-9,
    @sprintf("no-op tower: base %.12f  noop %.12f  |Δ|=%.1e", E_base10, E_noop, abs(E_noop - E_base10)))

# ---- H2/H3: coupled run at N=10, n=6 ----------------------------------------
tw = build_tower(10, 6, A)
t0 = time()
E_hyb10 = gsb(10; tower = tw)
t_hyb = time() - t0
Δ = E_hyb10 - E_base10
E0ps = oc.E0 / 10
gate!("H2", Δ >= -EPS, @sprintf("ΔCG8(N=10,n=6) = %+.3e  (base %.10f → hyb %.10f)", Δ, E_base10, E_hyb10))
gate!("H3", E_hyb10 <= E0ps + EPS, @sprintf("E_hyb %.10f ≤ E0/N %.10f  (slack %+.3e)", E_hyb10, E0ps, E0ps - E_hyb10))
push!(report, @sprintf("     cost: base %.1fs → hybrid %.1fs", t_base, t_hyb))

# ---- H4: n-monotonicity at N=12 ---------------------------------------------
E0_12, _ = heis_ground(12)
E_b12 = gsb(12)
E6  = gsb(12; tower = build_tower(12, 6, A))
E9  = gsb(12; tower = build_tower(12, 9, A))
gate!("H4a", E6 >= E_b12 - EPS && E9 >= E_b12 - EPS,
    @sprintf("N=12: base %.10f  CG6 %.10f  CG9 %.10f", E_b12, E6, E9))
gate!("H4b", E9 >= E6 - EPS, @sprintf("monotone: E9−E6 = %+.3e", E9 - E6))
gate!("H4c", max(E6, E9) <= E0_12 / 12 + EPS,
    @sprintf("validity: E0/N(12) = %.10f", E0_12 / 12))

println(ok ? "\nALL HYBRID GATES GREEN" : "\nHYBRID GATES FAILED")
open(joinpath(@__DIR__, "hybrid_test.out"), "w") do io
    println(io, "hybrid_test.jl  ", ok ? "PASS" : "FAIL", "  (seed 20260728, ε=5e-7)")
    foreach(l -> println(io, l), report)
end
exit(ok ? 0 : 1)
