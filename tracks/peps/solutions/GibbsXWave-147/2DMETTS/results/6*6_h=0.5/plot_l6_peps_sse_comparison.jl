using CairoMakie
using DelimitedFiles
using Statistics

const DEFAULT_CSV_PATH =
    "/Users/chuanshu/Desktop/code/quantum harness/main_code/data/6*6/l6-peps-sse-comparison.csv"

function read_comparison(path::AbstractString)
    isfile(path) || error("Input CSV does not exist: $(path)")

    raw = readdlm(path, ',', Any, '\n')
    size(raw, 1) > 1 || error("Input CSV contains no data rows: $(path)")

    header = String.(strip.(string.(vec(raw[1, :]))))
    columns = Dict(name => index for (index, name) in pairs(header))
    required_columns = [
        "beta",
        "peps_energy",
        "peps_stat_se",
        "qmc_energy",
        "qmc_se",
    ]
    missing_columns = filter(name -> !haskey(columns, name), required_columns)
    isempty(missing_columns) ||
        error("Missing required CSV columns: $(join(missing_columns, ", "))")

    data = raw[2:end, :]
    values(name) = Float64.(data[:, columns[name]])
    beta = values("beta")
    order = sortperm(beta)

    return (
        beta=beta[order],
        peps_energy=values("peps_energy")[order],
        peps_error=values("peps_stat_se")[order],
        sse_energy=values("qmc_energy")[order],
        sse_error=values("qmc_se")[order],
    )
end

function contiguous_ranges(beta::AbstractVector)
    length(beta) <= 1 && return [eachindex(beta)]
    typical_step = median(diff(beta))
    gap_indices = findall(diff(beta) .> 2 * typical_step)
    starts = vcat(firstindex(beta), gap_indices .+ 1)
    stops = vcat(gap_indices, lastindex(beta))
    return [start:stop for (start, stop) in zip(starts, stops)]
end

csv_path = abspath(get(ARGS, 1, DEFAULT_CSV_PATH))
output_prefix = abspath(get(
    ARGS,
    2,
    joinpath(@__DIR__, "l6_peps_sse_comparison"),
))
mkpath(dirname(output_prefix))

comparison = read_comparison(csv_path)
any(iszero, comparison.sse_energy) &&
    error("SSE energy contains zero, so relative error is undefined")

relative_error_percent =
    100 .* abs.(comparison.peps_energy .- comparison.sse_energy) ./
    abs.(comparison.sse_energy)
segments = contiguous_ranges(comparison.beta)

colors = Makie.wong_colors()
peps_color = colors[1]
sse_color = colors[2]
error_color = colors[4]

set_theme!(Theme(
    fontsize=16,
    Axis=(
        xgridvisible=true,
        ygridvisible=true,
        xgridcolor=(:gray, 0.18),
        ygridcolor=(:gray, 0.18),
        topspinevisible=false,
        rightspinevisible=false,
    ),
))

figure = Figure(size=(920, 820))
axis_energy = Axis(
    figure[1, 1],
    ylabel="Energy density  E/N",
    title="(a) Energy density",
)
axis_relative = Axis(
    figure[2, 1],
    xlabel="Inverse temperature  β",
    ylabel="Absolute relative error  (%)",
    title="(b) PEPS-METTS relative error with respect to SSE",
    yscale=log10,
    yticks=(
        [1e-4, 1e-3, 1e-2, 1e-1, 1, 10, 100],
        ["10⁻⁴", "10⁻³", "10⁻²", "10⁻¹", "1", "10", "100"],
    ),
)

for segment in segments
    lines!(
        axis_energy,
        comparison.beta[segment],
        comparison.peps_energy[segment];
        color=peps_color,
        linewidth=2.2,
    )
    lines!(
        axis_energy,
        comparison.beta[segment],
        comparison.sse_energy[segment];
        color=sse_color,
        linewidth=2.2,
    )
    lines!(
        axis_relative,
        comparison.beta[segment],
        relative_error_percent[segment];
        color=error_color,
        linewidth=2.2,
    )
end

errorbars!(
    axis_energy,
    comparison.beta,
    comparison.peps_energy,
    comparison.peps_error;
    color=(peps_color, 0.75),
    whiskerwidth=8,
    linewidth=1.1,
)
errorbars!(
    axis_energy,
    comparison.beta,
    comparison.sse_energy,
    comparison.sse_error;
    color=(sse_color, 0.75),
    whiskerwidth=8,
    linewidth=1.1,
)
scatter!(
    axis_energy,
    comparison.beta,
    comparison.peps_energy;
    color=peps_color,
    marker=:circle,
    markersize=8,
    label="PEPS-METTS",
)
scatter!(
    axis_energy,
    comparison.beta,
    comparison.sse_energy;
    color=sse_color,
    marker=:rect,
    markersize=8,
    label="SSE",
)
scatter!(
    axis_relative,
    comparison.beta,
    relative_error_percent;
    color=error_color,
    marker=:diamond,
    markersize=8,
)

hlines!(axis_relative, [0.1, 1.0]; color=(:gray35, 0.6), linestyle=:dash, linewidth=1.2)
axislegend(axis_energy; position=:rt, framevisible=false)
hidexdecorations!(axis_energy; grid=false)
linkxaxes!(axis_energy, axis_relative)
xlims!(axis_relative, extrema(comparison.beta)...)

Label(
    figure[0, 1],
    "6×6 PEPS-METTS and SSE comparison",
    fontsize=22,
    font=:bold,
)
rowsize!(figure.layout, 1, Relative(0.58))
rowgap!(figure.layout, 18)

png_path = output_prefix * ".png"
pdf_path = output_prefix * ".pdf"
save(png_path, figure; px_per_unit=2)
save(pdf_path, figure)

println("Read comparison data from $(csv_path)")
println("Saved figure to $(png_path)")
println("Saved figure to $(pdf_path)")
