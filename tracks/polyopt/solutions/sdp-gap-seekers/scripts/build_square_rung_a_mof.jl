#!/usr/bin/env julia

include(joinpath(@__DIR__, "build_square_primal_mof.jl"))

const RUNG_A_BASIS_SPEC = StructuredBasisSpec(:bare_weight_one, 1)
const RUNG_A_GAMMAS = (BigInt(0) // BigInt(1),)
const RUNG_A_BUILDER_RELATIVE_PATH =
    "tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_square_rung_a_mof.jl"

function rung_a_usage()
    println(
        """
        Usage:
          julia --project=julia-env \\
            tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_square_rung_a_mof.jl \\
            --output tracks/polyopt/solutions/sdp-gap-seekers/results/<run-id>

        Builds and independently reloads the solver-free Square J1-J2 Rung A
        gamma=0 model:
          g=1/2, L=1, d=2, unrestricted,
          positive basis = bare_weight_one/v1 (dimension 28),
          gap basis = bare_weight_one/v1 (dimension 4).

        The output directory must not already exist. This script never attaches
        an optimizer and never calls optimize!().
        """,
    )
end

function parse_rung_a_args(args::Vector{String})
    any(argument -> argument in ("-h", "--help"), args) && begin
        rung_a_usage()
        return nothing
    end
    return parse_args(args)
end

function main_rung_a(args::Vector{String}=ARGS)
    output_path = parse_rung_a_args(args)
    isnothing(output_path) && return 0
    mkpath(output_path)
    progress("Rung A bundle path: $(relpath(output_path, REPOSITORY_ROOT))")
    progress("no optimizer will be attached or invoked")

    shared_source_metadata = source_metadata([
        RUNG_A_BUILDER_RELATIVE_PATH,
    ])
    points = Dict[]
    for gamma in RUNG_A_GAMMAS
        push!(
            points,
            build_point(
                output_path,
                shared_source_metadata,
                gamma,
                RUNG_A_BASIS_SPEC,
            ),
        )
        GC.gc()
    end

    bundle = Dict(
        "schema_version" => BUNDLE_SCHEMA,
        "created_at_utc" => Dates.format(
            now(UTC),
            dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        ),
        "solver_invoked" => false,
        "experiment" => Dict(
            "name" => "square-j1-j2-relaxation-rung-a",
            "authorized_by_user" => true,
            "authorization_date" => "2026-07-28",
            "purpose" => "minimal_nonvacuous_end_to_end_smoke",
            "basis_family" => string(RUNG_A_BASIS_SPEC.family),
            "basis_family_version" => RUNG_A_BASIS_SPEC.version,
            "g" => rational_metadata(RATIFIED_G),
            "gammas" => [
                rational_metadata(gamma)
                for gamma in RUNG_A_GAMMAS
            ],
        ),
        "source" => shared_source_metadata,
        "points" => points,
    )
    bundle_path = joinpath(output_path, "bundle.toml")
    write_toml(bundle_path, bundle)
    open(joinpath(output_path, "SHA256SUMS"), "w") do io
        println(io, file_sha256(bundle_path), "  bundle.toml")
        for point in points
            println(
                io,
                point["runmeta_sha256"],
                "  ",
                point["relative_path"],
                "/runmeta.toml",
            )
            println(
                io,
                point["mof_sha256"],
                "  ",
                point["relative_path"],
                "/model.mof.json",
            )
        end
    end
    progress("Rung A bundle complete; all MOF reload checks passed")
    return 0
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(main_rung_a())
end
