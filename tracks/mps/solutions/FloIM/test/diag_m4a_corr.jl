include(joinpath(@__DIR__, "..", "src", "augmented_tempo.jl"))
using .AugmentedTEMPO
using UniformTEMPO
using LinearAlgebra

const σx = ComplexF64[0 1; 1 0]
const σz = ComplexF64[1 0; 0 -1]
const α = 0.05; const ωc = 2.5; const δt = π / 60
bcf = t -> α * ωc^2 / (1 + im * ωc * t)^2
pt = uniTEMPO(σz, δt, bcf, 1e-7)
qm = q_matrix(pt); vl = pt.v_l[:]
sz_cv = AugmentedTEMPO.op_covector(σz)
readC(a) = expect(capped_mps(a, vl), [sz_cv])

function run_case(ωd, h_onsite, label; t_ss=200.0, τmax=40.0)
    M = round(Int, 2π / (ωd * δt)); k_ss = round(Int, t_ss / δt); L = round(Int, τmax / δt)
    amps = init_amps(pt, 1)
    for k in 1:k_ss
        trotter_step!(amps, qm, onsite_superop(h_onsite((k - 0.75) * δt), δt / 2),
                      onsite_superop(h_onsite((k - 0.25) * δt), δt / 2), nothing; cutoff=1e-13, maxdim=64)
    end
    states = Vector{AugMPS}(undef, M)
    for m in 1:M
        states[m] = deepcopy(amps)
        trotter_step!(amps, qm, onsite_superop(h_onsite((k_ss + m - 0.75) * δt), δt / 2),
                      onsite_superop(h_onsite((k_ss + m - 0.25) * δt), δt / 2), nothing; cutoff=1e-13, maxdim=64)
    end
    C = zeros(ComplexF64, M, L + 1)
    for m in 1:M
        a = deepcopy(states[m]); insert_diagonal_left!(a, [1.0, -1.0])
        C[m, 1] = readC(a)
        for l in 1:L
            kk = k_ss + (m - 1) + l
            trotter_step!(a, qm, onsite_superop(h_onsite((kk - 0.75) * δt), δt / 2),
                          onsite_superop(h_onsite((kk - 0.25) * δt), δt / 2), nothing; cutoff=1e-13, maxdim=64)
            C[m, l + 1] = readC(a)
        end
    end
    Cbar = vec(sum(C, dims=1)) ./ M
    println("=== $label, ω_d=$ωd ===")
    for l in [0, 12, 24, 48, 96, 192, 384, 768]
        l <= L && println("  τ=$(round(l*δt, digits=2))  C̄=$(round(Cbar[l+1], sigdigits=4))")
    end
    # 单一起点 t'=states[1] 的 C
    for l in [24, 96, 384]
        l <= L && println("  τ=$(round(l*δt, digits=2))  C(t'_1)=$(round(C[1, l+1], sigdigits=4))")
    end
    # 粗 FFT 看主频
    n = L + 1
    freqs = [abs(sum(Cbar[l+1] * exp(-2im * π * j * l / n) for l in 0:(n - 1))) for j in 0:(n ÷ 2)]
    jmax = argmax(freqs[2:end]) + 1
    ωpeak = 2π * (jmax - 1) / (n * δt)
    println("  C̄(τ) 主频 ω ≈ $(round(ωpeak, digits=3))  (期待 Ω=1 与 nω_d±1 的边带结构)")
    # 次峰
    f2 = copy(freqs); f2[max(1, jmax-8):min(n÷2+1, jmax+8)] .= 0
    j2 = argmax(f2[2:end]) + 1
    println("  次峰 ω ≈ $(round(2π*(j2-1)/(n*δt), digits=3))  幅度比 $(round(f2[j2]/freqs[jmax], sigdigits=2))")
    return Cbar
end

run_case(1.0, t -> 0.5σx + cos(1.0 * t) * σz, "transversal")
run_case(2.5, t -> (0.5 + cos(2.5 * t)) * σx, "longitudinal")
