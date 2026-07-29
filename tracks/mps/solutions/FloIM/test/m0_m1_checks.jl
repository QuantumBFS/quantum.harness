# M0 / M1 checks for the augmented-MPS Floquet-uniTEMPO solver.
# Design: docs/design/2026-07-28-floquet-unitempo-manybody-ising.md §7
#
# M0:    N=1, paper params -> ⟨σz(t)⟩ must match the verified Fig.2 exact curve (machine-level, same algorithm)
# M1(b): N=4, J=0, full chain -> site-1 curve matches paper data at ωd = 2.5 and 10;
#        sites 2-4 match independent single-spin unitary reference
# M1(a): α=0 closed driven Ising chain N=10 -> TEBD vs Krylov ED reference
#
# 观测量一律走 capped-MPS 收缩（augmented_tempo.jl 的 measure 回调），
# 完整 2^N 密度矩阵只出现在 ED 参考一侧。
#
# Usage: julia --project=tracks/mps/env_floquet tracks/mps/solutions/m0_m1_checks.jl [out_dir]

include(joinpath(@__DIR__, "..", "src", "augmented_tempo.jl"))
using .AugmentedTEMPO
using UniformTEMPO
using LinearAlgebra
using DelimitedFiles
using KrylovKit
using SparseArrays

out_dir = length(ARGS) >= 1 ? ARGS[1] : joinpath(@__DIR__, "..", "..", "results", "20260728-augmps-m0m1")
mkpath(out_dir)
println("output dir: $out_dir"); flush(stdout)

# ---------------- shared parameters ----------------
const δt = π / 60
const α = 0.05
const ωc = 2.5
const TOL = 1e-7
bcf(t) = α * (ωc / (1 + im * ωc * t))^2

const σx = ComplexF64[0 1; 1 0]
const σz = ComplexF64[1 0; 0 -1]
const I2 = Matrix{ComplexF64}(I, 2, 2)

# paper Fig.2 mapping: H = Ω/2 σx + εd cos(ωd t) σz with Ω = εd = 1  →  hx = 0.5, A = 1, hz = 0
const HX_FIG2 = 0.5
const A_FIG2 = 1.0

ref_dir = joinpath(@__DIR__, "..", "..", "results", "20260727-195949-mickiewicz2026-fig2")

# ED 参考一侧的算符拼接：cap 出的 ρ 站点 1 是最快指标，Julia kron 最后因子最快，
# 故我们的站点 i 映射到 kron 位置 N+1-i。site_op 接受我们的站点编号。
site_op(op, i, N) = foldl(kron, [j == (N - i + 1) ? op : I2 for j in 1:N])

# ============================================================
println("=== building uniTEMPO influence functional (tol = $TOL) ==="); flush(stdout)
t_if = @elapsed pt = uniTEMPO(σz, δt, bcf, TOL)
println("IF built in $(round(t_if, digits=1)) s, χ_b = $(bond_dim(pt))"); flush(stdout)

# ---------------- M0: N=1 vs verified Fig.2 data (ωd = 2.5) ----------------
println("\n=== M0: N=1 wiring test (ωd = 2.5) ==="); flush(stdout)
ref = readdlm(joinpath(ref_dir, "ours_omega_d_2.5.csv"))
n_ref = size(ref, 1) - 1
h_fig2(t) = HX_FIG2 * σx + A_FIG2 * cos(2.5 * t) * σz
_, rec_m0 = run_chain(pt, 1, h_fig2, nothing, n_ref)
sz_m0 = [r.sz[1] for r in rec_m0]
Δ_m0 = maximum(abs.(sz_m0 .- ref[:, 2]))
println("M0: max|Δ| vs verified Fig.2 exact = $(Δ_m0)  (t_max = $(ref[end,1]))"); flush(stdout)
writedlm(joinpath(out_dir, "m0_sz.csv"), hcat(ref[:, 1], sz_m0))

# ---------------- M1(b): N=4, J=0, site 1 vs paper data; sites 2-4 vs unitary ----------------
println("\n=== M1(b): N=4 chain, J=0 ==="); flush(stdout)
t_max_b = 60.0
n_b = round(Int, t_max_b / δt)
result_b = Dict{Float64,Float64}()
for ωd in (2.5, 10.0)
    local ref
    h_drv(t) = HX_FIG2 * σx + A_FIG2 * cos(ωd * t) * σz
    tgrid, rec = run_chain(pt, 4, h_drv, nothing, n_b; report_every=2)
    # site 1 (our site index, bath-coupled) vs paper reference
    ref = readdlm(joinpath(ref_dir, "ours_omega_d_$(ωd).csv"))
    ref_sub = ref[1:2:(2 * length(rec) - 1), :]
    sz1 = [r.sz[1] for r in rec]
    Δ1 = maximum(abs.(sz1 .- ref_sub[:, 2]))
    # sites 2-4 vs independent single-spin unitary reference (substep δt/8)
    ρu = ComplexF64[1 0; 0 0]
    szu = Float64[]
    push!(szu, real(tr(σz * ρu)))
    for k in 1:n_b
        for s in 0:7
            tmid = (k - 1 + (s + 0.5) / 8) * δt
            u = exp(-1im * h_drv(tmid) * δt / 8)
            ρu = u * ρu * u'
        end
        if k % 2 == 0; push!(szu, real(tr(σz * ρu))); end
    end
    sz4 = [r.sz[4] for r in rec]
    Δ2 = maximum(abs.(sz4 .- szu))
    # factorization check: J=0 keeps product structure; purity from capped-MPS norm
    trρ2 = rec[end].pur
    println("  ωd = $ωd: site1 max|Δ| vs paper = $Δ1 ; site4 max|Δ| vs unitary = $Δ2 ; tr ρ²(t=60) = $trρ2"); flush(stdout)
    result_b[ωd] = Δ1
    writedlm(joinpath(out_dir, "m1b_sz1_wd$(ωd).csv"), hcat(tgrid, sz1))
end

# ---------------- M1(a): α=0 closed chain vs ED ----------------
println("\n=== M1(a): α=0 closed driven Ising chain, N=10, vs Krylov ED ==="); flush(stdout)
N_a = 6
J_a = 0.5
hx_a = 0.5
hz_a = 0.3
A_a = 1.0
ωd_a = 2.5
t_max_a = 5.0
n_a = round(Int, t_max_a / δt)

pt0 = UniformPTMPO(2, δt)   # trivial process tensor: identity bath (χ_b = 1)
h_chain_onsite(t) = hx_a * σx + (hz_a + A_a * cos(ωd_a * t)) * σz
u_bond = exp(-1im * J_a * kron(σz, σz) * δt / 2)
G_half = bond_superop(u_bond)

# 测量回调：⟨σz⟩ 全部站点 + Ising 能量 + 迹 + 纯度（全走 capped-MPS 收缩）
measure_a(amps, vl, t) = begin
    ts = capped_mps(amps, vl)
    (sz=sz_all(ts), E=energy_ising(ts, h_chain_onsite(t), J_a),
     tr=trace_rho(ts), pur=purity(ts))
end
tgrid_a, rec_a = run_chain(pt0, N_a, h_chain_onsite, G_half, n_a;
                           cutoff=1e-12, maxdim=256, measure=measure_a)

# ED reference: state vector, Krylov exponentiate with δt/8 substeps
function sparse_H(N, t)
    H = spzeros(ComplexF64, 2^N, 2^N)
    for i in 1:(N - 1)
        H += J_a * sparse(site_op(σz, i, N) * site_op(σz, i + 1, N))
    end
    f = hz_a + A_a * cos(ωd_a * t)
    for i in 1:N
        H += hx_a * sparse(site_op(σx, i, N)) + f * sparse(site_op(σz, i, N))
    end
    return H
end
ψ = zeros(ComplexF64, 2^N_a); ψ[1] = 1.0   # |↑...↑⟩
sz_ed = zeros(n_a + 1, 3)
E_ed = zeros(n_a + 1)
sz_ed[1, :] .= 1.0
E_ed[1] = real(ψ' * sparse_H(N_a, 0.0) * ψ)
for k in 1:n_a
    global ψ
    for s in 0:7
        tmid = (k - 1 + (s + 0.5) / 8) * δt
        ψ, = exponentiate(-1im * sparse_H(N_a, tmid), δt / 8, ψ; issymmetric=false, tol=1e-12)
    end
    sz_ed[k + 1, :] = [real(ψ' * site_op(σz, i, N_a) * ψ) for i in (1, 5, 10)]
    E_ed[k + 1] = real(ψ' * sparse_H(N_a, k * δt) * ψ)
    if k % 48 == 0
        println("  ED step $k / $n_a"); flush(stdout)
    end
end
sz_te = hcat([[r.sz[i] for r in rec_a] for i in (1, 5)]...)
E_te = [r.E for r in rec_a]
pur_te = [r.pur for r in rec_a]
Δ_a = maximum(abs.(sz_te .- sz_ed))
ΔE_a = maximum(abs.(E_te .- E_ed))
println("M1(a): max|Δ ⟨σz^i⟩| (i=1,5,10) = $Δ_a ; max|ΔE| = $ΔE_a ; tr ρ² drift = $(maximum(abs.(pur_te .- 1)))"); flush(stdout)
writedlm(joinpath(out_dir, "m1a_compare.csv"), hcat(tgrid_a, sz_te[:, 1], sz_ed[:, 1], sz_te[:, 2], sz_ed[:, 2], sz_te[:, 3], sz_ed[:, 3], E_te, E_ed))

println("\n=== summary ===")
println("M0    : max|Δ| = $Δ_m0   (target ≲ 1e-6)")
println("M1(b) : site1 max|Δ| = $(result_b[2.5]) (ωd=2.5), $(result_b[10.0]) (ωd=10)   (target ≲ 1e-6)")
println("M1(a) : max|Δ| = $Δ_a vs ED   (target ~ O(δt²) ≈ few 1e-3)")
flush(stdout)
