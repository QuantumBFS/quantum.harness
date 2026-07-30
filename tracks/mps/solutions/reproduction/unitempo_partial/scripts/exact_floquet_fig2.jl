#!/usr/bin/env julia

using DelimitedFiles
using Downloads
using LaTeXStrings
using Plots

const ARCHIVE_URL = "https://zenodo.org/api/records/19593671/files/exact_floquet_dynamics_of_strongly_damped_driven_quantum_systems.zip/content"

run_dir = length(ARGS) == 1 ? abspath(ARGS[1]) : error("usage: exact_floquet_fig2.jl <run-dir>")
mkpath(run_dir)
archive = joinpath(run_dir, "authors_zenodo_archive.zip")
source_dir = joinpath(run_dir, "authors_source")

if !isfile(archive)
    println("Downloading the authors' Fig. 2 archive..."); flush(stdout)
    Downloads.download(ARCHIVE_URL, archive)
end
if !isdir(joinpath(source_dir, "fig_2"))
    println("Extracting Fig. 2 data..."); flush(stdout)
    mkpath(source_dir)
    run(`unzip -oq $archive -d $source_dir`)
end

const Omega = 1.0
const epsilon_d = 1.0
const alpha = 0.05
const omega_c = 2.5
const chi = 235
const dt = pi / 60
const time = collect(0:dt:200)
const colors = palette(["#0C7BDC", "#fb6d72", "#00bf7d", "#864ff6", "#FFC20A"])

function trajectory(kind, omega_d)
    name = "dynamics_$(kind)_Omega_1_epsilon_d_1_omega_d_$(omega_d)_alpha_0.05_omega_c_2.5_bond_dim_235_dt_0.052.csv"
    # The deposited filenames retain Greek symbols; construct the exact path instead.
    name = "dynamics_$(kind)_Ω_1_ϵ_d_1_ω_d_$(omega_d)_α_0.05_ω_c_2.5_bond_dim_235_dt_0.052.csv"
    return vec(readdlm(joinpath(source_dir, "fig_2", name), Float64))
end

function panel(omega_d; legend = false)
    exact = trajectory("exact", omega_d)
    redfield = trajectory("Redfield_Magnus", omega_d)
    @assert length(exact) == length(time) == length(redfield)
    p = plot(
        dpi = 300,
        palette = colors,
        xlabel = "time " * L"\Omega t",
        ylabel = L"\langle \sigma_z(t) \rangle",
        gridalpha = 0.075,
        xticks = [0, 20, 40, 60],
        ylim = [-1, 1],
        xlim = [0, 60],
        framestyle = :box,
        size = (450, 300),
        legend = legend ? :topright : false,
        titlefont = (9, "Computer Modern"),
        guidefont = (9, "Computer Modern"),
        tickfont = (9, "Computer Modern"),
        legendfont = (9, "Computer Modern"),
    )
    annotate!(p, 30, 1.2, text(L"\omega_d = " * "$(omega_d)" * L"\Omega", 9, :center, "Computer Modern"))
    plot!(p, time, exact, line = (1.5, :solid, colors[1]), label = "exact")
    plot!(p, time, redfield, line = (1.5, :dash, colors[2]), label = "Redfield-Magnus")
    return p
end

ENV["GKSwstype"] = "100"
println("Rendering omega_d = 2.5 Omega and 10 Omega panels..."); flush(stdout)
slow = panel(2.5)
fast = panel(10; legend = true)
figure = plot(slow, fast, layout = (1, 2), size = (900, 300), margin = 2Plots.mm)
output = joinpath(run_dir, "fig2_reproduction.svg")
savefig(figure, output)
println("Wrote $(output)"); flush(stdout)
