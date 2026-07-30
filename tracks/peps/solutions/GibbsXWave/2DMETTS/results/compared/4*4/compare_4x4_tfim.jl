#!/usr/bin/env julia
# compare_4x4_tfim.jl — 2-panel version
# Panel 1: Energy per site vs T = 1/β (log x), all three methods
# Panel 2: Relative deviation |E - E_QMC|/|E_QMC| vs T (log x)
#
# Usage: julia compare_4x4_tfim.jl

using CairoMakie
using JLD2
using DelimitedFiles
using Printf

# ── Paths ──────────────────────────────────────────────────────────
const DATADIR = @__DIR__
const METTS_FILE = joinpath(DATADIR, "beta_scan_L4_J1_h0p5_D2_chi16.csv")
const TANTRG_FILE = joinpath(DATADIR, "OL4x4_J1.0_D512.jld2")
const QMC_AGG_FILE = joinpath(DATADIR,
    "notes", "assets", "qmc-xu-peps-metts-2026-07-28",
    "tfim-sse-xu-peps-metts-aggregate-2026-07-28.csv")

const N = 16  # 4×4 lattice

# ═══════════════════════════════════════════════════════════════════
# 1. Load PEPS-METTS (100 points, β = 0.1 .. 10.0)
# ═══════════════════════════════════════════════════════════════════
metts_raw = readdlm(METTS_FILE, ',', Float64, skipstart=1)
metts_beta = metts_raw[:, 1]
metts_E_ps = metts_raw[:, 4]
metts_E_se = metts_raw[:, 5]
metts_T    = 1.0 ./ metts_beta

# ═══════════════════════════════════════════════════════════════════
# 2. Load tanTRG (34 points)
# ═══════════════════════════════════════════════════════════════════
jld = jldopen(TANTRG_FILE, "r")
trg_beta = copy(jld["lsβ"])
trg_E    = copy(jld["lsE"])
close(jld)
trg_E_ps = trg_E ./ N
trg_T    = 1.0 ./ trg_beta

# ═══════════════════════════════════════════════════════════════════
# 3. Load QMC SSE (10 points, β = 1 .. 10, 4×4 only)
# ═══════════════════════════════════════════════════════════════════
qmc_raw = readdlm(QMC_AGG_FILE, ',', skipstart=1)
qmc_4x4 = qmc_raw[(qmc_raw[:,3].==4).&(qmc_raw[:,4].==4), :]
qmc_beta  = qmc_4x4[:, 8]
qmc_E_ps  = qmc_4x4[:, 13] ./ N
qmc_E_se  = qmc_4x4[:, 16] ./ N
qmc_T     = 1.0 ./ qmc_beta

# ═══════════════════════════════════════════════════════════════════
# 4. Compute relative deviation from QMC (at QMC β grid)
# ═══════════════════════════════════════════════════════════════════

# Interpolate tanTRG to QMC β grid
function lerp_trg(beta)
    if beta <= trg_beta[1];  return trg_E_ps[1]
    elseif beta >= trg_beta[end]; return trg_E_ps[end]
    end
    i = searchsortedlast(trg_beta, beta)
    t = (beta - trg_beta[i]) / (trg_beta[i+1] - trg_beta[i])
    return trg_E_ps[i] * (1 - t) + trg_E_ps[i+1] * t
end

trg_at_qmc = [lerp_trg(b) for b in qmc_beta]

# METTS at nearest β to QMC grid
metts_at_qmc = Float64[]
metts_se_at_qmc = Float64[]
for b in qmc_beta
    i = argmin(abs.(metts_beta .- b))
    push!(metts_at_qmc, metts_E_ps[i])
    push!(metts_se_at_qmc, metts_E_se[i])
end

# Relative error = |E - E_QMC| / |E_QMC|
metts_rel_err = abs.(metts_at_qmc .- qmc_E_ps) ./ abs.(qmc_E_ps)
trg_rel_err   = abs.(trg_at_qmc .- qmc_E_ps) ./ abs.(qmc_E_ps)

# Relative error bars: sqrt(SE_method² + SE_QMC²) / |E_QMC|
metts_rel_se = sqrt.(metts_se_at_qmc.^2 .+ qmc_E_se.^2) ./ abs.(qmc_E_ps)
trg_rel_se   = qmc_E_se ./ abs.(qmc_E_ps)   # tanTRG is deterministic

# ── Colours ───────────────────────────────────────────────────────
c_metts = :steelblue
c_trg   = :darkorange
c_qmc   = :darkgreen

# ═══════════════════════════════════════════════════════════════════
# 5. Figure
# ═══════════════════════════════════════════════════════════════════
fig = Figure(size=(1200, 520), fontsize=13)

# ── Panel A: Energy per site vs T ──────────────────────────────────
axA = Axis(fig[1, 1],
    xlabel = L"$T = 1/\beta$",
    ylabel = L"$E / N$",
    title  = L"4$\times$4 TFIM, $J=1$, $h=0.5$, OBC",
    xscale = log10,
    xminorticksvisible = true,
    xminorticks = IntervalsBetween(9),

)
ylims!(axA, (-1.548, -1.54))
xlims!(axA, (0.1, 1.0))
# tanTRG line (finest grid)
lines!(axA, trg_T, trg_E_ps,
    color = c_trg, linewidth = 2.5, label = "tanTRG (D=512)")

# PEPS-METTS scatter + error bars
scatter!(axA, metts_T, metts_E_ps,
    color = c_metts, markersize = 5, label = "PEPS-METTS (D=2, χ=16)")
errorbars!(axA, metts_T, metts_E_ps, metts_E_se,
    color = c_metts, linewidth = 0.8, whiskerwidth = 6)

# QMC scatter + error bars
scatter!(axA, qmc_T, qmc_E_ps,
    color = c_qmc, markersize = 9, marker = :diamond,
    label = "SSE-QMC")
errorbars!(axA, qmc_T, qmc_E_ps, qmc_E_se,
    color = c_qmc, linewidth = 1.2, whiskerwidth = 8)

axislegend(axA, position = :lb, fontsize = 11)

# ── Panel B: Relative deviation from QMC vs T ──────────────────────
axB = Axis(fig[1, 2],
    xlabel = L"$T = 1/\beta$",
    ylabel = L"$|E - E_{\mathrm{QMC}}| \,/\, |E_{\mathrm{QMC}}|$",
    title  = "Relative deviation from SSE-QMC",
    xscale = log10,
    yscale = log10,
    xminorticksvisible = true,
    yminorticksvisible = true,
    xminorticks = IntervalsBetween(9),
)

eps_y = 1e-16

# PEPS-METTS relative error
m_rel_low  = max.(eps_y, metts_rel_err .- metts_rel_se)
m_rel_high = metts_rel_err .+ metts_rel_se
scatter!(axB, qmc_T, metts_rel_err,
    color = c_metts, markersize = 9, label = "PEPS-METTS")
rangebars!(axB, qmc_T, m_rel_low, m_rel_high,
    color = c_metts, whiskerwidth = 8, linewidth = 1.2)

# tanTRG relative error
t_rel_low  = max.(eps_y, trg_rel_err .- trg_rel_se)
t_rel_high = trg_rel_err .+ trg_rel_se
scatter!(axB, qmc_T, trg_rel_err,
    color = c_trg, markersize = 9, marker = :utriangle,
    label = "tanTRG (D=512)")
rangebars!(axB, qmc_T, t_rel_low, t_rel_high,
    color = c_trg, whiskerwidth = 8, linewidth = 1.2)

axislegend(axB, position = :rt, fontsize = 11)

# ── Save ────────────────────────────────────────────────────────────
colgap!(fig.layout, 20)
outfile = joinpath(DATADIR, "compare_4x4_tfim.pdf")
save(outfile, fig)
println("Saved to: ", outfile)

# ── Summary table ───────────────────────────────────────────────────
println("\n─── Relative deviation from SSE-QMC ───")
println("  T       QMC(E/N)       METTS(E/N)     |Δ|/|QMC|    tanTRG(E/N)    |Δ|/|QMC|")
for (i, T) in enumerate(qmc_T)
    q = qmc_E_ps[i]
    m = metts_at_qmc[i]
    t = trg_at_qmc[i]
    @printf("%5.2f   %+.10f   %+.10f   %.2e   %+.10f   %.2e\n",
        T, q, m, metts_rel_err[i], t, trg_rel_err[i])
end
println("\nDone.")
