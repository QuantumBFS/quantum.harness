#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --job-name=gap_kag_n27
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=128
#SBATCH --mem-per-cpu=3800M
#SBATCH --output=gap_kagome_n27.out
#SBATCH --error=gap_kagome_n27.err

# Kagome N=27 d=3 — the tighter headline #88 bound (example.jl: ~1.15).
# Previous attempt OOM'd at 64 cpus / 243 GB. xhacnormalb nodes have 128 cores /
# ~500 GB, so 128 cpus -> ~486 GB (2x). Each solve is large (expect ~10-30 min);
# 10 gamma values ordered, try/caught, incrementally written.

export PATH="$HOME/julia-1.11.5/bin:$PATH"
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:$LD_LIBRARY_PATH"
export JULIA_NUM_THREADS=64

cd ~/quantum.harness
echo "Node: $(hostname), Start: $(date)"

julia --project=julia-env << 'JLEOF'
using SpectralGap, MosekTools, Dates

N = 27
triples = [[1,2,3],[1,4,5],[2,6,7],[3,8,9],[4,10,11],[5,12,13],[6,14,27],
           [7,15,16],[8,17,18],[9,19,20],[10,20,21],[11,22,23],[12,24,25],[13,26,27]]
edges = [[16,17],[23,24]]
triples0 = [[1,2,3],[1,4,5]]
edges0 = []
supp = vcat([[[3a[1]-2;3a[2]-2],[3a[1]-1;3a[2]-1],[3a[1];3a[2]],
             [3a[1]-2;3a[3]-2],[3a[1]-1;3a[3]-1],[3a[1];3a[3]],
             [3a[2]-2;3a[3]-2],[3a[2]-1;3a[3]-1],[3a[2];3a[3]]] for a in triples]...)
H = ncpoly(supp, 0.25 .* ones(9*length(triples)))
d = 3
println("Kagome N=27 d=3. |supp|=", length(H.supp), " start=", Dates.format(now(),"HH:MM:SS"))
flush(stdout)

gammas = [0.8, 1.0, 1.1, 1.13, 1.15, 1.16, 1.17, 1.18, 1.20, 1.25]
open("gap_kagome_n27.results", "w") do io
    println(io, "# Kagome N=27 d=3 gamma scan (128-cpu, ~486GB)")
end
lf, si = 0.0, Inf
for gamma in gammas
    global lf, si
    t = @elapsed begin
        flag = try
            certify_Heisenberg_kagome_gap(N, H, triples, edges, triples0, edges0, gamma, d, lso=5, QUIET=true)
        catch e
            println("  gamma=$gamma EXCEPTION: ", sprint(showerror, e)); flush(stdout); -1
        end
    end
    st = flag == 1 ? "FEASIBLE" : (flag == 0 ? "infeasible" : "ERROR")
    println("  gamma=", round(gamma, digits=3), " -> flag=", flag, " (", st, ") [", round(t,digits=1), "s]")
    flush(stdout)
    open("gap_kagome_n27.results", "a") do io
        println(io, gamma, "  ", flag, "  ", round(t, digits=1))
    end
    if flag == 1; lf = max(lf, gamma); end
    if flag == 0; si = min(si, gamma); end
end
println("TRANSITION N=27 d=3: largest_feasible=", lf, " smallest_infeasible=", si==Inf?"none":si)
flush(stdout)
open("gap_kagome_n27.results", "a") do io
    println(io, "TRANSITION largest_feasible=", lf, " smallest_infeasible=", si==Inf?"none":si)
end
println("=== DONE ===  ", Dates.format(now(),"HH:MM:SS")); flush(stdout)
JLEOF
echo "Finished: $(date)"
