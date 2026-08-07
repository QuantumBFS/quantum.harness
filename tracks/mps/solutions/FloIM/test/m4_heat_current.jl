# M4 热流密度：算符验证 + NESS 一致性 + j(ω_d) 初步扫描
# Design: docs/design/2026-07-28-floquet-unitempo-manybody-ising.md §7 (M4)
#
# 键流算符：j_{i,i+1} = J h_x (σy_i σz_{i+1} − σz_i σy_{i+1})（连续性方程导出）
# 能量平衡：NESS 下 j̄(任意键) = P̄_drive = −A ω_d ⟨sin(ω_d t) Σ_i⟨σz_i⟩⟩_period = 浴耗散率
# RM 预言 j̄ ≈ 0；非零即非马尔可夫/高阶 Floquet 物理。
#
# 检查结构：
#   A. 连续性方程数值检验（内部站点 de_i/dt ≈ j_{i-1,i} − j_{i,i+1}）
#   B. NESS 一致性：j_{1,2} ≈ j_{2,3} ≈ 驱动功率周期平均（ω_d=10, N=3）
#   C. A=0 极限：冷却到基态后 j → ~0
#   D. mini-scan：j̄(ω_d) at ω_d ∈ {2.5, 5, 10, 20}, N=3
#
# Usage: julia --project=tracks/mps/env_floquet tracks/mps/solutions/test/m4_heat_current.jl [out_dir]

include(joinpath(@__DIR__, "..", "src", "augmented_tempo.jl"))
using .AugmentedTEMPO, UniformTEMPO, LinearAlgebra, DelimitedFiles, Printf

out_dir = length(ARGS) >= 1 ? ARGS[1] : joinpath(@__DIR__, "..", "..", "results", "20260728-augmps-m4")
mkpath(out_dir)
println("output dir: $out_dir"); flush(stdout)

const δt = π / 60
const α = 0.05; const ωc = 2.5; const TOL = 1e-7
bcf(t) = α * (ωc / (1 + im * ωc * t))^2
const σx = ComplexF64[0 1; 1 0]
const σz = ComplexF64[1 0; 0 -1]

const HX = 0.5; const HZ = 0.3; const J = 0.5
const h_static = HX * σx + HZ * σz

const G_half = bond_superop(exp(-1im * J * kron(σz, σz) * δt / 2))

println("=== building uniTEMPO influence functional ==="); flush(stdout)
pt = uniTEMPO(σz, δt, bcf, TOL)
println("χ_b = $(bond_dim(pt))"); flush(stdout)

# 测量：站点能量（lab 能量密度，h(t) 含驱动）+ 键流 + ⟨σz⟩
# 连续性方程（lab）：de_i/dt = (j_{i-1,i} − j_{i,i+1}) − A ω_d sin(ω_d t)⟨σz_i⟩
# （末项是驱动的显式功率注入 ∂e_i/∂t）
meas_m4(A, ωd) = (amps, vl, t) -> begin
    hlab(t) = HX * σx + (HZ + A * cos(ωd * t)) * σz
    ts = capped_mps(amps, vl)
    (e=site_energies(ts, hlab(t), J), j=current_profile(ts, J, HX), sz=sz_all(ts))
end

# NESS 协议：先到 t_ss，再继续 K 个驱动周期逐步测量。
# 返回 (j̄ 逐键, s̄ 逐站点功率注入, P̄ 总驱动功率)。
# NESS 连续性（周期平均）：j̄_{i,i+1} − j̄_{i−1,i} = s̄_i（键流不必均匀——
# 驱动逐点注入能量）；全局 j_bath = s̄_1 − j̄_{1,2} = Σ s̄ = P̄。
function ness_current(N, ωd, A; t_ss=800.0, K=5, maxdim=256)
    h_onsite(t) = HX * σx + (HZ + A * cos(ωd * t)) * σz
    n_ss = round(Int, t_ss / δt)
    _, _, amps = run_chain(pt, N, h_onsite, G_half, n_ss; report_every=n_ss,
                           cutoff=1e-12, maxdim=maxdim, measure=meas_m4(A, ωd), keep_state=true)
    T_d = 2π / ωd
    n_per = round(Int, K * T_d / δt)
    qm = q_matrix(pt); vl = pt.v_l[:]
    j_acc = zeros(N - 1); s_acc = zeros(N); cnt = 0
    t = t_ss
    for k in 1:n_per
        u1 = onsite_superop(h_onsite((k - 0.75) * δt + t_ss), δt / 2)
        u2 = onsite_superop(h_onsite((k - 0.25) * δt + t_ss), δt / 2)
        trotter_step!(amps, qm, u1, u2, G_half; cutoff=1e-12, maxdim=maxdim)
        t = t_ss + k * δt
        ts = capped_mps(amps, vl)
        j_acc .+= current_profile(ts, J, HX)
        s_acc .+= -A * ωd * sin(ωd * t) .* sz_all(ts)
        cnt += 1
    end
    return j_acc ./ cnt, s_acc ./ cnt, sum(s_acc) / cnt
end

# ---------------- A: 流算符验证 ----------------
# A1: 封闭链（α=0）j(t)、e(t) 与 ED 逐点对照（最强算符级检验，Trotter 阶容差）
println("\n=== A1: closed chain j(t), e(t) vs ED pointwise (N=3, ωd=10) ==="); flush(stdout)
σy = ComplexF64[0 -1im; 1im 0]
I2 = Matrix{ComplexF64}(I, 2, 2)
site_op3(op, i) = foldl(kron, [j == (3 - i + 1) ? op : I2 for j in 1:3])
j_op_ed(i) = J * HX * (site_op3(σy, i) * site_op3(σz, i + 1) - site_op3(σz, i) * site_op3(σy, i + 1))
e2_op_ed(t) = HX * site_op3(σx, 2) + (HZ + cos(10.0 * t)) * site_op3(σz, 2) +
              J / 2 * (site_op3(σz, 1) * site_op3(σz, 2) + site_op3(σz, 2) * site_op3(σz, 3))
function H3_ed(t)
    H = zeros(ComplexF64, 8, 8)
    for i in 1:2; H += J * (site_op3(σz, i) * site_op3(σz, i + 1)); end
    f = HZ + cos(10.0 * t)
    for i in 1:3; H += HX * site_op3(σx, i) + f * site_op3(σz, i); end
    H
end
h10(t) = HX * σx + (HZ + 1.0 * cos(10.0 * t)) * σz
pt0 = UniformPTMPO(2, δt)
n_a = round(Int, 3.0 / δt)
times, rec0 = run_chain(pt0, 3, h10, G_half, n_a; measure=meas_m4(1.0, 10.0))
ψ = zeros(ComplexF64, 8); ψ[1] = 1.0
dj = 0.0; de = 0.0
for k in 1:length(times)
    t = times[k]
    if k > 1
        global ψ
        for s in 0:15
            ψ = exp(-1im * H3_ed(t - δt + (s + 0.5) * δt / 16) * δt / 16) * ψ
        end
    end
    global dj = max(dj, abs(rec0[k].j[1] - real(ψ' * j_op_ed(1) * ψ)),
                    abs(rec0[k].j[2] - real(ψ' * j_op_ed(2) * ψ)))
    global de = max(de, abs(rec0[k].e[2] - real(ψ' * e2_op_ed(t) * ψ)))
end
println("  max|Δj| = $(round(dj, sigdigits=3)), max|Δe_2| = $(round(de, sigdigits=3))  (target ≲ 1e-3, Trotter 阶)")
flush(stdout)

# A2: 带浴情形的积分形式连续性：e_i(T)−e_i(0) = ∫₀^T (j-diff + src) dt（梯形，免逐点差分误差）
println("\n=== A2: integral continuity with bath (N=3, ωd=10, T=10) ==="); flush(stdout)
n_a2 = round(Int, 10.0 / δt)
times, rec = run_chain(pt, 3, h10, G_half, n_a2; cutoff=1e-12, maxdim=256, measure=meas_m4(1.0, 10.0))
T = times[end]
for i in (2, 3)
    rhs = 0.0
    for k in 1:length(times)
        t = times[k]
        src = -1.0 * 10.0 * sin(10.0 * t) * rec[k].sz[i]
        jd = (i == 2 ? rec[k].j[1] - rec[k].j[2] : rec[k].j[2])
        w = (k == 1 || k == length(times)) ? 0.5 : 1.0
        rhs += w * (jd + src) * δt
    end
    Δe = rec[end].e[i] - rec[1].e[i]
    println("  site $i: Δe = $(round(Δe, sigdigits=4)), ∫(j-diff+src)dt = $(round(rhs, sigdigits=4)), |差| = $(round(abs(Δe-rhs), sigdigits=2))")
end
flush(stdout)

# ---------------- B: NESS 一致性 ----------------
# 检查：内部站点 j̄_{i,i+1} − j̄_{i−1,i} = s̄_i；全局 j_bath = s̄_1 − j̄_{1,2} = P̄
println("\n=== B: NESS consistency (N=3, ωd=10, A=1, t_ss=400 + 5 periods) ==="); flush(stdout)
j_b, s_b, P_b = ness_current(3, 10.0, 1.0)
jb_b = s_b[1] - j_b[1]
println("  j̄ = $(round.(j_b, sigdigits=3)) ; s̄ = $(round.(s_b, sigdigits=3)) ; P̄ = $(round(P_b, sigdigits=3))")
println("  内部站点: j̄23 − j̄12 = $(round(j_b[2]-j_b[1], sigdigits=3)) vs s̄_2 = $(round(s_b[2], sigdigits=3))")
println("  浴耗散 j_bath = s̄_1 − j̄12 = $(round(jb_b, sigdigits=3)) vs P̄ = $(round(P_b, sigdigits=3))")
flush(stdout)

# ---------------- C: A=0 极限 ----------------
println("\n=== C: no-drive limit (N=3, A=0) ==="); flush(stdout)
j_c, s_c, P_c = ness_current(3, 10.0, 0.0)
println("  j̄ = $(round.(j_c, sigdigits=3)) ; P̄ = $(round(P_c, sigdigits=3))  (target ≈ 0)")
flush(stdout)

# ---------------- D: mini-scan ----------------
# 注意：高 ω_d 下 NESS 流 ~1e-4 量级，与小 Bohr 频率慢模（γ∝ω）的暂态残余同量级——
# site-2 残差列给出各点的 NESS 收敛质量（≪ |P̄| 才可信）。慢模问题的正解是
# 周期映射主本征矢（设计文档 §7 的计划），大扫描应上集群。
println("\n=== D: mini-scan j̄(ω_d), N=3, A=1 ==="); flush(stdout)
println("  ω_d      j̄12          j̄23          s̄1           s̄2           s̄3           P̄            site2残差"); flush(stdout)
scan = Tuple{Float64,Vector{Float64},Vector{Float64},Float64}[]
for ωd in (2.5, 5.0, 10.0, 20.0)
    t0 = time()
    j_s, s_s, P_s = ness_current(3, ωd, 1.0)
    chk = (j_s[2] - j_s[1]) - s_s[2]
    push!(scan, (ωd, j_s, s_s, P_s))
    @printf("  %-4.1f   %+.6f   %+.6f   %+.6f   %+.6f   %+.6f   %+.6f   %+.2e   (%.0f s)\n",
            ωd, j_s[1], j_s[2], s_s[1], s_s[2], s_s[3], P_s, chk, time() - t0)
    flush(stdout)
end
writedlm(joinpath(out_dir, "m4_jbar_scan.csv"),
         hcat([s[1] for s in scan], [s[2][1] for s in scan], [s[2][2] for s in scan],
              [s[3][1] for s in scan], [s[3][2] for s in scan], [s[3][3] for s in scan], [s[4] for s in scan]))

println("\n=== M4 done ==="); flush(stdout)
