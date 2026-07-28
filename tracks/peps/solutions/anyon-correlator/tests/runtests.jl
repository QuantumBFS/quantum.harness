# Test suite — anyon-correlator solution.
#   M1 testset (G1–G6, seconds): toric-code Hamiltonian + 2×2 ED, from
#     scripts/ed_checks.jl. Independent of all PEPS machinery.
#   M2 testset (T1–T7): exact-tensor algebra (V/P vs closed form, intertwiner
#     structure), Hamiltonian term table vs M1 incidence, SU gate sanity,
#     grading preservation, and the h=0 energy-normalization anchors
#     (E_cell = −8, per composite site = −2, per edge spin = −1).
# T7 runs one CTMRG on the exact state (~1 min); all other tests are seconds.
# Usage: julia --project=julia-env tracks/peps/solutions/anyon-correlator/tests/runtests.jl

using Test
using Random

include(joinpath(@__DIR__, "..", "scripts", "ed_checks.jl"))

@testset "M1 — toric-code Hamiltonian, 2×2 ED" begin
    for g in acceptance_gates()
        @test g.passed
        println(@sprintf("[%s] %s — %s", g.passed ? "PASS" : "FAIL", g.gate, g.detail))
        flush(stdout)
    end
end

# M2 unit tests — algebra/construction checks (T1–T6, seconds) plus one CTMRG
# normalization anchor (T7, ~1 min). No optimization anywhere.
include(joinpath(@__DIR__, "..", "scripts", "tc_peps.jl"))

@testset "M2 — exact tensor, Hamiltonian, SU gates" begin
    # T1: V/P contraction (user's construction) equals the closed-form composite tensor
    @test exact_tensor_dense_VP() ≈ exact_tensor_dense()
    println("[PASS] T1 V/P contraction == closed-form rank-6 tensor"); flush(stdout)

    # T2: exact TensorMap is a Z₂ intertwiner; all 32 charge-allowed entries nonzero
    #     (±1/2), norm √8; dense read-back matches the reference array 64/64
    Tex = exact_peps_tensor()
    @test only(blocksectors(Tex)) == Z2Irrep(0)
    nnz = count(x -> abs(x) > 1e-14, block(Tex, Z2Irrep(0)))
    @test nnz == 32
    @test norm(Tex) ≈ sqrt(8)
    A = convert(Array, Tex)
    Tref = exact_tensor_dense_VP()
    @test all(abs(A[pE + 2pN + 1, n + 1, e + 1, s + 1, w + 1] -
                  Tref[pE + 1, pN + 1, n + 1, e + 1, s + 1, w + 1]) < 1e-12
              for pE in 0:1, pN in 0:1, n in 0:1, e in 0:1, s in 0:1, w in 0:1)
    println("[PASS] T2 exact tensor: intertwiner, 32 nonzero entries, norm √8, read-back 64/64")
    flush(stdout)

    # T3: Hamiltonian term table — 4 stars + 4 plaquettes on the (2,2) cell,
    #     term ops are (minus) Pauli products squaring to identity
    H0, table = toric_code_hamiltonian(0.0, 0.0)
    @test count(t -> t.kind == :star, table) == 4
    @test count(t -> t.kind == :plaquette, table) == 4
    @test length(H0.terms) == 8
    s_op, p_op = star_op(), plaq_op()
    @test s_op * s_op ≈ TensorKit.id(domain(s_op))
    @test p_op * p_op ≈ TensorKit.id(domain(p_op))
    # M1 incidence: star (r,c) touches composite sites (r,c), (r,c−1), (r+1,c);
    # plaquette (r,c) touches (r,c), (r−1,c), (r,c+1)
    for t in table
        r, c = t.center
        if t.kind == :star
            @test t.sites == ((r, c - 1), (r, c), (r + 1, c))
        elseif t.kind == :plaquette
            @test t.sites == ((r - 1, c), (r, c), (r, c + 1))
        end
    end
    println("[PASS] T3 Hamiltonian: 4+4 terms, Pauli ops square to I, incidence matches M1"); flush(stdout)

    # T4: closed-form Pauli gate equals dense matrix exponential
    A3 = phys_tmap(STAR_A_mat(), 3)
    g = pauli_gate3(A3, 0.05, 1.0)
    gref = TensorMap(exp(0.05 * STAR_A_mat()), PSPACE^3, PSPACE^3)
    @test g ≈ gref
    println("[PASS] T4 Pauli gate closed form == dense exp"); flush(stdout)

    # T5: SU circuit — 8 gates, all on NN-connected paths of the (2,2) cell
    circuit = build_su_circuit(0.05)
    @test length(circuit.gates) == 8
    for (sites, gate) in circuit.gates
        @test length(sites) == 3
        for i in 1:2
            d = abs(sites[i][1] - sites[i + 1][1]) + abs(sites[i][2] - sites[i + 1][2])
            @test d == 1
        end
    end
    println("[PASS] T5 SU circuit: 8 three-site MPO gates on NN paths"); flush(stdout)

    # T6: one su_iter step preserves the Z₂ grading (spaces unchanged)
    Random.seed!(1234)
    Vd2 = vspace(2)
    ψ = InfinitePEPS(randn, ComplexF64, fill(PSPACE, 2, 2), fill(Vd2, 2, 2))
    alg = SimpleUpdate(; trunc = PEPSKit._get_fixedspacetrunc(ψ), imaginary_time = true)
    env = init_suweight(ψ, vspace(2))
    ψ2, env2, ϵ = PEPSKit.su_iter(ψ, circuit, alg, env)
    @test all(space(ψ2.A[i]) == space(ψ.A[i]) for i in 1:4)
    println("[PASS] T6 su_iter preserves Z₂-graded spaces"); flush(stdout)

    # T7: energy normalization on the exact state (CTMRG, h = 0).
    # `expectation_value(peps, H, env)` must return the UNIT-CELL TOTAL:
    # E_cell = −8, per composite site = −2, per edge spin = −1.
    ψex = exact_peps()
    envex, _ = leading_boundary(CTMRGEnv(randn, ComplexF64, ψex, envspace(16)), ψex;
                                tol = 1e-9, maxiter = 300, verbosity = 0)
    H0, _ = toric_code_hamiltonian(0.0, 0.0)
    E_cell = real(expectation_value(ψex, H0, envex))
    # cross-check: raw total equals the sum of the 8 single-term evaluations
    lat = fill(PSPACE, 2, 2)
    term_sum = 0.0
    for r in 1:2, c in 1:2
        Hs = empty_localoperator(lat)
        PEPSKit.add_term!(Hs, [CartesianIndex(r, c - 1), CartesianIndex(r, c), CartesianIndex(r + 1, c)], star_op())
        Hp = empty_localoperator(lat)
        PEPSKit.add_term!(Hp, [CartesianIndex(r - 1, c), CartesianIndex(r, c), CartesianIndex(r, c + 1)], plaq_op())
        term_sum += real(expectation_value(ψex, Hs, envex)) + real(expectation_value(ψex, Hp, envex))
    end
    @test E_cell ≈ term_sum atol = 1e-10
    @test E_cell ≈ -8.0 atol = 1e-8
    @test E_cell / 4 ≈ -2.0 atol = 1e-8   # per composite PEPS site
    @test E_cell / 8 ≈ -1.0 atol = 1e-8   # per original edge spin
    println("[PASS] T7 normalization: E_cell = −8, per composite site = −2, per edge spin = −1")
    flush(stdout)
end

