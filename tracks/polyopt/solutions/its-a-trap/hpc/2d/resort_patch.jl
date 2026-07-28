# resort_patch.jl — method-lane monkey-patch for the upstream bug documented
# in BLOCKED.md. NOT loaded anywhere until the morning arbiter approves.
# Include AFTER `using QMBCertify`, BEFORE any lattice="square" GSB call.
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
