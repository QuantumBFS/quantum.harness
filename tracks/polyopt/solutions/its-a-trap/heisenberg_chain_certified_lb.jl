#!/usr/bin/env julia
# Certified lower bound on the ground-state energy per spin of the periodic
# spin-1/2 Heisenberg chain, via the structured NPA hierarchy (QMBCertify + Mosek).
#
# Reproduces Table 3 of arXiv:2604.01555 (Wang, Jansen, Frerot, Renou, Magron, Acin).
#   H = (1/4) sum_{i=1}^{N} sum_{a in {x,y,z}} sigma_i^a sigma_{i+1}^a,  site N+1 == site 1
#
# Usage:  julia --project=julia-env heisenberg_chain_certified_lb.jl <N> <outdir>

using QMBCertify
using JSON
using Printf

const N      = parse(Int, ARGS[1])
const OUTDIR = ARGS[2]

# --- Hamiltonian in QMBCertify normal form -----------------------------------
# Index convention: site i, Pauli component a in {1=x,2=y,3=z} -> 3*(i-1)+a.
# [1,4] is therefore sigma^x_1 sigma^x_2, the nearest-neighbour bond.
# SU(2) symmetry makes the x, y and z bond terms equal, so (1/4)*sum_a collapses
# to a single component with coefficient 3/4.
supp = [[1, 4]]
coe  = [3 / 4]

# --- Relaxation settings (see run.json for the rationale of each) ------------
const D          = 4        # relaxation order
const EXTRA      = 0        # basis reach r = EXTRA + 1 = 1 (nearest-neighbour pairs)
const RDM        = 8        # k-site reduced-density-matrix positivity
const PSO        = 3        # PSD state optimality (package default)
const LSO        = true     # linear state optimality
const THREE_TYPE = [1, 1]   # adjacent triples for the three-site words (live at d >= 3)

@printf("=== Heisenberg chain, N = %d, d = %d, r = %d ===\n", N, D, EXTRA + 1)
flush(stdout)

solve_time = @elapsed begin
    opt, data = GSB(supp, coe, N, D;
                    lattice     = "chain",
                    extra       = EXTRA,
                    rdm         = RDM,
                    pso         = PSO,
                    lso         = LSO,
                    lol         = N,
                    three_type  = THREE_TYPE,
                    SU2_symmetry = false,
                    Gram        = true,
                    QUIET       = false)
end

@printf("\nSDP solve wall time: %.1f s\n", solve_time)
@printf("raw optimum (opt)  : %.10f\n", opt)
@printf("opt / N            : %.10f\n", opt / N)
flush(stdout)

# --- Exact rational certification (1D chains only) ---------------------------
# snn=false, J2=0: certify against the PLAIN Heisenberg chain, no next-nearest
# neighbour term. Getting this wrong certifies a different Hamiltonian.
cert_time = NaN
certified = nothing
cert_error = nothing
try
    cert_time = @elapsed begin
        certified = certify_qmb(data, N, coe[1], opt;
                                tol_gram = 1e-15, tol_dft = 1e-12,
                                snn = false, J2 = 0)
    end
    @printf("\nexact certification wall time: %.1f s\n", cert_time)
    @printf("oldbound (raw numeric)   : %.10f\n", Float64(certified.oldbound))
    @printf("newbound (exactly certified): %.10f\n", Float64(certified.newbound))
    @printf("shift                    : %.3e\n", Float64(certified.shift))
catch e
    cert_error = sprint(showerror, e)
    @printf("\nexact certification FAILED: %s\n", cert_error)
end
flush(stdout)

# --- Persist ------------------------------------------------------------------
out = Dict(
    "N"              => N,
    "d"              => D,
    "r"              => EXTRA + 1,
    "rdm"            => RDM,
    "pso"            => PSO,
    "lso"            => LSO,
    "three_type"     => THREE_TYPE,
    "opt"            => opt,
    "opt_per_spin"   => opt / N,
    "solve_seconds"  => solve_time,
    "cert_seconds"   => cert_time,
    "oldbound"       => certified === nothing ? nothing : Float64(certified.oldbound),
    "newbound"       => certified === nothing ? nothing : Float64(certified.newbound),
    "shift"          => certified === nothing ? nothing : Float64(certified.shift),
    "cert_error"     => cert_error,
)
mkpath(OUTDIR)
open(joinpath(OUTDIR, "bound_N$(N).json"), "w") do io
    JSON.print(io, out, 2)
end
println("\nwrote ", joinpath(OUTDIR, "bound_N$(N).json"))
