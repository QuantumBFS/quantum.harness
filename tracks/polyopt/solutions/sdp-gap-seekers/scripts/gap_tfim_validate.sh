#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --job-name=gap_tfim
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem-per-cpu=3800M
#SBATCH --output=gap_tfim.out
#SBATCH --error=gap_tfim.err

# Gap-SDP Gate 5: validate certify_Ising_gap by reproducing the 1D TFIM
# benchmark. Target (from legacy-inventory-spec.md + example.jl): N=9, g=0.5,
# d=2, sign-symmetric -> certified upper bound on Delta ~ 0.24-0.258.
# Method: coarse gamma scan to locate the feasibility transition (largest
# feasible gamma = certified upper bound on the bulk gap). Each solve is small
# (N=9, d=2). This is the first end-to-end gap-cert run -- validates the
# SpectralGap.jl pipeline before we point it at the frustrated kagome target.

export PATH="$HOME/julia-1.11.5/bin:$PATH"
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:$LD_LIBRARY_PATH"
export JULIA_NUM_THREADS=8

cd ~/quantum.harness
echo "Node: $(hostname), Start: $(date)"

julia --project=julia-env << 'JLEOF'
using SpectralGap, MosekTools, Dates

println("SpectralGap TFIM validation -- N=9, g=0.5, d=2 (sign-symmetric)")
println("start: ", Dates.format(now(), "HH:MM:SS"))
flush(stdout)

# 1D transverse-field Ising:  H = -sum_i Z_i Z_{i+1} + g sum_i X_i
# ncpoly encoding: site i -> 3i-2=X_i, 3i-1=Y_i, 3i=Z_i
N = 9
g = 0.5
H = ncpoly([[3*[i; i+1] for i = 1:N-1]; [[3i-2] for i = 1:N]],
           [-ones(N-1); g*ones(N)])
d = 2
println("H built. N=$N, g=$g, d=$d. |supp|=", length(H.supp))
flush(stdout)

# coarse gamma scan to locate the feasibility transition.
#   flag=1 (OPTIMAL)  -> gamma is feasible  -> Delta could be >= gamma
#   flag=0 (other)    -> gamma infeasible    -> Delta <  gamma  (excludes gap>=gamma)
# largest feasible gamma = certified upper bound on the bulk gap.
gammas = [0.15, 0.20, 0.22, 0.24, 0.25, 0.26, 0.27, 0.28, 0.30, 0.34]
println("\n--- coarse gamma scan ---")
flush(stdout)
open("gap_tfim.results", "w") do io
    println(io, "# TFIM gap validation N=$N g=$g d=$d sign-symmetric")
    println(io, "# gamma  flag  time_s  (flag=1 feasible, flag=0 infeasible)")
end
largest_feasible = 0.0
smallest_infeasible = Inf
for gamma in gammas
    t = @elapsed begin
        flag = try
            certify_Ising_gap(N, H, gamma, d, QUIET=true)
        catch e
            println("  gamma=$gamma EXCEPTION: ", sprint(showerror, e)); flush(stdout)
            -1
        end
    end
    status = flag == 1 ? "FEASIBLE" : (flag == 0 ? "infeasible" : "ERROR")
    println("  gamma=", round(gamma, digits=3), "  -> flag=", flag, " (", status, ")  [",
            round(t, digits=1), "s]")
    flush(stdout)
    open("gap_tfim.results", "a") do io
        println(io, gamma, "  ", flag, "  ", round(t, digits=1))
    end
    if flag == 1 && gamma > largest_feasible
        largest_feasible = gamma
    end
    if flag == 0 && gamma < smallest_infeasible
        smallest_infeasible = gamma
    end
end

println("\n=== TRANSITION ===")
println("largest feasible gamma   = ", largest_feasible)
println("smallest infeasible gamma = ", smallest_infeasible == Inf ? "none (all feasible)" : smallest_infeasible)
if smallest_infeasible != Inf
    println("=> certified upper bound on Delta in (", largest_feasible, ", ",
            smallest_infeasible, "]")
    println("   (expected ~0.24-0.258 per legacy-inventory-spec / example.jl)")
else
    println("=> no infeasible point in scan range; bound > ", largest_feasible,
            " (widen scan)")
end
println("\n=== DONE ===  ", Dates.format(now(), "HH:MM:SS"))
flush(stdout)
JLEOF

echo "Finished: $(date)"
