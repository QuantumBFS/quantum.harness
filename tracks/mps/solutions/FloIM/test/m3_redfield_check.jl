# M3 高频 Redfield 一致性检验
# Design: docs/design/2026-07-28-floquet-unitempo-manybody-ising.md §7 (M3)
#
# 设定：h_x=0.5, A=1, ω_d=10 (=20 h_x), J=0.5, h_z=0.3；浴 α=0.05, ω_c=2.5,
#       δt=π/60, tol=1e-7（论文 IF 参数），初态全 |↑⟩。
# 判据：增广 MPS（精确）vs Redfield–Magnus（Born 二阶 + 一阶 Magnus）的
#       ⟨σz_i(t)⟩ 逐帧差应落在 RM 自身误差预算内：O(α) + O(A²/ω_d²) ~ 1e-2。
#       ⟨σz⟩ 对微运动免疫（[K,σz]=0），可逐帧直接对照。
#       能量在频闪帧对照（K(m·T_d)=I；T_d/δt = 12 恰为整数）。
#
# 结构：A. N=1 接线检查（新 Liouvillian vs 已验证的单自旋 RM 数据列）
#       B. N=2,3 稠密对照
#       C. N=6 对照（Redfield 侧 Krylov 步进）
#
# Usage: julia --project=tracks/mps/env_floquet tracks/mps/solutions/test/m3_redfield_check.jl [out_dir]

include(joinpath(@__DIR__, "..", "src", "augmented_tempo.jl"))
include(joinpath(@__DIR__, "..", "src", "redfield_ising.jl"))

using .AugmentedTEMPO, .RedfieldIsing
using UniformTEMPO, LinearAlgebra, DelimitedFiles, KrylovKit, Printf

out_dir = length(ARGS) >= 1 ? ARGS[1] : joinpath(@__DIR__, "..", "..", "results", "20260728-augmps-m3")
mkpath(out_dir)
println("output dir: $out_dir"); flush(stdout)

# ---------------- 参数 ----------------
const δt = π / 60
const α = 0.05; const ωc = 2.5; const TOL = 1e-7
bcf(t) = α * (ωc / (1 + im * ωc * t))^2

const σx = ComplexF64[0 1; 1 0]
const σz = ComplexF64[1 0; 0 -1]

const HX = 0.5; const A_DRV = 1.0; const HZ = 0.3; const J = 0.5; const ωd = 10.0
const T_MAX = 60.0
const n = round(Int, T_MAX / δt)
const REPORT = 2
const STROBE = 12                      # T_d/δt = (2π/10)/(π/60) = 12

h_onsite(t) = HX * σx + (HZ + A_DRV * cos(ωd * t)) * σz
const h_static = HX * σx + HZ * σz          # H_0 的单点部分（能量对照用，见下）
const G_half = bond_superop(exp(-1im * J * kron(σz, σz) * δt / 2))

# 能量对照用 tr(H_0 ρ)：两侧的"能量"必须都是静态 H_0 的期望。
# （含时 lab 能量 H(t) 在频闪帧取驱动最大值 cos=1，与 H_0 差 A·Σσz ——
#  直接用 h_onsite(t) 会引入 A·N 的虚假偏差。tr(H_0ρ) 含 σx 项、
#  对微运动不免疫，故只在频闪帧（K=I）对照。）
meas(amps, vl, t) = begin
    ts = capped_mps(amps, vl)
    (sz=sz_all(ts), E=energy_ising(ts, h_static, J))
end

# ---------------- IF（两个方法共用同一浴参数） ----------------
println("=== building uniTEMPO influence functional ==="); flush(stdout)
pt = uniTEMPO(σz, δt, bcf, TOL)
println("χ_b = $(bond_dim(pt))"); flush(stdout)

# ---------------- A: N=1 接线检查 ----------------
println("\n=== A: N=1 Redfield Liouvillian vs validated single-spin RM ==="); flush(stdout)
ref = readdlm(joinpath(@__DIR__, "..", "..", "results", "20260727-195949-mickiewicz2026-fig2", "ours_omega_d_10.0.csv"))
# N=1 静态极限 = 论文单自旋（hz=0, J 无键）：H_F = h_x σx
rm1 = redfield_liouvillian(1, 0.0, 0.0, HX, α, ωc)
n_ref = size(ref, 1)
sz_rm1 = [expect_redfield(rm1, σz, 1, exp(rm1.L * ref[k, 1]) * RedfieldIsing.initial_vec_en(rm1))
          for k in 1:n_ref]
Δ_a = maximum(abs.(sz_rm1 .- ref[:, 3]))
println("N=1: max|Δ| vs validated RM column = $Δ_a  (target ≲ 1e-10, same formula)")
# 健康检查：本征值实部、迹守恒
ev = eigvals(rm1.L)
println("      max Re(eigvals L) = $(maximum(real(ev))) ; tr ρ(t=60) = $(sum((exp(rm1.L * 60.0) * RedfieldIsing.initial_vec_en(rm1))[j + (j - 1) * 2] for j in 1:2))")
flush(stdout)

# ---------------- B/C: N 对照 ----------------
function m3_compare(N; krylov=false)
    println("\n=== N=$N ==="); flush(stdout)
    # 增广 MPS（精确）
    t_u = @elapsed (times, rec) = run_chain(pt, N, h_onsite, G_half, n;
                                            report_every=REPORT, cutoff=1e-12, maxdim=256,
                                            measure=meas)
    println("  uniTEMPO done in $(round(t_u, digits=1)) s"); flush(stdout)
    # Redfield–Magnus
    t_r = @elapsed begin
        rm = redfield_liouvillian(N, J, HZ, HX, α, ωc)
        if !krylov
            vs = evolve_redfield(rm, times)
        else
            # Krylov 步进：不显式构造 e^{Lt}，逐步 exponentiate
            vs = Vector{Vector{ComplexF64}}(undef, length(times))
            v = RedfieldIsing.initial_vec_en(rm)
            vs[1] = v
            for k in 2:length(times)
                τ = times[k] - times[k - 1]
                v, = exponentiate(rm.L, τ, v; tol=1e-12)
                vs[k] = v
            end
        end
    end
    println("  Redfield done in $(round(t_r, digits=1)) s  (Liouville dim $(size(rm.L, 1)))")
    # 健康检查
    ev_max = maximum(real(eigvals(rm.L)))
    println("  max Re(eigvals L) = $ev_max")
    # ⟨σz_i⟩ 逐帧对照
    Δ = zeros(N)
    for i in 1:N
        sz_u = [r.sz[i] for r in rec]
        sz_r = [expect_redfield(rm, σz, i, vs[k]) for k in 1:length(times)]
        Δ[i] = maximum(abs.(sz_u .- sz_r))
        writedlm(joinpath(out_dir, "m3_N$(N)_sz$(i).csv"), hcat(times, sz_u, sz_r))
    end
    # 稳态对照（N≤3 时把两侧都推到 t=150，RM 侧由零本征矢给出 t→∞）
    v_ss = steady_state_redfield(rm)
    sz_ss_rm = [expect_redfield(rm, σz, i, v_ss) for i in 1:N]
    n_long = round(Int, 150.0 / δt)
    _, rec_long = run_chain(pt, N, h_onsite, G_half, n_long;
                            report_every=n_long, cutoff=1e-12, maxdim=256, measure=meas)
    sz_ss_u = rec_long[end].sz
    Δss = maximum(abs.(sz_ss_u .- sz_ss_rm))
    # 频闪帧能量对照（tr(H_0 ρ) 两侧；K=I 处 lab=kick 系）
    idx_strobe = [1 + div(m * STROBE, REPORT) for m in 0:div(n, STROBE)]
    E_u = [rec[k].E for k in idx_strobe]
    O_en_H = rm.V' * Matrix(build_H0(N, J, HZ, HX)) * rm.V
    cvH = vec(transpose(O_en_H))
    E_r = [real(dot(cvH, vs[k])) for k in idx_strobe]
    ΔE = maximum(abs.(E_u .- E_r))
    println("  max|Δ⟨σz_i⟩| per site: $(round.(Δ, sigdigits=3))")
    println("  steady (t=150) ours = $(round.(sz_ss_u, digits=4))")
    println("  steady (t→∞)  RM  = $(round.(sz_ss_rm, digits=4))  → max|Δ| = $(round(Δss, sigdigits=3))")
    println("  strobe max|Δ tr(H_0 ρ)| = $(round(ΔE, sigdigits=3))")
    println("  budget: 暂态以同参数 N=1 RM 误差 (~0.1-0.2) 为基线；稳态以 O(α) 为基线")
    flush(stdout)
    return Δ, Δss, ΔE
end

# N=6 单独跑（uniTEMPO ~8 min + RM Krylov ~2 min）：julia ... m3_redfield_check.jl [out_dir] 6
if length(ARGS) >= 2 && ARGS[2] == "6"
    m3_compare(6; krylov=true)
else
    for N in (2, 3)
        m3_compare(N)
    end
end

println("\n=== M3 done ==="); flush(stdout)
