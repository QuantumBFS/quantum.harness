#!/usr/bin/env julia

# Compare the completed generated map with matching coordinates from the
# deposited author Fig. 4 data. Author values are read only in this script.
using DelimitedFiles
using LinearAlgebra
using Plots
using Printf
using Statistics

length(ARGS) == 2 || error("usage: compare_unitempo_fig4_lower_dense.jl OUTPUT_DIR AUTHOR_FIG4_DIR")
output_dir, author_dir = ARGS

function read_generated(path)
    lines = readlines(path)
    records = NamedTuple[]
    for line in lines[2:end]
        fields = split(line, ',')
        push!(records, (omega=parse(Float64, fields[1]), amplitude=parse(Float64, fields[2]), value=parse(Float64, fields[3])))
    end
    records
end

generated = read_generated(joinpath(output_dir, "fig4_lower_dense_generated.csv"))
omega_values = sort(unique(record.omega for record in generated))
amplitude_values = sort(unique(record.amplitude for record in generated))
generated_map = fill(NaN, length(amplitude_values), length(omega_values))
author_map = fill(NaN, length(amplitude_values), length(omega_values))

author_slices = Dict{Float64, Vector{Float64}}()
for path in readdir(author_dir; join=true)
    occursin("concurrence_avg_", basename(path)) || continue
    match_result = match(r"ω_d_([0-9.]+)_α", basename(path))
    isnothing(match_result) && continue
    author_slices[parse(Float64, match_result.captures[1])] = vec(readdlm(path, Float64))
end

for record in generated
    iomega = findfirst(==(record.omega), omega_values)
    iamp = findfirst(==(record.amplitude), amplitude_values)
    author_frequency = only(filter(key -> isapprox(key, record.omega; atol=1e-10), keys(author_slices)))
    author_amplitude_index = round(Int, record.amplitude / 0.05)
    generated_map[iamp, iomega] = record.value
    author_map[iamp, iomega] = author_slices[author_frequency][author_amplitude_index]
end

difference_map = generated_map - author_map
rmse = sqrt(mean(abs2, difference_map))
mae = mean(abs, difference_map)
bias = mean(difference_map)
correlation = cor(vec(generated_map), vec(author_map))
peak_generated = argmax(generated_map)
peak_author = argmax(author_map)

open(joinpath(output_dir, "fig4_lower_dense_author_subset.csv"), "w") do io
    println(io, "omega_drive_over_Omega,drive_amplitude_over_Omega,author_period_averaged_concurrence,generated_period_averaged_concurrence,difference_generated_minus_author")
    for iomega in eachindex(omega_values), iamp in eachindex(amplitude_values)
        @printf(io, "%.12g,%.12g,%.12g,%.12g,%.12g\n", omega_values[iomega], amplitude_values[iamp], author_map[iamp, iomega], generated_map[iamp, iomega], difference_map[iamp, iomega])
    end
end

open(joinpath(output_dir, "fig4_lower_dense_comparison_metrics.txt"), "w") do io
    @printf(io, "matched_points=600\nrmse=%.10f\nmae=%.10f\nbias=%.10f\npearson_correlation=%.10f\n", rmse, mae, bias, correlation)
    @printf(io, "author_range=%.10f,%.10f\ngenerated_range=%.10f,%.10f\n", minimum(author_map), maximum(author_map), minimum(generated_map), maximum(generated_map))
    @printf(io, "author_peak=omega %.6f, amplitude %.6f, value %.10f\n", omega_values[peak_author[2]], amplitude_values[peak_author[1]], author_map[peak_author])
    @printf(io, "generated_peak=omega %.6f, amplitude %.6f, value %.10f\n", omega_values[peak_generated[2]], amplitude_values[peak_generated[1]], generated_map[peak_generated])
end

p_author = heatmap(omega_values, amplitude_values, author_map; title="Author data (same 30 x 20 points)", xlabel="omega_d / Omega", ylabel="epsilon_d / Omega", c=:viridis, clims=(0, 0.5), colorbar_title="Cbar_ss", xrotation=35)
p_generated = heatmap(omega_values, amplitude_values, generated_map; title="Generated with UniformTEMPO", xlabel="omega_d / Omega", ylabel="epsilon_d / Omega", c=:viridis, clims=(0, 0.5), colorbar_title="Cbar_ss", xrotation=35)
p_difference = heatmap(omega_values, amplitude_values, difference_map; title="Generated minus author", xlabel="omega_d / Omega", ylabel="epsilon_d / Omega", c=:balance, clims=(-maximum(abs, difference_map), maximum(abs, difference_map)), colorbar_title="Delta Cbar_ss", xrotation=35)
figure = plot(p_author, p_generated, p_difference; layout=(1, 3), size=(1800, 570), margin=5Plots.mm)
savefig(figure, joinpath(output_dir, "fig4_lower_dense_author_comparison.png"))
savefig(figure, joinpath(output_dir, "fig4_lower_dense_author_comparison.svg"))

@printf("matched_points=600 rmse=%.8f mae=%.8f bias=%.8f correlation=%.8f\n", rmse, mae, bias, correlation)
@printf("author_peak=(%.3f, %.3f, %.8f) generated_peak=(%.3f, %.3f, %.8f)\n", omega_values[peak_author[2]], amplitude_values[peak_author[1]], author_map[peak_author], omega_values[peak_generated[2]], amplitude_values[peak_generated[1]], generated_map[peak_generated])
