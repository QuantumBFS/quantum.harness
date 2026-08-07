# M4a：单自旋（N=1）频率分辨热流密度 j̄(ω) —— 复刻 Mickiewicz et al. 图 3
# 公式（设计文档附录 B，唯一正确定义）：
#   j̄(ω) = 2ωJ(ω) Re ∫_0^∞ dτ e^{-iωτ} C̄(τ)，C̄(τ) = 周期平均 ⟨S(t'+τ)S(t')⟩
#   C̄ = C̄_decay + C̄_asym；C̄_asym = Σ_n c_n cos(nω_d τ) 给 δ 峰 πωJ Σc_n δ(ω−nω_d)。
# 协议（附录 B.5，与论文同款）：传播到 NESS → 一个周期内 M 个 t' 起点各插入 S 左乘，
#   再传播 τ ∈ [0, τmax] 读出 C(t', τ) → 周期平均 → 数值傅里叶积分。
# 对照：Zenodo 图 3 CSV（连续谱部分）+ 图 5 总流 Ī(ω_d) + 能量平衡 Ī=P̄。
# 用法：julia --project=tracks/mps/env_floquet tracks/mps/solutions/test/m4a_fig3_reproduction.jl

include(joinpath(@__DIR__, "..", "src", "augmented_tempo.jl"))

using .AugmentedTEMPO
using UniformTEMPO
using Printf
using DelimitedFiles
using LinearAlgebra
using Statistics

const σx = ComplexF64[0 1; 1 0]
const σz = ComplexF64[1 0; 0 -1]

# ---------------- 参数（论文/Zenodo 统一：α=0.05, ω_c=2.5, δt=π/60, tol=1e-7）----------------
const α = 0.05
const ωc = 2.5
const δt = π / 60
const TOL = 1e-7
const T_SS = 200.0          # NESS 暂态时长（N=1 阻尼快，远够）
const TAU_MAX = 100.0       # 关联衰减积分上限
const W_GRID = 0.005:0.005:15.0

const REF = joinpath(@__DIR__, "..", "..", "results", "20260727-195949-mickiewicz2026-fig2", "zenodo")
const OUT = joinpath(@__DIR__, "..", "..", "results", "20260729-augmps-m4a")
mkpath(OUT)

bcf = t -> α * ωc^2 / (1 + im * ωc * t)^2
Jw(ω) = α * ω * exp(-ω / ωc)

println("building the influence functional ..."); flush(stdout)
pt = uniTEMPO(σz, δt, bcf, TOL)
χb = size(pt.q, 1)
println("χ_b = $χb"); flush(stdout)
const qm = q_matrix(pt)
const vl = pt.v_l[:]

# 六个参数组：(标签, ω_d, 单点场 h(t), 作者 CSV 文件名种类)
h_trans(ωd) = t -> 0.5 * σx + cos(ωd * t) * σz          # 横场 σz 驱动（图 3 下板）
h_long(ωd) = t -> (0.5 + cos(ωd * t)) * σx              # 纵场 σx 驱动（图 3 上板）
sets = [
    ("transversal", 1.0, h_trans(1.0)),
    ("transversal", 1.5, h_trans(1.5)),
    ("transversal", 2.0, h_trans(2.0)),
    ("longitudinal", 2.5, h_long(2.5)),
    ("longitudinal", 5.0, h_long(5.0)),
    ("longitudinal", 10.0, h_long(10.0)),
]

author_file(kind, ωd) = joinpath(REF, @sprintf("heat_current_%s_Ω_1_ϵ_d_1_ω_d_%s_α_0.05_ω_c_2.5_bond_dim_235_dt_0.052.csv",
    kind, ωd == round(Int, ωd) ? string(round(Int, ωd)) : string(ωd)))

# 从绝对步号 k 构造两个半阶单点门（与 run_chain 同一约定）
half_gates(h_onsite, k) = (onsite_superop(h_onsite((k - 0.75) * δt), δt / 2),
                           onsite_superop(h_onsite((k - 0.25) * δt), δt / 2))

# 读出 tr(S·X)：S=σz 即站点 1 的 ⟨σz⟩ 余矢量收缩（对非态对象同样线性成立）
const sz_cv = AugmentedTEMPO.op_covector(σz)
read_S(a) = expect(capped_mps(a, vl), [sz_cv])
read_O(a, cv) = real(expect(capped_mps(a, vl), [cv]))

for (kind, ωd, h_onsite) in sets
    M = round(Int, 2π / (ωd * δt))          # 一个驱动周期的步数（δt=π/60 下全为整数）
    k_ss = round(Int, T_SS / δt)
    L = round(Int, TAU_MAX / δt)
    println("\n=== $kind, ω_d = $ωd  (M=$M, t_ss=$T_SS, τmax=$TAU_MAX) ==="); flush(stdout)

    # 1. 传播到 NESS
    amps = init_amps(pt, 1)
    for k in 1:k_ss
        u1, u2 = half_gates(h_onsite, k)
        trotter_step!(amps, qm, u1, u2, nothing; cutoff=1e-13, maxdim=64)
    end

    # 2. NESS 收敛检查：相邻两个周期的 ⟨σz⟩ 曲线差异；并记录一个周期的 ⟨S⟩、⟨σx⟩
    svals = zeros(M); xvals = zeros(M); states = Vector{AugMPS}(undef, M)
    sx_cv = AugmentedTEMPO.op_covector(σx)
    for m in 1:M
        states[m] = deepcopy(amps)
        ts = capped_mps(amps, vl)
        svals[m] = real(sz_all(ts)[1])
        xvals[m] = real(expect(ts, [sx_cv]))
        u1, u2 = half_gates(h_onsite, k_ss + m)
        trotter_step!(amps, qm, u1, u2, nothing; cutoff=1e-13, maxdim=64)
    end
    ness_diff = maximum(abs(read_S(amps) - read_S(states[1])))
    # 与下一周期逐点对比（NESS 收敛检查）
    svals2 = zeros(M)
    for m in 1:M
        svals2[m] = real(read_S(amps))
        u1, u2 = half_gates(h_onsite, k_ss + M + m)
        trotter_step!(amps, qm, u1, u2, nothing; cutoff=1e-13, maxdim=64)
    end
    period_diff = maximum(abs.(svals2 .- svals))
    println("  NESS: |ψ(T)−ψ(0)| = $(round(ness_diff, sigdigits=3)), 周期逐点差 = $(round(period_diff, sigdigits=3))"); flush(stdout)

    # 3. 双时关联：每个 t' 起点插入 S 左乘后传播 τ
    C = zeros(ComplexF64, M, L + 1)
    for m in 1:M
        a = deepcopy(states[m])
        insert_diagonal_left!(a, [1.0, -1.0])   # S = σz
        C[m, 1] = read_S(a)                      # τ=0 应为 tr(S²ρ)=1
        for l in 1:L
            u1, u2 = half_gates(h_onsite, k_ss + (m - 1) + l)
            trotter_step!(a, qm, u1, u2, nothing; cutoff=1e-13, maxdim=64)
            C[m, l + 1] = read_S(a)
        end
        if m % 20 == 0 || m == M
            println("  correlation: t' $m / $M"); flush(stdout)
        end
    end
    Cbar = vec(mean(C, dims=1))
    println("  C̄(0) = $(round(Cbar[1], sigdigits=4))（应 ≈ 1）, C̄(τmax) = $(round(Cbar[end], sigdigits=3))"); flush(stdout)

    # 4. 渐近部与 δ 峰权重（周期 ⟨S(t)⟩ 的傅里叶级数）
    a0 = mean(svals)
    nh = M ÷ 2
    an = [2 / M * sum(svals[m] * cos(2π * n * (m - 1) / M) for m in 1:M) for n in 1:nh]
    bn = [2 / M * sum(svals[m] * sin(2π * n * (m - 1) / M) for m in 1:M) for n in 1:nh]
    cn = vcat([a0^2], [(an[n]^2 + bn[n]^2) / 2 for n in 1:nh])   # cn[1]=c_0, cn[n+1]=c_n
    τl = (0:L) .* δt
    Casym = [sum(cn[n + 1] * cos(n * ωd * τ) for n in 0:nh) for τ in τl]
    Cdecay = Cbar .- Casym

    # 5. 连续谱：j̄(ω) = 2ωJ(ω) Re∫_0^τmax e^{-iωτ} C̄_decay(τ) dτ（梯形）
    w = collect(W_GRID)
    spec = zeros(length(w))
    for (i, ω) in enumerate(w)
        acc = 0.5 * Cdecay[1] + 0.5 * Cdecay[end] * exp(-1im * ω * τl[end])
        for l in 1:(L - 1)
            acc += Cdecay[l + 1] * exp(-1im * ω * τl[l + 1])
        end
        spec[i] = 2 * ω * Jw(ω) * real(acc) * δt
    end

    # 6. 对照作者数据
    ref = readdlm(author_file(kind, ωd), Float64)[:]
    mask = w .<= 10.0
    l2 = norm(spec[mask] .- ref[mask]) / norm(ref[mask])
    # 峰值位置（连续谱最大）
    i_pk = argmax(spec[mask][2:end]) + 1; i_pk_ref = argmax(ref[mask][2:end]) + 1
    println("  L2 残差 (ω≤10) = $(round(l2 * 100, sigdigits=3))%")
    println("  主峰位置: ours ω=$(w[mask][i_pk]), authors ω=$(w[mask][i_pk_ref])")
    println("  δ 峰权重: c_0=$(round(cn[1], sigdigits=3)), c_1=$(round(cn[2], sigdigits=3)), c_2=$(round(cn[3], sigdigits=3)), c_3=$(round(cn[4], sigdigits=3))"); flush(stdout)

    # 7. 总流：连续部积分 + δ 峰权重；能量平衡 Ī = P̄
    I_cont = sum(spec) * 0.005
    I_delta = sum(π * (n * ωd) * Jw(n * ωd) * cn[n + 1] for n in 1:nh if n * ωd <= 15.0; init=0.0)
    drv = kind == "transversal" ? svals : xvals   # ∂H/∂t = −Aω_d sin(ω_d t)·(σz 或 σx)
    # 功率相位必须用绝对时间（states[m] 位于 t = (k_ss+m-1)·δt）
    Pbar = -ωd * mean(sin(ωd * (k_ss + m - 1) * δt) * drv[m] for m in 1:M)
    println("  总流 Ī = $(round(I_cont + I_delta, sigdigits=4))（连续 $(round(I_cont, sigdigits=4)) + δ $(round(I_delta, sigdigits=4))）,  P̄ = $(round(Pbar, sigdigits=4))"); flush(stdout)

    # 8. 保存
    writedlm(joinpath(OUT, @sprintf("jbar_%s_wd%s.csv", kind, ωd)), hcat(w, spec, ref))
    writedlm(joinpath(OUT, @sprintf("cbars_%s_wd%s.csv", kind, ωd)), hcat(τl, Cbar, Casym, Cdecay))
    writedlm(joinpath(OUT, @sprintf("summary_%s_wd%s.txt", kind, ωd)),
        ["kind=$kind  ω_d=$ωd  M=$M  L2=$(l2)  I_cont=$(I_cont)  I_delta=$(I_delta)  I_tot=$(I_cont+I_delta)  Pbar=$(Pbar)",
         "cn = $(cn[1:min(8, length(cn))])"])
end

println("\n=== M4a done ==="); flush(stdout)
