#!/usr/bin/env julia

# Floquet heat current from a driven open Ising chain with one boundary bath.
using LinearAlgebra
using Printf
using Statistics
using UniformTEMPO
using Plots

length(ARGS) in (1, 2) || error("usage: unitempo_boundary_ising_floquet_heat.jl OUTPUT_DIR [CHAIN_LENGTH]")
const output_dir = ARGS[1]
mkpath(output_dir)

# Confirmed pilot setup.
const L = length(ARGS) == 2 ? parse(Int, ARGS[2]) : 4
L >= 2 || error("CHAIN_LENGTH must be at least 2")
const J, h0, amplitude, omega_drive = 1.0, 1.0, 0.5, 2.0
const alpha, omega_cutoff = 0.05, 5.0
const compression_tol, chi_cap, warmup_periods = 1e-8, 80, 200
const reference_delta_t = pi / 48

const sx = ComplexF64[0 1; 1 0]
const sz = ComplexF64[1 0; 0 -1]
const id2 = Matrix{ComplexF64}(I, 2, 2)

function onsite(operator, site)
    result = Matrix{ComplexF64}(undef, 0, 0)
    for index in 1:L
        factor = index == site ? operator : id2
        result = index == 1 ? factor : kron(result, factor)
    end
    result
end

const x_ops = [onsite(sx, site) for site in 1:L]
const z_ops = [onsite(sz, site) for site in 1:L]
const sum_x = sum(x_ops)
const h_ising = -J * sum(z_ops[site] * z_ops[site + 1] for site in 1:(L - 1))
const bath_coupling = z_ops[1]

field(t) = h0 + amplitude * cos(omega_drive * t)
hamiltonian(t) = h_ising - field(t) * sum_x
drive_power_operator(t) = amplitude * omega_drive * sin(omega_drive * t) * sum_x
bcf(t) = alpha * (omega_cutoff / (1 + im * omega_cutoff * t))^2

const period = 2pi / omega_drive
const delta_t = period / round(period / reference_delta_t)
const period_steps = round(Int, period / delta_t)

function energy(rho, time)
    real(tr(hamiltonian(time) * rho))
end

function power(rho, time)
    real(tr(drive_power_operator(time) * rho))
end

println("[setup] L=$L dimension=$(2^L) period=$(period) delta_t=$(delta_t) steps_per_period=$period_steps")
println("[setup] alpha=$alpha omega_c=$omega_cutoff chi_cap=$chi_cap warmup_periods=$warmup_periods")
flush(stdout)

ground = eigen(Hermitian(hamiltonian(0.0)))
psi0 = ground.vectors[:, 1]
rho0 = psi0 * psi0'

println("[1/3] building boundary-bath influence functional")
flush(stdout)
started = time()
pt = uniTEMPO(bath_coupling, delta_t, bcf, compression_tol; cap_rank=chi_cap, max_rank=chi_cap)
chi = bond_dim(pt)
println("[1/3] influence functional ready; chi=$chi")
flush(stdout)

println("[2/3] warming physical Floquet state for $warmup_periods periods")
flush(stdout)
rho_periodic = evolve(pt, rho0, warmup_periods * period_steps; h_s=hamiltonian, return_full=true)
println("[2/3] warm-up complete")
flush(stdout)

println("[3/3] sampling one Floquet period and evaluating heat current")
flush(stdout)
states = evolve(pt, rho_periodic, period_steps; h_s=hamiltonian)
cycle_states = states[1:end-1]
sample_count = length(cycle_states)
times = delta_t .* collect(0:(sample_count - 1))
energies = [energy(cycle_states[index], times[index]) for index in eachindex(times)]
powers = [power(cycle_states[index], times[index]) for index in eachindex(times)]
energy_derivatives = similar(energies)

for index in eachindex(energies)
    previous = index == 1 ? energy(cycle_states[end], -delta_t) : energies[index - 1]
    following = index == length(energies) ? energy(cycle_states[1], period) : energies[index + 1]
    energy_derivatives[index] = (following - previous) / (2delta_t)
end

heat_current = powers .- energy_derivatives # Positive means chain -> bath.
mean_power = mean(powers)
mean_energy_derivative = mean(energy_derivatives)
mean_current = mean(heat_current)
balance_current = mean_power - mean_energy_derivative
wall = time() - started

open(joinpath(output_dir, "heat_current_cycle.csv"), "w") do io
    println(io, "time_over_period,energy,drive_power,energy_derivative,heat_current_to_bath")
    for index in eachindex(times)
        @printf(io, "%.12g,%.12g,%.12g,%.12g,%.12g\n", times[index] / period, energies[index], powers[index], energy_derivatives[index], heat_current[index])
    end
end

open(joinpath(output_dir, "summary.txt"), "w") do io
    @printf(io, "L=%d\nJ=%.12g\nh0=%.12g\namplitude=%.12g\nomega_drive=%.12g\n", L, J, h0, amplitude, omega_drive)
    @printf(io, "alpha=%.12g\nomega_cutoff=%.12g\ndelta_t=%.12g\nperiod_steps=%d\n", alpha, omega_cutoff, delta_t, period_steps)
    @printf(io, "warmup_periods=%d\nbond_dimension=%d\nwall_seconds=%.6f\n", warmup_periods, chi, wall)
    @printf(io, "mean_drive_power=%.12g\nmean_energy_derivative=%.12g\nmean_heat_current_to_bath=%.12g\nbalance_current=%.12g\n", mean_power, mean_energy_derivative, mean_current, balance_current)
end

plot(times ./ period, [powers heat_current energy_derivatives];
    label=["drive power" "heat current to bath" "d<E>/dt"], xlabel="t / T", ylabel="energy rate",
    title="Boundary-bath Floquet Ising chain (L = $L)", lw=2, size=(900, 550))
savefig(joinpath(output_dir, "heat_current_cycle.png"))

@printf("[done] mean heat current to bath = %.8f; mean drive power = %.8f\n", mean_current, mean_power)
@printf("[done] mean energy derivative = %.3e; wall = %.1f s\n", mean_energy_derivative, wall)
flush(stdout)
