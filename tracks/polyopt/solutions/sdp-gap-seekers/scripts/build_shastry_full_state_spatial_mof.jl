#!/usr/bin/env julia

using Dates
using SHA
using TOML
using JuMP

const TRACK_ROOT = normpath(joinpath(@__DIR__, ".."))
const REPOSITORY_ROOT =
    normpath(joinpath(TRACK_ROOT, "..", "..", "..", ".."))

include(joinpath(TRACK_ROOT, "src", "SquareJ1J2Prototype.jl"))
using .SquareJ1J2Prototype
include(joinpath(TRACK_ROOT, "src", "GenericGapModel.jl"))
using .GenericGapModel
include(joinpath(TRACK_ROOT, "src", "PrimalGapSymbolics.jl"))
using .PrimalGapSymbolics
include(joinpath(TRACK_ROOT, "src", "PrimalGapAssembly.jl"))
using .PrimalGapAssembly
include(joinpath(TRACK_ROOT, "src", "PrimalGapJuMP.jl"))
using .PrimalGapJuMP
include(joinpath(TRACK_ROOT, "src", "ExactSymmetryReduction.jl"))
using .ExactSymmetryReduction
include(joinpath(TRACK_ROOT, "src", "ReducedPrimalGapAssembly.jl"))
using .ReducedPrimalGapAssembly
include(joinpath(
    TRACK_ROOT,
    "src",
    "ConjugationSymmetryReduction.jl",
))
using .ConjugationSymmetryReduction
include(joinpath(TRACK_ROOT, "src", "FullStateSymmetryReduction.jl"))
using .FullStateSymmetryReduction
include(joinpath(
    TRACK_ROOT,
    "src",
    "ShastryFullStateSpatialReduction.jl",
))
using .ShastryFullStateSpatialReduction
include(joinpath(
    TRACK_ROOT,
    "src",
    "ShastryFullStateSpatialPrimalGapJuMP.jl",
))
using .ShastryFullStateSpatialPrimalGapJuMP

const RUNMETA_SCHEMA = "shastry-l1d2-full-state-spatial-mof-v1"
const ALLOWED_COUPLINGS = (
    BigInt(0) // BigInt(1),
    BigInt(4) // BigInt(5),
)

function progress(message::AbstractString)
    println("[ss-full-state] ", message)
    flush(stdout)
end

function parse_rational(text::String)
    parts = split(text, '/')
    length(parts) == 1 &&
        return parse(BigInt, only(parts)) // BigInt(1)
    length(parts) == 2 ||
        throw(ArgumentError("expected integer or rational p/q"))
    denominator = parse(BigInt, parts[2])
    iszero(denominator) &&
        throw(ArgumentError("rational denominator cannot be zero"))
    return parse(BigInt, parts[1]) // denominator
end

function parse_args(arguments::Vector{String})
    values = Dict{String,String}()
    index = 1
    while index <= length(arguments)
        argument = arguments[index]
        if argument in ("--coupling", "--gamma", "--output", "--mode")
            index < length(arguments) ||
                throw(ArgumentError("$argument requires a value"))
            haskey(values, argument) &&
                throw(ArgumentError("$argument was supplied more than once"))
            values[argument] = arguments[index + 1]
            index += 2
        elseif argument in ("-h", "--help")
            println(
                "usage: build_shastry_full_state_spatial_mof.jl " *
                "--coupling 0|4/5 --gamma P/Q " *
                "--mode preflight|mof --output REPOSITORY_RELATIVE_PATH",
            )
            return nothing
        else
            throw(ArgumentError("unknown argument: $argument"))
        end
    end
    required = ("--coupling", "--gamma", "--output", "--mode")
    all(haskey(values, key) for key in required) ||
        throw(ArgumentError(join(required, ", ") * " are required"))

    coupling = parse_rational(values["--coupling"])
    coupling in ALLOWED_COUPLINGS ||
        throw(ArgumentError("coupling is restricted to 0 or 4/5"))
    gamma = parse_rational(values["--gamma"])
    gamma >= 0 || throw(ArgumentError("gamma must be nonnegative"))
    mode = Symbol(values["--mode"])
    mode in (:preflight, :mof) ||
        throw(ArgumentError("mode must be preflight or mof"))

    output = values["--output"]
    isabspath(output) &&
        throw(ArgumentError("--output must be repository-relative"))
    output_path = normpath(joinpath(REPOSITORY_ROOT, output))
    relative = relpath(output_path, REPOSITORY_ROOT)
    (
        relative != ".." &&
        !startswith(relative, ".." * Base.Filesystem.path_separator)
    ) || throw(ArgumentError("--output escapes the repository"))
    ispath(output_path) &&
        throw(ArgumentError("output path already exists"))
    return (
        coupling=coupling,
        gamma=gamma,
        mode=mode,
        output=output_path,
        output_relative=relative,
    )
end

file_sha256(path::AbstractString) = bytes2hex(open(sha256, path))

function peak_rss_kib()
    isfile("/proc/self/status") || return -1
    for line in eachline("/proc/self/status")
        startswith(line, "VmHWM:") || continue
        fields = split(line)
        return length(fields) >= 2 ? parse(Int, fields[2]) : -1
    end
    return -1
end

function measurement_dict(measurement)
    return Dict(
        "wall_seconds" => measurement.time,
        "gc_seconds" => measurement.gctime,
        "allocated_bytes" => measurement.bytes,
        "peak_process_rss_kib_after_step" => peak_rss_kib(),
    )
end

function rational_dict(value::Rational)
    return Dict(
        "numerator" => string(numerator(value)),
        "denominator" => string(denominator(value)),
        "canonical" => string(value),
        "float64" => Float64(value),
    )
end

git_output(arguments...) =
    readchomp(Cmd(`git $(arguments)`; dir=REPOSITORY_ROOT))

function source_dict()
    files = [
        "tracks/polyopt/solutions/sdp-gap-seekers/src/SquareJ1J2Prototype.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/GenericGapModel.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapSymbolics.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapAssembly.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapJuMP.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ExactSymmetryReduction.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ReducedPrimalGapAssembly.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ConjugationSymmetryReduction.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/FullStateSymmetryReduction.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastryFullStateSpatialReduction.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastryFullStateSpatialPrimalGapJuMP.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_shastry_full_state_spatial_mof.jl",
    ]
    dirty = git_output("status", "--porcelain", "--untracked-files=all")
    isempty(dirty) ||
        error("refusing to build from a dirty checkout")
    return Dict(
        "git_commit" => git_output("rev-parse", "HEAD"),
        "git_tree" => git_output("rev-parse", "HEAD^{tree}"),
        "git_branch" => git_output("symbolic-ref", "--short", "HEAD"),
        "files_sha256" => Dict(
            file => file_sha256(joinpath(REPOSITORY_ROOT, file))
            for file in files
        ),
    )
end

function write_checkpoint(path::String, metadata::Dict)
    temporary = path * ".tmp"
    open(temporary, "w") do io
        TOML.print(io, metadata; sorted=true)
    end
    mv(temporary, path; force=true)
end

function block_report_dict(report)
    return Dict(
        "source_moments" => report.source_moments,
        "spatial_moments" => report.spatial_moments,
        "positive_block_dimensions" =>
            report.positive_block_dimensions,
        "gap_block_dimensions" => report.gap_block_dimensions,
        "equality_count" => report.equality_count,
        "psd_triangle_entries" => report.psd_triangle_entries,
        "maximum_side" => report.maximum_side,
    )
end

function verify_reloaded_model(
    model::JuMP.Model,
    assembly::ShastryFullStateSpatialReducedPrimalAssembly,
)
    report =
        shastry_full_state_spatial_reduced_assembly_report(assembly)
    JuMP.num_variables(model) == report.spatial_moments ||
        error("MOF variable count changed during reload")
    isnothing(JuMP.constraint_by_name(model, "normalization")) &&
        error("MOF lost normalization")
    for index in eachindex(assembly.equalities)
        name = "shastry_l1d2_spatial_equality[$index]"
        isnothing(JuMP.constraint_by_name(model, name)) &&
            error("MOF lost equality $index")
    end
    for block in [assembly.positive_blocks; assembly.gap_blocks]
        name = shastry_full_state_spatial_block_name(block)
        reference = JuMP.constraint_by_name(model, name)
        isnothing(reference) && error("MOF lost PSD block $name")
        set = JuMP.constraint_object(reference).set
        set isa JuMP.MOI.PositiveSemidefiniteConeTriangle ||
            error("$name changed cone type during reload")
        set.side_dimension == length(block.rows) ||
            error("$name changed side dimension during reload")
    end
    return true
end

function main(arguments::Vector{String}=ARGS)
    options = parse_args(arguments)
    isnothing(options) && return
    source = source_dict()
    mkpath(options.output)
    checkpoint_path = joinpath(options.output, "runmeta.toml")
    metadata = Dict(
        "schema_version" => RUNMETA_SCHEMA,
        "state" => "running",
        "created_at_utc" => Dates.format(
            now(UTC),
            dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        ),
        "mode" => string(options.mode),
        "output_relative" => options.output_relative,
        "source" => source,
        "setup" => Dict(
            "hamiltonian" =>
                "H=sum_dimer S_i.S_j + g sum_square_nn S_i.S_j",
            "model" => "shastry-sutherland",
            "g_square_over_dimer" => rational_dict(options.coupling),
            "gamma" => rational_dict(options.gamma),
            "patch_level" => 1,
            "degree_d" => 2,
            "basis" => "complete-state-polynomial-v1",
            "stationarity" => "complete-inner-state-v1",
            "physical_boundary_condition" =>
                "none-local-consistency-window",
            "state_class" => "unrestricted",
        ),
        "stages" => Dict{String,Any}(),
    )
    write_checkpoint(checkpoint_path, metadata)

    progress("assemble complete L=1,d=2 state-polynomial primal")
    problem = GapProblem(
        square_patch_geometry(1),
        shastry_sutherland_model(options.coupling),
        options.gamma,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:full_state_polynomial, 1),
    )
    primal_measurement = @timed assemble_primal_gap(
        problem;
        stationarity_spec=StationaritySpec(:full_inner_state, 1),
    )
    primal = primal_measurement.value
    metadata["stages"]["primal"] = measurement_dict(primal_measurement)
    metadata["primal"] = Dict(
        "assembly_sha256" => primal.assembly_sha256,
        "problem_sha256" => primal.problem_sha256,
        "positive_dimension" => length(primal.positive_basis.entries),
        "gap_dimension" => length(primal.gap_basis.entries),
        "moment_count" => length(primal.moments),
        "stationarity_equality_count" =>
            length(primal.stationarity_equalities),
    )
    write_checkpoint(checkpoint_path, metadata)

    progress("exact centered/scalar and V4 reduction")
    v4_measurement =
        @timed assemble_full_state_v4_reduced_primal(primal)
    v4 = v4_measurement.value
    metadata["stages"]["v4"] = measurement_dict(v4_measurement)
    write_checkpoint(checkpoint_path, metadata)

    progress("exact conjugation realification")
    real_measurement =
        @timed assemble_full_state_real_reduced_primal(v4)
    real_reduced = real_measurement.value
    metadata["stages"]["conjugation"] =
        measurement_dict(real_measurement)
    write_checkpoint(checkpoint_path, metadata)

    progress("target-specific anti-diagonal truth and quotient")
    spatial_measurement =
        @timed assemble_shastry_full_state_spatial_reduced_primal(
            real_reduced,
        )
    spatial = spatial_measurement.value
    spatial_report =
        shastry_full_state_spatial_reduced_assembly_report(spatial)
    metadata["stages"]["spatial"] =
        measurement_dict(spatial_measurement)
    metadata["reduced"] = block_report_dict(spatial_report)
    metadata["reduced"]["assembly_sha256"] = spatial.assembly_sha256
    metadata["reduced"]["coefficient_map_sha256"] =
        spatial.coefficient_map_sha256
    write_checkpoint(checkpoint_path, metadata)

    if options.mode == :mof
        progress("materialize optimizer-free real PSD JuMP model")
        jump_measurement =
            @timed build_shastry_full_state_spatial_jump_primal(spatial)
        jump_model = jump_measurement.value
        metadata["stages"]["jump"] =
            measurement_dict(jump_measurement)
        write_checkpoint(checkpoint_path, metadata)

        progress("write and reload MOF")
        mof_path = joinpath(options.output, "model.mof.json")
        write_measurement =
            @timed JuMP.write_to_file(jump_model.model, mof_path)
        metadata["stages"]["write_mof"] =
            measurement_dict(write_measurement)
        metadata["mof_sha256"] = file_sha256(mof_path)
        replay_measurement = @timed JuMP.read_from_file(mof_path)
        verify_reloaded_model(replay_measurement.value, spatial)
        metadata["stages"]["reload_mof"] =
            measurement_dict(replay_measurement)
    end

    metadata["state"] = "complete"
    metadata["completed_at_utc"] = Dates.format(
        now(UTC),
        dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
    )
    write_checkpoint(checkpoint_path, metadata)
    progress("complete")
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
