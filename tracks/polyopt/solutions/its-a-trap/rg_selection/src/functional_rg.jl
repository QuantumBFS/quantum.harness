# functional_rg.jl — the [RG] optional family: Γ₃(x³) ⪰ 0 + link B₂Q₂y=T₃x³,
# realized by the gate-validated two-parity tower generator (cg_hybrid/
# tower_gen.jl: ED-oracle rows ≤ 1e-15) with the D=4 parity-resolved VUMPS
# map, UNMODIFIED. rg_spec output plugs into RGExt (ycoef/zblocks) — the
# dual identity is THEOREM_CONTRACT_RG_SELECTION §4 = cg_hybrid KKT.
include(joinpath(@__DIR__, "..", "..", "cg_hybrid", "tower_gen.jl"))

"load the persisted D=4 parity pair (provenance-pinned JSON)"
function load_D4()
    s = read(joinpath(@__DIR__, "..", "..", "cg_hybrid", "vumps_A_D4.json"), String)
    grab(key) = begin
        m = match(Regex("\"$key\":\\[\\[(.*?)\\],\\[(.*?)\\]\\]"), s)
        [parse.(Float64, split(m.captures[i], ",")) for i in 1:2]
    end
    As = [[begin
              v = grab("A$(i)_re")[μ] .+ 1im .* grab("A$(i)_im")[μ]
              m = Int(sqrt(length(v))); Matrix{ComplexF64}(reshape(v, m, m))
           end for μ in 1:2] for i in 1:2]
    @assert all(norm(sum(As[i][μ]' * As[i][μ] for μ in 1:2) - I) < 1e-10 for i in 1:2)
    return As
end

"map hash for provenance"
d4_hash() = bytes2hex(sha256(read(joinpath(@__DIR__, "..", "..", "cg_hybrid", "vumps_A_D4.json"))))[1:16]

"rg spec at level n (Lemma-1 bound n ≤ N−1): words + dual channels"
function rg_spec(N::Int, n::Int, As)
    tw = build_tower(N, n, As)
    words = unique(first.(vcat(tw.ycoef...)))
    return (words = words, ycoef = tw.ycoef, zblocks = tw.zblocks)
end

"compatibility residual (G2): parity-resolved flow composition —
W_{k+1}^{(q)} must equal the right-extension of W_k^{(q)} by the tensor of
parity q+k (the code echo of B₂C₁T₃ = T₃′C₂)."
function compat_residual(As; kmax = 4)
    mm = size(As[1][1], 1)
    worst = 0.0
    for q in 1:2, k in 2:kmax
        Wk = chainmap2(As, k, q); Wk1 = chainmap2(As, k + 1, q)
        A = As[mod1(q + k, 2)]
        built = zeros(ComplexF64, mm * mm, 2^(k + 1))
        for col in 1:2^k, ν in 1:2, I_ in 1:mm, J in 1:mm, K in 1:mm
            built[(I_-1)*mm+J, (col-1)*2+ν] += Wk[(I_-1)*mm+K, col] * A[ν][K, J]
        end
        worst = max(worst, maximum(abs, built - Wk1))
    end
    return worst
end
