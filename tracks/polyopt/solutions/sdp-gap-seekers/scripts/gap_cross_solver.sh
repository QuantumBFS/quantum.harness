#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --job-name=gap_xsol
#SBATCH --time=00:40:00
#SBATCH --cpus-per-task=16
#SBATCH --mem-per-cpu=3800M
#SBATCH --output=gap_cross_solver.out
#SBATCH --error=gap_cross_solver.err

# §8 cross-solver validation. The TFIM N=9 g=0.5 d=2 bracket is re-solved by an
# INDEPENDENT solver (Clarabel, pure Julia, zero shared code with Mosek). If
# both solvers agree on the feasibility transition (feasible at gamma=0.25,
# infeasible/no-feasible-lambda>0 at gamma=0.26+), the bound Delta<=0.26 is
# independently validated -- a defensible §8 "independently validated" claim
# without relying on a single solver's internal Farkas ray.

export PATH="$HOME/julia-1.11.5/bin:$PATH"
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:$LD_LIBRARY_PATH"
export JULIA_NUM_THREADS=8

cd ~/quantum.harness
echo "Node: $(hostname), Start: $(date)"

julia --project=julia-env << 'JLEOF'
using SpectralGap, MosekTools, Clarabel, Dates

N = 9; g = 0.5
H = ncpoly([[3*[i; i+1] for i = 1:N-1]; [[3i-2] for i = 1:N]],
           [-ones(N-1); g*ones(N)])
d = 2
println("CROSS-SOLVER validation: TFIM N=$N g=$g d=$d lso=6")
println("Mosek (MOSEKBINDIR set) vs Clarabel (pure Julia, independent)")
println("start: ", Dates.format(now(), "HH:MM:SS"))
flush(stdout)

# Run each gamma through BOTH solvers; classify each verdict.
# For the Max-lambda problem: OPTIMAL with lambda reachable => feasible (flag=1);
# anything else => the infeasible side. We report raw status from each solver.
function classify(r)
    r.flag == 1 && return "FEASIBLE"
    r.primal == MathOptInterface.INFEASIBILITY_CERTIFICATE && return "INFEASIBLE(cert)"
    return "non-OPTIMAL($(r.termination))"
end

open("gap_cross_solver.results", "w") do io
    println(io, "# gamma  mosek_flag  mosek_term  mosek_primal  | clarabel_flag  clarabel_term  clarabel_primal  | agree?")
end
for gamma in [0.25, 0.26]
    print("gamma=", gamma, " : "); flush(stdout)
    # Mosek (default path)
    rm = try
        certify_Ising_gap(N, H, gamma, d, QUIET=true,
                          optimizer=optimizer_with_attributes(Mosek.Optimizer))
    catch e
        println("MOSEK EXC: ", sprint(showerror, e)); flush(stdout)
        (flag=-1, termination="EXC", primal="EXC", dual="EXC", objective=NaN,
         farkas_mmat=nothing, farkas_min_eig=nothing)
    end
    flush(stdout)
    # Clarabel (independent, pure Julia) -- bounded so it returns a verdict on
    # this complex SDP where it is far slower than Mosek.
    rc = try
        certify_Ising_gap(N, H, gamma, d, QUIET=true,
                          optimizer=optimizer_with_attributes(Clarabel.Optimizer,
                              "max_iter" => 500, "time_limit" => 120))
    catch e
        println("CLARABEL EXC: ", sprint(showerror, e)); flush(stdout)
        (flag=-1, termination="EXC", primal="EXC", dual="EXC", objective=NaN,
         farkas_mmat=nothing, farkas_min_eig=nothing)
    end
    cm, cc = classify(rm), classify(rc)
    agree = (rm.flag == rc.flag) ? "YES" : "NO"
    println("  Mosek:    flag=", rm.flag, " (", cm, ")  term=", rm.termination)
    println("  Clarabel: flag=", rc.flag, " (", cc, ")  term=", rc.termination)
    println("  => agree on flag: ", agree)
    flush(stdout)
    open("gap_cross_solver.results", "a") do io
        println(io, gamma, "  ", rm.flag, "  ", rm.termination, "  ", rm.primal,
                "  |  ", rc.flag, "  ", rc.termination, "  ", rc.primal,
                "  |  ", agree)
    end
end
println("=== DONE ===  ", Dates.format(now(), "HH:MM:SS")); flush(stdout)
JLEOF
echo "Finished: $(date)"
