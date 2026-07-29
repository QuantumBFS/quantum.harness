#!/usr/bin/env julia
# run_n200.jl <probe|pair> — the N=200 deployment path on V_{S*}(200).
# probe: construction/resource numbers ONLY (solver capped via
#        RG_PROBE_MAXTIME; E discarded; no result values reported).
# pair : exactly ONE matched base/joint pair, same space/commit/settings/
#        allocation. Watchdog dumps state at WATCH_S then exits cleanly.
using Printf, SHA, Dates
include(joinpath(@__DIR__, "src", "rg_builder.jl"))
include(joinpath(@__DIR__, "src", "functional_rg.jl"))

const MODE = length(ARGS) >= 1 ? ARGS[1] : "probe"
const N = 200
const NRG = 6
const RESULTS = joinpath(@__DIR__, "results")
const WATCH_S = parse(Float64, get(ENV, "WATCH_S", "0"))   # 0 = off

fs = read(joinpath(RESULTS, "FROZEN_SELECTION.json"), String)
const SSTAR = Vector{String}(sort(unique([String(m.captures[1]) for m in eachmatch(r"\"(B_[a-z_]+)\"", fs)])))
const SEL_SHA = bytes2hex(sha256(read(joinpath(RESULTS, "FROZEN_SELECTION.json"))))
wt = normpath(joinpath(@__DIR__, "..", "..", "..", "..", ".."))
commit = try strip(read(`git -C $wt rev-parse HEAD`, String)) catch; "NA(remote)" end

rss_gb() = try parse(Float64, split(read("/proc/self/status", String)[findfirst("VmHWM", read("/proc/self/status", String))[1]:end])[2]) / 1e6 catch; Sys.maxrss() / 2^30 end
stage = Ref("init")
statefile = joinpath(RESULTS, "n200_$(MODE)_state.txt")
dump_state(tag) = open(statefile, "a") do io
    println(io, "$(now()) [$tag] stage=$(stage[]) rss=$(round(Sys.maxrss()/2^30, digits=1))G commit=$commit sel=$SEL_SHA S*=$(join(SSTAR,'+'))")
end
if WATCH_S > 0
    @async begin
        sleep(WATCH_S)
        dump_state("WATCHDOG")
        for f in readdir(tempdir(); join = true)   # attach last mosek log tail
            occursin("jl_", f) || continue
        end
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
