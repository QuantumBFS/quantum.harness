#!/usr/bin/env julia

using CairoMakie
using DelimitedFiles

const DEFAULT_CSV_PATH =
    "/Users/chuanshu/Desktop/code/quantum harness/xcs_for_submit/2DMETTS/results/10*10/tfim-sse-l10-peps-metts-aggregate-2026-07-29.csv"

function read_comparison(path::AbstractString)
    isfile(path) || error("Input CSV does not exist: $(path)")

    raw = readdlm(path, ',', Any, '\n')
    size(raw, 1) > 1 || error("Input CSV contains no data rows: $(path)")

    header = String.(strip.(string.(vec(raw[1, :]))))
    columns = Dict(name => index for (index, name) in pairs(header))
    required_columns = [
        "beta",
        "qmc_energy_per_site",
        "qmc_final_mcse",
        "peps_energy_per_site",
        "peps_statistical_se",
    ]
    missing_columns = filter(name -> !haskey(columns, name), required_columns)
    isempty(missing_columns) ||
        error("Missing required CSV columns: $(join(missing_columns, ", "))")

    data = raw[2:end, :]
    values(name) = Float64.(data[:, columns[name]])
    beta = values("beta")
    temperature = 1.0 ./ beta
    order = sortperm(temperature)

    return (
        temperature=temperature[order],
        peps_energy=values("peps_energy_per_site")[order],
        peps_error=values("peps_statistical_se")[order],
        sse_energy=values("qmc_energy_per_site")[order],
        sse_error=values("qmc_final_mcse")[order],
    )
end

csv_path = abspath(get(ARGS, 1, DEFAULT_CSV_PATH))
output_prefix = abspath(get(
    ARGS,
    2,
    joinpath(@__DIR__, "l10_peps_sse_comparison"),
))
mkpath(dirname(output_prefix))

comparison = read_comparison(csv_path)
any(iszero, comparison.sse_energy) &&
    error("SSE energy contains zero, so relative error is undefined")

relative_error_percent =
    100 .* abs.(comparison.peps_energy .- comparison.sse_energy) ./
    abs.(comparison.sse_energy)
any(relative_error_percent .<= 0) &&
    error("Relative error contains non-positive values and cannot be shown on a log scale")

colors = Makie.wong_colors()
peps_color = colors[1]
sse_color = colors[2]
relative_color = colors[4]

set_theme!(Theme(
    fontsize=16,
    Axis=(
        xgridvisible=true,
        ygridvisible=true,
        xgridcolor=(:gray, 0.18),
        ygridcolor=(:gray, 0.18),
        topspinevisible=false,
        rightspinevisible=false,
        xminorticksvisible=true,
        xminorticks=IntervalsBetween(9),
    ),
))

figure = Figure(size=(1260, 520))
temperature_ticks = (
    [0.1, 0.2, 0.5, 1, 2, 5, 10],
    ["0.1", "0.2", "0.5", "1", "2", "5", "10"],
)

axis_energy = Axis(
    figure[1, 1],
    xlabel="Temperature  T = 1/β",
    ylabel="Energy density  E/N",
    title="(a) Energy density",
    xscale=log10,
    xticks=temperature_ticks,
)

axis_relative = Axis(
    figure[1, 2],
    xlabel="Temperature  T = 1/β",
    ylabel="Absolute relative error  (%)",
    title="(b) PEPS-METTS relative error with respect to SSE",
    xscale=log10,
    yscale=log10,
    xticks=temperature_ticks,
    yminorticksvisible=true,
    yminorticks=IntervalsBetween(9),
)

lines!(
    axis_energy,
    comparison.temperature,
    comparison.peps_energy;
    color=peps_color,
    linewidth=2.2,
    label="PEPS-METTS",
)
errorbars!(
    axis_energy,
    comparison.temperature,
    comparison.peps_energy,
    comparison.peps_error;
    color=(peps_color, 0.65),
    whiskerwidth=6,
    linewidth=0.9,
)
scatter!(
    axis_energy,
    comparison.temperature,
    comparison.peps_energy;
    color=peps_color,
    marker=:circle,
    markersize=6,
)

lines!(
    axis_energy,
    comparison.temperature,
    comparison.sse_energy;
    color=sse_color,
    linewidth=2.2,
    label="SSE",
)
errorbars!(
    axis_energy,
    comparison.temperature,
    comparison.sse_energy,
    comparison.sse_error;
    color=(sse_color, 0.75),
    whiskerwidth=6,
    linewidth=0.9,
)
scatter!(
    axis_energy,
    comparison.temperature,
    comparison.sse_energy;
    color=sse_color,
    marker=:rect,
    markersize=6,
)

lines!(
    axis_relative,
    comparison.temperature,
    relative_error_percent;
    color=relative_color,
    linewidth=1.7,
)
scatter!(
    axis_relative,
    comparison.temperature,
    relative_error_percent;
    color=relative_color,
    marker=:diamond,
    markersize=7,
    label="|E_PEPS - E_SSE| / |E_SSE|",
)
hlines!(
    axis_relative,
    [0.01, 0.1, 1.0];
    color=(:gray35, 0.55),
    linestyle=:dash,
    linewidth=1.0,
)

axislegend(axis_energy; position=:rb, framevisible=false)
axislegend(axis_relative; position=:rt, framevisible=false, labelsize=13)
xlims!(axis_energy, 0.1, 10.0)
xlims!(axis_relative, 0.1, 10.0)

Label(
    figure[0, 1:2],
    "10×10 TFIM, J = 1, h = 0.5, OBC",
    fontsize=22,
    font=:bold,
)
colgap!(figure.layout, 32)

png_path = output_prefix * ".png"
pdf_path = output_prefix * ".pdf"
save(png_path, figure; px_per_unit=2)
save(pdf_path, figure)

println("Read comparison data from $(csv_path)")
println("Saved figure to $(png_path)")
println("Saved figure to $(pdf_path)")
