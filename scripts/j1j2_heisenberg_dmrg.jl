#!/usr/bin/env julia
# J1-J2 Heisenberg chain ground state via DMRG (ITensorMPS).
#
# H = J1 * sum_i S_i . S_{i+1}  +  J2 * sum_i S_i . S_{i+2}     (S = 1/2, OBC)
#
# At the Majumdar-Ghosh point J2/J1 = 1/2 the exact ground state is the
# dimer product state with E0/N = -3/8 = -0.375 exactly -> a clean anchor.
#
# Saves a convergence plot (energy vs sweep, per bond dimension) and a JSON
# manifest under results/j1j2_dmrg/.  Run:
#   julia --project=julia-env scripts/j1j2_heisenberg_dmrg.jl

using ITensors, ITensorMPS
using JSON
using Printf
using Plots

# ---- parameters (all explicit) ------------------------------------------
const N   = 100          # chain length (even)
const J1  = 1.0
const J2  = 0.5          # J2/J1 = 0.5  -> Majumdar-Ghosh point
const MAXDIMS = [20, 40, 80, 160]   # bond-dimension ladder, one stage each
const NSWEEPS_PER_STAGE = 4
const CUTOFF = 1e-12
const E_EXACT_PER_SITE = -0.375     # MG dimer-state energy per site

function build_hamiltonian(sites)
    os = OpSum()
    for i in 1:(N - 1)
        os += J1 * 0.5, "S+", i, "S-", i + 1
        os += J1 * 0.5, "S-", i, "S+", i + 1
        os += J1,       "Sz", i, "Sz", i + 1
    end
    for i in 1:(N - 2)
        os += J2 * 0.5, "S+", i, "S-", i + 2
        os += J2 * 0.5, "S-", i, "S+", i + 2
        os += J2,       "Sz", i, "Sz", i + 2
    end
    return MPO(os, sites)
end

function main()
    ENV["GKSwstype"] = get(ENV, "GKSwstype", "100")
    run_dir = abspath(joinpath(@__DIR__, "..", "results", "j1j2_dmrg"))
    mkpath(run_dir)

    println("J1-J2 Heisenberg chain ground state (DMRG / ITensorMPS)")
    @printf("N = %d, J1 = %.3f, J2 = %.3f  (J2/J1 = %.3f, Majumdar-Ghosh point)\n",
            N, J1, J2, J2 / J1)
    println("Exact anchor: E0/N = -3/8 = -0.375 (dimer product state)")
    println("Sz-conserving S=1/2 sites, OBC. Bond-dim ladder: $(MAXDIMS)")
    flush(stdout)

    sites = siteinds("S=1/2", N; conserve_qns = true)
    H = build_hamiltonian(sites)

    # Neel initial state in the Sz=0 sector.
    state = [isodd(i) ? "Up" : "Dn" for i in 1:N]
    psi0 = random_mps(sites, state; linkdims = 10)

    energy_trace = Float64[]   # energy after every sweep
    maxdim_trace = Int[]
    sweep_index  = Int[]
    psi = psi0
    energy = 0.0
    sweepno = 0
    t0 = time()
    for md in MAXDIMS
        for _ in 1:NSWEEPS_PER_STAGE
            sweepno += 1
            energy, psi = dmrg(H, psi;
                               nsweeps = 1, maxdim = md, cutoff = CUTOFF,
                               outputlevel = 0)
            push!(energy_trace, energy)
            push!(maxdim_trace, md)
            push!(sweep_index, sweepno)
            @printf("  sweep %2d  maxdim %3d   E = %.10f   E/N = %.8f   (err vs MG = %.2e)\n",
                    sweepno, md, energy, energy / N, abs(energy / N - E_EXACT_PER_SITE))
            flush(stdout)
        end
    end
    elapsed = time() - t0

    e_per_site = energy / N
    err = abs(e_per_site - E_EXACT_PER_SITE)
    @printf("\nFinal: E0 = %.10f,  E0/N = %.8f\n", energy, e_per_site)
    @printf("MG exact E0/N = %.8f,  |error| = %.3e\n", E_EXACT_PER_SITE, err)
    @printf("Wall time: %.2f s\n", elapsed)
    flush(stdout)

    # ---- convergence plot ------------------------------------------------
    png_path = joinpath(run_dir, "convergence.png")
    plt = plot(sweep_index, energy_trace .- E_EXACT_PER_SITE * N;
               yscale = :log10, marker = :circle, markersize = 4,
               xlabel = "DMRG sweep", ylabel = "E - E_exact",
               title = "J1-J2 chain, J2/J1=0.5, N=$N (MG point)",
               legend = false, lw = 2, color = :purple, grid = true)
    # annotate bond-dim stages with vertical separators
    for md in unique(maxdim_trace)
        first_sweep = sweep_index[findfirst(==(md), maxdim_trace)]
        vline!(plt, [first_sweep - 0.5]; color = :gray, ls = :dash, lw = 1, label = "")
        annotate!(plt, first_sweep, maximum(energy_trace .- E_EXACT_PER_SITE * N),
                  text("χ=$md", 8, :left, :gray))
    end
    savefig(plt, png_path)
    println("Figure: $(relpath(png_path, run_dir))")

    # ---- manifest --------------------------------------------------------
    manifest = Dict(
        "model" => "J1-J2 Heisenberg chain, S=1/2",
        "hamiltonian" => "H = J1 sum_i S_i.S_{i+1} + J2 sum_i S_i.S_{i+2}",
        "N" => N, "J1" => J1, "J2" => J2, "boundary" => "OBC",
        "method" => "DMRG (ITensorMPS)", "conserve_qns" => true,
        "maxdims" => MAXDIMS, "nsweeps_per_stage" => NSWEEPS_PER_STAGE,
        "cutoff" => CUTOFF,
        "E0" => energy, "E0_per_site" => e_per_site,
        "E_exact_per_site" => E_EXACT_PER_SITE, "abs_error" => err,
        "wall_seconds" => elapsed,
        "energy_trace" => energy_trace, "sweep_index" => sweep_index,
        "maxdim_trace" => maxdim_trace,
    )
    json_path = joinpath(run_dir, "result.json")
    open(json_path, "w") do io
        JSON.print(io, manifest)
    end
    println("Data: $(relpath(json_path, run_dir))")
    @printf("Done in %.2f s. Verification: |E/N - MG exact| = %.2e\n", elapsed, err)
end

main()
