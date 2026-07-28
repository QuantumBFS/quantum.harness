#!/usr/bin/env julia
# M1 — ω-tower module + gates (standalone; no QMBCertify dependency).
#
# State-picture coarse-grained LTI SDP per [B] arXiv:2412.07837 §2.3
# (Eqs. 2.13–2.17), decoded from the rendered equation images; THEOREM_CONTRACT
# §2 defines (T0)–(T4). All solves are numerical SDP lower bounds on the
# INFINITE-chain energy density (LTI relaxations); ED feasibility uses finite
# rings via Lemma 1 (n_tower ≤ N−1).
#
# GATE NOTE (measured tonight, reported to the operator): the previously
# specified "lossless equality" gate E_cg(4,unitary) == E_lti(4) is NOT a
# theorem — the links (T2)/(T3) trace out bond legs, which is lossy even for
# unitary W. Provable and enforced instead:
#   (G1)  sandwich  E_lti(3) − ε ≤ E_cg(4,W) ≤ E_lti(4) + ε   for ANY W
#   (G1b) strict oracle: CG(4) plus explicit ρ4 and the UNTRACED definition
#         ω4 == C(ρ4) must equal E_lti(4) to 1e-8 (validates the 𝒞-map code)
#   (G2)  flow composition (Lemma 2) residual ≤ 1e-12
#   (G3)  ED feasibility: translation-averaged ring ground-state marginals
#         satisfy every constraint to ≤ 1e-10 and give objective E0/N
#   (G4)  level monotonicity: E_cg(n+1) ≥ E_cg(n) − ε
#
# Usage: julia --project=julia-env tower.jl [outdir]

using JuMP, LinearAlgebra, Printf
using Mosek, MosekTools

const OUTDIR = length(ARGS) >= 1 ? ARGS[1] : "."
mkpath(OUTDIR)

include(joinpath(@__DIR__, "tower_lib.jl"))

# ------------------------------------------------------------- builders -----
"Uncompressed LTI relaxation to level n. Returns objective value."
function E_lti(n::Int)
    m = newmodel()
    ρ = Dict{Int,Any}()
    for M in 2:n
        ρ[M] = @variable(m, [1:2^M, 1:2^M] in HermitianPSDCone())
    end
    @constraint(m, real(tr(ρ[2])) == 1)
    for M in 3:n
        ceq!(m, ptr_first(ρ[M], 2^(M-1)), ρ[M-1])
        ceq!(m, ptr_last(ρ[M], 2^(M-1)), ρ[M-1])
    end
    @objective(m, Min, real(tr(h2 * ρ[2])))
    optimize!(m)
    return objective_value(m), termination_status(m)
end

"""Compressed tower to level n (n ≥ 4) with uMPS tensors A (m-dim bonds).
mode = :traced  — the real [B] 2.15/2.16 links (T2/T3)
mode = :oracle  — additionally carries explicit ρ_M and the UNTRACED
                  definitions ω_M == C_M(ρ_M) (must reproduce E_lti(n))."""
function E_cg(n::Int, A::Vector{Matrix{ComplexF64}}; mode::Symbol = :traced)
    mm = size(A[1], 1)
    dω = 2 * mm * mm * 2
    m = newmodel()
    ρ2 = @variable(m, [1:4, 1:4] in HermitianPSDCone())
    ρ3 = @variable(m, [1:8, 1:8] in HermitianPSDCone())
    ω = Dict{Int,Any}()
    for M in 4:n
        ω[M] = @variable(m, [1:dω, 1:dω] in HermitianPSDCone())
    end
    @constraint(m, real(tr(ρ2)) == 1)
    ceq!(m, ptr_first(ρ3, 4), ρ2)
    ceq!(m, ptr_last(ρ3, 4), ρ2)

    W2 = chainmap(A, 2)                       # (m²)×4
    # T2: boundary links.  ω4 legs (2, m, m, 2).
    #   left version: trace (J, μ4) of ω4  ==  Tr_J[(I⊗W2) ρ3 (I⊗W2)†]
    X = kron(σI, W2)                          # (2m²)×8
    G = X * ρ3 * X'                           # legs (2, m, m) [I then J]
    lhsL = ptr_last(ptr_mid_wrap(ω[4], 2 * mm, mm, 2), 2 * mm)   # trace μ4 then J
    rhsL = ptr_mid_wrap(G, 2 * mm, mm, 1)                        # trace J of (2,m,m)
    ceq!(m, lhsL, rhsL)
    #   right version: trace (μ1, I) of ω4 == Tr_I[(W2⊗I) ρ3 (W2⊗I)†]
    X2 = kron(W2, σI)                         # legs (m,m,2) [I,J,site]
    G2 = X2 * ρ3 * X2'
    lhsR = ptr_first(ptr_mid_left(ω[4], 2, mm, mm * 2), mm * 2)  # trace I then μ1
    rhsR = ptr_first_m(G2, mm, mm * 2)                            # trace I of (m,m,2)
    ceq!(m, lhsR, rhsR)

    # T3: tower links for M ≥ 4
    Bm = bmat(A); BmL = bmat_left(A)
    for M in 4:(n-1)
        # right: trace (J, μ_{M+1}) of ω_{M+1} == Tr_K[(I_{2m} ⊗ Bm) ω_M (…)†]
        TR = kron(Matrix{ComplexF64}(I, 2 * mm, 2 * mm), Bm)      # (2m·m)×(2m·m·2)
        YR = TR * ω[M] * TR'                                       # legs (2, m, K=m)
        # leg order: ω_{M+1} legs (2, m, m, 2): trace last phys -> (2,m,m); then trace J (last) -> (2,m)
        lhs = ptr_last_m(ptr_last(ω[M+1], 2 * mm * mm), 2 * mm, mm)
        rhs = ptr_last_m(YR, 2 * mm, mm)
        ceq!(m, lhs, rhs)
        # left: trace (μ1, I) of ω_{M+1} == Tr_K[(BmL ⊗ I_{m·2}) ω_M (…)†]
        TL = kron(BmL, Matrix{ComplexF64}(I, mm * 2, mm * 2))     # (m·m·2)×(2m·m·2)
        YL = TL * ω[M] * TL'                                       # legs (K=m, m, 2)
        lhs2 = ptr_first_m(ptr_first(ω[M+1], mm * mm * 2), mm, mm * 2)
        rhs2 = ptr_first_m(YL, mm, mm * 2)
        ceq!(m, lhs2, rhs2)
    end

    if mode == :oracle
        ρprev = ρ3
        for M in 4:n
            ρM = @variable(m, [1:2^M, 1:2^M] in HermitianPSDCone())
            ceq!(m, ptr_first(ρM, 2^(M-1)), ρprev)
            ceq!(m, ptr_last(ρM, 2^(M-1)), ρprev)
            C = cmat(chainmap(A, M - 2), mm)
            ceq!(m, ω[M], C * ρM * C')
            ρprev = ρM
        end
    end

    @objective(m, Min, real(tr(h2 * ρ2)))
    optimize!(m)
    return objective_value(m), termination_status(m)
end


# ----------------------------------------------------------------- gates ----

function main()
    results = String[]
    ok = true
    push!(results, "== M1 tower gates ==")

    # G2 flow composition (Lemma 2): W_{k+1} == contract(W_k, A) as matrices
    A = random_left_canonical(2)
    for k in 2:4
        Wk = chainmap(A, k); Wk1 = chainmap(A, k + 1)
        mm = 2
        # right-extension: (W_{k+1})_{(I,J),(μs,ν)} = Σ_K (W_k)_{(I,K),μs} A^ν[K,J]
        W_built = zeros(ComplexF64, mm * mm, 2^(k + 1))
        for col in 1:2^k, ν in 1:2
            for I in 1:mm, J in 1:mm, K in 1:mm
                W_built[(I-1)*mm+J, (col-1)*2+ν] += Wk[(I-1)*mm+K, col] * A[ν][K, J]
            end
        end
        r = maximum(abs, W_built - Wk1)
        push!(results, @sprintf("G2 flow k=%d->%d residual %.2e %s", k, k + 1, r, r <= 1e-12 ? "PASS" : "FAIL"))
        ok &= r <= 1e-12
    end

    # G1 + G1b at n=4 with an explicit unitary W2 (χ=4, m=2 bond pair)
    U = Matrix(qr(randn(ComplexF64, 4, 4)).Q)                    # unitary 4×4
    Au = [Matrix{ComplexF64}(undef, 2, 2) for _ in 1:2]          # decode U as chain of 2? Not generally an MPS chain —
    # For the unitary oracle we bypass chainmap: monkey-pass W2 directly.
    e3, s3 = E_lti(3); e4, s4 = E_lti(4)
    ecg, scg = E_cg_unitary(4, U)
    eor, sor = E_cg_unitary(4, U; oracle = true)
    push!(results, @sprintf("E_lti(3)=%.10f (%s)  E_lti(4)=%.10f (%s)", e3, s3, e4, s4))
    push!(results, @sprintf("G1  sandwich: E_cg(4,U)=%.10f (%s)  [lti3-1e-8 ≤ cg ≤ lti4+1e-8] %s",
        ecg, scg, (e3 - 1e-8 <= ecg <= e4 + 1e-8) ? "PASS" : "FAIL"))
    ok &= (e3 - 1e-8 <= ecg <= e4 + 1e-8)
    push!(results, @sprintf("G1b strict oracle: E=%.10f (%s) |Δ vs lti4|=%.2e %s",
        eor, sor, abs(eor - e4), abs(eor - e4) <= 1e-8 ? "PASS" : "FAIL"))
    ok &= abs(eor - e4) <= 1e-8
    push!(results, @sprintf("    measured lossless-equality claim: |E_cg−E_lti4|=%.2e (expected NONZERO — traced links are lossy; see GATE NOTE)",
        abs(ecg - e4)))

    # G4 level monotonicity with MPS tensors, n=4 -> 5 -> 6
    es = Float64[]
    for n in 4:6
        e, s = E_cg(n, A)
        push!(es, e)
        push!(results, @sprintf("E_cg(%d, mps m=2) = %.10f (%s)", n, e, s))
    end
    mono = all(es[i+1] >= es[i] - 1e-8 for i in 1:length(es)-1)
    push!(results, "G4 monotone in n: " * (mono ? "PASS" : "FAIL"))
    ok &= mono

    # G3 ED feasibility, N=8: translation-averaged ground state marginals
    g3ok, g3msg = ed_feasibility(8, 6, A)
    append!(results, g3msg); ok &= g3ok

    for l in results
        println(l)
    end
    open(joinpath(OUTDIR, "tower_gates.log"), "a") do io
        for l in results
            println(io, l)
        end
    end
    println(ok ? "M1 GATES: PASS (with GATE NOTE measured)" : "M1 GATES: FAIL")
    exit(ok ? 0 : 1)
end

# unitary-W2 variant: n=4 only (no T3 levels), W2 given directly as 4×4
function E_cg_unitary(n::Int, W2::Matrix{ComplexF64}; oracle::Bool = false)
    @assert n == 4
    mm = 2; dω = 16
    m = newmodel()
    ρ2 = @variable(m, [1:4, 1:4] in HermitianPSDCone())
    ρ3 = @variable(m, [1:8, 1:8] in HermitianPSDCone())
    ω4 = @variable(m, [1:dω, 1:dω] in HermitianPSDCone())
    @constraint(m, real(tr(ρ2)) == 1)
    ceq!(m, ptr_first(ρ3, 4), ρ2)
    ceq!(m, ptr_last(ρ3, 4), ρ2)
    X = kron(σI, W2); G = X * ρ3 * X'
    ceq!(m, ptr_last(ptr_last_m(ω4, 2 * mm * mm, 2), 2 * mm),   # trace μ4 -> (2,m,m); then J
         ptr_last_m(G, 2 * mm, mm))
    # NOTE: composite trace: first μ4 (last dim 2), then J (now last dim m)
    X2 = kron(W2, σI); G2 = X2 * ρ3 * X2'
    ceq!(m, ptr_first(ptr_first_m(ω4, 2, mm * mm * 2), mm * 2),
         ptr_first_m(G2, mm, mm * 2))
    if oracle
        ρ4 = @variable(m, [1:16, 1:16] in HermitianPSDCone())
        ceq!(m, ptr_first(ρ4, 8), ρ3)
        ceq!(m, ptr_last(ρ4, 8), ρ3)
        C = kron(σI, W2, σI)
        ceq!(m, ω4, C * ρ4 * C')
    end
    @objective(m, Min, real(tr(h2 * ρ2)))
    optimize!(m)
    return objective_value(m), termination_status(m)
end

# G3: exact-diagonalization feasibility on the N-ring, tower to n levels
function ed_feasibility(N::Int, n::Int, A)
    # dense ground state of H = Σ S·S (PBC) on N qubits
    dim = 2^N
    H = zeros(Float64, dim, dim)
    for s in 0:(dim-1)
        for b in 0:(N-1)
            b2 = (b + 1) % N
            u = (s >> b) & 1; v = (s >> b2) & 1
            if u == v
                H[s+1, s+1] += 0.25
            else
                H[s+1, s+1] -= 0.25
                t = s ⊻ ((1 << b) | (1 << b2))
                H[t+1, s+1] += 0.5
            end
        end
    end
    F = eigen(Symmetric(H), 1:1)
    E0 = F.values[1]; ψ = F.vectors[:, 1]
    # translation-averaged density: ρ = (1/N) Σ_t T^t |ψ⟩⟨ψ| T^{-t}; realize by
    # averaging marginals over all N window positions instead (equivalent).
    msgs = String[]; ok = true
    marg = Dict{Int,Matrix{ComplexF64}}()
    for M in 2:n
        ρM = zeros(ComplexF64, 2^M, 2^M)
        for pos in 0:(N-1)
            ρM .+= window_marginal(ψ, N, pos, M)
        end
        ρM ./= N
        marg[M] = ρM
    end
    e2 = real(tr(h2 * marg[2]))
    push!(msgs, @sprintf("G3 ED N=%d: tr(h ρ2)=%.12f vs E0/N=%.12f |Δ|=%.2e %s",
        N, e2, E0 / N, abs(e2 - E0 / N), abs(e2 - E0 / N) <= 1e-10 ? "PASS" : "FAIL"))
    ok &= abs(e2 - E0 / N) <= 1e-10
    # LTI residuals
    for M in 3:n
        r = max(maximum(abs, ptr_first(marg[M], 2^(M-1)) - marg[M-1]),
                maximum(abs, ptr_last(marg[M], 2^(M-1)) - marg[M-1]))
        push!(msgs, @sprintf("G3 LTI M=%d residual %.2e %s", M, r, r <= 1e-10 ? "PASS" : "FAIL"))
        ok &= r <= 1e-10
    end
    # tower links with MPS A: ω_M := C(ρ_M); check T2/T3 + PSD
    mm = size(A[1], 1)
    ω = Dict(M => (C = kron(σI, chainmap(A, M - 2), σI); C * marg[M] * C') for M in 4:n)
    W2 = chainmap(A, 2)
    X = kron(σI, W2); G = X * marg[3] * X'
    rT2 = maximum(abs, ptr_last_m(ptr_last(ω[4], 2 * mm * mm), 2 * mm, mm) - ptr_last_m(G, 2 * mm, mm))
    push!(msgs, @sprintf("G3 T2 residual %.2e %s", rT2, rT2 <= 1e-10 ? "PASS" : "FAIL"))
    ok &= rT2 <= 1e-10
    Bm = bmat(A)
    for M in 4:(n-1)
        TR = kron(Matrix{ComplexF64}(I, 2 * mm, 2 * mm), Bm)
        rT3 = maximum(abs, ptr_last_m(ptr_last(ω[M+1], 2 * mm * mm), 2 * mm, mm) -
                           ptr_last_m(TR * ω[M] * TR', 2 * mm, mm))
        push!(msgs, @sprintf("G3 T3 M=%d residual %.2e %s", M, rT3, rT3 <= 1e-10 ? "PASS" : "FAIL"))
        ok &= rT3 <= 1e-10
        λ = eigmin(Hermitian(ω[M]))
        push!(msgs, @sprintf("G3 ω_%d min-eig %.2e %s", M, λ, λ >= -1e-10 ? "PASS" : "FAIL"))
        ok &= λ >= -1e-10
    end
    return ok, msgs
end


main()
