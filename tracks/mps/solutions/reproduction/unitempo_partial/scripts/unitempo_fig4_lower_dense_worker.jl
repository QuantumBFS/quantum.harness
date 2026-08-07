#!/usr/bin/env julia

# One interleaved frequency partition of the approved 30-by-20 dense Fig. 4 scan.
using LinearAlgebra
using Printf
using Statistics
using UniformTEMPO

length(ARGS) == 3 || error("usage: unitempo_fig4_lower_dense_worker.jl OUTPUT_DIR WORKER_INDEX WORKER_COUNT")
const output_dir = ARGS[1]
const worker_index = parse(Int, ARGS[2])
const worker_count = parse(Int, ARGS[3])
const cells_dir = joinpath(output_dir, "cells")
mkpath(cells_dir)

const omega_values = [0.525, 0.6, 0.7, 0.775, 0.875, 0.95, 1.05, 1.125, 1.225, 1.3, 1.4, 1.475, 1.575, 1.65, 1.75, 1.825, 1.925, 2.0, 2.1, 2.175, 2.275, 2.35, 2.45, 2.525, 2.625, 2.7, 2.8, 2.875, 2.975, 3.0]
const amplitude_values = [0.05, 0.15, 0.3, 0.4, 0.55, 0.65, 0.8, 0.9, 1.05, 1.15, 1.3, 1.4, 1.55, 1.65, 1.8, 1.9, 2.05, 2.15, 2.3, 2.5]
const alpha, omega_cutoff = 0.1, 5.0
const reference_delta_t, compression_tol, chi_cap, warmup_periods = pi / 48, 1e-8, 80, 200

const sx = ComplexF64[0 1; 1 0]
const sy = ComplexF64[0 -im; im 0]
const sz = ComplexF64[1 0; 0 -1]
const i2 = Matrix{ComplexF64}(I, 2, 2)
const sx_a, sx_b, syy = kron(sx, i2), kron(i2, sx), kron(sy, sy)
const coupling = 0.5 * (kron(sz, i2) + kron(i2, sz))
const h_static = 0.5 * (sx_a + sx_b)
const rho_initial = ComplexF64[1 0 0 0; 0 0 0 0; 0 0 0 0; 0 0 0 0]
bcf(t) = alpha * (omega_cutoff / (1 + im * omega_cutoff * t))^2

function concurrence(rho)
    r = rho * syy * conj(rho) * syy
    roots = sort(sqrt.(max.(real.(eigvals(r)), 0.0)); rev=true)
    max(0.0, real(roots[1] - sum(roots[2:end])))
end

cell_number(iomega, iamp) = (iomega - 1) * length(amplitude_values) + iamp
cell_path(iomega, iamp) = joinpath(cells_dir, @sprintf("cell-%04d", cell_number(iomega, iamp)), "manifest.csv")
is_complete(path) = isfile(path) && length(readlines(path)) == 2

function save_cell(path, omega, amplitude, value, delta_t, period_steps, chi, wall)
    open(path, "w") do io
        println(io, "omega_drive_over_Omega,drive_amplitude_over_Omega,period_averaged_concurrence,delta_t,period_steps,bond_dimension,bond_dimension_cap,compression_tolerance,warmup_periods,wall_seconds")
        @printf(io, "%.12g,%.12g,%.12g,%.12g,%d,%d,%d,%.1e,%d,%.6f\n", omega, amplitude, value, delta_t, period_steps, chi, chi_cap, compression_tol, warmup_periods, wall)
    end
end

for iomega in 1:length(omega_values)
    (iomega - 1) % worker_count == worker_index || continue
    omega = omega_values[iomega]
    for iamp in 1:length(amplitude_values)
        path = cell_path(iomega, iamp)
        is_complete(path) && continue
        mkpath(dirname(path))
        amplitude = amplitude_values[iamp]
        period = 2pi / omega
        delta_t = period / round(period / reference_delta_t)
        period_steps = round(Int, period / delta_t)
        hamiltonian(t) = h_static + 0.5 * amplitude * cos(omega * t) * (sx_a + sx_b)
        @printf("[worker %d, cell-%04d] omega_d=%.3f epsilon_d=%.3f: building IF\n", worker_index, cell_number(iomega, iamp), omega, amplitude)
        flush(stdout)
        started = time()
        pt = uniTEMPO(coupling, delta_t, bcf, compression_tol; cap_rank=chi_cap, max_rank=chi_cap)
        chi = bond_dim(pt)
        periodic_state = evolve(pt, rho_initial, warmup_periods * period_steps; h_s=hamiltonian, return_full=true)
        states = evolve(pt, periodic_state, period_steps; h_s=hamiltonian)
        value = mean(concurrence.(states[1:end-1]))
        wall = time() - started
        save_cell(path, omega, amplitude, value, delta_t, period_steps, chi, wall)
        @printf("[worker %d, cell-%04d] Cbar_ss=%.7f chi=%d wall=%.1f s\n", worker_index, cell_number(iomega, iamp), value, chi, wall)
        flush(stdout)
    end
end
