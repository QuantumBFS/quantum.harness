#!/usr/bin/env julia
# check_row.jl <results.csv> <mode>  — compute nodes have no python3; this is
# the row-verdict tool for the 2D chain (quoted-CSV aware, stdlib only).
#   mode=canary   : row has opt, OPTIMAL, no limit_hit, and opt is a VALID
#                   lower bound of the 4x4 torus value E0/N = -0.7017802
#   mode=fitcheck : row has opt, no limit_hit, wall<=21600 s, rss<=80 GB
# Exit code is the verdict (0 pass / 1 fail).
function splitcsv(line::String)
    out = String[]; cur = IOBuffer(); q = false
    for c in line
        if c == '"'; q = !q
        elseif c == ',' && !q; push!(out, String(take!(cur)))
        else; write(cur, c); end
    end
    push!(out, String(take!(cur)))
    return out
end
lines = readlines(ARGS[1])
hdr = splitcsv(lines[1]); row = splitcsv(lines[end])
col(n) = row[findfirst(==(n), hdr)]
opt = col("opt"); lim = col("limit_hit"); ts = col("termination_status")
wall = tryparse(Float64, col("wall_s")); rss = tryparse(Float64, col("peak_rss_gb"))
println("row: opt=$opt status=$ts limit=$lim wall=$wall rss=$rss")
ok = if ARGS[2] == "canary"
    E0 = -0.7017802
    v = tryparse(Float64, opt)
    good = v !== nothing && isempty(lim) && ts == "OPTIMAL" && v <= E0 + 1e-6
    v !== nothing && println("canary slack vs 4x4 torus E0/N: $(E0 - v)")
    good
elseif ARGS[2] == "fitcheck"
    !isempty(opt) && isempty(lim) && wall !== nothing && wall <= 21600 &&
        rss !== nothing && rss <= 80
else
    error("unknown mode")
end
println(uppercase(ARGS[2]), " ", ok ? "PASS" : "FAIL")
exit(ok ? 0 : 1)
