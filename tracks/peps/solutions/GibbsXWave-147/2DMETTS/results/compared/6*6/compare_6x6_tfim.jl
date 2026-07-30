#!/usr/bin/env julia
# compare_6x6_tfim.jl -- tanTRG and PEPS-METTS comparison
# Panel 1: Low-temperature energy density vs T = 1/beta
# Panel 2: Relative deviation |E_METTS - E_tanTRG| / |E_tanTRG|
#
# Usage:
#   julia compare_6x6_tfim.jl [data_directory] [output_directory]

using CairoMakie
using JLD2
using DelimitedFiles
using Printf

const DEFAULT_DATADIR = "/Users/chuanshu/Desktop/code/quantum harness/main_code/data/6*6"
const DATADIR = isempty(ARGS) ? DEFAULT_DATADIR : abspath(ARGS[1])
const OUTDIR = length(ARGS) < 2 ? DATADIR : abspath(ARGS[2])
const METTS_FILE = joinpath(DATADIR, "beta_scan_L6_J1_h0p5_D2_chi16.csv")
const TANTRG_FILE = joinpath(DATADIR, "OL6x6_J1.0_D512.jld2")
const N = 36

isfile(METTS_FILE) || error("PEPS-METTS file not found: $METTS_FILE")
isfile(TANTRG_FILE) || error("tanTRG file not found: $TANTRG_FILE")
mkpath(OUTDIR)

metts_raw = readdlm(METTS_FILE, ',', Float64, skipstart=1)
metts_order = sortperm(metts_raw[:, 1])
metts_beta = metts_raw[metts_order, 1]
metts_E_ps = metts_raw[metts_order, 4]
metts_E_se = metts_raw[metts_order, 5]
metts_T = 1.0 ./ metts_beta

jldopen(TANTRG_FILE, "r") do file
    global trg_beta = Float64.(file["lsβ"])
    global trg_E_ps = Float64.(file["lsE"]) ./ N
end
trg_T = 1.0 ./ trg_beta

low_temperature_metts = (metts_beta .>= 1.0) .& (metts_beta .<= 10.0)
low_temperature_trg = (trg_beta .>= 1.0) .& (trg_beta .<= 10.0)

function metts_index_at(beta; tolerance=1e-10)
    index = argmin(abs.(metts_beta .- beta))
    abs(metts_beta[index] - beta) <= tolerance ||
        error("No PEPS-METTS point matching beta=$beta")
    return index
end

shared_beta = trg_beta[low_temperature_trg]
shared_metts_indices = [metts_index_at(beta) for beta in shared_beta]
shared_T = 1.0 ./ shared_beta
shared_trg_E = trg_E_ps[low_temperature_trg]
shared_metts_E = metts_E_ps[shared_metts_indices]
shared_metts_se = metts_E_se[shared_metts_indices]

relative_error = abs.(shared_metts_E .- shared_trg_E) ./ abs.(shared_trg_E)
relative_se = shared_metts_se ./ abs.(shared_trg_E)
error_floor = 1e-16
relative_low = max.(error_floor, relative_error .- relative_se)
relative_high = relative_error .+ relative_se

c_metts = :steelblue
c_trg = :darkorange

fig = Figure(size=(1200, 520), fontsize=13)

axA = Axis(
    fig[1, 1],
    xlabel=L"$T = 1/\beta$",
    ylabel=L"$E / N$",
    title=L"6$\times$6 TFIM, $J=1$, $h=0.5$, OBC",
    xscale=log10,
    xminorticksvisible=true,
    xminorticks=IntervalsBetween(9),
)
xlims!(axA, (0.1, 1.0))
ylims!(axA, (-1.708, -1.702))

lines!(
    axA,
    trg_T[low_temperature_trg],
    trg_E_ps[low_temperature_trg],
    color=c_trg,
    linewidth=2.5,
    label="tanTRG (D=512)",
)
scatter!(
    axA,
    metts_T[low_temperature_metts],
    metts_E_ps[low_temperature_metts],
    color=c_metts,
    markersize=5,
    label="PEPS-METTS (D=2, χ=16)",
)
errorbars!(
    axA,
    metts_T[low_temperature_metts],
    metts_E_ps[low_temperature_metts],
    metts_E_se[low_temperature_metts],
    color=c_metts,
    linewidth=0.8,
    whiskerwidth=6,
)
axislegend(axA, position=:lb, fontsize=11)

axB = Axis(
    fig[1, 2],
    xlabel=L"$T = 1/\beta$",
    ylabel=L"$|E_{\mathrm{METTS}} - E_{\mathrm{tanTRG}}| \,/\, |E_{\mathrm{tanTRG}}|$",
    title="Relative deviation from tanTRG",
    xscale=log10,
    yscale=log10,
    xminorticksvisible=true,
    yminorticksvisible=true,
    xminorticks=IntervalsBetween(9),
)
xlims!(axB, (0.1, 1.0))

scatter!(
    axB,
    shared_T,
    relative_error,
    color=c_metts,
    markersize=9,
    label="PEPS-METTS vs tanTRG",
)
rangebars!(
    axB,
    shared_T,
    relative_low,
    relative_high,
    color=c_metts,
    whiskerwidth=8,
    linewidth=1.2,
)
axislegend(axB, position=:rt, fontsize=11)

colgap!(fig.layout, 20)
pdf_path = joinpath(OUTDIR, "compare_6x6_tfim.pdf")
png_path = joinpath(OUTDIR, "compare_6x6_tfim.png")
save(pdf_path, fig)
save(png_path, fig, px_per_unit=2)
println("Saved to: $pdf_path")
println("Saved to: $png_path")

println("\n--- Relative deviation from tanTRG ---")
println(" beta     T       tanTRG(E/N)      METTS(E/N)       relative error")
for index in eachindex(shared_beta)
    @printf(
        "%5.1f  %6.3f   %+.12f   %+.12f   %.3e\n",
        shared_beta[index],
        shared_T[index],
        shared_trg_E[index],
        shared_metts_E[index],
        relative_error[index],
    )
end
