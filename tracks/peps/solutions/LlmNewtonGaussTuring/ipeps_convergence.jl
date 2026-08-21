#!/usr/bin/env julia --project=../../../../../../quantum.harness/julia-env
# iPEPS convergence study for Challenge 73 — cluster-ready.
# Usage: julia ipeps_convergence.jl D χ Omega [theta]
# Computes TFIM ground state via PEPSKit.jl and reports E/N.

using Random, LinearAlgebra, TensorKit, PEPSKit

Random.seed!(42)

# ─── Parse args ───
D     = parse(Int, ARGS[1])
χ     = parse(Int, ARGS[2])
Omega = parse(Float64, ARGS[3])
theta = length(ARGS) >= 4 ? parse(Float64, ARGS[4]) : 0.0

J = 1.0

# ─── Build TFIM Hamiltonian ───
if theta ≈ 0.0
    H = transverse_field_ising(ComplexF64, InfiniteSquare(); J=J, g=Omega)
else
    # Rotated Hamiltonian: H = R_x(θ) H₀ R_x†(θ)
    # Z → cosθ·Z - sinθ·Y,   X → X
    c, s = cos(theta), sin(theta)
    Vphys = ℂ^2
    σx = ComplexF64[0 1; 1 0]
    σy = ComplexF64[0 -im; im 0]
    σz = ComplexF64[1 0; 0 -1]
    I2  = diagm([1.0+0im, 1.0+0im])

    # Build bond operators Z⊗Z, Y⊗Z, Z⊗Y, Y⊗Y as 4-index TensorMaps
    ZZ = TensorMap(kron(σz, σz), Vphys⊗Vphys, Vphys⊗Vphys)
    YZ = TensorMap(kron(σy, σz), Vphys⊗Vphys, Vphys⊗Vphys)
    ZY = TensorMap(kron(σz, σy), Vphys⊗Vphys, Vphys⊗Vphys)
    YY = TensorMap(kron(σy, σy), Vphys⊗Vphys, Vphys⊗Vphys)

    horiz = CartesianIndex(1, 2)
    vert  = CartesianIndex(2, 1)
    site  = (CartesianIndex(1, 1),)

    H = LocalOperator(fill(Vphys, 1, 1),
        (CartesianIndex(1,1), horiz) =>  -J*c^2       * ZZ,
        (CartesianIndex(1,1), vert)  =>  -J*c^2       * ZZ,
        (CartesianIndex(1,1), horiz) =>   J*c*s       * (ZY + YZ),
        (CartesianIndex(1,1), vert)  =>   J*c*s       * (ZY + YZ),
        (CartesianIndex(1,1), horiz) =>  -J*s^2       * YY,
        (CartesianIndex(1,1), vert)  =>  -J*s^2       * YY,
        site                        => -Omega         * TensorMap(σx, Vphys, Vphys)
    )
end

# ─── iPEPS optimization ───
Vbond = ComplexSpace(D)
Venv  = ComplexSpace(χ)
Vphys = ℂ^2

peps0 = InfinitePEPS(randn, ComplexF64, Vphys, Vbond)
env0, info_ctm = leading_boundary(CTMRGEnv(peps0, Venv), peps0; tol=1e-8)

println("CTMRG done: converged=$(info_ctm.converged), err=$(info_ctm.convergence_error)")

peps, env, E, info = fixedpoint(H, peps0, env0;
    tol=1e-4, boundary_alg=(; tol=1e-8),
    reuse_env=true, verbosity=1)

E_per_N = real(E)
println("D=$D χ=$χ Omega=$Omega theta=$theta E/N=$E_per_N")
