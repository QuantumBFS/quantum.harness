# enum_search.jl — RESUMABLE exact enumeration (correction 3: written in
# parallel while run #1 is in flight; used only if run #1 dies, or for
# audit reruns). Differences vs the in-flight g3: incremental per-row
# flush to training.csv (with per-row wall seconds), skip-completed on
# restart, and the declared tie-break (a)/(b)/(c) applied at freeze.
# Usage: julia enum_search.jl   (from rg_selection/; idempotent)
using Printf
include(joinpath(@__DIR__, "rg_builder.jl"))
include(joinpath(@__DIR__, "functional_rg.jl"))

const RESULTS = joinpath(@__DIR__, "..", "results")
const CSV = joinpath(RESULTS, "training.csv")
const NRG = 6

subsets = [Vector{String}(sort([POOL[i] for i in 1:4 if (b >> (i - 1)) & 1 == 1]))
           for b in 1:15 if count_ones(b) <= 3] |> unique
done = Set{Tuple{Int,String}}()
if isfile(CSV)
    for l in Iterators.drop(eachline(CSV), 1)
        f = split(l, ","); length(f) >= 2 && push!(done, (parse(Int, f[1]), String(f[2])))
    end
else
    open(CSV, "w") do io
        println(io, "N,S,L_joint,L_base,eps_cmp,ordering,gamma2_dim,newwords,wall_s")
    end
end
As = load_D4()
bases = Dict{Int,Any}()
for N in (10, 12)
    bases[N] = build_rg_selection_model(N; vspace = :stock)
    rg = rg_spec(N, NRG, As)
    for S in subsets
        key = join(S, "+")
        (N, key) in done && continue
        t0 = time()
        r = build_rg_selection_model(N; S = S, rg = rg, vspace = :auto)
        w = time() - t0
        b0 = bases[N]
        ec = b0.resid.mu + r.resid.mu + 0.75 * (b0.resid.pfeas + b0.resid.dfeas +
                                                r.resid.pfeas + r.resid.dfeas)
        open(CSV, "a") do io
            @printf(io, "%d,%s,%.14f,%.14f,%.2e,%s,%d,%d,%.1f\n", N, key, r.E, b0.E,
                    ec, r.E >= b0.E - ec ? "ok" : "ORDER-VIOLATION",
                    get(r.counters, "gamma2_dim", -1), get(r.counters, "seam_newwords", -1), w)
        end
        @printf("done %d %s  E=%.12f  %.0fs\n", N, key, r.E, w)
    end
end
println("enumeration complete; run g3_finalize.jl for the tie-broken freeze")
