# ============================================================================
# redfield_ising.jl — 驱动斜场 Ising 链 + 边界浴的 Redfield–Magnus 基准
#
#   推导：docs/design/2026-07-28-redfield-benchmark-manybody-ising.md
#   要点：驱动轴 ∥ 耦合轴（都沿 σz）→ 一阶 Floquet–Magnus 修正为零，
#         H_F = H_0（静态 Ising），kick 只影响非 σz 型观测量。
#         ⟨σz_i⟩、⟨σz_iσz_{i+1}⟩、Ising 能量对微运动免疫 → 可与
#         增广 MPS 结果逐帧直接对照（无需 stroboscopic 限制）。
#
#   约定（与已验证的单自旋脚本 test/floquet_spin_boson_fig2.jl 完全一致）：
#     - Γ(ω) = ∫₀^∞ ds e^{iωs} η(s)，实部 παω e^{-ω/ωc} Θ(ω)，
#       虚部 α(−ωc + ω g(ω))，g 用 expinti/expint
#     - 𝒜[m,n] = S_en[m,n] Γ[n,m]，ℬ[m,n] = S_en[m,n] conj(Γ[m,n])（能量基）
#     - R = −kron(I,S𝒜) + kron(Sᵀ,𝒜) + kron(ℬᵀ,S) − kron((ℬS)ᵀ,I)
#     - L = −i(kron(I,H_F) − kron(H_Fᵀ,I)) + R，列主序 vec
#     - 全部在 H_F 能量基组装（ED 一次）
#
#   站点↔kron 约定与增广 MPS 模块一致：站点 i 映射到 kron 位置 N+1−i
#   （cap 出的 ρ 站点 1 最快；这里全程在计算基/能量基，无 cap，但 H_F、
#   σz_i 的构造必须与增广 MPS 的 site_op 镜像一致才能逐站点对照）。
# ============================================================================
module RedfieldIsing

using LinearAlgebra
using SpecialFunctions

export build_H0, site_op, bath_Gamma, redfield_liouvillian, RedfieldModel,
       evolve_redfield, expect_redfield, steady_state_redfield

const σx = ComplexF64[0 1; 1 0]
const σz = ComplexF64[1 0; 0 -1]
const I2 = Matrix{ComplexF64}(I, 2, 2)

# 站点 i 的单点算符（镜像约定：我们的站点 i ↔ kron 位置 N+1−i）
site_op(op, i, N) = foldl(kron, [j == (N - i + 1) ? op : I2 for j in 1:N])

# 静态 Ising 哈密顿量 H_0 = Σ J σzσz + Σ (h_z σz + h_x σx)
function build_H0(N, J, hz, hx)
    H = zeros(ComplexF64, 2^N, 2^N)
    for i in 1:(N - 1)
        H += J * (site_op(σz, i, N) * site_op(σz, i + 1, N))
    end
    for i in 1:N
        H += hz * site_op(σz, i, N) + hx * site_op(σx, i, N)
    end
    return Hermitian(H)
end

# 单边傅里叶变换 Γ(ω)（同单自旋验证版）
function bath_Gamma(ω, α, ωc)
    re = ω > 0 ? π * α * ω * exp(-ω / ωc) : 0.0
    g = if ω > 0
        exp(-ω / ωc) * expinti(ω / ωc)
    elseif ω < 0
        -exp(abs(ω) / ωc) * expint(abs(ω) / ωc)
    else
        0.0
    end
    return re + 1im * α * (-ωc + ω * g)
end

struct RedfieldModel
    N::Int
    HF::Matrix{ComplexF64}      # 计算基 H_0
    V::Matrix{ComplexF64}       # H_0 本征矢（计算基 → 能量基）
    E::Vector{Float64}          # 本征值
    S_en::Matrix{ComplexF64}    # 能量基下的耦合算符 σz^1
    L::Matrix{ComplexF64}       # Liouville 超算符（能量基，4^N × 4^N）
end

# 组装 Redfield Liouvillian（Bohr 频率形式，无久期近似）
function redfield_liouvillian(N, J, hz, hx, α, ωc)
    HF = Matrix(build_H0(N, J, hz, hx))
    E, V = eigen(Hermitian(HF))
    S0 = site_op(σz, 1, N)                    # 计算基 σz^1
    S_en = V' * S0 * V
    d = 2^N
    Γm = [bath_Gamma(E[a] - E[b], α, ωc) for a in 1:d, b in 1:d]
    𝒜 = S_en .* transpose(Γm)                 # 𝒜[m,n] = S_en[m,n] Γ[n,m]
    ℬ = S_en .* conj.(Γm)                     # ℬ[m,n] = S_en[m,n] conj(Γ[m,n])
    Id = Matrix{ComplexF64}(I, d, d)
    S𝒜 = S_en * 𝒜
    ℬS = ℬ * S_en
    R = -kron(Id, S𝒜) + kron(transpose(S_en), 𝒜) +
        kron(transpose(ℬ), S_en) - kron(transpose(ℬS), Id)
    Hs = Diagonal(E)
    L = -1im * (kron(Id, Hs) - kron(transpose(Hs), Id)) + R
    return RedfieldModel(N, HF, V, E, S_en, Matrix(L))
end

# 初态 vec ρ（能量基）：计算基乘积态 ρ0_comp = ⊗ |↑⟩⟨↑| 变换到能量基
function initial_vec_en(rm::RedfieldModel)
    ρ0 = zeros(ComplexF64, 2^rm.N, 2^rm.N); ρ0[1, 1] = 1.0   # 站点 1 最快 ⇒ |↑…↑⟩ = 基矢 1
    ρ0_en = rm.V' * ρ0 * rm.V
    return vec(ρ0_en)
end

# 演化：dense 情形用逐帧矩阵指数（N≤3）；Krylov 步进由调用方自选
function evolve_redfield(rm::RedfieldModel, times::AbstractVector)
    v0 = initial_vec_en(rm)
    out = Vector{Vector{ComplexF64}}(undef, length(times))
    for (k, t) in enumerate(times)
        out[k] = exp(rm.L * t) * v0
    end
    return out
end

# ⟨O_i⟩：tr(O ρ)，O_en = V' O V；covector = vec(transpose(O_en))
function expect_redfield(rm::RedfieldModel, op::AbstractMatrix, i::Int, v_en::AbstractVector)
    O_en = rm.V' * site_op(op, i, rm.N) * rm.V
    cv = vec(transpose(O_en))
    return real(dot(cv, v_en))
end

# 稳态：L 的零本征矢（dense，N≤6 可一次性 eigen）
function steady_state_redfield(rm::RedfieldModel)
    F = eigen(rm.L)
    k = argmin(abs.(F.values))
    v = F.vectors[:, k]
    # 归一化：tr ρ = 1 ⇒ Σ_i v[i 在 (r,c)=(j,j) 位置] = 1
    d = 2^rm.N
    trρ = sum(v[j + (j - 1) * d] for j in 1:d)
    return v / trρ
end

end # module
