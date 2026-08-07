# M4b：多体（N=4 链）频率分辨热流密度 j̄(ω)，与 N=1 单体对比
# 公式与协议同 M4a（附录 B，唯一正确定义）：
#   j̄(ω) = 2ωJ(ω) Re∫_0^τmax e^{-iωτ} C̄_decay(τ)dτ，C̄(τ) = 周期平均 ⟨σz¹(t'+τ)σz¹(t')⟩
# 多体点：浴只耦合站点 1（S=σz¹），链内 J σzσz 键把多体结构带进关联函数。
# 本脚本参数：J=0.5, h_x=0.5, h_z=0.3, A=1, ω_d=2.5（与 M1/M3 同系），t_ss=400, τmax=100。
# 用法：julia --project=tracks/mps/env_floquet tracks/mps/solutions/test/m4b_heat_current_n4.jl

include(joinpath(@__DIR__, "..", "src", "augmented_tempo.jl"))

using .AugmentedTEMPO
using UniformTEMPO
using Printf
using DelimitedFiles
using LinearAlgebra
using Statistics

const σx = ComplexF64[0 1; 1 0]
const σz = ComplexF64[1 0; 0 -1]

const α = 0.05
const ωc = 2.5
const δt = π / 60
const TOL = 1e-7
const TAU_MAX = 100.0
const W_GRID = 0.005:0.005:15.0

const OUT = joinpath(@__DIR__, "..", "..", "results", "20260729-augmps-m4b")
mkpath(OUT)

bcf = t -> α * ωc^2 / (1 + im * ωc * t)^2
Jw(ω) = α * ω * exp(-ω / ωc)

println("building the influence functional ..."); flush(stdout)
pt = uniTEMPO(σz, δt, bcf, TOL)
println("χ_b = $(size(pt.q,1))"); flush(stdout)
const qm = q_matrix(pt)
const vl = pt.v_l[:]
const sz_cv = AugmentedTEMPO.op_covector(σz)

# 通用谱计算：给定 N、h(t)、J，返回 (w, spec, cn, Cbar, Pbar, ness_info)
function heat_spectrum(N, ωd, h_onsite, J; t_ss, τmax=TAU_MAX, label="")
    M = round(Int, 2π / (ωd * δt))
    k_ss = round(Int, t_ss / δt)
    L = round(Int, τmax / δt)
    G_half = J == 0 ? nothing : bond_superop(exp(-1im * J * kron(σz, σz) * δt / 2))
    u1u2(k) = (onsite_superop(h_onsite((k - 0.75) * δt), δt / 2),
               onsite_superop(h_onsite((k - 0.25) * δt), δt / 2))
    println("  [$label] NESS transient: $k_ss steps (t_ss=$t_ss)"); flush(stdout)

    amps = init_amps(pt, N)
    t0 = time()
    for k in 1:k_ss
        u1, u2 = u1u2(k)
        trotter_step!(amps, qm, u1, u2, G_half; cutoff=1e-13, maxdim=256)
        if k % 1000 == 0
            println("  [$label] transient step $k / $k_ss  ($(round(time()-t0, digits=1)) s)"); flush(stdout)
        end
    end

    # 记录一个周期：状态 + ⟨σz¹⟩（asym 部与 NESS 检查用）+ ⟨Σσz⟩（功率用）
    svals = zeros(M); szsum = zeros(M); states = Vector{AugMPS}(undef, M)
    for m in 1:M
        states[m] = deepcopy(amps)
        ts = capped_mps(amps, vl)
        szs = sz_all(ts)
        svals[m] = szs[1]
        szsum[m] = sum(szs)
        u1, u2 = u1u2(k_ss + m)
        trotter_step!(amps, qm, u1, u2, G_half; cutoff=1e-13, maxdim=256)
    end
    # 下一周期逐点差（NESS 收敛判据）
    svals2 = zeros(M)
    for m in 1:M
        svals2[m] = expect(capped_mps(amps, vl), vcat([sz_cv], fill(AugmentedTEMPO.tr_cv, N - 1))) |> real
        u1, u2 = u1u2(k_ss + M + m)
        trotter_step!(amps, qm, u1, u2, G_half; cutoff=1e-13, maxdim=256)
    end
    period_diff = maximum(abs.(svals2 .- svals))
    println("  [$label] NESS 周期逐点差 = $(round(period_diff, sigdigits=3))"); flush(stdout)

    # 双时关联
    C = zeros(ComplexF64, M, L + 1)
    t0 = time()
    for m in 1:M
        a = deepcopy(states[m])
        insert_diagonal_left!(a, [1.0, -1.0])
        C[m, 1] = expect(capped_mps(a, vl), vcat([sz_cv], fill(AugmentedTEMPO.tr_cv, N - 1)))
        for l in 1:L
            u1, u2 = u1u2(k_ss + (m - 1) + l)
            trotter_step!(a, qm, u1, u2, G_half; cutoff=1e-13, maxdim=256)
            C[m, l + 1] = expect(capped_mps(a, vl), vcat([sz_cv], fill(AugmentedTEMPO.tr_cv, N - 1)))
        end
        if m % 4 == 0 || m == M
            println("  [$label] correlation t' $m / $M  ($(round(time()-t0, digits=1)) s)"); flush(stdout)
        end
    end
    Cbar = vec(mean(C, dims=1))

    # 渐近部（⟨σz¹(t)⟩ 傅里叶级数）与 δ 峰权重
    a0 = mean(svals)
    nh = M ÷ 2
    an = [2 / M * sum(svals[m] * cos(2π * n * (m - 1) / M) for m in 1:M) for n in 1:nh]
    bn = [2 / M * sum(svals[m] * sin(2π * n * (m - 1) / M) for m in 1:M) for n in 1:nh]
    cn = vcat([a0^2], [(an[n]^2 + bn[n]^2) / 2 for n in 1:nh])
    τl = (0:L) .* δt
    Casym = [sum(cn[n + 1] * cos(n * ωd * τ) for n in 0:nh) for τ in τl]
    Cdecay = Cbar .- Casym

    # 连续谱
    w = collect(W_GRID)
    spec = zeros(length(w))
    for (i, ω) in enumerate(w)
        acc = 0.5 * Cdecay[1] + 0.5 * Cdecay[end] * exp(-1im * ω * τl[end])
        for l in 1:(L - 1)
            acc += Cdecay[l + 1] * exp(-1im * ω * τl[l + 1])
        end
        spec[i] = 2 * ω * Jw(ω) * real(acc) * δt
    end

    # 总流与能量平衡（驱动作用于所有站点：P = −Aω_d sin(ω_d t)·Σ⟨σz⟩）
    I_cont = sum(spec) * 0.005
    I_delta = sum(π * (n * ωd) * Jw(n * ωd) * cn[n + 1] for n in 1:nh if n * ωd <= 15.0; init=0.0)
    A = 1.0
    Pbar = -A * ωd * mean(sin(ωd * (k_ss + m - 1) * δt) * szsum[m] for m in 1:M)
    println("  [$label] Ī = $(round(I_cont + I_delta, sigdigits=4))（连续 $(round(I_cont, sigdigits=4)) + δ $(round(I_delta, sigdigits=4))）,  P̄ = $(round(Pbar, sigdigits=4))"); flush(stdout)
    println("  [$label] C̄(0)=$(round(Cbar[1], sigdigits=4))  c_1=$(round(cn[2], sigdigits=3))  c_2=$(round(cn[3], sigdigits=3))  c_3=$(round(cn[4], sigdigits=3))"); flush(stdout)

    return (w=w, spec=spec, cn=cn, Cbar=Cbar, Casym=Casym, I_tot=I_cont + I_delta, Pbar=Pbar,
            period_diff=period_diff, svals=svals)
end

# ---------------- 参数：h(t) = 0.5σx + (0.3 + cos(2.5t))σz，J=0.5 ----------------
const ωd = 2.5
const J = 0.5
h_onsite = t -> 0.5 * σx + (0.3 + cos(ωd * t)) * σz

r1 = heat_spectrum(1, ωd, h_onsite, 0.0; t_ss=400.0, label="N=1")
writedlm(joinpath(OUT, "jbar_N1_wd2.5.csv"), hcat(r1.w, r1.spec))

r4 = heat_spectrum(4, ωd, h_onsite, J; t_ss=400.0, label="N=4")
writedlm(joinpath(OUT, "jbar_N4_wd2.5.csv"), hcat(r4.w, r4.spec))

writedlm(joinpath(OUT, "summary.txt"), [
    "M4b N=4 vs N=1, ω_d=2.5, J=0.5, hx=0.5, hz=0.3, A=1, α=0.05, ωc=2.5, t_ss=400, τmax=100",
    "N=1: Ī=$(r1.I_tot)  P̄=$(r1.Pbar)  period_diff=$(r1.period_diff)  c1..c3=$(r1.cn[2:4])",
    "N=4: Ī=$(r4.I_tot)  P̄=$(r4.Pbar)  period_diff=$(r4.period_diff)  c1..c3=$(r4.cn[2:4])",
])

println("\n=== M4b done ==="); flush(stdout)
