#!/usr/bin/env julia
# Verifier corruption self-tests (advisor Priority 0).
# Deliberately corrupt one field of the artifact at a time and require the
# verifier to FAIL each time. Proves the verifier is sound (binds everything to
# one x) rather than trusting separate exported copies.

include(joinpath(@__DIR__, "verify_certificate.jl"))   # defines audit, AuditResult (no main runs)

using Serialization

path = ARGS[1]
a = open(path) do io
    deserialize(io)
end

base = audit(a)
println("BASELINE (uncorrupted): ok=$(base.ok) label=$(base.label)  [expect ok=true]")
base.ok || error("baseline must pass before corruption tests are meaningful")

withfld(nt::NamedTuple, sym::Symbol, val) = merge(nt, NamedTuple{(sym,)}((val,)))

fails = 0

# 1. corrupt one affine coefficient (+1.0 on the first map entry) -> A*x residual grows
am = collect(a.affine_map)
am[1] = (am[1][1], am[1][2], am[1][3] + 1.0)
r = audit(withfld(a, :affine_map, am))
println("corrupt affine coef:  ok=$(r.ok)  [expect false]")
r.ok && (global fails += 1)

# 2. corrupt a PSD index-map entry -> reconstructed block asymmetric
pvp = [copy(m) for m in a.pos_var_positions]
ok2 = false
for i in 1:length(pvp)
    s = size(pvp[i], 1)
    if s >= 2
        pvp[i][1, 2] = pvp[i][2, 2]    # break the [1,2]==[2,1] aliasing
        global ok2 = true
        break
    end
end
if ok2
    r = audit(withfld(a, :pos_var_positions, pvp))
    println("corrupt psd index:    ok=$(r.ok)  [expect false]")
    r.ok && (global fails += 1)
else
    println("corrupt psd index:    SKIPPED (no >=2x2 pos block)")
end

# 3. zero the objective vector -> c'x = 0, not > tol
r = audit(withfld(a, :c, zeros(Float64, length(a.c))))
println("corrupt objective:    ok=$(r.ok)  [expect false]")
r.ok && (global fails += 1)

# 4. NaN in ray_values -> non-finite -> fail
x2 = copy(a.ray_values); x2[1] = NaN
r = audit(withfld(a, :ray_values, x2))
println("corrupt ray NaN:      ok=$(r.ok)  [expect false]")
r.ok && (global fails += 1)

# 5. wrong lambda_var_position -> c'x != x[lambda_pos] consistency fail
wrong_lp = a.lambda_var_position % a.nvars + 1
r = audit(withfld(a, :lambda_var_position, wrong_lp))
println("corrupt lambda_pos:   ok=$(r.ok)  [expect false]")
r.ok && (global fails += 1)

println("==================================================")
if fails == 0
    println("ALL CORRUPTION TESTS PASS: verifier rejects every inconsistency (sound)")
    exit(0)
else
    println("CORRUPTION TEST FAILURES: $fails (verifier accepted a corrupted artifact)")
    exit(1)
end
