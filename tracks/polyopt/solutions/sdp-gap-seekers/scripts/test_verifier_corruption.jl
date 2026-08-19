#!/usr/bin/env julia
# Verifier corruption self-tests (advisor recheck @491083f, Priority 0B).
#
# Deliberately corrupt one field of the artifact at a time and require the
# verifier to REJECT each (ok=false). Two test families:
#   A. one-x binding (5): affine coef, PSD index asymmetry, zero objective,
#      NaN ray, wrong lambda_pos.
#   B. schema completeness (9): omitted pos/gap map, empty-map-for-positive-size,
#      rectangular map, extra block, out-of-range affine row/var, wrong objective
#      length, schema_version mismatch.
#
# A skipped required test FAILS the suite (exact test counter). The verifier
# rejecting every corruption demonstrates the binding is real; it does not by
# itself prove general soundness.

include(joinpath(@__DIR__, "verify_certificate.jl"))   # defines audit (no main runs)
using Serialization

path = ARGS[1]
a = open(path) do io
    deserialize(io)
end

base = audit(a)
println("BASELINE (uncorrupted): ok=$(base.ok) label=$(base.label)  [expect ok=true]")
base.ok || error("baseline must pass before corruption tests are meaningful")

withfld(nt::NamedTuple, sym::Symbol, val) = merge(nt, NamedTuple{(sym,)}((val,)))

const EXPECTED_TESTS = 14
n_tests = 0
n_accepted = 0
accepted = String[]

function check(name::String, a2)
    global n_tests += 1
    r = audit(a2)
    rejected = !r.ok
    println("  $name: ok=$(r.ok) label=$(r.label)  [expect ok=false]")
    rejected || (global n_accepted += 1; push!(accepted, name))
end

# need at least one >=2x2 pos block for asymmetry/rectangular tests
i_sym = findfirst(s -> s >= 2, a.pos_sizes)
i_sym === nothing && error("artifact has no >=2x2 pos block (corruption tests need one)")

# --- A. one-x binding corruptions ---

am = collect(a.affine_map); am[1] = (am[1][1], am[1][2], am[1][3] + 1.0)
check("corrupt affine coef", withfld(a, :affine_map, am))

pvp = [copy(m) for m in a.pos_var_positions]
pvp[i_sym][1, 2] = pvp[i_sym][2, 2]      # break [1,2]==[2,1] aliasing
check("corrupt psd index (asymmetry)", withfld(a, :pos_var_positions, pvp))

check("corrupt objective (zero c)", withfld(a, :c, zeros(Float64, length(a.c))))

x2 = copy(a.ray_values); x2[1] = NaN
check("corrupt ray NaN", withfld(a, :ray_values, x2))

wrong_lp = a.lambda_var_position % a.nvars + 1
check("corrupt lambda_pos", withfld(a, :lambda_var_position, wrong_lp))

# --- B. schema-completeness corruptions ---

check("delete pos map (count mismatch)",
      withfld(a, :pos_var_positions, [a.pos_var_positions[2:end]...]))
check("delete gap map (count mismatch)",
      withfld(a, :gap_var_positions, [a.gap_var_positions[2:end]...]))

i_pos = findfirst(s -> s > 0, a.pos_sizes)
pvp2 = [copy(m) for m in a.pos_var_positions]
pvp2[i_pos] = zeros(Int, 0, 0)           # positive declared size, empty map
check("empty map for positive declared size", withfld(a, :pos_var_positions, pvp2))

pvp3 = [copy(m) for m in a.pos_var_positions]
pvp3[i_sym] = pvp3[i_sym][1:end-1, :]    # (n-1, n) rectangular
check("rectangular map", withfld(a, :pos_var_positions, pvp3))

check("extra pos block (count mismatch)",
      withfld(a, :pos_var_positions, [a.pos_var_positions..., zeros(Int, 0, 0)]))

am_r = collect(a.affine_map); am_r[1] = (a.nconstraints + 1, am_r[1][2], am_r[1][3])
check("affine row out-of-range", withfld(a, :affine_map, am_r))

am_v = collect(a.affine_map); am_v[1] = (am_v[1][1], a.nvars + 1, am_v[1][3])
check("affine var out-of-range", withfld(a, :affine_map, am_v))

check("objective length mismatch", withfld(a, :c, zeros(Float64, a.nvars - 1)))

check("schema_version mismatch", withfld(a, :schema_version, 2))

# --- verdict ---
println("==================================================")
println("executed $n_tests / $EXPECTED_TESTS corruption tests")
if n_tests != EXPECTED_TESTS
    println("TEST SUITE FAIL: expected $EXPECTED_TESTS tests, ran $n_tests (a required test was skipped)")
    exit(1)
end
if n_accepted == 0
    println("ALL CORRUPTION TESTS PASS: verifier rejects every inconsistency (sound)")
    exit(0)
else
    println("CORRUPTION TEST FAILURES: verifier accepted $n_accepted corrupted artifact(s): $accepted")
    exit(1)
end
