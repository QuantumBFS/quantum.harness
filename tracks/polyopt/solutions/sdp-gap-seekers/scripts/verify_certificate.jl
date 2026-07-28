#!/usr/bin/env julia
# Independent certificate verifier (advisor re-audit requirement).
#
# Reads a portable certificate artifact (produced by certify_Ising_gap with
# export_cert=...) and reconstructs the affine constraint identity from the
# exported data — WITHOUT calling JuMP, Mosek, or the original constraint-
# construction code. Only uses Serialization (to read the artifact) and
# LinearAlgebra (for eigvals). This is the "genuinely separate checker."
#
# Audit checks (all must pass):
#   (a) lambda_ray > 0                     (genuine improving direction)
#   (b) every pos block ⪰ 0                 (ray in the positivity cone)
#   (c) every gpos block ⪰ 0               (ray in the gap cone)
#   (d) reconstructed cons[k] ≈ 0 for all k (homogeneous affine identity holds)
# (d) is recomputed here from the affine map + ray values — NOT from value.(cons).

using Serialization, LinearAlgebra

function verify(path::AbstractString; tol::Float64=1e-6)
    a = open(path) do io
        deserialize(io)
    end
    println("=== Independent certificate audit ===")
    println("artifact: $path")
    println("N=$(a.N) gamma=$(a.gamma) d=$(a.d) lso=$(a.lso)")
    println("solver statuses (recorded): termination=$(a.termination) primal=$(a.primal) dual=$(a.dual)")
    println("block sizes: pos=$(a.pos_sizes) gap=$(a.gap_sizes)")
    println("affine map entries: $(length(a.affine_map))")

    # (d) reconstruct cons[k] = sum over map of coef * ray_values[var_position]
    cons = Dict{Int, Float64}()
    for (k, varpos, coef) in a.affine_map
        cons[k] = get(cons, k, 0.0) + coef * a.ray_values[varpos]
    end
    resid = isempty(cons) ? 0.0 : maximum(abs, values(cons))
    cons_ok = resid < tol

    # (b)/(c) PSD checks on the exported Gram matrices
    pos_min = Float64[]
    for m in a.pos_mats
        isempty(m) || push!(pos_min, minimum(eigvals(Symmetric(m))))
    end
    gpos_min = Float64[]
    for m in a.gpos_mats
        isempty(m) || push!(gpos_min, minimum(eigvals(Symmetric(m))))
    end
    psd_ok = (isempty(pos_min) || minimum(pos_min) >= -tol) &&
             (isempty(gpos_min) || minimum(gpos_min) >= -tol)

    # (a) lambda
    lam = a.lambda
    lam_ok = lam > tol

    println("--- residuals (recomputed by THIS verifier) ---")
    println("  max|cons| residual = ", resid, "  (<$tol? ", cons_ok, ")")
    println("  pos min eig  = ", round.(pos_min, digits=6), "  (all >= -$tol? ", isempty(pos_min) || minimum(pos_min) >= -tol, ")")
    println("  gpos min eig = ", round.(gpos_min, digits=6), "  (all >= -$tol? ", isempty(gpos_min) || minimum(gpos_min) >= -tol, ")")
    println("  lambda       = ", lam, "  (>$tol? ", lam_ok, ")")
    valid = cons_ok && psd_ok && lam_ok
    println("==================================================")
    println("RESULT: ", valid ? "certificate AUDITS (independent verifier, no JuMP/Mosek)"
                              : "AUDIT FAILS — not a valid certificate")
    if !valid && !cons_ok
        println("  (constraint residual too large — ray does not satisfy the affine identity)")
    end
    if a.termination != "DUAL_INFEASIBLE" && a.termination != "OPTIMAL"
        println("  NOTE: solver termination was $(a.termination) (not a decisive DUAL_INFEASIBLE);")
        println("        an audited ray here is a numerical candidate, not yet a rigorous proof")
        println("        (rational/interval post-processing still needed for strict certification).")
    end
    return valid
end

if abspath(PROGRAM_FILE) == @__FILE__
    if length(ARGS) < 1
        println(stderr, "usage: julia verify_certificate.jl <artifact.jls>")
        exit(2)
    end
    ok = verify(ARGS[1])
    exit(ok ? 0 : 1)
end
