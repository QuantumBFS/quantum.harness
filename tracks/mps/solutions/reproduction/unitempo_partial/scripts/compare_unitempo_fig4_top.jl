#!/usr/bin/env julia

using DelimitedFiles
using Printf
using Plots

length(ARGS) == 1 || error("usage: compare_unitempo_fig4_top.jl RESULT_DIR")
result_dir = ARGS[1]

function generated(name)
    data = readdlm(joinpath(result_dir, name), ',', Float64)
    return data[:, 1], data[:, 2]
end
author(name) = vec(readdlm(joinpath(result_dir, name), Float64))

time, driven = generated("concurrence_driven.csv")
_, driven_ss = generated("concurrence_driven_steady.csv")
_, undriven = generated("concurrence_undriven.csv")
_, undriven_ss = generated("concurrence_undriven_steady.csv")
author_driven = author("author_concurrence_driven.csv")
author_undriven = author("author_concurrence_undriven.csv")

driven_rmse = sqrt(sum(abs2, driven .- author_driven) / length(driven))
undriven_rmse = sqrt(sum(abs2, undriven .- author_undriven) / length(undriven))

default(fontfamily="sans-serif", linewidth=2.0, size=(950, 470), legend=:topright)
p = plot(xlabel="Omega t", ylabel="concurrence C", xlim=(0, 50), ylim=(0, 1), title="Fig. 4 top panel: generated (solid) and author data (dashed)")
plot!(p, time, driven_ss, color=:orangered, linestyle=:dot, alpha=0.7, label="our driven late-time C")
plot!(p, time, driven, color=:orangered, linestyle=:solid, label="our driven evolution")
plot!(p, time, author_driven, color=:orangered, linestyle=:dash, alpha=0.8, label="author driven evolution")
plot!(p, time, undriven_ss, color=:dodgerblue, linestyle=:dot, alpha=0.7, label="our undriven late-time C")
plot!(p, time, undriven, color=:dodgerblue, linestyle=:solid, label="our undriven evolution")
plot!(p, time, author_undriven, color=:dodgerblue, linestyle=:dash, alpha=0.8, label="author undriven evolution")
savefig(p, joinpath(result_dir, "fig4_top_author_vs_unitempo.png"))
savefig(p, joinpath(result_dir, "fig4_top_author_vs_unitempo.svg"))

open(joinpath(result_dir, "comparison_metrics.txt"), "w") do io
    println(io, "comparison=generated UniformTEMPO quench concurrence vs author-deposited Fig. 4 top-panel curves")
    @printf(io, "driven rmse=%.8g max_abs=%.8g final_generated=%.8g final_author=%.8g\n", driven_rmse, maximum(abs.(driven .- author_driven)), driven[end], author_driven[end])
    @printf(io, "undriven rmse=%.8g max_abs=%.8g final_generated=%.8g final_author=%.8g\n", undriven_rmse, maximum(abs.(undriven .- author_undriven)), undriven[end], author_undriven[end])
end
