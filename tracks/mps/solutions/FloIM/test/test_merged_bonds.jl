# merge_bonds 优化的 N=6 对照测试
#
# 判据：N=6 的 MPS 最大只需 χ=4³=64，maxdim=64 时截断永不触发，
# 两种模式在算符层面严格相等（[bonds,bath]=0），故逐帧观测量差应 ~1e-13。
# 附带：与 ED 的差保持 Trotter 阶（ΔE ~ 3e-3），并报告两种模式的耗时比。
#
# Usage: julia --project=tracks/mps/env_floquet tracks/mps/solutions/test_merged_bonds.jl

include(joinpath(@__DIR__, "..", "src", "augmented_tempo.jl"))
using .AugmentedTEMPO, UniformTEMPO, LinearAlgebra, KrylovKit, SparseArrays, Printf

const δt = π / 60
const σx = ComplexF64[0 1; 1 0]
const σz = ComplexF64[1 0; 0 -1]
const I2 = Matrix{ComplexF64}(I, 2, 2)

const N = 6
const J = 0.5; const HX = 0.5; const HZ = 0.3; const A = 1.0; const ωd = 2.5
const T_MAX = 5.0
const n = round(Int, T_MAX / δt)

h_onsite(t) = HX * σx + (HZ + A * cos(ωd * t)) * σz
const G_half = bond_superop(exp(-1im * J * kron(σz, σz) * δt / 2))
const G_full = bond_superop(exp(-1im * J * kron(σz, σz) * δt))

meas(amps, vl, t) = begin
    ts = capped_mps(amps, vl)
    (sz=sz_all(ts), E=energy_ising(ts, h_onsite(t), J), pur=purity(ts))
end

function compare(tag, rec_s, rec_m)
    dsz = maximum(maximum(abs.(rec_s[k].sz .- rec_m[k].sz)) for k in 1:length(rec_s))
    dE = maximum(abs(rec_s[k].E - rec_m[k].E) for k in 1:length(rec_s))
    dpur = maximum(abs(rec_s[k].pur - rec_m[k].pur) for k in 1:length(rec_s))
    println("  $tag : max|Δsz| = $(round(dsz, sigdigits=3)), max|ΔE| = $(round(dE, sigdigits=3)), max|Δpur| = $(round(dpur, sigdigits=3))")
    flush(stdout)
    return dsz, dE
end

# ---------- A: 封闭系统（平凡 IF, χ_b=1） ----------
println("=== A: α=0 closed chain, N=$N, standard vs merged (no truncation) ==="); flush(stdout)
pt0 = UniformPTMPO(2, δt)
t_s = @elapsed (_, rec_s0) = run_chain(pt0, N, h_onsite, G_half, n;
                                       cutoff=1e-13, maxdim=64, measure=meas)
t_m = @elapsed (_, rec_m0) = run_chain(pt0, N, h_onsite, G_full, n;
                                       cutoff=1e-13, maxdim=64, measure=meas, merge_bonds=true)
compare("closed", rec_s0, rec_m0)
println("  wall time: standard $(round(t_s, digits=2)) s, merged $(round(t_m, digits=2)) s, ratio $(round(t_s / t_m, digits=2))"); flush(stdout)

# ---------- B: 真实浴（uniTEMPO IF, χ_b=41） ----------
# 注意：带浴时 (1,2) 键的精确秩是 χ_b·4 = 164（记忆腿挂在站点 1 上），
# 要 maxdim ≥ 164 才是真正不截断。
println("\n=== B: paper bath (α=0.05, ωc=2.5), N=$N, standard vs merged (maxdim=1024, no truncation) ==="); flush(stdout)
pt = uniTEMPO(σz, δt, t -> 0.05 * (2.5 / (1 + im * 2.5 * t))^2, 1e-7)
t_s = @elapsed (_, rec_s) = run_chain(pt, N, h_onsite, G_half, n;
                                      cutoff=1e-14, maxdim=1024, measure=meas)
t_m = @elapsed (_, rec_m) = run_chain(pt, N, h_onsite, G_full, n;
                                      cutoff=1e-14, maxdim=1024, measure=meas, merge_bonds=true)
compare("bath", rec_s, rec_m)
println("  wall time: standard $(round(t_s, digits=2)) s, merged $(round(t_m, digits=2)) s, ratio $(round(t_s / t_m, digits=2))"); flush(stdout)

# ---------- C: merged 与 ED 的差应保持 Trotter 阶 ----------
println("\n=== C: merged vs Krylov ED (closed, Trotter level expected) ==="); flush(stdout)
site_op(op, i, N) = foldl(kron, [j == (N - i + 1) ? op : I2 for j in 1:N])
function sparse_H(N, t)
    H = spzeros(ComplexF64, 2^N, 2^N)
    for i in 1:(N - 1)
        H += J * sparse(site_op(σz, i, N) * site_op(σz, i + 1, N))
    end
    f = HZ + A * cos(ωd * t)
    for i in 1:N
        H += HX * sparse(site_op(σx, i, N)) + f * sparse(site_op(σz, i, N))
    end
    return H
end
ψ = zeros(ComplexF64, 2^N); ψ[1] = 1.0
E_ed = zeros(n + 1)
E_ed[1] = real(ψ' * sparse_H(N, 0.0) * ψ)
for k in 1:n
    global ψ
    for s in 0:15
        tmid = (k - 1 + (s + 0.5) / 16) * δt
        ψ, = exponentiate(-1im * sparse_H(N, tmid), δt / 16, ψ; tol=1e-13)
    end
    E_ed[k + 1] = real(ψ' * sparse_H(N, k * δt) * ψ)
end
dE_ed = maximum(abs(rec_m0[k].E - E_ed[k]) for k in 1:(n + 1))
println("  merged vs ED: max|ΔE| = $(round(dE_ed, sigdigits=3))  (Trotter 阶 ≈ 3e-3 预期)"); flush(stdout)
