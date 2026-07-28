#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --job-name=gap_cert_exp
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=3800M
#SBATCH --output=gap_cert_export.out
#SBATCH --error=gap_cert_export.err

# Portable certificate artifact + independent verifier (advisor re-audit Phase 1-2).
# Step 1: run certify_Ising_gap on TFIM N=9 gamma=0.26 with export_cert=...,
#         serializing the full primal ray + the sparse affine map to a .jls file.
# Step 2: run verify_certificate.jl — a GENUINELY SEPARATE checker (no JuMP,
#         no Mosek, no original constraint construction) that reconstructs the
#         affine identity from the exported map + ray and re-audits PSD/residual.

export PATH="$HOME/julia-1.11.5/bin:$PATH"
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:$LD_LIBRARY_PATH"
export JULIA_NUM_THREADS=4

cd ~/quantum.harness
echo "Node: $(hostname), Start: $(date)"

ARTIFACT="tfim_cert_N9_g0.26.jls"

echo "=== Step 1: certify TFIM N=9 gamma=0.26 (returns cert_artifact) ==="
julia --project=julia-env << JLEOF
using SpectralGap, MosekTools, Serialization, Dates
N=9; g=0.5
H = ncpoly([[3*[i; i+1] for i = 1:N-1]; [[3i-2] for i = 1:N]], [-ones(N-1); g*ones(N)])
println("certify start=", Dates.format(now(),"HH:MM:SS")); flush(stdout)
r = certify_Ising_gap(N, H, 0.26, 2, QUIET=true)
println("flag=", r.flag, " term=", r.termination, " primal=", r.primal); flush(stdout)
println("cert_ray=", r.cert_ray); flush(stdout)
if r.cert_artifact !== nothing
    open("$ARTIFACT", "w") do io
        serialize(io, r.cert_artifact)
    end
    println("artifact serialized to $ARTIFACT  (affine_map entries=", length(r.cert_artifact.affine_map), ")"); flush(stdout)
else
    println("NO cert_artifact (feasible side or no INFEASIBILITY_CERTIFICATE)"); flush(stdout)
end
JLEOF

echo; echo "=== Step 2: independent verifier (no JuMP/Mosek) ==="
ls -la "$ARTIFACT" 2>/dev/null
julia tracks/polyopt/solutions/sdp-gap-seekers/scripts/verify_certificate.jl "$ARTIFACT"
echo "verifier exit: $?"

echo "Finished: $(date)"
