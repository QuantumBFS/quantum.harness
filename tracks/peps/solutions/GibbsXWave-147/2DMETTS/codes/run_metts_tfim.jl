include("FinitePEPSMETTS.jl")
using .FinitePEPSMETTS

function print_summary(result::METTSResult)
    para = result.parameters
    println("================ finite-PEPS METTS TFIM ================")
    println("J=$(para[:J]), h=$(para[:h]), beta=$(para[:beta])")
    println("D=$(para[:D]), chi=$(para[:chi]), tau=$(para[:tau])")
    println("burn-in=$(para[:burn_in]), samples=$(para[:samples]), thinning=$(para[:thinning])")
    for key in (:energy_per_site, :x_magnetization, :z_magnetization, :zz_nearest_neighbor)
        estimate = result.summary[key]
        println(
            "$key = $(estimate.mean) +/- $(estimate.standard_error) " *
            "(tau_int=$(estimate.autocorrelation_time), N_eff=$(estimate.effective_samples))",
        )
    end
    for key in sort(filter(name -> startswith(String(name), "correlation_R"), collect(keys(result.summary))); by=String)
        estimate = result.summary[key]
        println("$key = $(estimate.mean) +/- $(estimate.standard_error)")
    end
end

function write_samples_csv(path::AbstractString, result::METTSResult)
    open(path, "w") do stream
        println(stream, "sample,transition,product_basis,collapse_basis,energy,energy_per_site,x_magnetization,z_magnetization,zz_nearest_neighbor,max_su_error,boundary_mps_truncation_error")
        for sample in result.samples
            println(
                stream,
                join((
                    sample.sample,
                    sample.transition,
                    sample.product_basis,
                    sample.collapse_basis,
                    sample.energy,
                    sample.energy_per_site,
                    sample.x_magnetization,
                    sample.z_magnetization,
                    sample.zz_nearest_neighbor,
                    sample.max_su_error,
                    sample.boundary_mps_truncation_error,
                ), ','),
            )
        end
    end
    return path
end

function main(; smoke_test=false)
    if smoke_test
        para = default_metts_parameters(
            h=2.9,
            beta=0.2,
            D=2,
            chi=16,
            tau=0.1,
            burn_in=1,
            samples=2,
            seed=20260727,
        )
        para[:measure_correlations] = false
        Lx, Ly = 2, 2
    else
        para = default_metts_parameters(
            h=2.9,
            beta=1 / 0.6085,
            D=3,
            chi=64,
            tau=0.05,
            burn_in=20,
            samples=100,
            seed=20260727,
        )
        Lx, Ly = 4, 4
    end
    result = run_metts(para; Lx, Ly)
    print_summary(result)
    output_path = joinpath(@__DIR__, smoke_test ? "metts_smoke_samples.csv" : "metts_samples.csv")
    write_samples_csv(output_path, result)
    println("samples written to $output_path")
    return result
end

if abspath(PROGRAM_FILE) == @__FILE__
    main(smoke_test="--smoke" in ARGS)
end
