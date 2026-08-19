#!/usr/bin/env julia

using Dates
using SHA
using TOML
using JuMP

const TRACK_ROOT = normpath(joinpath(@__DIR__, ".."))
const REPOSITORY_ROOT = normpath(joinpath(TRACK_ROOT, "..", "..", "..", ".."))

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
include(joinpath(TRACK_ROOT, "src", "ReducedPrimalGapJuMP.jl"))
using .ReducedPrimalGapJuMP

const RUNMETA_SCHEMA = "shastry-sutherland-reduced-mof-runmeta-v1"
const G_COUPLING = BigInt(4) // BigInt(5)

function progress(message::AbstractString)
    println("[ss-reduced-mof] ", message)
    flush(stdout)
end

function parse_rational(text::String)
    parts = split(text, '/')
    length(parts) == 1 && return parse(BigInt, only(parts)) // BigInt(1)
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
        if argument in ("--output", "--gamma")
            index < length(arguments) ||
                throw(ArgumentError("$argument requires a value"))
            values[argument] = arguments[index + 1]
            index += 2
        elseif argument in ("-h", "--help")
            println(
                "usage: build_shastry_sutherland_reduced_mof.jl " *
                "--gamma P/Q --output REPOSITORY_RELATIVE_PATH",
            )
            return nothing
        else
            throw(ArgumentError("unknown argument: $argument"))
        end
    end
    all(haskey(values, key) for key in ("--output", "--gamma")) ||
        throw(ArgumentError("--output and --gamma are required"))

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
        output=output_path,
        output_relative=relative,
        gamma=parse_rational(values["--gamma"]),
    )
end

file_sha256(path::AbstractString) =
    bytes2hex(open(sha256, path))

function peak_rss_kib()
    isfile("/proc/self/status") || return -1
    for line in eachline("/proc/self/status")
        startswith(line, "VmHWM:") || continue
        fields = split(line)
        return length(fields) >= 2 ? parse(Int, fields[2]) : -1
    end
    return -1
end

function timed_metadata(measurement)
    return Dict(
        "wall_seconds" => measurement.time,
        "gc_seconds" => measurement.gctime,
        "allocated_bytes" => measurement.bytes,
        "peak_process_rss_kib_after_step" => peak_rss_kib(),
    )
end

git_output(arguments...) =
    readchomp(Cmd(`git $(arguments)`; dir=REPOSITORY_ROOT))

function source_metadata()
    files = [
        "tracks/polyopt/solutions/sdp-gap-seekers/src/SquareJ1J2Prototype.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/GenericGapModel.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapSymbolics.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapAssembly.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapJuMP.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ExactSymmetryReduction.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ReducedPrimalGapAssembly.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ReducedPrimalGapJuMP.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_shastry_sutherland_reduced_mof.jl",
    ]
    dirty = git_output("status", "--porcelain", "--untracked-files=all")
    return Dict(
        "git_commit" => git_output("rev-parse", "HEAD"),
        "git_tree" => git_output("rev-parse", "HEAD^{tree}"),
        "git_branch" => git_output("branch", "--show-current"),
        "dirty_paths_at_build" =>
            isempty(dirty) ? String[] : split(dirty, '\n'; keepempty=false),
        "files_sha256" => Dict(
            file => file_sha256(joinpath(REPOSITORY_ROOT, file))
            for file in files
        ),
    )
end

function rational_metadata(value::Rational)
    return Dict(
        "numerator" => string(numerator(value)),
        "denominator" => string(denominator(value)),
        "canonical" => string(value),
        "float64" => Float64(value),
    )
end

character_label(character) =
    string("rx", Int(character.rx), "_ry", Int(character.ry))

block_name(block) =
    join((block.role, block.family, character_label(block.character)), "_")

function verify_reloaded_model(model::JuMP.Model, reduced)
    length(JuMP.all_variables(model)) == length(reduced.moments) ||
        error("MOF variable count changed during reload")
    isnothing(JuMP.constraint_by_name(model, "normalization")) &&
        error("MOF lost normalization")
    for index in eachindex(reduced.equalities)
        isnothing(
            JuMP.constraint_by_name(model, "reduced_equality[$index]"),
        ) && error("MOF lost reduced equality $index")
    end

    dimensions = Dict{String,Int}()
    for block in [reduced.positive_blocks; reduced.gap_blocks]
        name = block_name(block) * "_psd"
        reference = JuMP.constraint_by_name(model, name)
        isnothing(reference) && error("MOF lost PSD block $name")
        set = JuMP.constraint_object(reference).set
        set isa JuMP.MOI.HermitianPositiveSemidefiniteConeTriangle ||
            error("$name changed cone type during reload")
        set.side_dimension == length(block.rows) ||
            error("$name changed dimension during reload")
        dimensions[name] = set.side_dimension
    end
    expected_constraints =
        1 + length(reduced.equalities) +
        length(reduced.positive_blocks) + length(reduced.gap_blocks)
    JuMP.num_constraints(
        model;
        count_variable_in_set_constraints=false,
    ) == expected_constraints ||
        error("MOF constraint count changed during reload")
    return Dict(
        "passed" => true,
        "variable_count" => length(reduced.moments),
        "constraint_count_excluding_variable_sets" => expected_constraints,
        "psd_block_dimensions" => dimensions,
    )
end

function write_toml(path::String, data)
    open(path, "w") do io
        TOML.print(io, data; sorted=true)
    end
end

function write_checksums(directory::String, filenames::Vector{String})
    open(joinpath(directory, "SHA256SUMS"), "w") do io
        for filename in filenames
            println(io, file_sha256(joinpath(directory, filename)), "  ", filename)
        end
    end
end

function main(arguments::Vector{String}=ARGS)
    options = parse_args(arguments)
    isnothing(options) && return
    source = source_metadata()
    mkpath(options.output)

    progress("exact source assembly")
    problem = GapProblem(
        square_patch_geometry(1),
        shastry_sutherland_model(G_COUPLING),
        options.gamma,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:one_symbol_lift, 1),
    )
    source_measurement = @timed assemble_primal_gap(problem)
    assembly = source_measurement.value

    progress("exhaustive exact reduction truth checks and reduced assembly")
    reduced_measurement = @timed assemble_reduced_primal(assembly)
    reduced = reduced_measurement.value
    reduction_report = reduced_assembly_report(reduced)

    progress("optimizer-free reduced JuMP model")
    jump_measurement = @timed build_reduced_jump_primal(reduced)
    jump_model = jump_measurement.value

    mof_path = joinpath(options.output, "model.mof.json")
    progress("write MOF")
    write_measurement = @timed JuMP.write_to_file(jump_model.model, mof_path)
    mof_sha256 = file_sha256(mof_path)

    progress("reload and verify MOF")
    replay_measurement = @timed JuMP.read_from_file(mof_path)
    replay = verify_reloaded_model(replay_measurement.value, reduced)

    runmeta = Dict(
        "schema_version" => RUNMETA_SCHEMA,
        "created_at_utc" => Dates.format(
            now(UTC),
            dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        ),
        "claim_level" => "solver_free_exact_equivalent_reduction",
        "solver_invoked" => false,
        "optimizer_attached" => false,
        "output_relative" => options.output_relative,
        "source" => source,
        "runtime" => Dict(
            "julia_version" => string(VERSION),
            "jump_version" => string(Base.pkgversion(JuMP)),
            "mathoptinterface_version" =>
                string(Base.pkgversion(JuMP.MOI)),
        ),
        "setup" => Dict(
            "model" => "shastry-sutherland",
            "g_square_over_dimer" => rational_metadata(G_COUPLING),
            "gamma" => rational_metadata(options.gamma),
            "patch_level" => 1,
            "degree_d" => 2,
            "state_class" => "unrestricted",
            "physical_boundary_condition" => "none-local-consistency-window",
        ),
        "source_assembly" => Dict(
            "problem_sha256" => assembly.problem_sha256,
            "assembly_sha256" => assembly.assembly_sha256,
            "moment_count" => length(assembly.moments),
            "positive_dimension" =>
                length(assembly.positive_basis.entries),
            "gap_dimension" => length(assembly.gap_basis.entries),
            "stationarity_equality_count" =>
                length(assembly.stationarity_equalities),
        ),
        "exact_reduction" => Dict(
            "schema" => reduced.schema,
            "assembly_sha256" => reduced.assembly_sha256,
            "coefficient_map_sha256" =>
                reduced.coefficient_map_sha256,
            "moment_count" => reduction_report.reduced_moments,
            "eliminated_moment_count" =>
                reduction_report.eliminated_moments,
            "positive_block_dimensions" =>
                reduction_report.positive_block_dimensions,
            "gap_block_dimensions" =>
                reduction_report.gap_block_dimensions,
            "equality_count" => reduction_report.equality_count,
            "truth_checks_exhaustive" => true,
        ),
        "timing" => Dict(
            "source_assembly" => timed_metadata(source_measurement),
            "exact_reduction" => timed_metadata(reduced_measurement),
            "jump_build" => timed_metadata(jump_measurement),
            "mof_write" => timed_metadata(write_measurement),
            "mof_reload" => timed_metadata(replay_measurement),
        ),
        "mof" => Dict(
            "filename" => "model.mof.json",
            "bytes" => filesize(mof_path),
            "sha256" => mof_sha256,
        ),
        "replay" => replay,
    )
    write_toml(joinpath(options.output, "runmeta.toml"), runmeta)
    write_checksums(options.output, ["model.mof.json", "runmeta.toml"])

    progress(
        "complete; moments=$(reduction_report.reduced_moments), " *
        "max_block=$(maximum(reduction_report.positive_block_dimensions)), " *
        "mof_bytes=$(filesize(mof_path)), sha256=$mof_sha256",
    )
end

main()
