#!/usr/bin/env julia

using DelimitedFiles
using Printf
using Plots

length(ARGS) == 1 || error("usage: compare_unitempo_fig3.jl RESULT_DIR")
result_dir = ARGS[1]

function read_generated(path)
    data = readdlm(path, ',', Float64)
    return data[:, 1], data[:, 2]
end

function read_author(path)
    return vec(readdlm(path, Float64))
end

function compare_panel!(plot_handle, result_dir, kind, drives, x_limit)
    rmses = Dict{Float64, Float64}()
    maxima = Dict{Float64, Float64}()
    for (drive, style) in zip(drives, (:solid, :dash, :dashdot))
        generated_file = joinpath(result_dir, @sprintf("heat_current_%s_omega_d_%.1f.csv", kind, drive))
        author_file = joinpath(result_dir, @sprintf("author_%s_omega_d_%.1f.csv", kind, drive))
        frequency, generated = read_generated(generated_file)
        author = read_author(author_file)[1:length(generated)]
        rmses[drive] = sqrt(sum(abs2, generated .- author) / length(generated))
        maxima[drive] = maximum(abs.(generated .- author))
        plot!(plot_handle, frequency, generated, color=:black, linestyle=style, label=@sprintf("ours, omega_d = %.1f", drive))
        plot!(plot_handle, frequency, author, color=:red, linestyle=style, alpha=0.8, label=@sprintf("author, omega_d = %.1f", drive))
    end
    xlims!(plot_handle, 0, x_limit)
    return rmses, maxima
end

default(fontfamily="sans-serif", linewidth=1.7, size=(1000, 760), legend=:topright)
top = plot(xlabel="bath frequency omega/Omega", ylabel="jbar(omega)/Omega", ylim=(-0.005, 0.15), title="longitudinal drive: black = independent UniformTEMPO, red = authors")
bottom = plot(xlabel="bath frequency omega/Omega", ylabel="jbar(omega)/Omega", ylim=(-0.005, 0.15), title="transversal drive: black = independent UniformTEMPO, red = authors")
long_rmse, long_max = compare_panel!(top, result_dir, "longitudinal", (10.0, 5.0, 2.5), 10.0)
trans_rmse, trans_max = compare_panel!(bottom, result_dir, "transversal", (2.0, 1.5, 1.0), 4.0)
figure = plot(top, bottom, layout=(2, 1), size=(1000, 760))
savefig(figure, joinpath(result_dir, "fig3_author_vs_unitempo.png"))
savefig(figure, joinpath(result_dir, "fig3_author_vs_unitempo.svg"))

open(joinpath(result_dir, "comparison_metrics.txt"), "w") do io
    println(io, "comparison=generated UniformTEMPO continuous spectra vs author-deposited continuous CSV curves")
    println(io, "note=author data are read only after independent generation; delta-function weights are not compared as sampled curves")
    for drive in (10.0, 5.0, 2.5)
        @printf(io, "longitudinal omega_d=%.1f rmse=%.8g max_abs=%.8g\n", drive, long_rmse[drive], long_max[drive])
    end
    for drive in (2.0, 1.5, 1.0)
        @printf(io, "transversal omega_d=%.1f rmse=%.8g max_abs=%.8g\n", drive, trans_rmse[drive], trans_max[drive])
    end
end
