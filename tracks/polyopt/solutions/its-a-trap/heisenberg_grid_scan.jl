#!/usr/bin/env julia
# (d, r) grid scan for the periodic spin-1/2 Heisenberg chain, to identify which
# relaxation setting reproduces Table 3 of arXiv:2604.01555.
#
# Skips the exact-rational post-step (Gram=false, no certify_qmb): we only need the
# SDP optimum to compare against the table, and certification is slow.
#
# Cells run cheapest-first and results are flushed after each one, so a slow cell
# never costs the results already in hand.
#
# Usage:  julia --project=julia-env heisenberg_grid_scan.jl <N> <outdir>

using QMBCertify
using JSON
using Printf

const N      = parse(Int, ARGS[1])
const OUTDIR = ARGS[2]

supp = [[1, 4]]     # sigma^x_1 sigma^x_2   (index = 3*(site-1) + component)
coe  = [3 / 4]      # SU(2) collapses the x/y/z bond terms onto one component

# Table 3 of arXiv:2604.01555, transcribed: N => (DMRG upper, SDP Old, SDP New)
const TABLE3 = Dict(
     10 => (-0.4515446, -0.4515446, -0.4515446),
     14 => (-0.4473964, -0.4474032, -0.4473964),
     18 => (-0.4457083, -0.4457344, -0.4457085),
     20 => (-0.4452193, -0.4452516, -0.4452196),
     22 => (-0.4448582, -0.4448981, -0.4448585),
     26 => (-0.4443707, -0.4444334, -0.4443714),
     30 => (-0.4440654, -0.4441512, -0.4440668),
     34 => (-0.4438616, -0.4439644, -0.4438632),
     38 => (-0.4437189, -0.4438331, -0.4437212),
     40 => (-0.4436630, -0.4437820, -0.4436649),
     42 => (-0.4436150, -0.4437371, -0.4436176),
     46 => (-0.4435370, -0.4436656, -0.4435397),
     50 => (-0.4434771, -0.4436101, -0.4434798),
     60 => (-0.4433762, -0.4435169, -0.4433804),
     80 => (-0.4432758, -0.4435377, -0.4432808),
    100 => (-0.4432295, -0.4435928, -0.4432378),
)
const TAB_DMRG, TAB_OLD, TAB_NEW = get(TABLE3, N, (NaN, NaN, NaN))
isnan(TAB_DMRG) && @warn "N=$N is not a row of Table 3 — gap figures will be NaN"

# cheapest first. Optional 3rd arg: "d:extra,d:extra,..." to override the grid.
# NOTE: get_basis only branches on d>1, d>2, d>3 — there is no d>4 branch, so d
# saturates at 4 and `extra` (r = extra+1) is the only live tightening knob.
const GRID = length(ARGS) >= 3 ?
    [(parse(Int, split(c, ':')[1]), parse(Int, split(c, ':')[2])) for c in split(ARGS[3], ',')] :
    [(4, 0), (4, 1), (4, 2), (5, 0), (5, 1), (5, 2)]

results = Dict{String,Any}[]
mkpath(OUTDIR)
outfile = joinpath(OUTDIR, "grid_N$(N).json")

for (d, extra) in GRID
    r = extra + 1
    @printf("\n===== N=%d  d=%d  r=%d  (extra=%d) =====\n", N, d, r, extra)
    flush(stdout)

    local opt = NaN
    local err = nothing
    t = NaN
    try
        t = @elapsed begin
            opt, _ = GSB(supp, coe, N, d;
                         lattice      = "chain",
                         extra        = extra,
                         rdm          = 8,
                         pso          = 3,
                         lso          = true,
                         lol          = N,
                         three_type   = [1, 1],
                         SU2_symmetry = false,
                         Gram         = false,
                         QUIET        = get(ENV, "QMB_QUIET", "1") == "1")
        end
    catch e
        err = sprint(showerror, e)
        @printf("FAILED: %s\n", first(err, 200))
    end

    if err === nothing
        gap = abs(opt - TAB_DMRG) / abs(TAB_DMRG) * 100
        @printf("opt = %.10f   rel gap = %.4f%%   wall = %.1f s\n", opt, gap, t)
        @printf("   vs Table 3 New %.7f | Old %.7f\n", TAB_NEW, TAB_OLD)
    end
    flush(stdout)

    push!(results, Dict(
        "N" => N, "d" => d, "r" => r, "extra" => extra,
        "opt" => err === nothing ? opt : nothing,
        "rel_gap_percent" => err === nothing ? abs(opt - TAB_DMRG) / abs(TAB_DMRG) * 100 : nothing,
        "wall_seconds" => t,
        "error" => err,
    ))

    # flush after every cell
    open(outfile, "w") do io
        JSON.print(io, Dict("reference" => Dict("dmrg" => TAB_DMRG,
                                                "sdp_new" => TAB_NEW,
                                                "sdp_old" => TAB_OLD),
                            "cells" => results), 2)
    end
end

println("\n===== summary =====")
@printf("%-4s %-4s %-16s %-10s %s\n", "d", "r", "opt", "gap%", "wall")
for c in results
    if c["opt"] === nothing
        @printf("%-4d %-4d %-16s %-10s %.1f s  (failed)\n", c["d"], c["r"], "-", "-", c["wall_seconds"])
    else
        @printf("%-4d %-4d %-16.10f %-10.4f %.1f s\n",
                c["d"], c["r"], c["opt"], c["rel_gap_percent"], c["wall_seconds"])
    end
end
println("\nwrote ", outfile)
