#!/usr/bin/env julia
# Overnight reproduction harness for OVERNIGHT.md.
# The protocol file is authoritative; this script implements it and nothing more.
#
# Usage: julia --project=julia-env overnight_harness.jl <outdir> <step> <cellspec...>
#   cellspec = "label:N:key=val,key=val"   (overrides applied to CONFIG A)
#
# Does not modify QMBCertify. Solver status is parsed from the captured solver
# log because GSB returns only (objv, data) and qmb_data carries no JuMP model.

using QMBCertify
using Printf
using SHA
using Dates

const OUTDIR = ARGS[1]
const STEP   = ARGS[2]
const CELLS  = ARGS[3:end]

mkpath(OUTDIR)
mkpath(joinpath(OUTDIR, "cell_logs"))

# ---------------------------------------------------------------- budgets ----
# ENV-overridable (plan: 7200 s per 1D cell for the targets queue).
const MAX_WALL_S       = parse(Int,     get(ENV, "MAX_WALL_S", "600"))
const MAX_RSS_GB       = parse(Float64, get(ENV, "MAX_RSS_GB", "18"))
const MAX_PROC_SWAP_GB = parse(Float64, get(ENV, "MAX_PROC_SWAP_GB", "0.5"))
# Mosek thread cap (0 = auto). On shared HPC nodes auto-detect sees ALL
# physical cores, not the cgroup share — set explicitly in sbatch scripts.
const MOSEK_THREADS    = parse(Int,     get(ENV, "MOSEK_THREADS", "0"))

# ------------------------------------------------- CONFIG A (source of truth) --
# One object. It both constructs the GSB call and serialises into the row.
config_a(N) = (
    d = 4, extra = 4, rdm = 10, pso = 3, lso = true, lol = N,
    three_type = [1, 1], SU2_symmetry = false, lattice = "chain",
    Gram = false, correlation = false, J2 = 0,
    mosek_tol_pfeas = 1e-8, mosek_tol_dfeas = 1e-8, mosek_tol_relgap = 1e-8,
    supp = [[1, 4]], coe = [3 / 4],
)

# Reference of record: high-precision Bethe references (J2=0 rows) from
# bethe_ref.json in OUTDIR, if present. MG point J2=0.5 is exact (-0.375).
function load_bethe(outdir)
    p = joinpath(outdir, "bethe_ref.json")
    isfile(p) || return Dict{Int,Float64}()
    d = Dict{Int,Float64}()
    for m in eachmatch(r"\"(\d+)\":\s*(-?[0-9.eE+-]+)", read(p, String))
        d[parse(Int, m.captures[1])] = parse(Float64, m.captures[2])
    end
    return d
end
const BETHE = load_bethe(OUTDIR)

# Table 3 of arXiv:2604.01555 — N => (DMRG upper, SDP Old, SDP New)
const TABLE3 = Dict(
    10 => (-0.4515446, -0.4515446, -0.4515446), 14 => (-0.4473964, -0.4474032, -0.4473964),
    18 => (-0.4457083, -0.4457344, -0.4457085), 20 => (-0.4452193, -0.4452516, -0.4452196),
    22 => (-0.4448582, -0.4448981, -0.4448585), 26 => (-0.4443707, -0.4444334, -0.4443714),
    30 => (-0.4440654, -0.4441512, -0.4440668), 34 => (-0.4438616, -0.4439644, -0.4438632),
    38 => (-0.4437189, -0.4438331, -0.4437212), 40 => (-0.4436630, -0.4437820, -0.4436649),
    42 => (-0.4436150, -0.4437371, -0.4436176), 46 => (-0.4435370, -0.4436656, -0.4435397),
    50 => (-0.4434771, -0.4436101, -0.4434798), 60 => (-0.4433762, -0.4435169, -0.4433804),
    80 => (-0.4432758, -0.4435377, -0.4432808), 100 => (-0.4432295, -0.4435928, -0.4432378),
)

# ------------------------------------------------------------- provenance ----
filesha(p) = isfile(p) ? bytes2hex(sha256(read(p))) : "MISSING"
function gitcommit(dir)
    try
        return strip(read(`git -C $dir rev-parse HEAD`, String))
    catch
        return "MISSING"
    end
end
function cpumodel()
    for l in eachline("/proc/cpuinfo")
        startswith(l, "model name") && return strip(split(l, ':', limit = 2)[2])
    end
    return "unknown"
end
function mosekversion()
    # Read from the Manifest we already hash — no extra import, no guessing.
    try
        t = read("julia-env/Manifest.toml", String)
        out = String[]
        for name in ("Mosek", "MosekTools")
            m = match(Regex("\\[\\[deps\\.$name\\]\\](.*?)(?=\\n\\[\\[|\\z)", "s"), t)
            m === nothing && continue
            v = match(r"^version\s*=\s*\"([^\"]+)\""m, m.captures[1])
            v !== nothing && push!(out, "$name=$(v.captures[1])")
        end
        return isempty(out) ? "unknown" : join(out, ";")
    catch
        return "unknown"
    end
end

const PROV = (
    protocol_sha256      = filesha("tracks/polyopt/solutions/its-a-trap/OVERNIGHT.md"),
    harness_commit       = gitcommit("."),
    qmbcertify_commit    = gitcommit(".external/QMBCertify"),
    script_sha256        = filesha(@__FILE__),
    project_toml_sha256  = filesha("julia-env/Project.toml"),
    manifest_toml_sha256 = filesha("julia-env/Manifest.toml"),
    julia_version        = string(VERSION),
    mosek_version        = mosekversion(),
    hostname             = gethostname(),
    cpu_model            = cpumodel(),
)

# ------------------------------------------------------- process resources ----
function proc_kb(key)
    for l in eachline("/proc/self/status")
        startswith(l, key) && return parse(Float64, split(l)[2])
    end
    return 0.0
end
rss_gb()  = proc_kb("VmRSS:")   / 1024 / 1024
swap_gb() = proc_kb("VmSwap:")  / 1024 / 1024

# ------------------------------------------------------------ log parsing ----
# GSB prints "termination status: X" / "solution status: Y" ONLY when the solve
# is not MOI.OPTIMAL (bound_gsp.jl:594-597). Absence of those lines is therefore
# a sound inference of OPTIMAL, recorded with status_source so the row is
# self-describing rather than asserting an unmeasured value.
function parse_solverlog(path)
    txt = isfile(path) ? read(path, String) : ""
    term = "OPTIMAL"; prim = "FEASIBLE_POINT"; src = "inferred_absent_warning_line"
    m = match(r"termination status:\s*(\S+)", txt)
    if m !== nothing
        term = m.captures[1]; src = "printed_by_GSB"
        m2 = match(r"solution status:\s*(\S+)", txt)
        prim = m2 === nothing ? "UNKNOWN" : m2.captures[1]
    end
    # last interior-point iteration row: ITE PFEAS DFEAS GFEAS PRSTATUS POBJ DOBJ MU TIME
    pfeas = dfeas = mu = NaN
    for l in eachline(IOBuffer(txt))
        f = split(strip(l))
        length(f) >= 9 || continue
        tryparse(Int, f[1]) === nothing && continue
        p = tryparse(Float64, f[2]); d = tryparse(Float64, f[3]); u = tryparse(Float64, f[8])
        (p === nothing || d === nothing || u === nothing) && continue
        pfeas, dfeas, mu = p, d, u
    end
    solve_s = NaN
    ms = match(r"SDP solving time:\s*([0-9.eE+-]+)\s*seconds", txt)
    ms !== nothing && (solve_s = parse(Float64, ms.captures[1]))
    return (termination_status = term, primal_status = prim, status_source = src,
            primal_residual = pfeas, dual_residual = dfeas, duality_gap = mu,
            solve_s = solve_s)
end

# ------------------------------------------------------------------- CSV ----
const COLS = [
  "step","label","N","opt","E_ref","ref_source","gap_ref","rel_err","J2_model",
  "table3_dmrg","table3_new","table3_old","dev_vs_dmrg","dev_vs_new",
  "d","extra","r","rdm","pso","lso","lol","three_type","SU2_symmetry","lattice","Gram",
  "correlation","J2","supp","coe","mosek_tol_pfeas","mosek_tol_dfeas","mosek_tol_relgap",
  "termination_status","primal_status","status_source","primal_residual","dual_residual",
  "duality_gap","solve_s","wall_s","peak_rss_gb","peak_swap_gb","limit_hit","error",
  "protocol_sha256","harness_commit","qmbcertify_commit","script_sha256",
  "project_toml_sha256","manifest_toml_sha256","julia_version","mosek_version",
  "hostname","cpu_model","timestamp_utc",
]
const CSV = joinpath(OUTDIR, "results.csv")
csvesc(x) = (s = string(x); occursin(r"[,\"\n]", s) ? "\"" * replace(s, "\"" => "\"\"") * "\"" : s)
function flushrow(row)
    isfile(CSV) || open(CSV, "w") do io; println(io, join(COLS, ",")); end
    open(CSV, "a") do io
        println(io, join([csvesc(get(row, Symbol(c), "")) for c in COLS], ","))
    end
end
logline(s) = open(joinpath(OUTDIR, "LOG.md"), "a") do io
    println(io, "- `", Dates.format(now(UTC), "yyyy-mm-ddTHH:MM:SSZ"), "` ", s)
end

# ------------------------------------------------------------- run a cell ----
function runcell(step, label, N, overrides)
    cfg = merge(config_a(N), overrides)
    cell_log = joinpath(OUTDIR, "cell_logs", "$(step)_$(label)_N$(N).log")
    t3 = get(TABLE3, N, (NaN, NaN, NaN))

    peak_rss = Ref(rss_gb()); peak_swap = Ref(swap_gb()); breach = Ref("")
    optref = Ref{Any}(""); errref = Ref("")
    t0 = time()

    # GSB runs on a worker thread so the budget monitor on the main thread can
    # actually preempt it. Requires julia -t >=2; with -t 1 the monitor cannot
    # run during a compute-bound GSB and budgets are recorded, not enforced.
    task = Threads.@spawn begin
        try
            open(cell_log, "w") do io
                redirect_stdout(io) do
                    o, _ = GSB(cfg.supp, cfg.coe, N, cfg.d;
                               lattice = cfg.lattice, extra = cfg.extra, rdm = cfg.rdm,
                               pso = cfg.pso, lso = cfg.lso, lol = cfg.lol,
                               three_type = cfg.three_type, SU2_symmetry = cfg.SU2_symmetry,
                               Gram = cfg.Gram, correlation = cfg.correlation, J2 = cfg.J2,
                               QUIET = false,
                               mosek_setting = mosek_para(cfg.mosek_tol_pfeas,
                                                          cfg.mosek_tol_dfeas,
                                                          cfg.mosek_tol_relgap, MOSEK_THREADS))
                    optref[] = o
                end
            end
        catch e
            errref[] = first(sprint(showerror, e), 300)
        end
    end

    while !istaskdone(task)
        r = rss_gb(); s = swap_gb()
        r > peak_rss[]  && (peak_rss[]  = r)
        s > peak_swap[] && (peak_swap[] = s)
        if r > MAX_RSS_GB;                 breach[] = "MAX_RSS_GB";       break; end
        if s > MAX_PROC_SWAP_GB;           breach[] = "MAX_PROC_SWAP_GB"; break; end
        if (time() - t0) > MAX_WALL_S;     breach[] = "MAX_WALL_S";       break; end
        sleep(0.5)
    end
    opt = optref[]; err = errref[]
    wall = time() - t0

    p = parse_solverlog(cell_log)
    # Reference of record + signed gap (plan correction 7).
    # gap_ref = E_ref/site − opt/site: positive = our bound sits below the
    # reference, as a lower bound must vs an upper/near-exact reference.
    J2m = Float64(get(overrides, :J2_model, 0.0))
    E_ref = ""; ref_source = ""
    if J2m == 0.0 && haskey(BETHE, N)
        E_ref = BETHE[N]; ref_source = "bethe_high_precision"
    elseif J2m == 0.5
        E_ref = -0.375; ref_source = "MG_exact"
    end
    # GSB's objv is already per-site (cf. Table 3 units; overnight rows).
    gap_ref = (opt isa Number && E_ref isa Number) ? E_ref - opt : ""
    rel_err = (gap_ref isa Number && E_ref isa Number) ? abs(gap_ref / E_ref) : ""
    row = merge(PROV, (
        step = step, label = label, N = N, opt = opt,
        E_ref = E_ref, ref_source = ref_source, gap_ref = gap_ref,
        rel_err = rel_err, J2_model = J2m,
        table3_dmrg = t3[1], table3_old = t3[2], table3_new = t3[3],
        dev_vs_dmrg = opt isa Number ? opt - t3[1] : "",
        dev_vs_new  = opt isa Number ? opt - t3[3] : "",
        d = cfg.d, extra = cfg.extra, r = cfg.extra + 1, rdm = cfg.rdm, pso = cfg.pso,
        lso = cfg.lso, lol = cfg.lol, three_type = string(cfg.three_type),
        SU2_symmetry = cfg.SU2_symmetry, lattice = cfg.lattice, Gram = cfg.Gram,
        correlation = cfg.correlation, J2 = cfg.J2,
        supp = string(cfg.supp), coe = string(cfg.coe),
        mosek_tol_pfeas = cfg.mosek_tol_pfeas, mosek_tol_dfeas = cfg.mosek_tol_dfeas,
        mosek_tol_relgap = cfg.mosek_tol_relgap,
        termination_status = p.termination_status, primal_status = p.primal_status,
        status_source = p.status_source, primal_residual = p.primal_residual,
        dual_residual = p.dual_residual, duality_gap = p.duality_gap,
        solve_s = p.solve_s, wall_s = wall,
        peak_rss_gb = peak_rss[], peak_swap_gb = peak_swap[],
        limit_hit = breach[], error = err,
        timestamp_utc = Dates.format(now(UTC), "yyyy-mm-ddTHH:MM:SSZ"),
    ))
    flushrow(row)

    @printf("[%s/%s N=%d] opt=%s solve=%.1fs wall=%.1fs rss=%.2fGB %s%s\n",
            step, label, N, string(opt), p.solve_s, wall, peak_rss[],
            p.termination_status, isempty(breach[]) ? "" : " LIMIT=" * breach[])
    flush(stdout)
    return (row = row, breach = breach[], err = err)
end

# ------------------------------------------------------------------ main ----
function parsecell(spec)
    label, nstr, rest = let parts = split(spec, ':')
        (parts[1], parts[2], length(parts) >= 3 ? parts[3] : "")
    end
    ov = Dict{Symbol,Any}()
    for kv in split(rest, ',', keepempty = false)
        k, v = split(kv, '=')
        ov[Symbol(k)] = v == "true" ? true : v == "false" ? false :
                        something(tryparse(Int, v), tryparse(Float64, v), v)
    end
    # model=j1j2 switches the Hamiltonian encoding (J2 value from the J2 key).
    # GSB's own J2 kwarg is correlation-path-only (bound_gsp.jl:557) and stays 0.
    if get(ov, :model, "") == "j1j2"
        J2 = Float64(get(ov, :J2, 0.0))
        ov[:supp] = [[1, 4], [1, 7]]
        ov[:coe]  = [3 / 4, 3 / 4 * J2]
        ov[:J2]   = 0          # keep the kwarg out of the energy objective
        ov[:J2_model] = J2     # serialized so the row records the physics
        delete!(ov, :model)
    end
    return (label, parse(Int, nstr), NamedTuple(ov))
end

logline("**$STEP** started; cells = `$(join(CELLS, " "))`")
# warm-up runs ONCE for the sweep, not once per restarted driver. The protocol
# asks for a warm-up "before any timing is recorded"; because a killed cell
# forces a driver restart, repeating it per cell would cost ~34 min each.
if startswith(STEP, "step4") &&
   !any(startswith(l, STEP * ",") for l in (isfile(CSV) ? readlines(CSV) : String[]))
    logline("warm-up throwaway N=10 solve (not recorded; once per sweep)")
    open(joinpath(OUTDIR, "cell_logs", "warmup_$(STEP).log"), "w") do io
        redirect_stdout(io) do
            try
                # Warm-up must carry the same overrides as the sweep, or it pays a
                # config cost the sweep never pays (rdm=10 construction is ~2050 s).
                c = merge(config_a(10), isempty(CELLS) ? NamedTuple() : parsecell(CELLS[1])[3])
                GSB(c.supp, c.coe, 10, c.d; lattice = c.lattice, extra = c.extra,
                    rdm = c.rdm, pso = c.pso, lso = c.lso, lol = c.lol,
                    three_type = c.three_type, SU2_symmetry = c.SU2_symmetry,
                    Gram = c.Gram, correlation = c.correlation, J2 = c.J2, QUIET = true,
                    mosek_setting = mosek_para(c.mosek_tol_pfeas, c.mosek_tol_dfeas,
                                               c.mosek_tol_relgap, MOSEK_THREADS))
            catch
            end
        end
    end
    println("warm-up done"); flush(stdout)
end

for spec in CELLS
    label, N, ov = parsecell(spec)
    res = runcell(STEP, label, N, ov)
    if !isempty(res.err)
        logline("**FAILURE** $STEP/$label N=$N — `$(res.err)`; retrying once")
        res = runcell(STEP, label * "_retry", N, ov)
        isempty(res.err) || logline("**FAILURE (retry)** $STEP/$label N=$N — giving up on this cell")
    end
    if res.breach in ("MAX_RSS_GB", "MAX_PROC_SWAP_GB")
        logline("**RESOURCE FRONTIER** at N=$N — hit $(res.breach); stopping ascending sweep")
        println("STOP: resource frontier at N=$N ($(res.breach))")
        exit(9)
    elseif res.breach == "MAX_WALL_S"
        logline("N=$N killed at MAX_WALL_S (600 s); row recorded with no `opt`; continuing to next N")
        println("KILLED: N=$N hit MAX_WALL_S")
        exit(124)   # cell killed; driver cannot survive an aborted GSB, bash restarts at next N
    end
end
logline("**$STEP** finished")
println("STEP $STEP COMPLETE")
