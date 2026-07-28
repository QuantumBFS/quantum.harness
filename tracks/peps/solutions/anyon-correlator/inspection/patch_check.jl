# Finite open-patch contraction — used to diagnose the cycle-gas vs cut-gas
# tensor error (the naive Z-basis copy gave ⟨A_s⟩ = 0 on the patch).
# STATUS: superseded after the X-basis copy fix; the patch amplitude logic
# assumes Z-basis copies, so it no longer applies to the corrected tensor.
# Kept for the record.
include(joinpath(@__DIR__, "..", "scripts", "tc_peps.jl"))

R, C = 3, 3
T = exact_tensor_dense_VP()  # [pE,pN,n,e,s,w]

# bonds: h[r,c] r=1..R, c=0..C (h[r,c] = link (r,c)-(r,c+1));
#        v[r,c] r=0..R, c=1..C (v[r,c] = link (r,c)-(r+1,c))
nh = R * (C + 1)
nv = (R + 1) * C
nbits = nh + nv
hbit(r, c) = (c) * R + r - 1            # c=0..C
vbit(r, c) = nh + (c - 1) * (R + 1) + r  # r=0..R

amp = zeros(Float64, 2^(2R * C))
spin_index(pE, pN) = sum(((pE[r, c] + 2 * pN[r, c]) << (2 * ((c - 1) * R + r - 1)) for r in 1:R, c in 1:C)) + 1

for bits in 0:(2^nbits - 1)
    h(r, c) = (bits >> hbit(r, c)) & 1
    v(r, c) = (bits >> vbit(r, c)) & 1
    pE = zeros(Int, R, C); pN = zeros(Int, R, C)
    ok = true
    for r in 1:R, c in 1:C
        n, e, s, w = v(r - 1, c), h(r, c), v(r, c), h(r, c - 1)
        if !iszero(n ⊻ e ⊻ s ⊻ w)
            ok = false; break
        end
        pE[r, c] = e; pN[r, c] = n
    end
    ok && (amp[spin_index(pE, pN)] += 1.0)
end

nonzero = count(>(1e-14), amp)
println("allowed configs: $nonzero / $(2^(2R*C))  (expect 2^($(2R*C) - $(R*C)) = $(2^(R*C)))")
println("all amplitudes 1: ", all(a -> a ≈ 1.0, amp[amp .> 1e-14]))

# ⟨A_s⟩ for the central star (2,2): flips pE(2,2), pE(2,1), pN(2,2), pN(3,2)
function flip_star(idx)
    pbits = digits(idx - 1, base = 2, pad = 2R * C)
    flipbits = [2 * ((2 - 1) * R + 2 - 1) - 1,   # pE(2,2) -> bit position
                2 * ((1 - 1) * R + 2 - 1) - 1,   # pE(2,1)
                2 * ((2 - 1) * R + 2 - 1),       # pN(2,2)
                2 * ((3 - 1) * R + 2 - 1)]       # pN(3,2)
    for b in flipbits
        pbits[b + 1] ⊻= 1
    end
    return sum(pbits[k] * 2^(k - 1) for k in 1:length(pbits)) + 1
end
numer = sum(amp[i] * amp[flip_star(i)] for i in 1:length(amp))
denom = sum(amp .^ 2)
println("⟨A_star(2,2)⟩ on patch = ", numer / denom, "  (want 1 if stabilized)")
