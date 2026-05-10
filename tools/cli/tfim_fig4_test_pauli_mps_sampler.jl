# Regression for exact/batched Pauli-MPS sampling primitives used by Fig. 4.

using Random
using Printf

include(joinpath(@__DIR__, "..", "..", "scripts", "tfim_fig4_paper_grade.jl"))
include(joinpath(@__DIR__, "pauli_mps_sampler.jl"))

function pauli_string_from_index(idx0::Int, L::Int)
    p = zeros(Int, L)
    x = idx0
    for i in 1:L
        p[i] = x & 3
        x >>= 2
    end
    return p
end

function brute_force_squared_norm(Bs)
    L = length(Bs)
    total = 0.0
    for idx0 in 0:(4^L - 1)
        p = pauli_string_from_index(idx0, L)
        total += abs2(pauli_mps_amplitude(Bs, p))^2
    end
    return total
end

function main()
    L = 4
    h = 0.8
    E, psi, sites = dmrg_groundstate(L, h, 6; nsweeps=8, pbc=true)
    Bs = pauli_mps_tensors(psi, sites)

    for p in ([0, 0, 0, 0],
              [3, 0, 3, 0],
              [1, 1, 0, 0],
              [2, 2, 0, 0])
        amp = pauli_mps_amplitude(Bs, collect(p))
        ref = mps_pauli_expectation(psi, collect(p), sites) / sqrt(2.0^L)
        @assert isapprox(amp, ref; atol=1e-10, rtol=1e-10)
    end

    sampler = SquaredPauliMPSSampler(Bs)
    norm_exact = brute_force_squared_norm(Bs)
    norm_sampler = pauli_squared_mps_norm(sampler)
    @assert isapprox(norm_sampler, norm_exact; atol=1e-10, rtol=1e-10)

    Bs_compressed, trunc_err = compress_pauli_mps(Bs, 64, 1e-14)
    compressed_norm = pauli_squared_mps_norm(SquaredPauliMPSSampler(Bs_compressed))
    @assert trunc_err <= 1e-20
    @assert isapprox(compressed_norm, norm_exact; atol=1e-10, rtol=1e-10)

    rng = MersenneTwister(0x515A)
    p = sample_pauli_string(sampler, rng)
    @assert length(p) == L
    @assert all(0 .<= p .<= 3)

    Eh, psih, sitesh = dmrg_groundstate(L ÷ 2, h, 6; nsweeps=8, pbc=true)
    Bhalf = pauli_mps_tensors(psih, sitesh)
    exact_cL = log(pauli_squared_mps_norm(sampler) /
                   pauli_squared_mps_norm(SquaredPauliMPSSampler(Bhalf))^2)
    bridge = pauli_mps_bridge_cL(Bs, Bhalf; n_samples=1_000, seed=0xCACE)
    @assert isapprox(bridge.cL, exact_cL; atol=0.10, rtol=0.0)

    @printf("Pauli-MPS sampler regression passed at L=%d h=%.2f E=%.8f norm=%.12e bridge=%.8f exact=%.8f\n",
            L, h, E, norm_sampler, bridge.cL, exact_cL)
end

main()
