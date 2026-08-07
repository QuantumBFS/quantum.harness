ENV["GKSwstype"] = "100"

include(joinpath(@__DIR__, "rde_beta16_common.jl"))
using .RDEBeta16Common

using DelimitedFiles
using FileIO
using Plots
using PNGFiles
using SHA

const PNG_SIGNATURE = UInt8[0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]

file_sha256(path) = bytes2hex(SHA.sha256(read(path)))

function validate_png(path)
    isfile(path) || error("missing Gtau PNG: $path")
    filesize(path) > length(PNG_SIGNATURE) ||
        error("Gtau PNG is too small: $path")
    signature = open(path, "r") do io
        read(io, length(PNG_SIGNATURE))
    end
    signature == PNG_SIGNATURE ||
        error("Gtau output does not have a PNG signature: $path")
    decoded = FileIO.load(path)
    ndims(decoded) >= 2 || error("decoded PNG has fewer than two dimensions")
    all(>(0), size(decoded)) || error("decoded PNG has an empty dimension")
    return decoded
end

function read_plot_metadata(path)
    isfile(path) || error("missing Gtau PNG metadata: $path")
    metadata = Dict{String,String}()
    for line in filter(!isempty, strip.(readlines(path)))
        fields = split(line, "="; limit=2)
        length(fields) == 2 || error("malformed plot metadata line: $line")
        haskey(metadata, fields[1]) &&
            error("duplicate plot metadata key: $(fields[1])")
        metadata[fields[1]] = fields[2]
    end
    return metadata
end

function expected_plot_metadata(run_root, merged_csv, plot_input)
    return Dict(
        "schema" => "2",
        "points" => "17",
        "merged_csv_sha256" => file_sha256(merged_csv),
        "plot_input_sha256" => file_sha256(plot_input),
        "source_lock_sha256" => source_lock_sha256(run_root),
        "revision_lock_sha256" => revision_lock_sha256(run_root),
        "run_config_sha256" => run_config_sha256(run_root),
        "environment_fingerprint_sha256" =>
            environment_fingerprint_sha256(run_root),
    )
end

function validate_existing_plot(
        output,
        metadata_path,
        expected_metadata)
    validate_png(output)
    metadata = read_plot_metadata(metadata_path)
    for (key, expected) in expected_metadata
        get(metadata, key, nothing) == expected ||
            error("existing Gtau PNG metadata mismatch for $key")
    end
    png_hash = get(metadata, "png_sha256", nothing)
    png_hash == file_sha256(output) ||
        error("existing Gtau PNG hash does not match its metadata")
    return nothing
end

function plot_metadata_content(expected_metadata, png_hash)
    keys_in_order = (
        "schema",
        "points",
        "merged_csv_sha256",
        "plot_input_sha256",
        "source_lock_sha256",
        "revision_lock_sha256",
        "run_config_sha256",
        "environment_fingerprint_sha256",
    )
    lines = [
        "$key=$(expected_metadata[key])" for key in keys_in_order
    ]
    push!(lines, "png_sha256=$png_hash")
    return join(lines, "\n") * "\n"
end

function main()
    length(ARGS) == 1 || error("usage: rde_beta16_plot.jl RUN_ROOT")
    run_root = abspath(ARGS[1])
    merged_csv = joinpath(run_root, "outputs", "gtau_beta16.csv")
    input = joinpath(run_root, "outputs", "gtau_beta16_plot.dat")
    output = joinpath(run_root, "outputs", "gtau_beta16.png")
    metadata_path = output * ".meta"
    isfile(merged_csv) || error("missing merged Gtau CSV: $merged_csv")
    isfile(input) || error("missing merged Gtau plot input: $input")
    expected_metadata =
        expected_plot_metadata(run_root, merged_csv, input)

    if isfile(output)
        if isfile(metadata_path)
            validate_existing_plot(output, metadata_path, expected_metadata)
        else
            validate_png(output)
            atomic_write(
                metadata_path,
                plot_metadata_content(
                    expected_metadata,
                    file_sha256(output),
                ),
            )
            validate_existing_plot(output, metadata_path, expected_metadata)
        end
        println(
            "PLOT_RESULT status=already_complete points=17 output=$output",
        )
        return
    end
    ispath(metadata_path) &&
        error("Gtau PNG metadata exists without its PNG: $metadata_path")

    values = readdlm(input; comments=true, comment_char='#')
    size(values, 1) == 17 || error("plot input must contain exactly 17 rows")
    size(values, 2) == 3 || error("plot input must contain three columns")
    taus = Float64.(values[:, 1])
    gtau_real = Float64.(values[:, 2])
    gtau_imag = Float64.(values[:, 3])
    all(isfinite, vcat(taus, gtau_real, gtau_imag)) ||
        error("plot input contains non-finite data")

    figure = plot(
        taus,
        gtau_real;
        marker=:circle,
        linewidth=2,
        xlabel="τ",
        ylabel="G(τ)",
        title="β=16, Nb=9, Residual Driven Expansion",
        label="Re G(τ)",
        legend=:best,
        grid=true,
        dpi=180,
        size=(900, 600),
    )
    if maximum(abs, gtau_imag) > 1e-12
        plot!(
            figure,
            taus,
            gtau_imag;
            marker=:diamond,
            linestyle=:dash,
            label="Im G(τ)",
        )
    end

    temporary = joinpath(
        dirname(output),
        "." * basename(output) * ".tmp." * string(getpid()) * ".png",
    )
    ispath(temporary) &&
        error("refusing to reuse temporary plot path: $temporary")
    try
        savefig(figure, temporary)
        validate_png(temporary)
        png_hash = file_sha256(temporary)
        mv(temporary, output)
        atomic_write(
            metadata_path,
            plot_metadata_content(expected_metadata, png_hash),
        )
        validate_existing_plot(output, metadata_path, expected_metadata)
    finally
        isfile(temporary) && rm(temporary; force=true)
    end
    println("PLOT_RESULT status=success points=17 output=$output")
end

main()
