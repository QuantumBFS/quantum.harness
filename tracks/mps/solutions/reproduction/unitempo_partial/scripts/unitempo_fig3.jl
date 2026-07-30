#!/usr/bin/env julia

using DelimitedFiles
using LinearAlgebra
using Printf
using UniformTEMPO
using Plots

length(ARGS) == 1 || error("usage: unitempo_fig3.jl OUTPUT_DIR")
output_dir = ARGS[1]
isdir(output_dir) || error("output directory does not exist: $output_dir")

# Units are set by Omega = 1. This script generates its spectra from the
# analytic bath correlation; it never reads the authors' deposited CSV files.
const Omega = 1.0
const alpha = 0.05
const omega_cutoff = 2.5 * Omega
const drive_amplitude = Omega
const delta_t = pi / (60 * Omega)
const compression_tol = 1e-8
const chi_cap = 120
const tau_max = 100 / Omega

const sigma_x = ComplexF64[0 1; 1 0]
const sigma_z = ComplexF64[1 0; 0 -1]
const identity_2 = Matrix{ComplexF64}(I, 2, 2)

bcf(t) = alpha * (omega_cutoff / (1 + im * omega_cutoff * t))^2

function advance_state(pt, q, state, hamiltonian, start_time)
    half = pt.delta_t / 2
    u1 = UniformTEMPO.local_channel((start_time, start_time + half), hamiltonian)
    u2 = UniformTEMPO.local_channel((start_time + half, start_time + pt.delta_t), hamiltonian)
    state = state * transpose(u1)
    state = reshape(q * state[:], size(state))
    return state * transpose(u2)
end

function reduced_state(pt, state)
    return reshape(pt.v_l * state, pt.s_dim, pt.s_dim)
end

function trapezoid_weights(n, step)
    weights = fill(step, n)
    weights[1] /= 2
    weights[end] /= 2
    return weights
end

function connected_correlation(pt, x0, hamiltonian, period_steps, correlation_steps, label)
    q = reshape(pt.q, size(pt.q, 1) * size(pt.q, 2), :)
    phase_states = Vector{Matrix{ComplexF64}}(undef, period_steps)
    phase_means = zeros(ComplexF64, period_steps)
    state = copy(x0)
    for phase in 1:period_steps
        phase_states[phase] = copy(state)
        phase_means[phase] = tr(reduced_state(pt, state) * sigma_z)
        state = advance_state(pt, q, state, hamiltonian, (phase - 1) * pt.delta_t)
    end

    correlation = zeros(ComplexF64, correlation_steps + 1)
    o_left = kron(identity_2, sigma_z)
    trace_tensor = transpose(o_left) * identity_2[:]
    progress_stride = max(1, fld(period_steps, 8))

    for phase in 1:period_steps
        shifted_hamiltonian(t) = hamiltonian(t + (phase - 1) * pt.delta_t)
        corr_state = phase_states[phase] * transpose(o_left)
        correlation[1] += pt.v_l * corr_state * trace_tensor
        for step in 1:correlation_steps
            corr_state = advance_state(pt, q, corr_state, shifted_hamiltonian, (step - 1) * pt.delta_t)
            correlation[step + 1] += pt.v_l * corr_state * trace_tensor
        end
        if phase % progress_stride == 0 || phase == period_steps
            @printf("%s: correlations %d/%d phase points\n", label, phase, period_steps)
            flush(stdout)
        end
    end
    correlation ./= period_steps

    asymptotic = zeros(ComplexF64, correlation_steps + 1)
    for step in 0:correlation_steps
        asymptotic[step + 1] = sum(phase_means[mod1(phase + step, period_steps)] * phase_means[phase] for phase in 1:period_steps) / period_steps
    end
    return correlation - asymptotic, phase_means
end

function delta_peak_weights(phase_means, omega_drive)
    max_harmonic = floor(Int, 4.0 / omega_drive)
    rows = Matrix{Float64}(undef, max_harmonic, 3)
    for n in 1:max_harmonic
        coefficient = sum(phase_means[phase] * exp(-2im * pi * n * (phase - 1) / length(phase_means)) for phase in eachindex(phase_means)) / length(phase_means)
        c_n = 2 * abs2(coefficient)
        omega = n * omega_drive
        weight = pi * (alpha * omega * exp(-omega / omega_cutoff)) * omega * c_n
        rows[n, 1] = n
        rows[n, 2] = omega
        rows[n, 3] = weight
    end
    return rows
end

function heat_current(frequencies, connected)
    tau = (0:(length(connected) - 1)) .* delta_t
    weights = trapezoid_weights(length(tau), delta_t)
    values = zeros(Float64, length(frequencies))
    for (index, omega) in pairs(frequencies)
        kernel = sin.(omega .* tau) .+ im .* cos.(omega .* tau)
        integral = sum(weights .* imag.(kernel .* connected))
        values[index] = 2 * (alpha * omega * exp(-omega / omega_cutoff)) * omega * integral
    end
    return values
end

function run_drive(pt, drive_kind, omega_drive, frequency_max)
    drive_operator = drive_kind == :longitudinal ? sigma_x : sigma_z
    hamiltonian(t) = 0.5 * Omega * sigma_x + drive_amplitude * cos(omega_drive * t) * drive_operator
    period = 2pi / omega_drive
    period_steps = round(Int, period / delta_t)
    @assert isapprox(period_steps * delta_t, period; atol=1e-12)
    floquet_pt = floquet_process_tensor(pt, hamiltonian, period)
    x0 = steadystate(floquet_pt; return_full=true, ED=true)
    correlation_steps = round(Int, tau_max / delta_t)
    label = @sprintf("%s omega_d/Omega = %.1f", String(drive_kind), omega_drive)
    @printf("%s: period steps = %d, correlation steps = %d\n", label, period_steps, correlation_steps)
    flush(stdout)
    connected, phase_means = connected_correlation(pt, x0, hamiltonian, period_steps, correlation_steps, label)
    frequencies = collect(0.005:0.005:frequency_max)
    current = heat_current(frequencies, connected)
    peaks = drive_kind == :transversal ? delta_peak_weights(phase_means, omega_drive) : zeros(Float64, 0, 3)
    return frequencies, current, peaks
end

wall_start = time()
println("Building uniform influence functional from the analytic Ohmic bath ...")
flush(stdout)
pt = uniTEMPO(sigma_z, delta_t, bcf, compression_tol; cap_rank=chi_cap, max_rank=chi_cap)
chi = bond_dim(pt)
@printf("Influence functional complete: chi = %d, elapsed = %.1f s\n", chi, time() - wall_start)
flush(stdout)

specs = [
    (:longitudinal, 10.0, 10.0),
    (:longitudinal, 5.0, 10.0),
    (:longitudinal, 2.5, 10.0),
    (:transversal, 2.0, 4.0),
    (:transversal, 1.5, 4.0),
    (:transversal, 1.0, 4.0),
]

results = Dict{Tuple{Symbol, Float64}, Tuple{Vector{Float64}, Vector{Float64}, Matrix{Float64}}}()
for (kind, omega_drive, frequency_max) in specs
    frequencies, current, peaks = run_drive(pt, kind, omega_drive, frequency_max)
    results[(kind, omega_drive)] = (frequencies, current, peaks)
    name = @sprintf("heat_current_%s_omega_d_%.1f.csv", String(kind), omega_drive)
    writedlm(joinpath(output_dir, name), hcat(frequencies, current), ',')
    if kind == :transversal
        peak_name = @sprintf("delta_peaks_transversal_omega_d_%.1f.csv", omega_drive)
        writedlm(joinpath(output_dir, peak_name), peaks, ',')
    end
    @printf("%s omega_d/Omega = %.1f complete; max continuous current = %.6g\n", String(kind), omega_drive, maximum(current))
    flush(stdout)
end

default(fontfamily="sans-serif", linewidth=2.0, size=(900, 700), legend=:topright)
top = plot(xlabel="bath frequency omega/Omega", ylabel="jbar(omega)/Omega", xlim=(0, 10), ylim=(-0.005, 0.15), title="longitudinal drive")
bottom = plot(xlabel="bath frequency omega/Omega", ylabel="jbar(omega)/Omega", xlim=(0, 4), ylim=(-0.005, 0.15), title="transversal drive")
for (omega_drive, style) in zip((10.0, 5.0, 2.5), (:solid, :dash, :dashdot))
    frequency, current, _ = results[(:longitudinal, omega_drive)]
    plot!(top, frequency, current, linestyle=style, label=@sprintf("omega_d = %.1f Omega", omega_drive))
end
for (omega_drive, style) in zip((2.0, 1.5, 1.0), (:solid, :dash, :dashdot))
    frequency, current, peaks = results[(:transversal, omega_drive)]
    plot!(bottom, frequency, current, linestyle=style, label=@sprintf("omega_d = %.1f Omega", omega_drive))
    for row in eachrow(peaks)
        row[2] <= 4.0 || continue
        vline!(bottom, [row[2]], color=:black, alpha=0.45, label=false)
    end
end
figure = plot(top, bottom, layout=(2, 1), size=(900, 700))
savefig(figure, joinpath(output_dir, "fig3_unitempo.png"))
savefig(figure, joinpath(output_dir, "fig3_unitempo.svg"))

open(joinpath(output_dir, "metadata.txt"), "w") do io
    println(io, "method=UniformTEMPO.jl uniTEMPO plus custom paper Eq. (18)-(24) postprocessor")
    println(io, "data_provenance=generated locally from analytic Ohmic bath correlation; no author CSV read")
    println(io, "Omega=$(Omega)")
    println(io, "alpha=$(alpha)")
    println(io, "omega_cutoff=$(omega_cutoff)")
    println(io, "drive_amplitude=$(drive_amplitude)")
    println(io, "delta_t=$(delta_t)")
    println(io, "compression_tol=$(compression_tol)")
    println(io, "bond_dimension=$(chi)")
    println(io, "bond_dimension_cap=$(chi_cap)")
    println(io, "tau_max=$(tau_max)")
end

@printf("Finished. Total wall time: %.1f s\n", time() - wall_start)
flush(stdout)
