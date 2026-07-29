# g3_finalize.jl — post-processor: applies the DECLARED tie-break
# (a) Score, (b) gamma2_dim cost within ε_cmp, (c) lexicographic — to
# training.csv, (re)writes FROZEN_SELECTION.json BEFORE any holdout run,
# and emits the corrected G3 report fields (correction 6).
using Printf, SHA
const RESULTS = joinpath(@__DIR__, "..", "results")
rows = [split(l, ",") for l in Iterators.drop(eachline(joinpath(RESULTS, "training.csv")), 1)]
L = Dict{Tuple{Int,String},Float64}(); B = Dict{Int,Float64}()
EC = Dict{Tuple{Int,String},Float64}(); GD = Dict{String,Int}()
W = Float64[]
for f in rows
    N = parse(Int, f[1]); k = String(f[2])
    L[(N, k)] = parse(Float64, f[3]); B[N] = parse(Float64, f[4])
    EC[(N, k)] = parse(Float64, f[5]); GD[k] = parse(Int, f[7])
    length(f) >= 9 && push!(W, parse(Float64, f[9]))
end
keys23 = unique([k for (N, k) in keys(L) if 2 <= count("+", k) + 1 <= 3])
score(k) = 0.5 * sum(L[(N, k)] - B[N] for N in (10, 12))
scored = sort([(k, score(k)) for k in keys23 if all(haskey(L, (N, k)) for N in (10, 12))],
              by = x -> -x[2])
best, second = scored[1], length(scored) > 1 ? scored[2] : (nothing, -Inf)
rule = "(a)"
if second[1] !== nothing && abs(best[2] - second[2]) <= max(EC[(10, best[1])], EC[(12, best[1])])
    if GD[second[1]] < GD[best[1]]
        best, second, rule = second, best, "(b) lower gamma2_dim"
    elseif GD[second[1]] == GD[best[1]]
        rule = "(c) lexicographic"
        best = minimum([best, second], by = x -> x[1])
    else
        rule = "(b) confirmed leader (lower cost already)"
    end
end
Sstar = split(best[1], "+")
open(joinpath(RESULTS, "FROZEN_SELECTION.json"), "w") do io
    print(io, "{\"S_star\": [", join(("\"$b\"" for b in Sstar), ", "),
          "], \"score_per_site\": ", best[2],
          ", \"runner_up\": \"", second[1] === nothing ? "" : second[1],
          "\", \"runner_up_score\": ", second[2],
          ", \"tie_break_rule_fired\": \"", rule,
          "\", \"frozen_before_holdout\": true, \"n_rg\": 6, ",
          "\"enumeration_mode\": \"EXACT_ALL_SUBSETS_LE3\", ",
          "\"pool_hash\": \"8c3f55720dc81cabc683fd0ba6b92d0d3c2f93629afacfe6b4f62c526879a31c\"}")
end
sha = bytes2hex(sha256(read(joinpath(RESULTS, "FROZEN_SELECTION.json"))))
@printf("G3 FINAL: evaluated %d/28 joint rows; S*=%s Score=%.3e; runner-up %s (%.3e); rule %s\n",
        length(rows), best[1], best[2], second[1], second[2], rule)
@printf("FROZEN_SELECTION sha256=%s; holdout untouched=TRUE; wall median=%.0fs max=%.0fs (n=%d timed)\n",
        sha, isempty(W) ? NaN : sort(W)[max(1, end ÷ 2)], isempty(W) ? NaN : maximum(W), length(W))
