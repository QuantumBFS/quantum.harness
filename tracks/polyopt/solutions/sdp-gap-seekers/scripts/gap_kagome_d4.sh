#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --job-name=gap_kag_d4
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=32
#SBATCH --mem-per-cpu=3800M
#SBATCH --output=gap_kagome_d4.out
#SBATCH --error=gap_kagome_d4.err

# Kagome N=13 d=4 — tighter than the banked d=3 bound (Delta <= 1.28).
# N=27 d=3 OOM'd at 243 GB, so this is the productive remaining kagome run:
# same N=13 patch that succeeded at d=3, one relaxation order higher.
# d=4 SDP is bigger than d=3 but should fit (d=3 used only a fraction of 243 GB).

export PATH="$HOME/julia-1.11.5/bin:$PATH"
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:$LD_LIBRARY_PATH"
export JULIA_NUM_THREADS=16

cd ~/quantum.harness
echo "Node: $(hostname), Start: $(date)"

julia --project=julia-env << 'JLEOF'
using SpectralGap, MosekTools, Dates

N = 13
triples = [[1,2,3],[1,4,5],[2,6,7],[3,8,9],[4,10,11],[5,12,13]]
edges = []
triples0 = [[1,2,3],[1,4,5]]
edges0 = []
supp = vcat([[[3a[1]-2;3a[2]-2],[3a[1]-1;3a[2]-1],[3a[1];3a[2]],
             [3a[1]-2;3a[3]-2],[3a[1]-1;3a[3]-1],[3a[1];3a[3]],
             [3a[2]-2;3a[3]-2],[3a[2]-1;3a[3]-1],[3a[2];3a[3]]] for a in triples]...)
H = ncpoly(supp, 0.25 .* ones(9*length(triples)))
d = 4
println("Kagome N=13 d=4. |supp|=", length(H.supp), " start=", Dates.format(now(),"HH:MM:SS"))
flush(stdout)

gammas = [0.8, 1.1, 1.15, 1.18, 1.20, 1.22, 1.24, 1.26, 1.28, 1.3]
open("gap_kagome_d4.results", "w") do io
    println(io, "# Kagome N=13 d=4 gamma scan")
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
    open("gap_kagome_d4.results", "a") do io
        println(io, gamma, "  ", flag, "  ", round(t, digits=1))
    end
    if flag == 1; lf = max(lf, gamma); end
    if flag == 0; si = min(si, gamma); end
end
println("TRANSITION N=13 d=4: largest_feasible=", lf, " smallest_infeasible=", si == Inf ? "none" : si)
flush(stdout)
open("gap_kagome_d4.results", "a") do io
    println(io, "TRANSITION largest_feasible=", lf, " smallest_infeasible=", si == Inf ? "none" : si)
end
println("=== DONE ===  ", Dates.format(now(),"HH:MM:SS")); flush(stdout)
JLEOF
echo "Finished: $(date)"
