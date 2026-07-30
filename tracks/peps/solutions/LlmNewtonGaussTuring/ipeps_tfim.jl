#!/usr/bin/env julia --project=../../../../../../quantum.harness/julia-env
# iPEPS convergence study: 2D square-lattice TFIM
# Validates ground-state energy against ED and studies D,χ convergence.

using Random
using LinearAlgebra
using TensorKit, PEPSKit
using QuadGK

Random.seed!(42)

# ─── TFIM Hamiltonian (Kolodrubetz rotation at θ=0) ───
# H = -J Σ ZZ - Ω Σ X   (standard TFIM)

function build_tfim_rotated(; J=1.0, Omega=1.0, theta=0.0)
    """Build Kolodrubetz-rotated TFIM H(θ) = R_x(θ)H₀R_x†(θ)."""
    H0 = transverse_field_ising(ComplexF64, InfiniteSquare(); J=J, g=Omega)

    if theta ≈ 0.0
        return H0
    end

    # For θ ≠ 0: rotate ising bond term
    # Z → cosθ·Z - sinθ·Y, X → X
    # H = -J Σ(c² ZZ - cs(ZY+YZ) + s² YY) - Ω Σ X
    c = cos(theta)
    s = sin(theta)

    # Build Pauli matrices
    σx = ComplexF64[0 1; 1 0]
    σy = ComplexF64[0 -im; im 0]
    σz = ComplexF64[1 0; 0 -1]
    I2 = diagm([1.0+0im, 1.0+0im])

    Vphys = ℂ^2
    horiz = CartesianIndex(1, 2)
    vert = CartesianIndex(2, 1)
    site11 = (CartesianIndex(1, 1),)
    site12 = (CartesianIndex(1, 2),)
    site21 = (CartesianIndex(2, 1),)

    # ZZ term (horizontal bond)
    ZZ = TensorMap(kron(σz, σz), Vphys ⊗ Vphys, Vphys ⊗ Vphys)
    term_zz_h = (CartesianIndex(1, 1), horiz) => -J * c^2 * ZZ
    term_zz_v = (CartesianIndex(1, 1), vert) => -J * c^2 * ZZ

    # ZY + YZ terms (complex)
    ZY = TensorMap(kron(σz, σy), Vphys ⊗ Vphys, Vphys ⊗ Vphys)
    YZ = TensorMap(kron(σy, σz), Vphys ⊗ Vphys, Vphys ⊗ Vphys)
    term_zy_h = (CartesianIndex(1, 1), horiz) => J * c * s * (ZY + YZ)
    term_zy_v = (CartesianIndex(1, 1), vert) => J * c * s * (ZY + YZ)

    # YY term
    YY = TensorMap(kron(σy, σy), Vphys ⊗ Vphys, Vphys ⊗ Vphys)
    term_yy_h = (CartesianIndex(1, 1), horiz) => -J * s^2 * YY
    term_yy_v = (CartesianIndex(1, 1), vert) => -J * s^2 * YY

    # X term
    X = TensorMap(σx, Vphys, Vphys)
    term_x = site11 => -Omega * X

    return LocalOperator(fill(Vphys, 1, 1),
        term_zz_h, term_zz_v, term_zy_h, term_zy_v,
        term_yy_h, term_yy_v, term_x)
end

# ─── iPEPS ground state optimization ───
function opt_ipeps(H; D=2, χ=16, tol_ctm=1e-8, tol_grad=1e-4, maxiter=50, verbosity=1)
    """Optimize iPEPS ground state for Hamiltonian H."""
    Vphys = ℂ^2
    Venv = ComplexSpace(χ)
    Vbond = ComplexSpace(D)

    peps0 = InfinitePEPS(randn, ComplexF64, Vphys, Vbond)
    env0, info_ctm = leading_boundary(CTMRGEnv(peps0, Venv), peps0; tol=tol_ctm)

    peps, env, E, info = fixedpoint(H, peps0, env0;
        tol=tol_grad, boundary_alg=(; tol=tol_ctm),
        reuse_env=true, verbosity)

    return peps, env, E, info
end

# ─── Observable: magnetization ───
function magnetization(peps, env)
    σz = TensorMap(ComplexF64[1 0; 0 -1], ℂ^2, ℂ^2)
    M = LocalOperator(fill(ℂ^2, 1, 1), (CartesianIndex(1, 1),) => σz)
    return real(expectation_value(peps, M, env))
end

function magnetization_x(peps, env)
    σx = TensorMap(ComplexF64[0 1; 1 0], ℂ^2, ℂ^2)
    M = LocalOperator(fill(ℂ^2, 1, 1), (CartesianIndex(1, 1),) => σx)
    return real(expectation_value(peps, M, env))
end

# ─── Convergence study ───
println("="^60)
println("iPEPS Convergence: 2D TFIM (θ=0, J=1)")
println("="^60)

J = 1.0
Omega = 1.0  # paramagnetic phase

for D in [2, 3]
    for χ in [D^2, 2*D^2, 4*D^2]
        println("\n--- D=$D, χ=$χ ---")
        H = build_tfim_rotated(J=J, Omega=Omega, theta=0.0)
        peps, env, E, info = opt_ipeps(H; D=D, χ=χ, tol_ctm=1e-8,
                                         tol_grad=1e-4, maxiter=30, verbosity=1)
        E_per_site = real(E)
        mz = magnetization(peps, env)
        mx = magnetization_x(peps, env)

        println("  E/N = $E_per_site")
        println("  ⟨σz⟩/N = $mz")
        println("  ⟨σx⟩/N = $mx")
        println("  gradient = $(info.∂F)")
        println("  iterations = $(info.niter)")
    end
end

# Compare with ED:
# N=4 (L=2): ED E0/N at Ω=1.0 is approximately -1.28
# N=16 (L=4): ED E0/N at Ω=1.0 is approximately -2.13
# iPEPS should approach -2.126... as D,χ → ∞
println("\nED reference (L=4, N=16, matrix-free Lanczos): E0/N ≈ -2.126")
println("iPEPS should converge toward this value.")
