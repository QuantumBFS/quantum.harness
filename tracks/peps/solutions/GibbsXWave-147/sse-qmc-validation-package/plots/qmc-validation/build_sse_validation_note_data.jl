#!/usr/bin/env julia

"""
Build the compact CSV tables consumed by `tfim-sse-validation-note.tex`.

This script reuses the hash-checked loaders from the benchmark-figure builder
and writes only exact common beta points; it never interpolates.
"""

include(joinpath(@__DIR__, "build_energy_comparison_figures.jl"))

const L2_NOTE_DATA =
    joinpath(@__DIR__, "data", "tfim-l2-validation-note-data.csv")
const L4_NOTE_DATA =
    joinpath(@__DIR__, "data", "tfim-l4-validation-note-data.csv")

function write_l2_note_data(path)
    verify_source(L2_ED_SSE_PATH, EXPECTED_L2_ED_SSE_SHA256)
    ed, qmc = load_l2_ed_sse(L2_ED_SSE_PATH)
    tantrg = load_l2_tantrg(DEFAULT_L2_TANTRG_PATH, ed.beta)

    atomic_write(path) do io
        println(
            io,
            "beta,ed_energy,qmc_energy,qmc_mcse,tantrg_energy," *
            "qmc_relative,qmc_mcse_relative,tantrg_relative",
        )
        for index in eachindex(ed.beta)
            reference = abs(ed.energy[index])
            println(
                io,
                join(
                    (
                        ed.beta[index],
                        ed.energy[index],
                        qmc.energy[index],
                        qmc.error[index],
                        tantrg.energy[index],
                        abs(qmc.energy[index] - ed.energy[index]) / reference,
                        qmc.error[index] / reference,
                        abs(tantrg.energy[index] - ed.energy[index]) / reference,
                    ),
                    ',',
                ),
            )
        end
    end
    return path
end

function write_l4_note_data(path)
    verify_source(L4_QMC_PATH, EXPECTED_L4_QMC_SHA256)
    verify_source(L4_QMC_HIGH_T_PATH, EXPECTED_L4_QMC_HIGH_T_SHA256)
    verify_source(L4_TANTRG_PATH, EXPECTED_L4_TANTRG_SHA256)
    qmc, tantrg =
        load_l4_sse_tantrg(L4_QMC_PATH, L4_QMC_HIGH_T_PATH, L4_TANTRG_PATH)

    atomic_write(path) do io
        println(
            io,
            "beta,qmc_energy,qmc_mcse,tantrg_energy," *
            "tantrg_relative,qmc_mcse_relative",
        )
        for index in eachindex(qmc.beta)
            reference = abs(qmc.energy[index])
            println(
                io,
                join(
                    (
                        qmc.beta[index],
                        qmc.energy[index],
                        qmc.error[index],
                        tantrg.energy[index],
                        abs(tantrg.energy[index] - qmc.energy[index]) /
                        reference,
                        qmc.error[index] / reference,
                    ),
                    ',',
                ),
            )
        end
    end
    return path
end

println("WROTE_L2=", write_l2_note_data(L2_NOTE_DATA))
println("WROTE_L4=", write_l4_note_data(L4_NOTE_DATA))
