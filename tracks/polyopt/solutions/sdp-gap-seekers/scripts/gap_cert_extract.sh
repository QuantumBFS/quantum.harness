#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --job-name=gap_cert
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=3800M
#SBATCH --output=gap_cert_extract.out
#SBATCH --error=gap_cert_extract.err

# §8 certificate extraction — CORRECTED (advisor). The certify_Ising_gap return
# now carries cert_ray = (lambda, pos_min_eig, gpos_min_eig, cons_residual),
# read from the VARIABLE PRIMAL VALUES (not dual(con_eq) -- that was the wrong
# side). Validation: lambda>0 AND every Gram block PSD AND cons_residual~0.
# JuMP's value.(cons) evaluates the affine identity independently of Mosek's flag.

export PATH="$HOME/julia-1.11.5/bin:$PATH"
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:$LD_LIBRARY_PATH"
export JULIA_NUM_THREADS=4

cd ~/quantum.harness
echo "Node: $(hostname), Start: $(date)"

julia --project=julia-env << 'JLEOF'
using SpectralGap, MosekTools, JuMP, MathOptInterface, LinearAlgebra, Dates

function run_one(N, g, gamma, d)
    H = ncpoly([[3*[i; i+1] for i = 1:N-1]; [[3i-2] for i = 1:N]],
               [-ones(N-1); g*ones(N)])
    r = certify_Ising_gap(N, H, gamma, d, QUIET=true)
    println("--- TFIM N=$N g=$g d=$d gamma=$gamma ---")
    println("  flag=", r.flag, "  term=", r.termination, "  primal=", r.primal,
            "  dual=", r.dual, "  obj=", round(r.objective, digits=4))
    if r.cert_ray === nothing
        println("  cert_ray = nothing (no INFEASIBILITY_CERTIFICATE primal status)")
        return
    end
    cr = r.cert_ray
    tol = 1e-6
    # filter NaN (empty blocks) for the PSD check
    pos_me = filter(!isnan, cr.pos_min_eig)
    gpos_me = filter(!isnan, cr.gpos_min_eig)
    lam_ok = cr.lambda > tol
    psd_ok = (!isempty(pos_me) ? minimum(pos_me) >= -tol : true) &&
             (!isempty(gpos_me) ? minimum(gpos_me) >= -tol : true)
    cons_ok = cr.cons_residual < tol
    valid = lam_ok && psd_ok && cons_ok
    println("  cert_ray: lambda=", round(cr.lambda, digits=4),
            "  pos_min_eig=", round.(pos_me, digits=6),
            "  gpos_min_eig=", round.(gpos_me, digits=6),
            "  cons_residual=", round(cr.cons_residual, digits=6))
    println("  checks: lambda>0:", lam_ok, "  PSD:", psd_ok,
            "  cons~0:", cons_ok)
    println("  => RAY ", valid ? "VALIDATES (independent of solver flag) -> candidate certificate"
                                : "FAILS audit (no certificate)")
    flush(stdout)
end

println("=== §8 TFIM N=9 d=2 (the established bracket) ==="); flush(stdout)
run_one(9, 0.5, 0.25, 2)   # feasible side
run_one(9, 0.5, 0.26, 2)   # candidate-infeasible side (SLOW_PROGRESS)
run_one(9, 0.5, 0.30, 2)

println("\n=== §8 smaller N (look for decisive DUAL_INFEASIBLE, not SLOW_PROGRESS) ==="); flush(stdout)
for N in (5, 7)
    run_one(N, 0.5, 0.25, 2)
    run_one(N, 0.5, 0.30, 2)   # a clearly-infeasible gamma for the smaller window
end
println("\n=== DONE ===  ", Dates.format(now(), "HH:MM:SS")); flush(stdout)
JLEOF
echo "Finished: $(date)"
