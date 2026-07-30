#!/usr/bin/env julia
# finalize_replacement.jl — replacement_summary.csv + SUMMARY.md skeleton from
# replacement_build.csv + replacement_solve.csv ONLY (v4 §7 metrics; every
# eta beside PSD-scalar/largest-block/wall/RSS ratios; signed, uncapped).
using Printf, SHA, Dates
const R = joinpath(@__DIR__, "results")

bethe = Dict{Int,Float64}()
for m in eachmatch(r"\"(\d+)\":\s*(-[0-9.eE-]+)", read(joinpath(@__DIR__, "..", "hpc", "refs", "bethe_ref.json"), String))
    bethe[parse(Int, m.captures[1])] = parse(Float64, m.captures[2])
end

rows = Dict{Tuple{Int,String},Dict{String,String}}()
SHDR = split("N,arm,E,pfeas,dfeas,mu,scalarized,mosek_rows,newwords,gamma2_dim,rg_rows,wall_s,rss_gb,status,config_sha16", ",")
for l in readlines(joinpath(R, "replacement_solve.csv"))[2:end]
    f = split(l, ","); length(f) >= 14 || continue
    rows[(parse(Int, f[1]), String(f[2]))] = Dict(String(SHDR[i]) => String(f[i]) for i in 1:min(length(f), 15))
end
builds = Dict{Tuple{Int,String},Dict{String,String}}()
BHDR = split("N,arm,psd_scalars,psd_blocks,largest_block,tsupp_rows,cons_nnz,rg_rows,build_s,rss_gb,status,config_sha16", ",")
for l in readlines(joinpath(R, "replacement_build.csv"))[2:end]
    f = split(l, ","); length(f) >= 11 || continue
    builds[(parse(Int, f[1]), String(f[2]))] = Dict(String(BHDR[i]) => String(f[i]) for i in 1:min(length(f), 12))
end

E(N, a) = haskey(rows, (N, a)) && rows[(N, a)]["status"] == "OPTIMAL" ? parse(Float64, rows[(N, a)]["E"]) : NaN
res(N, a, k) = parse(Float64, rows[(N, a)][k])
ec(N, a, b) = res(N, a, "mu") + res(N, b, "mu") +
              0.75 * (res(N, a, "pfeas") + res(N, a, "dfeas") + res(N, b, "pfeas") + res(N, b, "dfeas"))
bnum(N, a, k) = haskey(builds, (N, a)) && builds[(N, a)][k] != "" ? parse(Float64, builds[(N, a)][k]) : NaN
snum(N, a, k) = haskey(rows, (N, a)) && rows[(N, a)][k] != "" ? parse(Float64, rows[(N, a)][k]) : NaN

open(joinpath(R, "replacement_summary.csv"), "w") do io
    println(io, "N,d_AB,d_resolved,eta_CG6,eta_CG10,eta_pool_given_CG,eta_transferred_given_CG,eta_residual_given_E,eta_total," *
        "R_psd_C6_over_A,R_psd_D_over_A,R_bigblk_C6_over_A,R_bigblk_D_over_A,R_wall_C6_over_A,R_wall_D_over_A,R_rss_C6_over_A,R_rss_D_over_A," *
        "trip_A,trip_B,trip_C6,trip_D,trip_E,ord_B_le_A,ord_B_C6_D,ord_C6_E_D")
    for N in (14, 20, 26)
        haskey(rows, (N, "B")) || continue
        LA, LB, LC, LD, LE_ = E(N, "A"), E(N, "B"), E(N, "C6"), E(N, "D"), E(N, "E")
        LC10 = E(N, "C10")
        ref = bethe[N]
        trip(a) = (v = E(N, a); isnan(v) ? "NA" : (v <= ref + 5e-7 ? "ok" : "VIOLATION"))
        d = LA - LB
        dres = !isnan(d) && d > ec(N, "A", "B") ? "resolved-positive" : "unresolved-or-NA"
        eta(x, y) = isnan(x) || isnan(y) || !(dres == "resolved-positive") ? NaN : (x - y) / d
        oBA = isnan(LA) || isnan(LB) ? "NA" : (LB <= LA + ec(N, "A", "B") ? "ok" : "IMPLEMENTATION_RED_3b")
        oBCD = any(isnan, (LB, LC, LD)) ? "NA" :
               (LB <= LC + ec(N, "B", "C6") && LC <= LD + ec(N, "C6", "D") ? "ok" : "ORDER-VIOLATION")
        oCED = isnan(LE_) ? "NA" :
               (LC <= LE_ + ec(N, "C6", "E") && LE_ <= LD + ec(N, "E", "D") ? "ok" : "ORDER-VIOLATION")
        rr(k, num, den) = (x = k(N, num, "psd_scalars"); y = k(N, den, "psd_scalars"); x / y)
        @printf(io, "%d,%.3e,%s,%s,%s,%s,%s,%s,%s,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%s,%s,%s,%s,%s,%s,%s,%s\n",
            N, d, dres,
            (x -> isnan(x) ? "NA" : @sprintf("%+.4f", x))(eta(LC, LB)),
            (x -> isnan(x) ? "NA" : @sprintf("%+.4f", x))(eta(LC10, LB)),
            (x -> isnan(x) ? "NA" : @sprintf("%+.4f", x))(eta(LD, LC)),
            (x -> isnan(x) ? "NA" : @sprintf("%+.4f", x))(eta(LE_, LC)),
            (x -> isnan(x) ? "NA" : @sprintf("%+.4f", x))(eta(LD, LE_)),
            (x -> isnan(x) ? "NA" : @sprintf("%+.4f", x))(eta(LD, LB)),
            bnum(N, "C6", "psd_scalars") / bnum(N, "A", "psd_scalars"),
            bnum(N, "D", "psd_scalars") / bnum(N, "A", "psd_scalars"),
            bnum(N, "C6", "largest_block") / bnum(N, "A", "largest_block"),
            bnum(N, "D", "largest_block") / bnum(N, "A", "largest_block"),
            snum(N, "C6", "wall_s") / snum(N, "A", "wall_s"),
            snum(N, "D", "wall_s") / snum(N, "A", "wall_s"),
            snum(N, "C6", "rss_gb") / snum(N, "A", "rss_gb"),
            snum(N, "D", "rss_gb") / snum(N, "A", "rss_gb"),
            trip("A"), trip("B"), trip("C6"), trip("D"), trip("E"), oBA, oBCD, oCED)
    end
end
println(read(joinpath(R, "replacement_summary.csv"), String))
# grid completeness assertion (mandatory 8 cells present as row or record)
miss = [(N, a) for N in (14, 20), a in ("A", "B", "C6", "D") if !haskey(rows, (N, a))]
isempty(miss) ? println("GRID COMPLETE (mandatory 8 accounted)") : println("MISSING: ", miss)
