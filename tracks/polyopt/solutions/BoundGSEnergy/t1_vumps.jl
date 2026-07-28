# T1 — VUMPS uniform MPS for the 1D Heisenberg AFM (the coarse-grainer for
# the Kull-Schuch compressed-LTI relaxation, challenge #49).
# Test-first: the variational energy must approach e0 = 1/4 - ln2 from ABOVE
# and tighten with D. Saves the MPS tensors for T2 via Serialization.

using MPSKit, MPSKitModels, TensorKit, LinearAlgebra, Serialization, Printf

e0_exact = 1/4 - log(2)   # Bethe ansatz, H = sum S_i . S_{i+1}, J = 1
out = Dict{Int, Any}()

for D in [2, 3]
    L = 2   # 2-site unit cell: AFM Néel period; VUMPS is far better conditioned than 1-site
    H = heisenberg_XXX(Float64, Trivial, InfiniteChain(L); spin=1//2)
    psi = InfiniteMPS(Float64, fill(physicalspace(H, 1), L), fill(ComplexSpace(D), L))
    psi, envs, delta = find_groundstate(psi, H, VUMPS(; tol=1e-12, maxiter=400))
    E = expectation_value(psi, H, envs) / L   # energy density per site
    @printf("D = %d:  E/N = %.10f   (exact %.10f, variational gap %.2e, ||B|| = %.1e)\n",
            D, real(E), e0_exact, real(E) - e0_exact, delta)
    flush(stdout)
    @assert real(E) > e0_exact - 1e-12 "variational principle violated at D=$D"
    out[D] = psi
end

serialize(joinpath(@__DIR__, "vumps_mps.jls"), out)
println("MPS tensors saved to vumps_mps.jls"); flush(stdout)
