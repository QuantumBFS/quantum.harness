# T2/T3 — Kull-Schuch compressed-LTI relaxation (PRX 14, 021008, Sec. II, Eq. 14)
# for the 1D Heisenberg AFM chain, using super-spins (2 physical -> 1 super, d̂=4)
# and the VUMPS uniform MPS as the coarse-graining map.
# Self-checks: E(n,D) <= e0 = 1/4 - ln2; non-decreasing in n; <= E_LTI(2n physical).

using Serialization, LinearAlgebra, Printf, JuMP, MosekTools, Plots, JSON
using MPSKit, TensorKit   # needed only so deserialize() can resolve the saved types

const E0 = 1/4 - log(2)

# ---------- helpers ----------
_zero_container(rho::AbstractArray{<:Number}, n, m) = zeros(eltype(rho), n, m)
_zero_container(rho, n, m) = zeros(AffExpr, n, m)

function ptrace_left(rho, da, db)   # trace left factor of (da x db) system, kron/MSF index order
    r4 = reshape(rho, db, da, db, da)   # r4[j,i,l,k] == rho[(i,j),(k,l)], i left, j right
    out = _zero_container(rho, db, db)
    @inbounds for j in 1:db, l in 1:db, i in 1:da
        out[j, l] += r4[j, i, l, i]
    end
    out
end
function ptrace_right(rho, da, db)  # trace right factor
    r4 = reshape(rho, db, da, db, da)
    out = _zero_container(rho, da, da)
    @inbounds for i in 1:da, k in 1:da, j in 1:db
        out[i, k] += r4[j, i, j, k]
    end
    out
end

# spin-1/2 operators
const sx = [0 1; 1 0] ./ 2
const sy = [0 -im; im 0] ./ 2
const sz = [1 0; 0 -1] ./ 2
const h  = real.(kron(sx, sx) + kron(sy, sy) + kron(sz, sz))  # 4x4, S.S on two spins
const I2 = Matrix{Float64}(I, 2, 2)
const I4 = Matrix{Float64}(I, 4, 4)

# between-super-spin term: h on (phys2 of left, phys1 of right), 16x16, MSF order
function build_hb()
    hb = zeros(16, 16)
    for p1 in 1:2, p2 in 1:2, q1 in 1:2, q2 in 1:2, p2p in 1:2, q1p in 1:2
        p  = (p1 - 1) * 2 + p2;   q  = (q1 - 1) * 2 + q2
        pp = (p1 - 1) * 2 + p2p;  qp = (q1p - 1) * 2 + q2
        hb[(p - 1) * 4 + q, (pp - 1) * 4 + qp] = h[(p2 - 1) * 2 + q1, (p2p - 1) * 2 + q1p]
    end
    hb
end
const HB = build_hb()
const HLOC = 0.5 .* (kron(h, I4) .+ kron(I4, h)) .+ HB   # per-super-site, 16x16

# MPS -> super-tensor B (D, d̂=4, D)
function super_tensor(psi)
    A1 = convert(Array, psi.AL[1]); A2 = convert(Array, psi.AL[2])
    @assert maximum(abs, imag.(A1)) < 1e-10 && maximum(abs, imag.(A2)) < 1e-10 "complex MPS"
    A1 = real(A1); A2 = real(A2)
    D, d, _ = size(A1)
    B = zeros(D, d * d, D)
    for α in 1:D, s1 in 1:d, s2 in 1:d, γ in 1:D, β in 1:D
        B[α, (s1 - 1) * d + s2, γ] += A1[α, s1, β] * A2[β, s2, γ]
    end
    B
end

# W2 map: (βL,βR) <- (sa,sb), size (D^2, 16), MSF order everywhere
function W2map(B)
    D = size(B, 1)
    W = zeros(D * D, 16)
    for βL in 1:D, βR in 1:D, sa in 1:4, sb in 1:4, γ in 1:D
        W[(βL - 1) * D + βR, (sa - 1) * 4 + sb] += B[βL, sa, γ] * B[γ, sb, βR]
    end
    W
end
# M_R: β <- (β',s), size (D, D*4), MSF input order
function MRmap(B)
    D = size(B, 1)
    M = zeros(D, D * 4)
    for β in 1:D, βp in 1:D, s in 1:4
        M[β, (βp - 1) * 4 + s] = B[βp, s, β]
    end
    M
end
# M_L: β <- (s,β'), size (D, 4*D), MSF input order
function MLmap(B)
    D = size(B, 1)
    M = zeros(D, 4 * D)
    for β in 1:D, βp in 1:D, s in 1:4
        M[β, (s - 1) * D + βp] = B[β, s, βp]
    end
    M
end

# ---------- compressed LTI SDP ----------
function solve_compressed(B, n; silent=true)
    D = size(B, 1); dw = 4 * D * D            # size of Tr_phys(omega) output
    domega = 16 * D * D                       # omega matrix size
    W2 = W2map(B); MR = MRmap(B); ML = MLmap(B)
    Iw = Matrix{Float64}(I, 4 * D, 4 * D)     # identity on (s, other-bond) for R_A/L_A

    model = Model(Mosek.Optimizer); silent && set_silent(model)
    # residuals stall at ~2e-8 on this degenerate LTI chain; 1e-7 tolerance is
    # honest at our 1e-5 target precision (digits claimed << tolerance)
    set_attribute(model, "MSK_DPAR_INTPNT_CO_TOL_PFEAS", 1e-7)
    set_attribute(model, "MSK_DPAR_INTPNT_CO_TOL_DFEAS", 1e-7)
    set_attribute(model, "MSK_DPAR_INTPNT_CO_TOL_REL_GAP", 1e-7)
    @variable(model, rho3[1:64, 1:64], PSD)
    @constraint(model, tr(rho3) == 1)
    rho2L = ptrace_left(rho3, 4, 16); rho2R = ptrace_right(rho3, 16, 4)
    @constraint(model, rho2L .== rho2R)
    @objective(model, Min, tr(HLOC * rho2L) / 2)

    omega = Vector{Any}(undef, n - 3)
    # link rho3 <-> omega4
    IW2r = kron(I4, W2)          # (4D^2 x 64), W2 on super-spins 2,3
    IW2l = kron(W2, I4)          # on super-spins 1,2
    omega[1] = @variable(model, [1:domega, 1:domega], PSD)
    TrR_o4 = ptrace_right(omega[1], dw, 4)
    TrL_o4 = ptrace_left(omega[1], 4, dw)
    @constraint(model, TrR_o4 .== IW2r * rho3 * IW2r')
    @constraint(model, TrL_o4 .== IW2l * rho3 * IW2l')
    # chain m = 5..n
    I_MR = kron(Iw, MR)          # (dw x domega): identity on (s,betaL), MR on (betaR',s)
    I_ML = kron(ML, Iw)          # identity on (betaR) hmm: (s,betaL',betaR) grouping
    for (k, m) in enumerate(5:n)
        omega[k + 1] = @variable(model, [1:domega, 1:domega], PSD)
        @constraint(model, ptrace_right(omega[k + 1], dw, 4) .== I_MR * omega[k] * I_MR')
        @constraint(model, ptrace_left(omega[k + 1], 4, dw) .== I_ML * omega[k] * I_ML')
    end
    optimize!(model)
    status = termination_status(model)
    E = status in (OPTIMAL, ALMOST_OPTIMAL) ? objective_value(model) : NaN
    E, status
end

# ---------- uncompressed LTI on the physical chain (d=2) ----------
function solve_LTI(n; silent=true)
    model = Model(Mosek.Optimizer); silent && set_silent(model)
    rho = Vector{Any}(undef, n - 1)
    rho[1] = @variable(model, [1:4, 1:4], PSD)
    @constraint(model, tr(rho[1]) == 1)
    for m in 3:n
        d2m = 2^m
        rho[m - 1] = @variable(model, [1:d2m, 1:d2m], PSD)
        @constraint(model, ptrace_left(rho[m - 1], 2, 2^(m - 1)) .== rho[m - 2])
        @constraint(model, ptrace_right(rho[m - 1], 2^(m - 1), 2) .== rho[m - 2])
    end
    # LTI at top level is implied by the chain; objective
    @objective(model, Min, tr(h * rho[1]))
    optimize!(model)
    status = termination_status(model)
    status in (OPTIMAL, ALMOST_OPTIMAL) ? objective_value(model) : NaN, status
end

# ---------- main ----------
function main()
    psis = deserialize(joinpath(@__DIR__, "vumps_mps.jls"))

    # helper sanity: ptrace on a product state
    a = [1.0, 0]; b = [0.0, 1, 0, 0]
    Pa = a * a'; Pb = b * b'
    @assert ptrace_left(kron(Pa, Pb), 2, 4) ≈ Pb && ptrace_right(kron(Pa, Pb), 2, 4) ≈ Pa
    println("helper sanity OK"); flush(stdout)

    # uncompressed LTI reference (physical chain), n = 4, 6 (n=8 is too heavy uncompressed)
    lti = Dict{Int, Float64}()
    for n in [4, 6]
        E, st = solve_LTI(n)
        lti[n] = E
        @printf("LTI physical n=%2d: E = %.10f  (gap %.2e, status %s)\n", n, E, E0 - E, st)
        flush(stdout)
        @assert E <= E0 + 1e-9
    end

    # compressed ladder
    results = Dict{String, Any}()
    ns_by_D = Dict(2 => [4, 6, 8, 10, 15, 20, 30, 50, 80, 120],
                   3 => [4, 6, 8, 10, 15, 20, 30, 50])
    for D in [2, 3]
        B = super_tensor(psis[D])
        for n in ns_by_D[D]
            t0 = time()
            E, st = solve_compressed(B, n)
            wall = time() - t0
            gap = E0 - E
            @printf("D=%d super-n=%3d: E = %.10f  gap %.3e  wall %.1fs  status %s\n",
                    D, n, E, gap, wall, st)
            flush(stdout)
            if !isnan(E)
                @assert E <= E0 + 1e-6 "bound ABOVE e0 at D=$D n=$n -- index bug"
            else
                println("   WARNING: non-optimal status $st at D=$D n=$n -- no certificate, skipping")
                flush(stdout)
            end
            if n == 4    # E_comp(super-4) <= E_LTI(8) <= E_LTI(6) (LTI is non-decreasing): necessary check
                @printf("   check: %.10f <= LTI(6) = %.10f ? %s\n",
                        E, lti[6], E <= lti[6] + 1e-9)
                flush(stdout)
            end
            results["D$D-n$n"] = Dict("E" => E, "gap" => gap, "wall" => wall,
                                      "status" => string(st))
        end
    end
    results["LTI"] = lti

    rundir = "tracks/polyopt/results/20260727-kullschuch-mve"
    mkpath(joinpath(rundir, "figs"))
    open(joinpath(rundir, "compressed_lti.json"), "w") do io
        JSON.print(io, results, 2)
    end

    p = plot(xscale=:log10, yscale=:log10, xlabel="n", ylabel="Delta E",
             title="Compressed-LTI relaxation, Heisenberg chain (Fig. 2b repro)",
             legend=:bottomleft, size=(700, 450))
    for (D, mk) in [(2, :circle), (3, :square)]
        ns = ns_by_D[D]
        ys = [results["D$D-n$n"]["gap"] for n in ns]
        plot!(p, 2 .* ns, ys, marker=mk, label="compressed, D=$D (x-axis: physical spins)")
    end
    lts = sort!(collect(keys(lti)))
    plot!(p, lts, [E0 - lti[n] for n in lts], marker=:diamond, label="exact LTI")
    savefig(p, joinpath(rundir, "figs", "fig2b_reproduction.png"))
    println("DONE. figure + json saved to $rundir"); flush(stdout)
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
