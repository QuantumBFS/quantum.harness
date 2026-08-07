# ============================================================================
# augmented_tempo.jl — 增广 MPS 求解器
#
#   物理问题：驱动斜场 Ising 链（H = Σ J σzσz + Σ [h_x σx + h_z(t) σz]）
#             左端点（站点 1）耦合零温 Ohmic 玻色浴。
#   方法：浴的影响泛函（IF）只含站点 1 的 Liouville 路径 → 精确因子化为
#         uniTEMPO 均匀 MPO（键维 χ_b 不随时间增长）；系统密度矩阵用
#         空间 MPS（Liouville 空间，物理腿维度 4）承载；边界张量同时挂
#         记忆腿和空间键腿。设计文档：
#         docs/design/2026-07-28-floquet-unitempo-manybody-ising.md
#
#   数据结构（AugMPS）：
#     B[m, μ, a]   — 站点 1 边界张量：m = 记忆腿 (χ_b)，μ = 站点 1 的
#                    Liouville 指标 (1..4)，a = 空间键 (χ_1)
#     A[i-1][l, μ, r] — 站点 i = 2..N 的体部张量
#     整个增广 MPS 表示 Ψ(μ_1..μ_N; m)，用 pt.v_l 收缩记忆腿 m（"cap"）
#     后得到系统的 Liouville 矢量 ρ(μ_1..μ_N)（站点 1 是最快指标）。
#
#   约定（与 UniformTEMPO.jl 严格一致，勿改）：
#     - Liouville vec 用列主序：μ = r + 2(c-1) 对应基元 |r⟩⟨c|
#     - pt.q 形状 (χ_b, 4, χ_b, 4) = (记忆-out, 系统-out, 记忆-in, 系统-in)
#     - 局域通道 u*⊗u 即 kron(conj(u), u)（同 UniformTEMPO.local_channel）
#     - 每步结构 onsite(δt/2) → bonds(δt/2) → 浴步(Q) → bonds(δt/2) → onsite(δt/2)，
#       N=1 时退化为 UniformTEMPO.evolve 的 u1 → q → u2
#
#   观测量：一律在 capped MPS 上收缩计算（期望/纯度 O(N χ²)），不生成
#   2^N × 2^N 密度矩阵；cap_density 仅留作 N≤12 的 ED 对照调试用。
# ============================================================================
module AugmentedTEMPO

using LinearAlgebra
using UniformTEMPO

export AugMPS, init_amps, onsite_superop, bond_superop, bond_covector, op2,
       onsite!, bath_step!, bond12_step!, bulk_bond_step!, insert_diagonal_left!,
       capped_mps, expect, expect_bond, sz_all, trace_rho, purity, energy_ising,
       site_energies, current_bond, current_profile,
       cap_density, q_matrix, trotter_step!, run_chain

const σx = ComplexF64[0 1; 1 0]
const σy = ComplexF64[0 -1im; 1im 0]
const σz = ComplexF64[1 0; 0 -1]

mutable struct AugMPS
    B::Array{ComplexF64,3}          # 站点 1：(χ_b, 4, χ_1)
    A::Vector{Array{ComplexF64,3}}  # A[i-1] ↔ 站点 i = 2..N，各为 (χ_{i-1}, 4, χ_i)
    N::Int
end

# ---------- 基本构造 ----------

# 把 pt.q 重排成 (χ_b·4)×(χ_b·4) 矩阵，作用在 vec(记忆⊗系统) 上
# （与 UniformTEMPO.evolve 内部的 reshape 完全相同，列主序）
q_matrix(pt::UniformPTMPO) = reshape(pt.q, size(pt.q, 1) * 4, size(pt.q, 1) * 4)

# 初态：ρ0 = ⊗_i |↑⟩⟨↑|（乘积态，所有键维为 1），记忆腿置为 pt.v_r
# （对应 IF 链的最右端边界矢量，同 UniformTEMPO 的初态构造）
function init_amps(pt::UniformPTMPO, N::Int)
    ρup = zeros(ComplexF64, 4); ρup[1] = 1.0   # vec(|↑⟩⟨↑|)，列主序：μ=1 ↔ (r,c)=(1,1)
    χb = size(pt.q, 1)
    B = zeros(ComplexF64, χb, 4, 1)
    B[:, :, 1] = pt.v_r * transpose(ρup)
    A = [reshape(copy(ρup), 1, 4, 1) for _ in 2:N]
    return AugMPS(B, A, N)
end

# 单点 Liouville 门：U = u*⊗u，u = exp(-i h τ)，列主序 vec
# 与 UniformTEMPO.local_channel 相同：kron(transpose(exp(+im h τ)), exp(-im h τ)) = kron(conj(u), u)
function onsite_superop(h::AbstractMatrix, τ::Real)
    u = exp(-1im * Matrix(h) * τ)
    return kron(conj(u), u)
end

# 两点 Liouville 门 G（16×16），作用在 (μ_i, μ_j) 对上。
# 指标约定：μ = r + 2(c-1)；对指标 = μ_i + 4(μ_j-1)。
# u_b 是 4×4 Hilbert 空间键幺正（如 exp(-i J σzσz τ)）。
# 矩阵元：G[(ν_i,ν_j),(μ_i,μ_j)] = u_b[r',r] · conj(u_b[c',c])，
# 其中 r = (r_i,r_j) 等按 r_i + 2(r_j-1) 展平。
function bond_superop(u_b::AbstractMatrix)
    dec(μ) = (mod(μ - 1, 2) + 1, div(μ - 1, 2) + 1)   # μ → (r, c)
    G = zeros(ComplexF64, 16, 16)
    for νj in 1:4, νi in 1:4, μj in 1:4, μi in 1:4
        ri, ci = dec(μi); rj, cj = dec(μj)
        ri′, ci′ = dec(νi); rj′, cj′ = dec(νj)
        G[νi + 4 * (νj - 1), μi + 4 * (μj - 1)] =
            u_b[ri′ + 2 * (rj′ - 1), ri + 2 * (rj - 1)] * conj(u_b[ci′ + 2 * (cj′ - 1), ci + 2 * (cj - 1)])
    end
    return G
end

# ---------- TEBD 基元操作 ----------

# 单点门作用：X[.., μ, ..] → Σ_ν U[μ,ν] X[..,ν,..]，对 B 和 A[i] 通用
function onsite!(X::Array{ComplexF64,3}, U::AbstractMatrix)
    s1, _, s3 = size(X)
    Y = reshape(permutedims(X, (2, 1, 3)), 4, s1 * s3)
    Y = U * Y
    X .= permutedims(reshape(Y, 4, s1, s3), (2, 1, 3))
    return X
end

# 浴步（只作用在站点 1）：对每个空间键指标 a，把 (χ_b,4) 切片 vec 后乘 q_mat。
# 这就是 uniTEMPO 的短时传播子 Q（含站点 1 的本地系统演化在内——注意
# trotter_step! 里浴步前后还有半阶 onsite 门，与 UniformTEMPO.evolve 的
# u1→q→u2 结构一致，Q 内部的 u 对应其中央全阶部分）。
function bath_step!(B::Array{ComplexF64,3}, q_mat::AbstractMatrix)
    χb, _, χs = size(B)
    for a in 1:χs
        B[:, :, a] = reshape(q_mat * B[:, :, a][:], χb, 4)
    end
    return B
end

# 截断 SVD：保留 s > cutoff·s_max 的奇异值且总数 ≤ maxdim。
# 返回 U, s, V† 和被丢弃的权重 Σ 被丢奇异值²。
# 注意：Julia 解构 `U, s, Vt = svd(M)` 拿到的第三个是 V 不是 V†（名字误导），
# 这里显式取 F.Vt（= V'），不要再踩坑。
function _trunc_svd(M; cutoff, maxdim)
    F = svd(M)
    s = F.S
    k = min(count(>(cutoff * s[1]) , s), maxdim)
    k = max(k, 1)
    dw = k < length(s) ? sum(s[k+1:end] .^ 2) : 0.0
    return F.U[:, 1:k], s[1:k], F.Vt[1:k, :], dw
end

# 把 16×16 门 G 作用到已收缩的两点矩阵 M 上。
# M 的行指标是 (x, μ_i)，列指标是 (μ_j, y)，其中 x/y 是左右环境腿的展平。
function _apply_gate(M, G, nx, ny)
    T = reshape(M, nx, 4, 4, ny)                 # (x, μ_i, μ_j, y)
    T = permutedims(T, (2, 3, 1, 4))             # (μ_i, μ_j, x, y)
    T = reshape(G * reshape(T, 16, nx * ny), 4, 4, nx, ny)
    return reshape(permutedims(T, (3, 1, 2, 4)), nx * 4, 4 * ny)
end

# 键 (1,2)：收缩 B–A[1] → 加门 → SVD 截断。
# 记忆腿留在 B 侧且不参与截断（截断只发生在空间键上）。
function bond12_step!(amps::AugMPS, G::AbstractMatrix; cutoff=1e-12, maxdim=256)
    B, A2 = amps.B, amps.A[1]
    χb, _, χ1 = size(B)
    χ2 = size(A2, 3)
    M = reshape(B, χb * 4, χ1) * reshape(A2, χ1, 4 * χ2)   # 行 (m,μ1)，列 (μ2,r)
    M = _apply_gate(M, G, χb, χ2)
    U, s, Vt, dw = _trunc_svd(M; cutoff=cutoff, maxdim=maxdim)
    k = length(s)
    amps.B = reshape(U, χb, 4, k)
    amps.A[1] = reshape(Diagonal(s) * Vt, k, 4, χ2)
    return dw
end

# 体部键 (i,i+1)，i ≥ 2：收缩 A[i-1]–A[i] → 加门 → SVD 截断
function bulk_bond_step!(amps::AugMPS, i::Int, G::AbstractMatrix; cutoff=1e-12, maxdim=256)
    A1, A2 = amps.A[i-1], amps.A[i]
    χl, _, χm = size(A1)
    χr = size(A2, 3)
    M = reshape(A1, χl * 4, χm) * reshape(A2, χm, 4 * χr)   # 行 (l,μi)，列 (μj,r)
    M = _apply_gate(M, G, χl, χr)
    U, s, Vt, dw = _trunc_svd(M; cutoff=cutoff, maxdim=maxdim)
    k = length(s)
    amps.A[i-1] = reshape(U, χl, 4, k)
    amps.A[i] = reshape(Diagonal(s) * Vt, k, 4, χr)
    return dw
end

# ---------- capped MPS 与观测量（核心计算路径，不生成 2^N 矩阵）----------
#
# cap：用 v_l 收缩记忆腿，得到普通 MPS（站点 1 左边界维度为 1）。
# 之后所有观测量都在这个 MPS 上收缩，代价 O(N χ²·4) 或 O(N χ³)，
# 与 Hilbert 空间维度 2^N 无关 → 大 N 也可用。
#
# 观测量收缩的原理：⟨O⟩ = tr(O ρ) = Σ_μ ρ_μ · c_O[μ]，其中
#   c_O[μ] = tr(O |r⟩⟨c|) = ⟨c|O|r⟩ = O[c,r] = vec(transpose(O))[μ]
# 即每个站点乘一个 4 维"余矢量"再全收缩。无算符的站点用迹余矢量
# tr_cv = [1,0,0,1]（μ=(r,c)，r=c 时为 1）。

const tr_cv = ComplexF64[1, 0, 0, 1]

# 单点算符 O（2×2）→ Liouville 余矢量 vec(transpose(O))
op_covector(O::AbstractMatrix) = vec(transpose(Matrix(O)))

# 两点算符 O2（4×4，站点 i,j 的 Hilbert 直积序）→ 16 维余矢量，
# 指标排列与 bond_superop 一致：对指标 = μ_i + 4(μ_j-1)。
function bond_covector(O2::AbstractMatrix)
    dec(μ) = (mod(μ - 1, 2) + 1, div(μ - 1, 2) + 1)
    g = zeros(ComplexF64, 16)
    for μj in 1:4, μi in 1:4
        ri, ci = dec(μi); rj, cj = dec(μj)
        g[μi + 4 * (μj - 1)] = O2[ci + 2 * (cj - 1), ri + 2 * (rj - 1)]
    end
    return g
end

# cap 成普通 MPS：ts[1][1, μ, a] = Σ_m v_l[m] B[m, μ, a]，其余为 A[i-1]
function capped_mps(amps::AugMPS, vl::AbstractVector)
    χb, _, χ1 = size(amps.B)
    C1 = transpose(vl[:]) * reshape(amps.B, χb, 4 * χ1)     # (1, 4·χ1)
    ts = Vector{Array{ComplexF64,3}}(undef, amps.N)
    ts[1] = reshape(C1, 1, 4, χ1)
    for i in 2:amps.N
        ts[i] = amps.A[i-1]
    end
    return ts
end

# 通用单点余矢量期望：cvs[i] 是站点 i 的 4 维余矢量，全收缩得标量
function expect(ts::Vector{Array{ComplexF64,3}}, cvs::Vector{<:AbstractVector})
    E = ones(ComplexF64, 1)                       # 左环境（站点 1 左边界维度 1）
    for i in 1:length(ts)
        Ti = ts[i]
        χl, _, χr = size(Ti)
        E2 = zeros(ComplexF64, χr)
        for r in 1:χr, μ in 1:4, l in 1:χl
            E2[r] += E[l] * Ti[l, μ, r] * cvs[i][μ]
        end
        E = E2
    end
    return only(E)
end

# 两点期望：⟨O_{i,i+1}⟩，g 为 bond_covector 生成的 16 维余矢量
function expect_bond(ts::Vector{Array{ComplexF64,3}}, g::AbstractVector, i::Int)
    N = length(ts)
    E = ones(ComplexF64, 1)
    for j in 1:(i - 1)                            # 站点 <i 用迹收缩
        Tj = ts[j]
        χl, _, χr = size(Tj)
        E2 = zeros(ComplexF64, χr)
        for r in 1:χr, μ in 1:4, l in 1:χl
            E2[r] += E[l] * Tj[l, μ, r] * tr_cv[μ]
        end
        E = E2
    end
    # 站点 i, i+1 与 g 收缩
    Ti, Tj = ts[i], ts[i + 1]
    χl, _, χm = size(Ti)
    χr = size(Tj, 3)
    E2 = zeros(ComplexF64, χr)
    for r in 1:χr, μj in 1:4, m in 1:χm, μi in 1:4, l in 1:χl
        E2[r] += E[l] * Ti[l, μi, m] * Tj[m, μj, r] * g[μi + 4 * (μj - 1)]
    end
    E = E2
    for j in (i + 2):N                            # 站点 >i+1 用迹收缩
        Tj = ts[j]
        χl, _, χr = size(Tj)
        E3 = zeros(ComplexF64, χr)
        for r in 1:χr, μ in 1:4, l in 1:χl
            E3[r] += E[l] * Tj[l, μ, r] * tr_cv[μ]
        end
        E = E3
    end
    return only(E)
end

# MPS 范数² = ⟨ρ|ρ⟩ = Σ_μ |ρ_μ|² = tr(ρ†ρ)（ρ 厄米时即纯度 tr ρ²）。
# 双层收缩，O(N χ³)。
function mps_norm2(ts::Vector{Array{ComplexF64,3}})
    E = ones(ComplexF64, 1, 1)
    for Ti in ts
        χl, _, χr = size(Ti)
        sl, _ = size(E)
        E2 = zeros(ComplexF64, χr, χr)
        for r2 in 1:χr, r1 in 1:χr, μ in 1:4, l2 in 1:χl, l1 in 1:χl
            E2[r1, r2] += E[l1, l2] * Ti[l1, μ, r1] * conj(Ti[l2, μ, r2])
        end
        E = E2
    end
    return real(only(E))
end

# ---- 常用观测量的便捷封装（输入 capped MPS）----

sz_all(ts) = [real(expect(ts, [j == i ? op_covector(σz) : tr_cv for j in 1:length(ts)]))
              for i in 1:length(ts)]

trace_rho(ts) = real(expect(ts, [tr_cv for _ in 1:length(ts)]))

purity(ts) = mps_norm2(ts)

# 两点算符的 4×4 矩阵约定：站点 i 是最快指标（列主序 r = r_i + 2(r_j−1)），
# 而 Julia kron 的最后因子最快 —— 故算符 "O_i ⊗ O_{i+1}" 的矩阵 = kron(O_{i+1}, O_i)。
# 与 bond_superop 的 u_b 同一约定。（σzσz 对称不暴露此坑，σy 型算符会翻号！）
op2(Oi, Oj) = kron(Oj, Oi)

# Ising 链能量：E(t) = Σ_i tr(h_loc(t) ρ_i) + J Σ_i ⟨σz_i σz_{i+1}⟩
# hmat = 当前时刻单点哈密顿量（2×2），J = 耦合强度
function energy_ising(ts, hmat::AbstractMatrix, J::Real)
    N = length(ts)
    cv = op_covector(hmat)
    E = sum(expect(ts, [j == i ? cv : tr_cv for j in 1:N]) for i in 1:N)
    g = bond_covector(op2(σz, σz))
    E += J * sum(expect_bond(ts, g, i) for i in 1:(N - 1))
    return real(E)
end

# 站点能量密度 e_i = tr(h_loc ρ_i) + (J/2)(⟨zz_{i-1,i}⟩ + ⟨zz_{i,i+1}⟩)
# （端点只计一侧键） Σ_i e_i = energy_ising
function site_energies(ts, hmat::AbstractMatrix, J::Real)
    N = length(ts)
    cv = op_covector(hmat)
    e = [real(expect(ts, [j == i ? cv : tr_cv for j in 1:N])) for i in 1:N]
    g = bond_covector(op2(σz, σz))
    for i in 1:(N - 1)
        zz = real(expect_bond(ts, g, i))
        e[i] += J / 2 * zz
        e[i + 1] += J / 2 * zz
    end
    return e
end

# 键 (i,i+1) 的【体系内部】能量流算符期望：j = J h_x (σy_i σz_{i+1} − σz_i σy_{i+1})
# 推导：de_i/dt = j_{i-1,i} − j_{i,i+1}（连续性方程，h_z(t) 全部对易掉）。
# 已经 ED 仲裁（test/m4_heat_current.jl A 节 + 封闭链逐点对照）。
# 符号约定：j > 0 表示能量从站点 i 流向 i+1（浴在左端 ⇒ NESS 下 j < 0）。
# 注意：这不是论文图 3 的热流密度 j̄(ω)！后者是浴模式分辨量，由双时关联
# 计算（设计文档附录 B，heat_current_spectrum / 双时关联流程），本函数只是体系侧诊断。
function current_bond(ts, J::Real, hx::Real, i::Int)
    g_yz = bond_covector(op2(σy, σz))   # σy_i σz_{i+1}
    g_zy = bond_covector(op2(σz, σy))   # σz_i σy_{i+1}
    return J * hx * real(expect_bond(ts, g_yz, i) - expect_bond(ts, g_zy, i))
end

# 所有键的流分布
current_profile(ts, J::Real, hx::Real) = [current_bond(ts, J, hx, i) for i in 1:(length(ts) - 1)]

# ---------- 双时关联（附录 B 热流密度机制） ----------

# 在边界站点 1 上施加【对角算符 S 的左乘】：ρ → Sρ。
# 对 S = diag(d)（σz 耦合 d = [1,-1]），左乘在 Liouville 指标 μ=(r,c) 上就是对角的：乘 d[r]。
# 双时关联 ⟨S(t+τ)S(t)⟩ = tr(S · 𝒰(τ)[S ρ(t)])：先 insert_diagonal_left!，再照常传播 τ，
# 最后用 sz_all(ts)[1] 读出（tr(S·) 即 σz 余矢量）。IF 记忆腿自动携带浴记忆跨过插入。
function insert_diagonal_left!(amps::AugMPS, d::AbstractVector)
    dec(μ) = (mod(μ - 1, 2) + 1, div(μ - 1, 2) + 1)
    for μ in 1:4
        r, _ = dec(μ)
        amps.B[:, μ, :] .*= d[r]
    end
    return amps
end

# ---------- 调试专用：全收缩成 2^N × 2^N 密度矩阵（仅 N ≲ 12 的 ED 对照用） ----------
# 注意：不要在生产计算里用它算观测量（维度随 N 指数增长），观测量请走上面的
# capped-MPS 收缩路径。这里保留只为和 ED 做逐矩阵元对照。
function cap_density(amps::AugMPS, vl::AbstractVector)
    χb = size(amps.B, 1)
    v = transpose(vl) * reshape(amps.B, χb, :)             # (1, 4·χ1)
    v = reshape(v, 4, :)                                    # (4, χ1)，行指标 μ1
    for Ai in amps.A
        χi = size(Ai, 3)
        w = v * reshape(Ai, size(Ai, 1), 4 * χi)            # (4^{i-1}, (μ_i, χ_i))
        v = reshape(reshape(w, size(w, 1), 4, χi), 4 * size(w, 1), χi)
    end
    w = vec(v)                                              # 4^N，指标 (μ1..μN)，μ1 最快
    T = reshape(w, ntuple(_ -> 2, 2 * amps.N))              # (r1,c1,r2,c2,...)
    perm = vcat(1:2:(2 * amps.N - 1), 2:2:(2 * amps.N))
    return reshape(permutedims(T, perm), 2^amps.N, 2^amps.N)
end

# ---------- 时间演化驱动 ----------

# 键层扫描：bond12 + 体部键各一次。抽出来供两种步进模式共用。
function bond_sweep!(amps, G; cutoff, maxdim)
    dw = bond12_step!(amps, G; cutoff=cutoff, maxdim=maxdim)
    for i in 2:(amps.N - 1)
        dw += bulk_bond_step!(amps, i, G; cutoff=cutoff, maxdim=maxdim)
    end
    return dw
end

# 一个时间步。两种模式（merge_bonds 控制，默认 false 保留原写法）：
#
#   merge_bonds = false（标准 Strang）：
#     onsite(δt/2) → bonds(δt/2) → 浴 → bonds(δt/2) → onsite(δt/2)
#     每步 2(N−1) 次键 SVD。G 传半阶门 exp(−iJzz δt/2)。
#
#   merge_bonds = true（合并键层，仅对 σz 耦合成立）：
#     onsite(δt/2) → bonds(δt) → 浴 → onsite(δt/2)
#     依据：σz 耦合下键门 G 与浴步 q 在 μ 指标上都是对角操作，[bonds, bath] = 0，
#     故 e^{B/2} e^{C} e^{B/2} = e^{B} e^{C} 严格相等（算符层面，非近似），
#     键 SVD 减半（2× 加速），唯一差别是截断样式。G 传全阶门 exp(−iJzz δt)。
function trotter_step!(amps, qm, u1, u2, G; cutoff, maxdim, merge_bonds=false)
    dw = 0.0
    onsite!(amps.B, u1)
    for Ai in amps.A; onsite!(Ai, u1); end
    if G !== nothing
        dw += bond_sweep!(amps, G; cutoff=cutoff, maxdim=maxdim)
        bath_step!(amps.B, qm)
        if !merge_bonds
            dw += bond_sweep!(amps, G; cutoff=cutoff, maxdim=maxdim)
        end
    else
        bath_step!(amps.B, qm)
    end
    onsite!(amps.B, u2)
    for Ai in amps.A; onsite!(Ai, u2); end
    return dw
end

# 默认测量：所有站点的 ⟨σz⟩、tr ρ、纯度 tr ρ²（全部走 capped-MPS 收缩）
function default_measure(amps, vl, t)
    ts = capped_mps(amps, vl)
    return (sz=sz_all(ts), tr=trace_rho(ts), pur=purity(ts))
end

# 主循环。每 report_every 步测一次观测量并存记录，不存密度矩阵。
#   pt          — UniformPTMPO（uniTEMPO(σz, δt, bcf, tol) 或平凡构造 UniformPTMPO(2, δt)）
#   h_onsite    — 函数 t -> 2×2 单点哈密顿量
#   G           — 键门（bond_superop 生成；merge_bonds=false 传半阶门，true 传全阶门）或 nothing
#   measure     — 回调 (amps, vl, t) -> NamedTuple；自定义观测量（如能量）从这里注入
#   merge_bonds — 见 trotter_step!；仅 σz 耦合可开
#   keep_state  — true 时额外返回末态 amps（用于接续演化，如 NESS 后继续细采样）
# 每帧记录自动附加 χs（当前最大空间键维）和 dw（聚积丢弃权重），
# 配合多次 maxdim 运行即可做 χ_s 收敛序列对照。
# 返回 (times, records) 或 (times, records, amps)。
function run_chain(pt, N, h_onsite, G, n; report_every=1, cutoff=1e-12, maxdim=256,
                   measure=default_measure, merge_bonds=false, keep_state=false)
    δt = pt.delta_t
    vl = pt.v_l[:]
    qm = q_matrix(pt)
    amps = init_amps(pt, N)
    times = collect(0:report_every:n) .* δt
    χs_now() = maximum(vcat([size(amps.B, 3)], [size(Ai, 3) for Ai in amps.A]))
    dw_acc = 0.0
    records = [merge(measure(amps, vl, 0.0), (χs=χs_now(), dw=0.0))]
    for k in 1:n
        u1 = onsite_superop(h_onsite((k - 0.75) * δt), δt / 2)
        u2 = onsite_superop(h_onsite((k - 0.25) * δt), δt / 2)
        dw_acc += trotter_step!(amps, qm, u1, u2, G; cutoff=cutoff, maxdim=maxdim,
                                merge_bonds=merge_bonds)
        if k % report_every == 0
            push!(records, merge(measure(amps, vl, k * δt), (χs=χs_now(), dw=dw_acc)))
        end
        if k % 200 == 0
            println("  step $k / $n  (max χ_s = $(χs_now()), discarded = $(round(dw_acc, sigdigits=3)))"); flush(stdout)
        end
    end
    println("  final max χ_s = $(χs_now()), total discarded weight = $(round(dw_acc, sigdigits=3))"); flush(stdout)
    return keep_state ? (times, records, amps) : (times, records)
end

end # module
