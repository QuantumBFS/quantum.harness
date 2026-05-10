# Regression checks for the cached MPS Pauli-expectation backend used by Fig. 4.

using Printf

include(joinpath(@__DIR__, "..", "..", "scripts", "tfim_fig4_paper_grade.jl"))

function main()
    L = 6
    h = 0.8
    E, psi, sites = dmrg_groundstate(L, h, 16; nsweeps=12, pbc=true)
    cache = CachedMPSPauliExpectation(psi, sites)

    test_strings = [
        [0, 0, 0, 0, 0, 0],
        [3, 0, 3, 0, 3, 0],
        [1, 1, 0, 0, 3, 3],
        [2, 2, 0, 0, 1, 1],
        [1, 3, 1, 3, 1, 3],
    ]

    for p in test_strings
        set_pauli_string!(cache, p)
        v_cached = cached_pauli_value(cache)
        v_ref = mps_pauli_expectation(psi, p, sites)
        @assert isapprox(v_cached, v_ref; atol=1e-10, rtol=1e-10)
    end

    p0 = [0, 0, 0, 0, 0, 0]
    set_pauli_string!(cache, p0)
    v0 = cached_pauli_value(cache)
    old = set_cached_pauli!(cache, 3, 1)
    @assert cache.p[3] == 1
    set_cached_pauli!(cache, 3, old)
    @assert cache.p == p0
    @assert isapprox(cached_pauli_value(cache), v0; atol=1e-12, rtol=1e-12)

    cell = compute_cL_cell(10, h; chi=16, n_steps=20, n_warmup=5, seed_offset=3)
    @assert occursin("mps_cached", cell.expectation_backend)

    E10, psi10, sites10 = dmrg_groundstate(10, h, 16; nsweeps=12, pbc=true)
    E5, psi5, sites5 = dmrg_groundstate(5, h, 16; nsweeps=12, pbc=true)
    expect10 = q -> mps_pauli_expectation(psi10, q, sites10)
    expect5 = q -> mps_pauli_expectation(psi5, q, sites5)
    sector_filter = tfim_fig4_pauli_sector
    stateless = pauli_markov_cL_eq24(expect10, expect5, 10;
                                     n_steps=30, n_warmup=5, seed=UInt32(0x1234),
                                     progress_every=10^9,
                                     sample_filter=sector_filter,
                                     factor_filter=sector_filter)
    cached = pauli_markov_cL_eq24_cached(CachedMPSPauliExpectation(psi10, sites10),
                                         expect5, 10;
                                         half_cache1=CachedMPSPauliExpectation(psi5, sites5),
                                         half_cache2=CachedMPSPauliExpectation(psi5, sites5),
                                         n_steps=30, n_warmup=5, seed=UInt32(0x1234),
                                         progress_every=10^9,
                                         sample_filter=sector_filter,
                                         factor_filter=sector_filter)
    @assert cached.expectation_backend == "mps_cached_env"
    @assert isapprox(cached.mean_R, stateless.mean_R; atol=1e-10, rtol=1e-10)
    @assert isapprox(cached.cL, stateless.cL; atol=1e-10, rtol=1e-10)

    norm_cell = compute_cL_cell(8, h; chi=16, n_steps=0, n_warmup=0,
                                seed_offset=4, estimator=:pauli_mps_norm,
                                pauli_chi=16, pauli_chi_check=32)
    @assert norm_cell.expectation_backend == "pauli_mps_compressed_norm"
    @assert isfinite(norm_cell.cL)
    @assert norm_cell.se >= norm_cell.pauli_chi_error

    @printf("cached MPS Pauli regression passed at L=%d h=%.2f E=%.8f\n", L, h, E)
end

main()
