# Aggregator for paper-grade Fig 4 reproduction. Collects all per-cell manifests
# (written by tfim_fig4_paper_grade.jl in per-cell SLURM mode), runs Stage 3
# (increment recursion), and emits panels (a), (b), the σ_{m_2}-vs-L inset, and
# data.json + summary.
#
# Run after the SLURM array job finishes:
#   julia --project=julia-env scripts/tfim_fig4_aggregate.jl
#
# Resume-friendly: skips cells whose manifest is missing (they show up in the
# missing-cell list at the bottom of the report).

using JSON
using Printf
using Plots

const OUTDIR   = joinpath(@__DIR__, "..", "results", "tfim_fig4_paper_grade")
const CELL_DIR = joinpath(OUTDIR, "cells")

function load_cells()
    cells = Dict{Tuple{Int,Float64}, Dict{String,Any}}()
    for f in readdir(CELL_DIR; join=true)
        endswith(f, ".json") || continue
        startswith(basename(f), "manifest_") || continue
        d = open(f) do io; JSON.parse(io); end
        L = d["L"]
        h = d["h"]
        cells[(L, h)] = d
    end
    return cells
end

function increment_recursion_M2(M2_min::Float64, L_min::Int, cs::Vector{Float64})
    out = Dict{Int, Float64}()
    out[L_min] = M2_min
    M2_prev = M2_min
    for (k, c) in enumerate(cs)
        L_k = L_min * 2^k
        out[L_k] = 2 * M2_prev - c
        M2_prev = out[L_k]
    end
    return out
end

function main()
    cells = load_cells()
    if isempty(cells)
        error("No manifests under $CELL_DIR — run the per-cell SLURM job first.")
    end

    # Reconstruct (L, h) grid from manifests.
    Ls_chain = sort(unique([k[1] for k in keys(cells)]))
    h_grid   = sort(unique([k[2] for k in keys(cells)]))
    L_min    = first(values(cells))["L_min"]
    chi      = first(values(cells))["chi"]
    n_steps  = first(values(cells))["n_steps"]
    pbc      = first(values(cells))["pbc"]
    Ls_full  = [L_min; Ls_chain...]

    @printf("Aggregator: L_chain=%s   h_grid=%s   L_min=%d   χ=%d   N_S=%d   PBC=%s\n",
            string(Ls_chain), string(h_grid), L_min, chi, n_steps, string(pbc))
    flush(stdout)

    # M_2 anchors at L_min (per-h, taken from any cell at that h).
    M2_anchor = Dict{Float64, Float64}()
    for h in h_grid
        for L in Ls_chain
            if haskey(cells, (L, h))
                M2_anchor[h] = cells[(L, h)]["M2_anchor_at_L_min"]
                break
            end
        end
    end

    # Missing-cell tracking.
    missing_cells = Tuple{Int,Float64}[]
    for L in Ls_chain, h in h_grid
        haskey(cells, (L, h)) || push!(missing_cells, (L, h))
    end
    if !isempty(missing_cells)
        @printf("WARNING: %d cells missing — Stage 3 will be partial.\n  %s\n",
                length(missing_cells), string(missing_cells))
        flush(stdout)
    end

    # Stage 3: increment recursion per h.
    M2_grid = Dict{Tuple{Int,Float64}, Float64}()
    M2_err  = Dict{Tuple{Int,Float64}, Float64}()
    cL_data = Dict{Tuple{Int,Float64}, Float64}()
    cL_err  = Dict{Tuple{Int,Float64}, Float64}()
    println("\n############ Stage 3: increment recursion ############")
    for h in h_grid
        # Stop the recursion at the first L missing a cell.
        usable_chain = Int[]
        for L in Ls_chain
            haskey(cells, (L, h)) || break
            push!(usable_chain, L)
            cL_data[(L, h)] = cells[(L, h)]["cL"]
            cL_err[(L, h)]  = cells[(L, h)]["se"]
        end

        cs   = [cL_data[(L, h)] for L in usable_chain]
        cerr = [cL_err[(L, h)]  for L in usable_chain]
        rec  = increment_recursion_M2(M2_anchor[h], L_min, cs)
        M2_grid[(L_min, h)] = rec[L_min]
        M2_err[(L_min, h)]  = 0.0
        prev_err = 0.0
        for (k, L) in enumerate(usable_chain)
            M2_grid[(L, h)] = rec[L]
            err_k = sqrt((2*prev_err)^2 + cerr[k]^2)
            M2_err[(L, h)] = err_k
            prev_err = err_k
        end
        @printf("  h=%.2f   m_2(L_min=%d) = %.5f   m_2(L=%d) = %.5f ± %.5f\n",
                h, L_min, rec[L_min]/L_min, last(usable_chain),
                rec[last(usable_chain)] / last(usable_chain),
                M2_err[(last(usable_chain), h)] / last(usable_chain))
    end
    flush(stdout)

    # data.json: full reproduction record.
    combined = Dict(
        "model"     => "1D TFIM",
        "estimator" => "Eq.-(24) ratio chain (paper-grade)",
        "L_min"     => L_min,
        "Ls_chain"  => Ls_chain,
        "Ls_full"   => Ls_full,
        "h_grid"    => h_grid,
        "chi"       => chi,
        "n_steps"   => n_steps,
        "pbc"       => pbc,
        "M2_anchor" => Dict(string(h) => M2_anchor[h] for h in h_grid),
        "c_L"       => Dict(string(L) => [get(cL_data, (L, h), NaN)  for h in h_grid] for L in Ls_chain),
        "c_L_err"   => Dict(string(L) => [get(cL_err,  (L, h), NaN)  for h in h_grid] for L in Ls_chain),
        "M_2"       => Dict(string(L) => [get(M2_grid, (L, h), NaN)  for h in h_grid] for L in Ls_full),
        "M_2_err"   => Dict(string(L) => [get(M2_err,  (L, h), NaN)  for h in h_grid] for L in Ls_full),
        "missing_cells" => [collect(c) for c in missing_cells],
    )
    open(joinpath(OUTDIR, "data.json"), "w") do f
        JSON.print(f, combined, 2)
    end
    println("Saved → $(joinpath(OUTDIR, "data.json"))")
    flush(stdout)

    # Plots: panel (a), panel (b), inset.
    palette = [:steelblue, :firebrick, :seagreen, :darkorange, :mediumorchid]

    pa = plot(xlabel="h", ylabel="c_L = 2 M_2(L/2) − M_2(L)",
              title="Fig 4(a) — Eq.-(24) ratio chain (paper-grade)",
              xticks=h_grid, legend=:bottomright)
    for (k, L) in enumerate(Ls_chain)
        cs   = [get(cL_data, (L, h), NaN) for h in h_grid]
        errs = [get(cL_err,  (L, h), NaN) for h in h_grid]
        plot!(pa, h_grid, cs; yerror=errs,
              seriestype=:scatter, marker=:circle, ms=6, c=palette[k],
              label="L=$L")
        plot!(pa, h_grid, cs; ls=:dot, c=palette[k], lw=1, label="")
    end
    savefig(pa, joinpath(OUTDIR, "panel_a_cL_vs_h.png"))

    pb = plot(xlabel="h", ylabel="m_2 = M_2 / L",
              title="Fig 4(b) — m_2 via increment recursion (paper-grade)",
              xticks=h_grid, legend=:topright)
    for (k, L) in enumerate(Ls_full)
        m2s    = [get(M2_grid, (L, h), NaN) / L for h in h_grid]
        m2errs = [get(M2_err,  (L, h), NaN) / L for h in h_grid]
        plot!(pb, h_grid, m2s; yerror=m2errs,
              seriestype=:scatter, marker=:circle, ms=6, c=palette[k],
              label="L=$L")
        plot!(pb, h_grid, m2s; ls=:dot, c=palette[k], lw=1, label="")
    end
    savefig(pb, joinpath(OUTDIR, "panel_b_m2_vs_h.png"))

    pc = plot(pa, pb; layout=(1,2), size=(1100, 450))
    savefig(pc, joinpath(OUTDIR, "fig4_combined.png"))

    # Inset: σ_{m_2}(L) at h_c on log-log scale.
    h_at_critical = h_grid[argmin(abs.(h_grid .- 1.0))]
    sigmas_full = [get(M2_err, (L, h_at_critical), NaN) / L for L in Ls_full]
    valid = .!isnan.(sigmas_full) .& (sigmas_full .> 0)
    if any(valid)
        Ls_valid = Float64.(Ls_full[valid])
        sigs     = sigmas_full[valid]
        pi_ = plot(xlabel="L", ylabel="σ(m_2) at h_c=1",
                   title="Fig 4(b) inset — sampling error vs L (log-log)",
                   xscale=:log10, yscale=:log10, legend=:topright)
        plot!(pi_, Ls_valid, sigs; seriestype=:scatter, marker=:circle, ms=8, c=:firebrick,
              label="Eq.-(24) ratio chain")
        plot!(pi_, Ls_valid, sigs; ls=:solid, c=:firebrick, lw=1, label="")
        if length(Ls_valid) ≥ 2 && sigs[1] > 0
            ref_inv_sqrt = sigs[1] .* sqrt(Ls_valid[1] ./ Ls_valid)
            ref_inv_log  = sigs[1] .* (log(Ls_valid[1]) ./ log.(Ls_valid))
            plot!(pi_, Ls_valid, ref_inv_sqrt; ls=:dash, c=:gray,  lw=1, label="∝ 1/√L (ref)")
            plot!(pi_, Ls_valid, ref_inv_log;  ls=:dot,  c=:black, lw=1, label="∝ 1/log L (ref)")
        end
        savefig(pi_, joinpath(OUTDIR, "panel_b_inset_sigma_vs_L.png"))
    end

    println("Saved plots → panel_a_cL_vs_h.png, panel_b_m2_vs_h.png, panel_b_inset_sigma_vs_L.png, fig4_combined.png")
    flush(stdout)

    # Summary.
    println("\n=========================================================")
    println("SUMMARY — paper-grade Fig 4 reproduction (Eq.-(24) ratio chain)")
    println("=========================================================")
    @printf("  Cells: %d / %d collected (%d missing).\n",
            length(cells), length(Ls_chain)*length(h_grid), length(missing_cells))
    println("  c_L extremum (most negative) per L:")
    for L in Ls_chain
        cs = Float64[]
        hs = Float64[]
        for h in h_grid
            haskey(cL_data, (L, h)) || continue
            push!(cs, cL_data[(L, h)]); push!(hs, h)
        end
        if !isempty(cs)
            idx_min = argmin(cs)
            @printf("    L=%3d  argmin(c_L) at h=%.2f  c_L = %+.5f ± %.5f\n",
                    L, hs[idx_min], cs[idx_min],
                    get(cL_err, (L, hs[idx_min]), NaN))
        end
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
