#!/usr/bin/env julia
# run_n200.jl — N=200 deployment paths.
#   PRODUCTION (Amendment 4/4A/4B/4C):
#     julia run_n200.jl --mode a200 --manifest A200_CONFIG.json
#   a200: ONE adaptive arm F_core(rdm=false) ∩ C_RG ∩ C_S. EVERY semantic
#   parameter comes from the manifest (4C §2: only source of truth; the
#   resolved builder call is logged, never an independent config source).
#   Missing/mismatched manifest field => RED stop (exit 2).
#   Durable output (4A.5): stage file + heartbeat thread during build AND
#   solve; final JSON/CSV written atomically (tmp+rename).
#   LEGACY (historical, non-production): probe | pair (positional arg).
using Printf, SHA, Dates
include(joinpath(@__DIR__, "src", "rg_builder.jl"))
include(joinpath(@__DIR__, "src", "functional_rg.jl"))
include(joinpath(@__DIR__, "src", "semhash.jl"))

function argval(flag)
    i = findfirst(==(flag), ARGS)
    i === nothing || i == length(ARGS) ? nothing : ARGS[i+1]
end
const MODE = something(argval("--mode"),
    (length(ARGS) >= 1 && !startswith(ARGS[1], "--")) ? ARGS[1] : "probe")
const RESULTS = joinpath(@__DIR__, "results")
const WATCH_S = parse(Float64, get(ENV, "WATCH_S", "0"))   # 0 = off

if MODE == "a200"
    red(msg) = (println("A200 RED: ", msg); flush(stdout); exit(2))
    mpath = argval("--manifest")
    mpath === nothing && red("missing --manifest flag (4C §2)")
    isfile(mpath) || red("manifest not found: $mpath")
    raw = read(mpath, String)
    manifest_sha = bytes2hex(sha256(raw))
    jstr(k) = (m = match(Regex("\"$k\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\""), raw);
               m === nothing && red("missing field: $k"); String(m.captures[1]))
    jlit(k) = (m = match(Regex("\"$k\"\\s*:\\s*([0-9.eE+-]+|true|false)"), raw);
               m === nothing && red("missing field: $k"); String(m.captures[1]))
    jarr(k) = (m = match(Regex("\"$k\"\\s*:\\s*(\\[[^\\]]*\\])"), raw);
               m === nothing && red("missing field: $k"); String(m.captures[1]))
    jobj(k) = (m = match(Regex("\"$k\"\\s*:\\s*(\\{[^}]*\\})"), raw);
               m === nothing && red("missing field: $k"); String(m.captures[1]))
    # ---- strict manifest resolution (no semantic defaults) ----
    jstr("mode") == "a200"                 || red("mode != a200")
    Nm    = parse(Int, jlit("N"))
    dm    = parse(Int, jlit("d"));          dm == 4       || red("d != 4 unsupported")
    jlit("rdm") == "false"                 || red("rdm must be false on the A200 chassis")
    psom  = parse(Int, jlit("pso"));        psom == 0     || red("pso != 0")
    jlit("lso") == "false"                 || red("lso must be false (4A.1)")
    rm_   = parse(Int, jlit("r"));          rm_ == r_of(Nm) || red("r=$(rm_) != r_of(N)=$(r_of(Nm))")
    extam = parse(Int, jlit("extra"));      extam == rm_ - 1 || red("extra != r-1")
    occursin(r"\"supp\"\s*:\s*\[\s*\[\s*1\s*,\s*4\s*\]\s*\]", raw) || red("supp missing/mismatch vs builder convention")
    occursin(r"\"coe\"\s*:\s*\[\s*0\.75\s*\]", raw)                || red("coe missing/mismatch vs builder convention")
    conv  = jstr("coefficient_convention")
    hid   = jstr("hamiltonian_id"); qid = jstr("quotient_id")
    stol  = jobj("solver_tol")
    rgid  = jstr("rg_map_id"); rgh16 = jstr("rg_map_hash16")
    nrgm  = parse(Int, jlit("n_rg"))
    jstr("vspace") == "auto"               || red("vspace must be auto")
    bidm  = jarr("bundle_ids")
    Sids  = Vector{String}(sort([String(m.captures[1]) for m in eachmatch(r"\"(B_[a-z_]+)\"", bidm)]))
    isempty(Sids) && red("bundle_ids empty")
    all(b -> b in POOL, Sids)              || red("bundle_ids outside immutable pool")
    poolh = jstr("pool_hash")
    selst = jstr("selection_status")
    selst in ("FRESH_REPLACEMENT_SELECTION", "A200_FIXED_BUNDLE_PILOT") ||
        red("selection_status invalid: $selst")
    jstr("selection_note")   # presence required
    # cross-checks against recomputable/frozen quantities
    As = load_D4()
    d4h = d4_hash()
    startswith(d4h, rgh16) || red("rg_map_hash16 $rgh16 != recomputed $(d4h[1:16])")
    fsp = joinpath(RESULTS, "FROZEN_SELECTION.json")
    if isfile(fsp)
        fpm = match(r"\"pool_hash\"\s*:\s*\"([0-9a-f]+)\"", read(fsp, String))
        fpm !== nothing && fpm.captures[1] != poolh && red("pool_hash != frozen record")
    end
    wt = normpath(joinpath(@__DIR__, "..", "..", "..", "..", ".."))
    commit = try strip(read(`git -C $wt rev-parse HEAD`, String)) catch; "NA(remote)" end
    # ---- durable state: stage file + heartbeat thread (build AND solve) ----
    stage = Ref("manifest-ok")
    stagef = joinpath(RESULTS, "a200_stage.txt")
    hbf    = joinpath(RESULTS, "a200_heartbeat.txt")
    mark(s) = (stage[] = s; open(io -> println(io,
        "$(now()) stage=$s rss=$(round(Sys.maxrss()/2^30, digits=2))G commit=$commit manifest=$manifest_sha"),
        stagef, "a"))
    hb_stop = Ref(false)
    hb = Threads.@spawn begin
        n = 0
        while !hb_stop[]
            n += 1
            try open(io -> println(io,
                "$(now()) beat=$n stage=$(stage[]) rss_gb=$(round(Sys.maxrss()/2^30, digits=2))"),
                hbf, "a") catch end
            for _ in 1:60; hb_stop[] && break; sleep(1.0) end
        end
    end
    Threads.nthreads() >= 2 || println("WARN: nthreads=1, heartbeat may stall during MOSEK solve (launch with -t 2)")
    if WATCH_S > 0
        Threads.@spawn begin
            sleep(WATCH_S)
            mark("WATCHDOG-EXIT")
            println("WATCHDOG EXIT (clean, pre-slurm-wall)"); flush(stdout)
            exit(0)
        end
    end
    mark("start")
    rg = rg_spec(Nm, nrgm, As)
    mark("rg-spec-built")
    resolved = "build_rg_selection_model($Nm; S=$(Sids), rg=rg_spec($Nm,$nrgm,D4), " *
               "vspace=:auto, rdm=false, pso=$psom, lso=false)  [derived from manifest $manifest_sha]"
    println("RESOLVED: ", resolved); flush(stdout)
    mark("build+solve")
    logkeep = joinpath(RESULTS, "a200_mosek.log")
    t0 = time()
    r = build_rg_selection_model(Nm; S = Sids, rg = rg, vspace = :auto,
                                 rdm = false, pso = psom, lso = false,
                                 keeplog = logkeep)
    wall = time() - t0
    mark("solved")
    hb_stop[] = true
    log = isfile(logkeep) ? read(logkeep, String) : ""
    logsha = isempty(log) ? "NA" : bytes2hex(sha256(log))
    mt = match(r"Optimizer terminated\. Time:\s*([0-9.]+)", log)
    solve_s = mt === nothing ? NaN : parse(Float64, mt.captures[1])
    ms = match(r"Solution status\s*:\s*(\w+)", log)
    solstat = ms === nothing ? "UNPARSED" : ms.captures[1]
    # ---- semantic hash of the active extension (R4b/R4c cross-check) ----
    semhash = ext_semhash(r.ext; include_words = true)
    # ---- atomic final outputs ----
    fin = joinpath(RESULTS, "a200_final.json")
    body = """
{"mode": "a200", "N": $Nm, "commit": "$commit", "manifest_sha256": "$manifest_sha",
 "selection_status": "$selst", "bundle_ids": "$(join(Sids, "+"))",
 "resolved_call": "$(replace(resolved, "\"" => "'"))",
 "rg_map_hash": "$d4h", "pool_hash": "$poolh", "semantic_hash": "$semhash",
 "hamiltonian_id": "$hid", "quotient_id": "$qid",
 "coefficient_convention": "$(replace(conv, "\"" => "'"))",
 "solver_tol": $stol,
 "E_per_site_lower_bound": $(r.E),
 "pfeas": $(r.resid.pfeas), "dfeas": $(r.resid.dfeas), "mu": $(r.resid.mu),
 "solution_status": "$solstat",
 "sig_nblk": $(r.sig.nblk), "sig_mwords": $(r.sig.mwords),
 "sig_matvars": $(r.sig.matvars), "sig_scalarized": $(r.sig.scalarized),
 "sig_nrows": $(r.sig.nrows),
 "newwords": $(get(r.counters, "seam_newwords", -1)),
 "gamma2_dim": $(get(r.counters, "gamma2_dim", -1)),
 "rg_rows": $(get(r.counters, "rg_rows", -1)),
 "total_wall_s": $(round(wall, digits = 1)), "solver_wall_s": $solve_s,
 "peak_rss_gb": $(round(Sys.maxrss() / 2^30, digits = 2)),
 "mosek_log_sha256": "$logsha"}
"""
    open(io -> print(io, body), fin * ".tmp", "w"); mv(fin * ".tmp", fin; force = true)
    csvp = joinpath(RESULTS, "a200_result.csv")
    row = "a200,$Nm,$(r.E),$(r.resid.pfeas),$(r.resid.dfeas),$(r.resid.mu)," *
          "$(round(wall,digits=1)),$solve_s,$(round(Sys.maxrss()/2^30,digits=2))," *
          "$commit,$manifest_sha,$semhash,$selst\n"
    open(io -> print(io, "arm,N,E,pfeas,dfeas,mu,total_wall_s,solver_wall_s,rss_gb,commit,manifest_sha,semantic_hash,selection_status\n" * row),
         csvp * ".tmp", "w"); mv(csvp * ".tmp", csvp; force = true)
    mark("final-written")
    @printf("A200 DONE E=%.12f wall=%.0fs solve=%.0fs rss=%.1fG status=%s\n",
            r.E, wall, solve_s, Sys.maxrss() / 2^30, solstat)
    exit(0)
end

# ======================= LEGACY MODES (historical) =========================
const N = 200
const NRG = 6

fs = read(joinpath(RESULTS, "FROZEN_SELECTION.json"), String)
const SSTAR = Vector{String}(sort(unique([String(m.captures[1]) for m in eachmatch(r"\"(B_[a-z_]+)\"", fs)])))
const SEL_SHA = bytes2hex(sha256(read(joinpath(RESULTS, "FROZEN_SELECTION.json"))))
wt = normpath(joinpath(@__DIR__, "..", "..", "..", "..", ".."))
commit = try strip(read(`git -C $wt rev-parse HEAD`, String)) catch; "NA(remote)" end

stage = Ref("init")
statefile = joinpath(RESULTS, "n200_$(MODE)_state.txt")
dump_state(tag) = open(statefile, "a") do io
    println(io, "$(now()) [$tag] stage=$(stage[]) rss=$(round(Sys.maxrss()/2^30, digits=1))G commit=$commit sel=$SEL_SHA S*=$(join(SSTAR,'+'))")
end
if WATCH_S > 0
    @async begin
        sleep(WATCH_S)
        dump_state("WATCHDOG")
        println("WATCHDOG EXIT (clean, pre-slurm-wall)"); flush(stdout)
        exit(0)
    end
end

dump_state("start:$MODE")
As = load_D4()
rg = rg_spec(N, NRG, As)
stage[] = "spec-built"
dump_state("spec")

if MODE == "probe"
    ENV["RG_PROBE_MAXTIME"] = get(ENV, "RG_PROBE_MAXTIME", "60")
    t0 = time()
    r = try
        build_rg_selection_model(N; S = SSTAR, rg = rg, vspace = :auto)
    catch e
        @info "probe: solver stage aborted as designed" typeof(e)
        nothing
    end
    wall = time() - t0
    stage[] = "probe-done"
    open(joinpath(RESULTS, "n200_probe.json"), "w") do io
        c = r === nothing ? Dict{String,Int}() : r.counters
        sig = r === nothing ? "capture-only" : string(r.sig)
        print(io, "{\"commit\": \"$commit\", \"selection_sha\": \"$SEL_SHA\", ",
              "\"S_star\": \"", join(SSTAR, "+"), "\", ",
              "\"newwords\": ", get(c, "seam_newwords", -1), ", ",
              "\"gamma2_dim\": ", get(c, "gamma2_dim", -1), ", ",
              "\"link_rows\": ", get(c, "rg_rows", -1), ", ",
              "\"sig\": \"", sig, "\", ",
              "\"build_plus_capped_solve_wall_s\": ", round(wall, digits = 1), ", ",
              "\"peak_rss_gb\": ", round(Sys.maxrss() / 2^30, digits = 2), "}")
    end
    println("PROBE DONE wall=$(round(wall, digits=1))s rss=$(round(Sys.maxrss()/2^30, digits=2))G ",
            "newwords=", r === nothing ? "?" : get(r.counters, "seam_newwords", -1))
elseif MODE == "pair"
    for (arm, kw) in (("base", (;)), ("joint", (S = SSTAR, rg = rg)))
        stage[] = "arm:$arm"
        dump_state("arm-start")
        t0 = time()
        r = build_rg_selection_model(N; vspace = :auto, kw...)
        w = time() - t0
        open(joinpath(RESULTS, "n200_pair.csv"), "a") do io
            println(io, "$arm,$(r.E),$(r.resid.pfeas),$(r.resid.dfeas),$(r.resid.mu),$(round(w,digits=1)),$(round(Sys.maxrss()/2^30,digits=2)),$commit,$SEL_SHA")
        end
        @printf("%s ARM DONE E=%.12f wall=%.0fs rss=%.1fG\n", arm, r.E, w, Sys.maxrss() / 2^30)
        flush(stdout)
    end
    stage[] = "pair-done"
    dump_state("done")
end
