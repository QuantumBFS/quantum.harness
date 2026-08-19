#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --job-name=sdp_overnight
#SBATCH --time=10:00:00
#SBATCH --cpus-per-task=64
#SBATCH --mem-per-cpu=3800M
#SBATCH --output=sdp_overnight.out
#SBATCH --error=sdp_overnight.err

# Overnight energy-cert sweep. Cranks the proven GSB call along three axes:
#   - higher d (relaxation order): tightens certified lower bounds
#   - larger L (system size):      pushes the frontier
#   - g in {0, 0.3, 0.5, 0.535, 0.7}: adds the challenge point g=0.535
# Cases are ordered cheap->valuable->expensive so a late-case SLURM kill
# (10h wall) still banks everything before. Each case is independent
# (try/catch) and appends to sdp_overnight.results after completion, so a
# kill loses at most one cell. Gap-SDP (challenge #88 target) is NOT here:
# per square-j1j2-gap-sdp-spec.md §12 it needs implementation + validation
# gates first, so it is not overnight-safe.

export PATH="$HOME/julia-1.11.5/bin:$PATH"
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:$LD_LIBRARY_PATH"
export JULIA_NUM_THREADS=32

cd ~/quantum.harness
echo "Node: $(hostname), Start: $(date)"

# NO Pkg operations. Manifest is pre-resolved. Just load and run.
julia --project=julia-env << 'JLEOF'
using QMBCertify, MosekTools, LinearAlgebra, Dates

@eval QMBCertify function resort(a::Vector{Vector{T}}, b::Vector{S}) where {T,S}
    p = sortperm(a); return a[p], b[p]
end

println("QMBCertify loaded. Version: ", pkgversion(QMBCertify))
println("Start sweep: ", Dates.format(now(), "yyyy-mm-dd HH:MM:SS"))
flush(stdout)

# supp/coe convention mirrors sdp_final.sh (validated: L=4 g=0 -> -0.7025 vs ref -0.7018).
#   Heisenberg bond -> [[1;4]], coef 3/2 ;  J2 diagonal -> [[1;7]], coef 3/2*g.
function run_case(tag, L, d, g, rdm, ref)
    supp = g > 0 ? [[1; 4], [1; 7]] : [[1; 4]]
    coe  = g > 0 ? [1.5, 1.5 * g] : [1.5]   # Float64, not Rational: GSB dispatches on coe's eltype
    refstr = isnan(ref) ? "none" : string(ref)
    println("=" ^ 70)
    println("$tag : L=$L d=$d g=$g rdm=$rdm  (ref=$refstr)")
    flush(stdout)
    open("sdp_overnight.results", "a") do io
        println(io, "START ", Dates.format(now(), "yyyy-mm-ddTHH:MM:SS"),
                " $tag L=$L d=$d g=$g rdm=$rdm ref=$refstr")
    end
    try
        t = @elapsed opt, _ = GSB(supp, coe, L, d;
                                  lattice="square", rdm=rdm, pso=0, extra=0, QUIET=true)
        println("  -> E0/N=", round(opt, digits=6), "  (ref=$refstr)  [",
                round(t, digits=1), "s]")
        flush(stdout)
        open("sdp_overnight.results", "a") do io
            println(io, "DONE  ", Dates.format(now(), "yyyy-mm-ddTHH:MM:SS"),
                    " $tag L=$L d=$d g=$g rdm=$rdm opt=$opt ref=$refstr t=",
                    round(t, digits=1))
        end
    catch e
        msg = sprint(showerror, e)
        println("  -> FAILED: ", msg)
        flush(stdout)
        open("sdp_overnight.results", "a") do io
            println(io, "FAIL  ", Dates.format(now(), "yyyy-mm-ddTHH:MM:SS"),
                    " $tag L=$L d=$d g=$g rdm=$rdm err=", msg)
        end
    end
end

# NOTE: the first submission banked L=4 J1-J2 d=6 (g=0.3,0.5,0.535,0.7) and
# found d=6 == d=4 to 6 digits -> the bound is d-converged at L=4 (rdm=8 is
# doing the work). So d-tightening J1-J2 is unproductive; this resubmission
# focuses on (a) Heisenberg L-frontier for the thermodynamic trend and
# (b) d-convergence probes to confirm the same holds at g=0, plus challenge-
# point d=8. rdm convention mirrors sdp_final.sh: rdm=8 for L<=6, rdm=0 for L>=8.

rdm_of(L) = L <= 6 ? 8 : 0

# ---- Tier 1: L=4 Heisenberg d-convergence probe (cheap) ----
println("\n##### TIER 1: L=4 Heisenberg d-convergence (d=6,8) #####"); flush(stdout)
run_case("L4-g0.0-d6",  4, 6, 0.0, rdm_of(4), -0.7018)
run_case("L4-g0.0-d8",  4, 8, 0.0, rdm_of(4), -0.7018)

# ---- Tier 2: Heisenberg L=6,8 d=6 (tighten + paper ref) ----
println("\n##### TIER 2: Heisenberg L=6,8 at d=6 #####"); flush(stdout)
run_case("L6-g0.0-d6",  6, 6, 0.0, rdm_of(6), -0.678872)
run_case("L8-g0.0-d6",  8, 6, 0.0, rdm_of(8), -0.676370)

# ---- Tier 3: L frontier at d=4 (thermodynamic trend) ----
println("\n##### TIER 3: Heisenberg L=10,12,14 at d=4 (frontier) #####"); flush(stdout)
run_case("L10-g0.0-d4", 10, 4, 0.0, rdm_of(10), NaN)
run_case("L12-g0.0-d4", 12, 4, 0.0, rdm_of(12), NaN)
run_case("L14-g0.0-d4", 14, 4, 0.0, rdm_of(14), NaN)

# ---- Tier 4: challenge-point d=8 convergence (g=0.5, 0.535) ----
println("\n##### TIER 4: challenge-point d=8 (g=0.5, 0.535) #####"); flush(stdout)
run_case("L4-g0.5-d8",   4, 8, 0.5,   rdm_of(4), -0.4976)
run_case("L4-g0.535-d8", 4, 8, 0.535, rdm_of(4), NaN)

# ---- Tier 5: expensive frontier d=6 (run only if earlier tiers leave time) ----
println("\n##### TIER 5: Heisenberg L=10,12 at d=6 (expensive) #####"); flush(stdout)
run_case("L10-g0.0-d6", 10, 6, 0.0, rdm_of(10), NaN)
run_case("L12-g0.0-d6", 12, 6, 0.0, rdm_of(12), NaN)

println("\n=== ALL DONE ===  ", Dates.format(now(), "yyyy-mm-dd HH:MM:SS"))
flush(stdout)
JLEOF

echo "Finished: $(date)"
