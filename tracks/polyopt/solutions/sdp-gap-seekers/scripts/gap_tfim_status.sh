#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --job-name=gap_status
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=16
#SBATCH --mem-per-cpu=3800M
#SBATCH --output=gap_tfim_status.out
#SBATCH --error=gap_tfim_status.err

# STATUS-GATE calibration (per Sihan 11:52). The patched certify_*_gap now
# returns (flag, termination, primal, dual, objective). This run exercises the
# TFIM N=9 g=0.5 d=2 lso=6 bracket at gamma=0.25/0.26/0.30 and prints the RAW
# MOI status for each, so non-OPTIMAL is no longer blindly collapsed to
# "infeasible" -- we see whether it is truly INFEASIBLE vs SLOW_PROGRESS/etc.
# (the §8 status-gate fix). SpectralGap will recompile (sdp.jl changed).

export PATH="$HOME/julia-1.11.5/bin:$PATH"
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:$LD_LIBRARY_PATH"
export JULIA_NUM_THREADS=8

cd ~/quantum.harness
echo "Node: $(hostname), Start: $(date)"

julia --project=julia-env << 'JLEOF'
using SpectralGap, MosekTools, Dates

N = 9; g = 0.5
H = ncpoly([[3*[i; i+1] for i = 1:N-1]; [[3i-2] for i = 1:N]],
           [-ones(N-1); g*ones(N)])
d = 2
println("STATUS-GATE calibration: TFIM N=$N g=$g d=$d lso=6 (default)")
println("certify_Ising_gap now returns (flag, termination, primal, dual, objective)")
println("start: ", Dates.format(now(), "HH:MM:SS"))
flush(stdout)

open("gap_tfim_status.results", "w") do io
    println(io, "# gamma  flag  termination  primal  dual  objective  farkas_min_eig_per_block")
end
for gamma in [0.25, 0.26, 0.30]
    t = @elapsed begin
        r = try
            certify_Ising_gap(N, H, gamma, d, QUIET=true)
        catch e
            println("  gamma=$gamma EXCEPTION: ", sprint(showerror, e)); flush(stdout)
            (flag=-1, termination="EXC", primal="EXC", dual="EXC", objective=NaN,
             farkas_mmat=nothing, farkas_min_eig=nothing)
        end
    end
    println("  gamma=", gamma, "  flag=", r.flag,
            "  term=", r.termination, "  primal=", r.primal,
            "  dual=", r.dual, "  obj=", round(r.objective, digits=4),
            "  [", round(t, digits=1), "s]")
    if r.farkas_min_eig !== nothing
        # §8 validation: the dual moment matrix (Farkas/SOS certificate) must be
        # PSD for each block. min_eig >= -tol => certificate is valid.
        tol = 1e-6
        psd_ok = all(me -> me >= -tol, r.farkas_min_eig)
        println("    FARKAS cert: min_eig per block=", round.(r.farkas_min_eig, digits=6),
                "  => ", psd_ok ? "PSD (certificate VALID, §8 satisfied)" : "NOT PSD (cert weak/invalid)")
    end
    flush(stdout)
    open("gap_tfim_status.results", "a") do io
        fme = r.farkas_min_eig === nothing ? "none" : join(round.(r.farkas_min_eig, digits=6), ",")
        println(io, gamma, "  ", r.flag, "  ", r.termination,
                "  ", r.primal, "  ", r.dual, "  ", r.objective, "  ", fme)
    end
end
println("=== DONE ===  ", Dates.format(now(), "HH:MM:SS")); flush(stdout)
JLEOF
echo "Finished: $(date)"
