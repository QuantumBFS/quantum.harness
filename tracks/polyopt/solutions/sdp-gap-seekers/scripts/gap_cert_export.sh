#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --job-name=gap_cert_exp
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=3800M
#SBATCH --output=gap_cert_export.out
#SBATCH --error=gap_cert_export.err

set -euo pipefail

# Sound certificate pipeline (advisor recheck): export one-x artifact -> sound
# verify -> corruption self-tests. Fails (nonzero exit) if any step fails.

export PATH="$HOME/julia-1.11.5/bin:$PATH"
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:${LD_LIBRARY_PATH:-}"
export JULIA_NUM_THREADS=4

cd ~/quantum.harness
SCRIPTS=tracks/polyopt/solutions/sdp-gap-seekers/scripts
EVID=tracks/polyopt/solutions/sdp-gap-seekers/evidence
mkdir -p "$EVID"
ARTIFACT="$EVID/tfim_cert_N9_g0.26.jls"

echo "Node: $(hostname), Start: $(date)"
echo "Julia: $(julia --version), repo: $(git rev-parse --short HEAD 2>/dev/null)"
echo "patch SHA-256: $(sha256sum tracks/polyopt/solutions/sdp-gap-seekers/spectralgap_a1171c9.patch | cut -d' ' -f1)"

echo "=== Step 1: certify TFIM N=9 gamma=0.26 (returns cert_artifact) ==="
julia --project=julia-env << JLEOF
using SpectralGap, MosekTools, Serialization, Dates
N=9; g=0.5
H = ncpoly([[3*[i; i+1] for i = 1:N-1]; [[3i-2] for i = 1:N]], [-ones(N-1); g*ones(N)])
println("certify start=", Dates.format(now(),"HH:MM:SS")); flush(stdout)
r = certify_Ising_gap(N, H, 0.26, 2, QUIET=true)
println("flag=", r.flag, " term=", r.termination, " primal=", r.primal); flush(stdout)
if r.cert_artifact === nothing
    println("ERROR: no cert_artifact"); flush(stdout); exit(1)
end
open("$ARTIFACT", "w") do io; serialize(io, r.cert_artifact); end
println("artifact serialized: $ARTIFACT  (nvars=\$(r.cert_artifact.nvars), ncons=\$(r.cert_artifact.nconstraints), affmap=\$(length(r.cert_artifact.affine_map)))"); flush(stdout)
JLEOF

echo; echo "=== Step 2: SOUND verifier (one-x binding, no JuMP/Mosek) ==="
ls -la "$ARTIFACT"
julia "$SCRIPTS/verify_certificate.jl" "$ARTIFACT"
echo "verifier exit: $?"

echo; echo "=== Step 3: corruption self-tests (verifier must reject each) ==="
julia "$SCRIPTS/test_verifier_corruption.jl" "$ARTIFACT"
echo "corruption-test exit: $?"

echo; echo "=== Epilogue: artifact hash + package versions ==="
sha256sum "$ARTIFACT"
julia --project=julia-env -e 'using JuMP, MathOptInterface, MosekTools; for m in (JuMP, MathOptInterface, MosekTools); println("$(m) v$(pkgversion(m))"); end; println("julia v", VERSION)'
echo "Finished: $(date)"
