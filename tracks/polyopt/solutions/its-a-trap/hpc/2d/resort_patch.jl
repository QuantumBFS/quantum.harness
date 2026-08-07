# resort_patch.jl — method-lane monkey-patch for the upstream bug documented
# in BLOCKED.md. APPROVED by the arbiter 2026-07-29 morning ("2D 用
# monkey-patch 跑起来"). Loaded via `julia -L resort_patch.jl` in the 2D
# sbatch scripts; self-contained (loads QMBCertify itself).
using QMBCertify
#
# Semantics: sort the support list, merge coefficients of duplicates —
# matching the call sites in eigen_circmat (basic_function.jl:316/:341) where
# supp :: Vector{Vector{UInt16}} (words) and coe :: Vector{<:Number}.
# Validation is the canary gate (valid LB vs 4x4 torus E0/N, OPTIMAL).
@eval QMBCertify function resort(supp, coe)
    nsupp = sort(supp)
    unique!(nsupp)
    ncoe = zeros(eltype(coe), length(nsupp))
    for (i, s) in enumerate(supp)
        ncoe[bfind(nsupp, s)] += coe[i]
    end
    return nsupp, ncoe
end
@info "QMBCertify.resort monkey-patched (method lane; see BLOCKED.md)"
