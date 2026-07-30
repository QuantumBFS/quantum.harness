#!/usr/bin/env julia

using DelimitedFiles
using LinearAlgebra
using Printf
using UniformTEMPO
using Plots

length(ARGS) == 1 || error("usage: unitempo_fig4_top.jl OUTPUT_DIR")
output_dir = ARGS[1]
isdir(output_dir) || error("output directory does not exist: $output_dir")

# Units are set by Omega = 1. No author data files are read by this script.
const Omega = 1.0
const alpha = 0.1
const omega_cutoff = 5.0 * Omega
const omega_drive = 2.15 * Omega
const drive_amplitude = 1.15 * Omega
const reference_delta_t = pi / (48 * Omega)
const drive_period = 2pi / omega_drive
const delta_t = drive_period / round(drive_period / reference_delta_t)
const time_max = 100 / Omega
const compression_tol = 1e-8
const chi_cap = 80

const sigma_x = ComplexF64[0 1; 1 0]
const sigma_y = ComplexF64[0 -im; im 0]
const sigma_z = ComplexF64[1 0; 0 -1]
const identity_2 = Matrix{ComplexF64}(I, 2, 2)
const sigma_x_a = kron(sigma_x, identity_2)
const sigma_x_b = kron(identity_2, sigma_x)
const sigma_y_y = kron(sigma_y, sigma_y)
const sigma_z_a = kron(sigma_z, identity_2)
const sigma_z_b = kron(identity_2, sigma_z)
const coupling = 0.5 * (sigma_z_a + sigma_z_b)
const h_undriven = 0.5 * Omega * (sigma_x_a + sigma_x_b)
const rho_initial = ComplexF64[1 0 0 0; 0 0 0 0; 0 0 0 0; 0 0 0 0]

bcf(t) = alpha * (omega_cutoff / (1 + im * omega_cutoff * t))^2

function concurrence(rho)
    # Wootters concurrence for a two-qubit density matrix.
    r_matrix = rho * sigma_y_y * conj(rho) * sigma_y_y
    roots = sort(sqrt.(max.(real.(eigvals(r_matrix)), 0.0)); rev=true)
    return max(0.0, real(roots[1] - sum(roots[2:end])))
end

function concurrence_curve(states)
    return [concurrence(rho) for rho in states]
end

wall_start = time()
println("Building shared-bath influence functional for the two-spin model ...")
flush(stdout)
pt = uniTEMPO(coupling, delta_t, bcf, compression_tol; cap_rank=chi_cap, max_rank=chi_cap)
chi = bond_dim(pt)
@printf("Influence functional complete: chi = %d, elapsed = %.1f s\n", chi, time() - wall_start)
flush(stdout)

steps = round(Int, time_max / delta_t)
times = collect(0:steps) .* delta_t
hamiltonian_driven(t) = h_undriven + 0.5 * drive_amplitude * cos(omega_drive * t) * (sigma_x_a + sigma_x_b)

println("Finding driven Floquet steady state ...")
flush(stdout)
floquet_pt = floquet_process_tensor(pt, hamiltonian_driven, drive_period)
x_driven_ss = steadystate(floquet_pt; return_full=true, ED=true)

println("Propagating driven quench and steady-state concurrence ...")
flush(stdout)
driven_quench = concurrence_curve(evolve(pt, rho_initial, steps; h_s=hamiltonian_driven))
period_steps = round(Int, drive_period / delta_t)
warmup_steps = 200 * period_steps
println("Warming the driven state through $warmup_steps steps to select the physical periodic branch ...")
flush(stdout)
x_driven_periodic = evolve(pt, rho_initial, warmup_steps; h_s=hamiltonian_driven, return_full=true)
driven_steady = concurrence_curve(evolve(pt, x_driven_periodic, steps; h_s=hamiltonian_driven))

println("Finding undriven steady state and propagating the undriven quench ...")
flush(stdout)
x_undriven_ss = steadystate(pt; h_s=h_undriven, return_full=true, ED=true)
undriven_quench = concurrence_curve(evolve(pt, rho_initial, steps; h_s=h_undriven))
undriven_steady = undriven_quench[end]

writedlm(joinpath(output_dir, "concurrence_driven.csv"), hcat(times, driven_quench), ',')
writedlm(joinpath(output_dir, "concurrence_driven_steady.csv"), hcat(times, driven_steady), ',')
writedlm(joinpath(output_dir, "concurrence_undriven.csv"), hcat(times, undriven_quench), ',')
writedlm(joinpath(output_dir, "concurrence_undriven_steady.csv"), hcat(times, fill(undriven_steady, length(times))), ',')

default(fontfamily="sans-serif", linewidth=2.1, size=(900, 430), legend=:topright)
figure = plot(xlabel="Omega t", ylabel="concurrence C", xlim=(0, 50), ylim=(0, 1), title="Fig. 4 top panel: generated UniformTEMPO data")
plot!(figure, times, driven_steady, color=:orangered, linestyle=:dash, alpha=0.7, label="driven steady state")
plot!(figure, times, driven_quench, color=:orangered, label="driven evolution")
plot!(figure, times, fill(undriven_steady, length(times)), color=:dodgerblue, linestyle=:dash, alpha=0.7, label="undriven steady state")
plot!(figure, times, undriven_quench, color=:dodgerblue, label="undriven evolution")
savefig(figure, joinpath(output_dir, "fig4_top_unitempo.png"))
savefig(figure, joinpath(output_dir, "fig4_top_unitempo.svg"))

open(joinpath(output_dir, "metadata.txt"), "w") do io
    println(io, "method=UniformTEMPO.jl uniTEMPO plus Wootters concurrence")
    println(io, "data_provenance=generated locally from analytic Ohmic bath correlation; no author CSV read")
    println(io, "alpha=$(alpha)")
    println(io, "omega_cutoff=$(omega_cutoff)")
    println(io, "omega_drive=$(omega_drive)")
    println(io, "drive_amplitude=$(drive_amplitude)")
    println(io, "delta_t=$(delta_t)")
    println(io, "compression_tol=$(compression_tol)")
    println(io, "bond_dimension=$(chi)")
    println(io, "bond_dimension_cap=$(chi_cap)")
    println(io, "time_max=$(time_max)")
    println(io, "undriven_steady_concurrence=$(undriven_steady)")
end

@printf("Finished. Total wall time: %.1f s\n", time() - wall_start)
flush(stdout)
