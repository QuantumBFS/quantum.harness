#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --job-name=gap_kagome
#SBATCH --time=03:00:00
#SBATCH --cpus-per-task=32
#SBATCH --mem-per-cpu=3800M
#SBATCH --output=gap_kagome.out
#SBATCH --error=gap_kagome.err

# Gap-SDP for the FRUSTRATED kagome Heisenberg model (challenge #88 target).
# SpectralGap.jl's certify_Heisenberg_kagome_gap is a turnkey certifier; this
# script gamma-scans to locate the feasibility transition (= certified upper
# bound on the bulk gap) for N=13 (d=2, d=3) and N=27 (d=2), matching the
# reference values in example.jl (~1.31 / ~1.28 / ~1.24). Kagome is a genuinely
# frustrated spin-1/2 model, so this is the headline #88 gap result.
# Pipeline already validated on TFIM (Delta <= 0.26, matches ref 0.258).

export PATH="$HOME/julia-1.11.5/bin:$PATH"
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:$LD_LIBRARY_PATH"
export JULIA_NUM_THREADS=16

cd ~/quantum.harness
echo "Node: $(hostname), Start: $(date)"

julia --project=julia-env << 'JLEOF'
using SpectralGap, MosekTools, Dates

println("SpectralGap kagome Heisenberg gap certification")
println("start: ", Dates.format(now(), "HH:MM:SS"))
flush(stdout)

# Heisenberg on kagome: H = sum over triangles of S_i.S_j for each bond pair.
# Encoding: site i -> 3i-2=X_i, 3i-1=Y_i, 3i=Z_i. S_i.S_j = 0.25(XX+YY+ZZ).
# 9 terms per triangle (3 pairs x 3 Pauli components), coefficient 0.25.
function kagome_H(triples)
    supp = vcat([[[3a[1]-2;3a[2]-2],[3a[1]-1;3a[2]-1],[3a[1];3a[2]],
                  [3a[1]-2;3a[3]-2],[3a[1]-1;3a[3]-1],[3a[1];3a[3]],
                  [3a[2]-2;3a[3]-2],[3a[2]-1;3a[3]-1],[3a[2];3a[3]]] for a in triples]...)
    return ncpoly(supp, 0.25 .* ones(9*length(triples)))
end

function scan_gamma_kagome(tag, N, H, triples, edges, triples0, edges0, d, gammas)
    println("=" ^ 70)
    println("$tag : N=$N d=$d  (gamma scan)")
    flush(stdout)
    open("gap_kagome.results", "a") do io
        println(io, "SCAN ", Dates.format(now(), "yyyy-mm-ddTHH:MM:SS"),
                " $tag N=$N d=$d")
    end
    results = Tuple{Float64,Int,Float64}[]
    for gamma in gammas
        t = @elapsed begin
            flag = try
                certify_Heisenberg_kagome_gap(N, H, triples, edges, triples0, edges0,
                                              gamma, d, lso=5, QUIET=true)
            catch e
                println("  gamma=$gamma EXCEPTION: ", sprint(showerror, e))
                flush(stdout)
                -1
            end
        end
        st = flag == 1 ? "FEASIBLE" : (flag == 0 ? "infeasible" : "ERROR")
        println("  gamma=", round(gamma, digits=3), " -> flag=", flag, " (", st,
                ") [", round(t, digits=1), "s]")
        flush(stdout)
        open("gap_kagome.results", "a") do io
            println(io, "  ", gamma, "  ", flag, "  ", round(t, digits=1))
        end
        push!(results, (gamma, flag, t))
    end
    feas = [r[1] for r in results if r[2] == 1]
    infeas = [r[1] for r in results if r[2] == 0]
    lf = isempty(feas) ? 0.0 : maximum(feas)
    si = isempty(infeas) ? Inf : minimum(infeas)
    sistr = si == Inf ? "none" : string(si)
    println("  TRANSITION $tag: largest_feasible=", lf,
            " smallest_infeasible=", sistr)
    flush(stdout)
    open("gap_kagome.results", "a") do io
        println(io, "TRANSITION $tag largest_feasible=", lf,
                " smallest_infeasible=", sistr)
    end
end

# ---------- Config 1: N=13, d=2 (expected Delta <= ~1.31) ----------
N = 13
triples = [[1,2,3],[1,4,5],[2,6,7],[3,8,9],[4,10,11],[5,12,13]]
edges = []
triples0 = [[1,2,3],[1,4,5]]
edges0 = []
H13 = kagome_H(triples)
println("N=13 H built. |triples|=", length(triples), " |supp|=", length(H13.supp))
flush(stdout)
scan_gamma_kagome("Kagome-N13-d2", N, H13, triples, edges, triples0, edges0, 2,
                  [0.8, 1.0, 1.2, 1.28, 1.30, 1.31, 1.32, 1.34, 1.4, 1.6])

# ---------- Config 2: N=13, d=3 (expected Delta <= ~1.28, tighter) ----------
scan_gamma_kagome("Kagome-N13-d3", N, H13, triples, edges, triples0, edges0, 3,
                  [0.8, 1.0, 1.2, 1.26, 1.28, 1.29, 1.30, 1.32, 1.4, 1.6])

# ---------- Config 3: N=27, d=2 (expected Delta <= ~1.24, bigger patch) ----------
N = 27
triples = [[1,2,3],[1,4,5],[2,6,7],[3,8,9],[4,10,11],[5,12,13],[6,14,27],
           [7,15,16],[8,17,18],[9,19,20],[10,20,21],[11,22,23],[12,24,25],[13,26,27]]
edges = [[16,17],[23,24]]
triples0 = [[1,2,3],[1,4,5]]
edges0 = []
H27 = kagome_H(triples)
println("N=27 H built. |triples|=", length(triples), " |supp|=", length(H27.supp))
flush(stdout)
scan_gamma_kagome("Kagome-N27-d2", N, H27, triples, edges, triples0, edges0, 2,
                  [0.8, 1.0, 1.15, 1.20, 1.22, 1.24, 1.25, 1.26, 1.30, 1.4])

println("\n=== ALL DONE ===  ", Dates.format(now(), "HH:MM:SS"))
flush(stdout)
JLEOF

echo "Finished: $(date)"
