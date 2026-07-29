#!/usr/bin/env julia
# M2 step 1 — VUMPS D=2 coarse tensors for the two-parity ω-tower.
# History (kept honest): 1-site TI VUMPS/GradientGrassmann land on spurious
# stationary states (ferro e=+0.25; Néel-cat e=-0.25) — the Marshall sign
# structure needs period 2. 2-site VUMPS converges cleanly (probe:
# e=-0.42791, 96.6% of E∞); the tower generator was generalized to the
# two-parity block family ω_M^p accordingly.
# Gates:
#   V1 2-site VUMPS: ‖B‖ ≤ 1e-9 AND e ≤ −0.42 (kills the spurious traps)
#   V2 left-canonicity of BOTH extracted tensors ≤ 1e-12
#   V3 two-parity generator oracle (N=10, n=6) rows ≤ 1e-10
#   V4 hybrid smoke N=10 rdm=8: ΔCG8(n=6,9) ≥ −ε, E_hyb ≤ E0/N + ε (ε=5e-7)
using JuMP, Mosek, MosekTools, LinearAlgebra, SparseArrays, Printf, SHA, Random
using MPSKit, MPSKitModels, TensorKit
const DD = length(ARGS) >= 1 ? parse(Int, ARGS[1]) : 2
include(joinpath(@__DIR__, "gsb_cg.jl"))
include(joinpath(@__DIR__, "tower_gen.jl"))

const EPS = 5e-7
report = String[]; ok = true
gate!(n, c, m) = (global ok &= c; l = @sprintf("%-3s %s  %s", n, c ? "PASS" : "FAIL", m);
                  push!(report, l); println(l); flush(stdout))

H = heisenberg_XXZ(ComplexF64, Trivial, InfiniteChain(2); spin = 1 // 2, Delta = 1.0)
Random.seed!(7)
psi = InfiniteMPS([physicalspace(H, i) for i in 1:2], fill(ComplexSpace(DD), 2))
psi, envs = find_groundstate(psi, H, VUMPS(; tol = 1e-11, maxiter = 800, verbosity = 0))
e_site = real(expectation_value(psi, H)) / 2
bnorm = sqrt(sum(abs2(MPSKit.calc_galerkin(p, psi, H, psi, envs)) for p in 1:2) / 2)
E∞ = 0.25 - log(2)
gate!("V1", bnorm <= 1e-9 && e_site <= -0.42,
    @sprintf("VUMPS D=2 2-site: e=%.10f (E∞=%.10f, ΔvsE∞=%+.2e) ‖B‖=%.2e",
    e_site, E∞, e_site - E∞, bnorm))

arrs = [convert(Array, psi.AL[i]) for i in 1:2]
As = [[Matrix{ComplexF64}(arrs[i][:, μ, :]) for μ in 1:2] for i in 1:2]
canres = maximum(norm(sum(As[i][μ]' * As[i][μ] for μ in 1:2) - I) for i in 1:2)
gate!("V2", canres <= 1e-12, @sprintf("left-canonical residual (worst of 2) %.2e", canres))

oc = oracle_check(10, 6, As)
gate!("V3", oc.pass, @sprintf("two-parity oracle: reduce %.1e reconstruct %.1e rows %.1e",
    oc.worst_reduce, oc.worst_reconstruct, oc.worst_row))

if !haskey(ENV, "SKIP_V4")   # V4 duplicates m2_arms; skip for big-D builds
    supp = [[1, 4]]; coe = [3 / 4]
    gsb(N; tower = nothing) = GSB_cg(supp, coe, N, 4; extra = 4, rdm = 8, pso = 0,
                                     lso = false, QUIET = true, tower = tower)[1]
    E_base = gsb(10)
    E_hyb6 = gsb(10; tower = build_tower(10, 6, As))
    E_hyb9 = gsb(10; tower = build_tower(10, 9, As))
    Δ6 = E_hyb6 - E_base; Δ9 = E_hyb9 - E_base
    E0ps = oc.E0 / 10
    gate!("V4", Δ6 >= -EPS && Δ9 >= -EPS && max(E_hyb6, E_hyb9) <= E0ps + EPS,
        @sprintf("ΔCG8(n=6)=%+.3e ΔCG8(n=9)=%+.3e (base %.10f, E0/N %.10f)", Δ6, Δ9, E_base, E0ps))
else
    push!(report, "V4 SKIPPED (SKIP_V4 set; m2_arms is the real measurement)")
end

wt = normpath(joinpath(@__DIR__, "..", "..", "..", "..", ".."))
js(v) = "[" * join(v, ",") * "]"
open(joinpath(@__DIR__, "vumps_A_D$(DD).json"), "w") do io
    print(io, "{\"D\":$(DD),\"cell\":2,\"e_site\":$(e_site),\"bnorm\":$(bnorm),")
    print(io, "\"canres\":$(canres),\"E_inf_ref\":$(E∞),")
    for i in 1:2
        print(io, "\"A$(i)_re\":[", join((js(vec(real(As[i][μ]))) for μ in 1:2), ","), "],")
        print(io, "\"A$(i)_im\":[", join((js(vec(imag(As[i][μ]))) for μ in 1:2), ","), "],")
    end
    print(io, "\"layout\":\"column-major vec of 2x2, As[parity][mu][left,right]\",")
    print(io, "\"git_commit\":\"$(strip(read(`git -C $wt rev-parse HEAD`, String)))\",")
    print(io, "\"manifest_sha256\":\"$(bytes2hex(sha256(read(joinpath(wt,"julia-env","Manifest.toml")))))\"}")
end
open(joinpath(@__DIR__, "vumps_gates.log"), "w") do io
    println(io, "vumps_tensor.jl  ", ok ? "PASS" : "FAIL", "  (2-site, two-parity tower)")
    foreach(l -> println(io, l), report)
end
println(ok ? "VUMPS TENSOR GATES GREEN" : "VUMPS GATES FAILED")
exit(ok ? 0 : 1)
