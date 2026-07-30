#!/usr/bin/env julia

using DelimitedFiles
using LinearAlgebra
using Printf
using UniformTEMPO
using OrdinaryDiffEq
using Plots

length(ARGS) == 1 || error("usage: unitempo_fig2.jl OUTPUT_DIR")
output_dir = ARGS[1]
isdir(output_dir) || error("output directory does not exist: $output_dir")

# Units are set by Omega = 1. The bath correlation is the analytic
# zero-temperature transform of the exponential Ohmic spectral density.
Omega = 1.0
alpha = 0.05
omega_cutoff = 2.5 * Omega
drive_amplitude = Omega
delta_t = pi / (60 * Omega)
time_max = 60 / Omega
steps = round(Int, time_max / delta_t)
compression_tol = 1e-8

sigma_x = ComplexF64[0 1; 1 0]
sigma_z = ComplexF64[1 0; 0 -1]
rho_initial = ComplexF64[1 0; 0 0]

bcf(t) = alpha * (omega_cutoff / (1 + im * omega_cutoff * t))^2

println("Building uniform influence functional from the Ohmic bath ...")
flush(stdout)
wall_start = time()
pt = uniTEMPO(sigma_z, delta_t, bcf, compression_tol)
chi = bond_dim(pt)
@printf("Influence functional complete: chi = %d, elapsed = %.1f s\n", chi, time() - wall_start)
flush(stdout)

frequencies = [2.5 * Omega, 10.0 * Omega]
curves = Vector{Vector{Float64}}()
times = collect(0:steps) .* delta_t

for omega_drive in frequencies
    hamiltonian(t) = 0.5 * Omega * sigma_x + drive_amplitude * cos(omega_drive * t) * sigma_z
    @printf("Propagating omega_d/Omega = %.1f for %d steps ...\n", omega_drive / Omega, steps)
    flush(stdout)
    states = evolve(pt, rho_initial, steps; h_s=hamiltonian)
    sigma_z_expectation = [real(tr(rho * sigma_z)) for rho in states]
    push!(curves, sigma_z_expectation)
    @printf("Completed omega_d/Omega = %.1f; final <sigma_z> = %.6f\n", omega_drive / Omega, sigma_z_expectation[end])
    flush(stdout)
end

for (omega_drive, curve) in zip(frequencies, curves)
    filename = joinpath(output_dir, @sprintf("sigma_z_omega_d_%.1f.csv", omega_drive / Omega))
    writedlm(filename, hcat(times, curve), ',')
end

default(fontfamily="sans-serif", linewidth=2.2, legend=:bottomright, size=(980, 380))
figure = plot(layout=(1, 2), xlabel="Omega t", ylabel="<sigma_z>", ylims=(-1.05, 1.05))
for (panel, omega_drive, curve) in zip(1:2, frequencies, curves)
    plot!(figure[panel], times, curve, color=:black, label="uniform IF")
    title!(figure[panel], @sprintf("omega_d = %.1f Omega", omega_drive / Omega))
end
savefig(figure, joinpath(output_dir, "fig2_unitempo.svg"))
savefig(figure, joinpath(output_dir, "fig2_unitempo.png"))

open(joinpath(output_dir, "metadata.txt"), "w") do io
    println(io, "method=UniformTEMPO.jl uniTEMPO")
    println(io, "data_provenance=generated locally from analytic bath correlation; no author CSV read")
    println(io, "Omega=$(Omega)")
    println(io, "alpha=$(alpha)")
    println(io, "omega_cutoff=$(omega_cutoff)")
    println(io, "drive_amplitude=$(drive_amplitude)")
    println(io, "delta_t=$(delta_t)")
    println(io, "time_max=$(time_max)")
    println(io, "compression_tol=$(compression_tol)")
    println(io, "bond_dimension=$(chi)")
    println(io, "initial_state=|0><0|; <sigma_z>(0)=+1")
end

@printf("Finished. Total wall time: %.1f s\n", time() - wall_start)
flush(stdout)
