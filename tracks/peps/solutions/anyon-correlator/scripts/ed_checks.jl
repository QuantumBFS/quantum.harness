# M1 — Toric-code Hamiltonian on the 2×2 periodic torus + ED unit checks.
# Conventions (PLAN.md §2): H = −Jₑ Σₛ Aₛ − Jₘ Σₚ B_p − hₓ Σᵢ Xᵢ − h_z Σᵢ Zᵢ,
# Jₑ = Jₘ = 1; Aₛ = ∏_{i∈s} Xᵢ (stars), B_p = ∏_{i∈p} Zᵢ (plaquettes); spins on edges.
# 2×2 torus: 4 vertices, 8 edge spins, 4 stars, 4 plaquettes (each 4-body).
#
# Usage: julia --project=julia-env scripts/ed_checks.jl  (writes CSV + prints checks)
#        julia --project=julia-env tests/runtests.jl     (testset, no CSV)

using LinearAlgebra
using Printf
using Dates

# ---------- lattice geometry (2×2, mod-2 arithmetic) ----------
# vertices (x,y), x,y ∈ {0,1}. Horizontal edge h(x,y): (x,y)→(x+1,y);
# vertical edge v(x,y): (x,y)→(x,y+1). Spin index: h(x,y) → 1+x+2y (1..4),
# v(x,y) → 5+x+2y (5..8).

const NSPIN = 8
hedge(x, y) = 1 + mod(x, 2) + 2 * mod(y, 2)
vedge(x, y) = 5 + mod(x, 2) + 2 * mod(y, 2)

"Edges of the star at vertex (x,y): h(x,y), h(x−1,y), v(x,y), v(x,y−1)."
star_edges(x, y) = [hedge(x, y), hedge(x - 1, y), vedge(x, y), vedge(x, y - 1)]

"Edges of the plaquette with lower-left corner (x,y): h(x,y), h(x,y+1), v(x,y), v(x+1,y)."
plaquette_edges(x, y) = [hedge(x, y), hedge(x, y + 1), vedge(x, y), vedge(x + 1, y)]

const STARS = [star_edges(x, y) for x in 0:1, y in 0:1][:]
const PLAQUETTES = [plaquette_edges(x, y) for x in 0:1, y in 0:1][:]

# ---------- 8-qubit operator construction ----------
const XMAT = ComplexF64[0 1; 1 0]
const ZMAT = ComplexF64[1 0; 0 -1]
const I2 = ComplexF64[1 0; 0 1]

"Single-spin operator P acting on site i of NSPIN qubits."
function op_on_site(P, i)
    ops = fill(I2, NSPIN)
    ops[i] = P
    return kron(ops...)
end

const XOPS = [op_on_site(XMAT, i) for i in 1:NSPIN]
const ZOPS = [op_on_site(ZMAT, i) for i in 1:NSPIN]

"Aₛ = ∏ X on star s; B_p = ∏ Z on plaquette p — built via prod_ops."
function prod_ops(ops)
    M = ops[1]
    for k in 2:length(ops)
        M = M * ops[k]
    end
    return M
end

const AOPS = [prod_ops(XOPS[s]) for s in STARS]        # star terms
const BOPS = [prod_ops(ZOPS[p]) for p in PLAQUETTES]   # plaquette terms

"Full Hamiltonian H(hₓ, h_z; Jₑ, Jₘ), PLAN.md C1 convention (Jₑ = Jₘ = 1 default)."
function hamiltonian(hx, hz; Je = 1.0, Jm = 1.0)
    H = -Je * sum(AOPS) - Jm * sum(BOPS)
    for i in 1:NSPIN
        H = H - hx * XOPS[i] - hz * ZOPS[i]
    end
    return Hermitian(H)
end

"(E₀, gap above the ground space, degeneracy at tol) of H(hₓ, h_z)."
function spectrum0(hx, hz; tol = 1e-9, kwargs...)
    vals = eigvals(hamiltonian(hx, hz; kwargs...))
    E0 = vals[1]
    degen = count(v -> v < E0 + tol, vals)
    gap = degen < length(vals) ? vals[degen + 1] - E0 : NaN
    return (E0 = E0, gap = gap, degen = degen)
end

# ---------- operator-level construction checks (small tests) ----------
"Geometry + algebra checks that validate the construction before any spectrum is trusted."
function check_operators()
    msgs = String[]
    ok = true
    # incidence structure: every edge in exactly 2 stars and 2 plaquettes
    for i in 1:NSPIN
        ns = count(s -> i in s, STARS)
        np = count(p -> i in p, PLAQUETTES)
        (ns == 2 && np == 2) || (ok = false; push!(msgs, "edge $i incidence ($ns stars, $np plaquettes)"))
    end
    # every star/plaquette has exactly 4 distinct edges
    for s in STARS
        length(unique(s)) == 4 || (ok = false; push!(msgs, "star $s not 4 distinct edges"))
    end
    for p in PLAQUETTES
        length(unique(p)) == 4 || (ok = false; push!(msgs, "plaquette $p not 4 distinct edges"))
    end
    # involutions: Aₛ² = B_p² = I
    IE = Matrix{ComplexF64}(I, 2^NSPIN, 2^NSPIN)
    for (k, A) in enumerate(AOPS)
        norm(A * A - IE) < 1e-12 || (ok = false; push!(msgs, "A_$k not an involution"))
    end
    for (k, B) in enumerate(BOPS)
        norm(B * B - IE) < 1e-12 || (ok = false; push!(msgs, "B_$k not an involution"))
    end
    # mutual commutation of all stabilizers
    for (i, A) in enumerate(AOPS), (j, B) in enumerate(BOPS)
        norm(A * B - B * A) < 1e-12 || (ok = false; push!(msgs, "[A_$i, B_$j] ≠ 0"))
    end
    for i in 1:4, j in (i + 1):4
        norm(AOPS[i] * AOPS[j] - AOPS[j] * AOPS[i]) < 1e-12 || (ok = false; push!(msgs, "[A_$i, A_$j] ≠ 0"))
        norm(BOPS[i] * BOPS[j] - BOPS[j] * BOPS[i]) < 1e-12 || (ok = false; push!(msgs, "[B_$i, B_$j] ≠ 0"))
    end
    # stars commute with the X-field (structural identity along the (hₓ,0) axis)
    Hxf = sum(XOPS)
    for (i, A) in enumerate(AOPS)
        norm(A * Hxf - Hxf * A) < 1e-12 || (ok = false; push!(msgs, "[A_$i, ΣX] ≠ 0"))
    end
    return ok, msgs
end

# ---------- acceptance gates (PLAN.md §6 M1) ----------
# G1–G3: construction correctness (operator algebra, h=0 anchor, stabilizers).
# G4–G6: physics sanity (self-duality, monotonicity, large-field limits).
# Gate semantics: "gap" = first excitation above the (degenerate) ground space;
# large-field windows are derived from [Aₛ, ΣX] = 0, not fitted tolerances.
function acceptance_gates()
    results = NamedTuple[]
    # G1: operator-level construction
    ok, msgs = check_operators()
    push!(results, (gate = "G1 operator construction (incidence, involutions, commutation, [A,ΣX]=0)", passed = ok,
                    detail = ok ? "all operator checks passed" : join(msgs, "; ")))
    # G2: E₀(0,0) = −8, degeneracy 4, gap 4
    r0 = spectrum0(0.0, 0.0)
    ok = abs(r0.E0 + 8.0) < 1e-10 && r0.degen == 4 && abs(r0.gap - 4.0) < 1e-9
    push!(results, (gate = "G2 h=0 anchor: E₀ = −8, degeneracy 4, gap 4", passed = ok,
                    detail = @sprintf("E₀ = %.12f, degeneracy %d, gap %.6f", r0.E0, r0.degen, r0.gap)))
    # G3: stabilizer expectation in every ground state: ⟨Aₛ⟩ = ⟨B_p⟩ = 1
    H0 = hamiltonian(0.0, 0.0)
    vals, vecs = eigen(H0)
    gs = vecs[:, vals .< vals[1] + 1e-9]
    maxdev = maximum(1:4) do k
        maximum(abs, [real(dot(v, AOPS[k], v)) - 1 for v in eachcol(gs)])
    end
    maxdevp = maximum(1:4) do k
        maximum(abs, [real(dot(v, BOPS[k], v)) - 1 for v in eachcol(gs)])
    end
    ok = max(maxdev, maxdevp) < 1e-10
    push!(results, (gate = "G3 all 4 ground states stabilized: ⟨Aₛ⟩ = ⟨B_p⟩ = 1", passed = ok,
                    detail = @sprintf("max |⟨A⟩−1| = %.2e, max |⟨B⟩−1| = %.2e", maxdev, maxdevp)))
    # G4: self-duality E₀(hₓ, h_z) = E₀(h_z, hₓ)
    d1 = abs(spectrum0(0.3, 0.0).E0 - spectrum0(0.0, 0.3).E0)
    d2 = abs(spectrum0(0.2, 0.4).E0 - spectrum0(0.4, 0.2).E0)
    ok = max(d1, d2) < 1e-12
    push!(results, (gate = "G4 self-duality E₀(hₓ,h_z) = E₀(h_z,hₓ)", passed = ok,
                    detail = @sprintf("|Δ| = %.2e, %.2e", d1, d2)))
    # G5: monotonic decrease of E₀ along (hₓ, 0)
    hs = [0.0, 0.1, 0.2, 0.3, 0.5]
    es = [spectrum0(h, 0.0).E0 for h in hs]
    ok = all(diff(es) .< 0)
    push!(results, (gate = "G5 E₀ monotonically decreasing along (hₓ,0), h ≤ 0.5", passed = ok,
                    detail = @sprintf("E₀(h) = %s", join([@sprintf("%.4f", e) for e in es], ", "))))
    # G6: large-field axis limit. [Aₛ, ΣX] = 0 ⇒ E₀(hₓ,0) = −4Jₑ + e(hₓ), so
    # E₀/N → −hₓ − 1/2 (per spin, J = 1) with only O(Jₘ²/hₓ) plaquette dressing below.
    r5 = spectrum0(5.0, 0.0).E0 / NSPIN
    ok = -5.65 < r5 < -5.5
    push!(results, (gate = "G6a large field (5,0): E₀/N ∈ (−5.65, −5.5) [= −hₓ − Jₑ/2 window]", passed = ok,
                    detail = @sprintf("E₀/N = %.6f", r5)))
    # G6b: diagonal large field: E₀/N within [−√50 − 0.6, −√50] (O(J) first-order shift below)
    r55 = spectrum0(5.0, 5.0).E0 / NSPIN
    ok = -sqrt(50) - 0.6 < r55 < -sqrt(50)
    push!(results, (gate = "G6b large field (5,5): E₀/N ∈ (−√50 − 0.6, −√50)", passed = ok,
                    detail = @sprintf("E₀/N = %.6f, −√50 = %.6f", r55, -sqrt(50))))
    return results
end

# ---------- main: CSV + gate report ----------
function main()
    rundir = joinpath(@__DIR__, "..", "..", "..", "results", Dates.format(now(), "yyyymmdd-HHMMSS") * "-ed-checks")
    mkpath(rundir)
    grid = [(0.0, 0.0), (0.1, 0.0), (0.2, 0.0), (0.3, 0.0), (0.328, 0.0), (0.5, 0.0),
            (0.0, 0.3), (0.2, 0.2), (0.3, 0.3), (5.0, 0.0), (0.0, 5.0), (5.0, 5.0)]
    csv = joinpath(rundir, "ed_2x2.csv")
    open(csv, "w") do io
        println(io, "hx,hz,E0,E0_per_spin,gap,degeneracy")
        for (hx, hz) in grid
            r = spectrum0(hx, hz)
            println(io, @sprintf("%.3f,%.3f,%.12f,%.12f,%.9f,%d", hx, hz, r.E0, r.E0 / NSPIN, r.gap, r.degen))
            println(@sprintf("  point (%.3f, %.3f): E₀/N = %.8f, gap = %.6f", hx, hz, r.E0 / NSPIN, r.gap))
            flush(stdout)
        end
    end
    println("CSV written: $csv")
    flush(stdout)
    println("\n--- M1 acceptance gates ---")
    flush(stdout)
    allpass = true
    for g in acceptance_gates()
        status = g.passed ? "PASS" : "FAIL"
        allpass &= g.passed
        println(@sprintf("[%s] %s\n       %s", status, g.gate, g.detail))
        flush(stdout)
    end
    println(allpass ? "ALL M1 GATES PASSED" : "SOME GATES FAILED")
    flush(stdout)
    return allpass
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(main() ? 0 : 1)
end
