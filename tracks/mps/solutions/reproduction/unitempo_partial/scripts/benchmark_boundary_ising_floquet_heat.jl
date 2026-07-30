#!/usr/bin/env julia

# Null-bath and periodic-branch benchmarks for the L=3 Floquet Ising current.
using LinearAlgebra
using OrdinaryDiffEq
using Plots
using Printf
using Statistics
using UniformTEMPO

length(ARGS) == 1 || error("usage: benchmark_boundary_ising_floquet_heat.jl OUTPUT_DIR")
const output_dir = ARGS[1]
mkpath(output_dir)
const L = 3
const J, h0, amplitude, omega_drive = 1.0, 1.0, 0.5, 2.0
const alpha, omega_cutoff = 0.05, 5.0
const tol, chi_cap, warmup_periods = 1e-8, 80, 200
const period = 2pi / omega_drive
const delta_t = period / round(period / (pi / 48))
const period_steps = round(Int, period / delta_t)

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
hamiltonian(t) = h_ising - (h0 + amplitude * cos(omega_drive * t)) * sum_x
power_operator(t) = amplitude * omega_drive * sin(omega_drive * t) * sum_x
bcf(a) = t -> a * (omega_cutoff / (1 + im * omega_cutoff * t))^2

function cycle_observables(states)
    physical = states[1:end-1]
    times = delta_t .* collect(0:(length(physical) - 1))
    energy = [real(tr(hamiltonian(times[index]) * physical[index])) for index in eachindex(times)]
    power = [real(tr(power_operator(times[index]) * physical[index])) for index in eachindex(times)]
    derivative = similar(energy)
    for index in eachindex(energy)
        previous = index == 1 ? real(tr(hamiltonian(-delta_t) * physical[end])) : energy[index - 1]
        following = index == length(energy) ? real(tr(hamiltonian(period) * physical[1])) : energy[index + 1]
        derivative[index] = (following - previous) / (2delta_t)
    end
    (mean_power=mean(power), mean_derivative=mean(derivative), mean_balance=mean(power .- derivative))
end

# A Floquet eigenstate is exactly periodic for the isolated chain.
function floquet_eigenstate()
    dimension = 2^L
    function schrodinger!(du, u, _, time)
        du .= vec(-im * hamiltonian(time) * reshape(u, dimension, dimension))
    end
    solution = solve(ODEProblem(schrodinger!, vec(Matrix{ComplexF64}(I, dimension, dimension)), (0.0, period)),
        Tsit5(), abstol=1e-11, reltol=1e-11, saveat=[period])
    propagator = reshape(solution.u[end], dimension, dimension)
    spectrum = eigen(propagator)
    psi = spectrum.vectors[:, argmin(abs.(angle.(spectrum.values)))]
    psi * psi'
end

println("[1/3] null-bath test: isolated Floquet eigenstate")
flush(stdout)
rho_floquet = floquet_eigenstate()
pt_zero = uniTEMPO(bath_coupling, delta_t, bcf(0.0), tol; cap_rank=chi_cap, max_rank=chi_cap)
zero_observables = cycle_observables(evolve(pt_zero, rho_floquet, period_steps; h_s=hamiltonian))
@printf("[1/3] alpha=0 mean balance current = %.3e\n", zero_observables.mean_balance)
flush(stdout)

println("[2/3] physical bath: build process tensor and warm $warmup_periods periods")
flush(stdout)
started = time()
pt = uniTEMPO(bath_coupling, delta_t, bcf(alpha), tol; cap_rank=chi_cap, max_rank=chi_cap)
ground = eigen(Hermitian(hamiltonian(0.0)))
rho0 = ground.vectors[:, 1] * ground.vectors[:, 1]'
state = evolve(pt, rho0, warmup_periods * period_steps; h_s=hamiltonian, return_full=true)

println("[3/3] compare three consecutive post-warm-up periods")
flush(stdout)
cycle_means = Float64[]
cycle_derivatives = Float64[]
cycle_balances = Float64[]
for cycle in 1:3
    states = evolve(pt, state, period_steps; h_s=hamiltonian)
    values = cycle_observables(states)
    push!(cycle_means, values.mean_power)
    push!(cycle_derivatives, values.mean_derivative)
    push!(cycle_balances, values.mean_balance)
    global state = states[end] # Internal process-tensor state; valid input for the next cycle.
    @printf("[cycle %d] mean_power=%.8f mean_balance=%.8f\n", cycle, values.mean_power, values.mean_balance)
    flush(stdout)
end

drift = maximum(cycle_means) - minimum(cycle_means)
open(joinpath(output_dir, "benchmark_summary.txt"), "w") do io
    @printf(io, "null_bath_mean_balance_current=%.12g\n", zero_observables.mean_balance)
    @printf(io, "null_bath_mean_drive_power=%.12g\n", zero_observables.mean_power)
    @printf(io, "physical_alpha=%.12g\nchi=%d\nwarmup_periods=%d\nwall_seconds=%.6f\n", alpha, bond_dim(pt), warmup_periods, time() - started)
    for cycle in 1:3
        @printf(io, "cycle_%d_mean_power=%.12g\ncycle_%d_mean_energy_derivative=%.12g\ncycle_%d_mean_balance_current=%.12g\n", cycle, cycle_means[cycle], cycle, cycle_derivatives[cycle], cycle, cycle_balances[cycle])
    end
    @printf(io, "three_cycle_power_drift=%.12g\n", drift)
end

plot(1:3, [cycle_means cycle_balances]; marker=:circle, lw=2,
    label=["mean drive power" "mean energy-balance current"], xlabel="post-warm-up period", ylabel="period average",
    title="Floquet-period convergence, boundary Ising chain", xticks=1:3, size=(800, 480))
savefig(joinpath(output_dir, "periodicity_benchmark.png"))
@printf("[done] null current=%.3e; three-cycle power drift=%.3e\n", zero_observables.mean_balance, drift)
flush(stdout)
