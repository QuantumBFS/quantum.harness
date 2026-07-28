#!/usr/bin/env julia

include(joinpath(@__DIR__, "..", "src", "LegacyInventoryFormat.jl"))
using .LegacyInventoryFormat

function main(args = ARGS)
    freeze = false
    if length(args) == 2 && args[1] == "--freeze"
        freeze = true
        path = args[2]
    elseif length(args) == 1
        path = only(args)
    else
        throw(ArgumentError(
            "usage: verify_legacy_inventory.jl [--freeze] LEGACY_INVENTORY.math.txt",
        ))
    end
    report = verify_math_inventory_file(path; freeze)
    println("verified canonical math SHA-256: ", report.math_sha256)
    println("SpectralGap source (unhashed provenance): ", report.spectralgap_source)
    println("freeze provenance gate: ", report.freeze_verified ? "passed" : "not requested")
    for (model, h_count, tsupp_count) in
        zip(report.models, report.h_counts, report.tsupp_counts)
        println(model, ": H=", h_count, " tsupp=", tsupp_count)
    end
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    main()
end
