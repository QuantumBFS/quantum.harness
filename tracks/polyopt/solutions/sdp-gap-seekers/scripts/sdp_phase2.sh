#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --job-name=sdp_phase2
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=64
#SBATCH --mem-per-cpu=5000M
#SBATCH --output=sdp_phase2.out
#SBATCH --error=sdp_phase2.err

# Phase-2 energy sweep: fill the E0(g) phase diagram + probe the rdm knob.
# Context: overnight job established d is SATURATED at small L (d=4=d=6=d=8) and
# L=10 is the memory frontier (L=12 d=4 OOM'd at 243 GB). So the remaining
# energy-side value is (a) a dense g-sweep through the J1-J2 critical region
# (g_c ~ 0.5) for the writeup E0(g) curve, (b) challenge-point d=8 convergence
# confirm, and (c) ONE rdm probe -- since d is saturated, rdm is the real
# limiting knob and we should learn whether higher rdm tightens the bound.
# All L=4 (cheap, ~30s each); mem bumped to 5000M/cpu for the rdm=16 probe.

export PATH="$HOME/julia-1.11.5/bin:$PATH"
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:$LD_LIBRARY_PATH"
export JULIA_NUM_THREADS=32

cd ~/quantum.harness
echo "Node: $(hostname), Start: $(date)"

julia --project=julia-env << 'JLEOF'
using QMBCertify, MosekTools, LinearAlgebra, Dates

@eval QMBCertify function resort(a::Vector{Vector{T}}, b::Vector{S}) where {T,S}
    p = sortperm(a); return a[p], b[p]
end

println("QMBCertify loaded. Version: ", pkgversion(QMBCertify))
flush(stdout)

function run_case(tag, L, d, g, rdm, ref)
    supp = g > 0 ? [[1; 4], [1; 7]] : [[1; 4]]
    coe  = g > 0 ? [1.5, 1.5 * g] : [1.5]
    refstr = isnan(ref) ? "none" : string(ref)
    println("=" ^ 70)
    println("$tag : L=$L d=$d g=$g rdm=$rdm  (ref=$refstr)")
    flush(stdout)
    open("sdp_phase2.results", "a") do io
        println(io, "START ", Dates.format(now(), "yyyy-mm-ddTHH:MM:SS"),
                " $tag L=$L d=$d g=$g rdm=$rdm ref=$refstr")
    end
    try
        t = @elapsed opt, _ = GSB(supp, coe, L, d;
                                  lattice="square", rdm=rdm, pso=0, extra=0, QUIET=true)
        println("  -> E0/N=", round(opt, digits=6), "  (ref=$refstr)  [",
                round(t, digits=1), "s]")
        flush(stdout)
        open("sdp_phase2.results", "a") do io
            println(io, "DONE  ", Dates.format(now(), "yyyy-mm-ddTHH:MM:SS"),
                    " $tag L=$L d=$d g=$g rdm=$rdm opt=$opt ref=$refstr t=",
                    round(t, digits=1))
        end
    catch e
        msg = sprint(showerror, e)
        println("  -> FAILED: ", msg)
        flush(stdout)
        open("sdp_phase2.results", "a") do io
            println(io, "FAIL  ", Dates.format(now(), "yyyy-mm-ddTHH:MM:SS"),
                    " $tag L=$L d=$d g=$g rdm=$rdm err=", msg)
        end
    end
end

# ---- 1. E0(g) phase-diagram sweep: fill gaps around the critical g~0.5 ----
println("\n##### E0(g) sweep (L=4, d=4, rdm=8) — fill critical region #####"); flush(stdout)
for g in [0.1, 0.2, 0.4, 0.45, 0.55, 0.6]
    run_case("L4-g$g-d4", 4, 4, g, 8, NaN)
end

# ---- 2. Challenge-point d=8 convergence confirm (g=0.5, 0.535) ----
println("\n##### Challenge-point d=8 (L=4, rdm=8) #####"); flush(stdout)
run_case("L4-g0.5-d8",   4, 8, 0.5,   8, -0.4976)
run_case("L4-g0.535-d8", 4, 8, 0.535, 8, NaN)

# ---- 3. rdm probe: does higher rdm tighten the d-saturated bound? ----
println("\n##### rdm probe (L=4, g=0, d=4) — is rdm the limiting knob? #####"); flush(stdout)
run_case("L4-g0.0-d4-rdm16", 4, 4, 0.0, 16, -0.7018)

println("\n=== ALL DONE ===  ", Dates.format(now(), "yyyy-mm-dd HH:MM:SS"))
flush(stdout)
JLEOF

echo "Finished: $(date)"
